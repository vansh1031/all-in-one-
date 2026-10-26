"""Web server for Edge AI Predictive Maintenance.

Serves the single-screen dashboard and streams the engine's readings and
predictions to it.

    python3 pm_server.py                       # listens on 127.0.0.1:8766
    PM_HOST=0.0.0.0 python3 pm_server.py       # allow other machines
"""

import json
import os
import time

from flask import Flask, Response, jsonify, request, send_from_directory

from pm_engine import BASE_DIR, MaintenanceEngine, SerialSensors

WEB_DIR    = os.path.join(BASE_DIR, "web")
ASSETS_DIR = os.path.join(os.path.dirname(BASE_DIR), "assets")

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="/static")
engine = MaintenanceEngine()


@app.route("/")
@app.route("/start")
def index():
    engine.start()
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/logo.svg")
def logo():
    return send_from_directory(ASSETS_DIR, "yash_logo.svg")


@app.route("/events")
def events():
    """Server-sent events: state twice a second with only the new readings."""
    def stream():
        seq = max(0, engine.event_seq - 50)
        sample_seq = score_seq = 0
        yield "retry: 1000\n\n"
        while True:
            for event in engine.events_since(seq):
                seq = event["id"]
                yield f"event: log\ndata: {json.dumps(event)}\n\n"
            snap = engine.snapshot(sample_seq, score_seq)
            sample_seq, score_seq = snap["sample_seq"], snap["score_seq"]
            yield f"event: state\ndata: {json.dumps(snap)}\n\n"
            time.sleep(0.5)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/state")
def state():
    snap = engine.snapshot(engine.sample_seq, engine.score_seq)
    return jsonify(snap)


@app.post("/api/engine")
def engine_control():
    action = (request.get_json(silent=True) or {}).get("action")
    if action == "start":
        engine.start()
    elif action == "stop":
        engine.stop()
    else:
        return jsonify(error="action must be 'start' or 'stop'"), 400
    return jsonify(running=engine.running)


@app.post("/api/learn")
def learn():
    engine.learn()
    return jsonify(ok=True)


@app.post("/api/sim")
def sim():
    try:
        engine.inject((request.get_json(silent=True) or {}).get("fault"))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True)


@app.post("/api/settings")
def settings():
    try:
        return jsonify(engine.update_settings(request.get_json(silent=True) or {}))
    except (TypeError, ValueError) as e:
        return jsonify(error=str(e)), 400


@app.get("/api/serial/ports")
def serial_ports():
    return jsonify(ports=SerialSensors.available_ports())


@app.get("/api/export.csv")
def export_csv():
    name = time.strftime("sensor_history_%Y%m%d_%H%M%S.csv")
    return Response(engine.history_csv(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={name}"})


if __name__ == "__main__":
    host = os.environ.get("PM_HOST", "127.0.0.1")
    port = int(os.environ.get("PM_PORT", "8766"))
    engine.start()
    app.run(host=host, port=port, threaded=True)
