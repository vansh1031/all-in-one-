"""Web server for the Hazardous Zone Detector.

Serves the single-screen UI and streams the detector's video and state to it.
The dashboard card keeps using http://127.0.0.1:8765/start - that URL now
opens the full application instead of spawning separate windows.

    python3 hazard_server.py              # listens on 127.0.0.1:8765
    HAZARD_HOST=0.0.0.0 python3 hazard_server.py   # allow other machines
"""

import json
import os
import time

from flask import Flask, Response, jsonify, request, send_from_directory

from detector_engine import BASE_DIR, HazardEngine, SerialLink

WEB_DIR = os.path.join(BASE_DIR, "web")

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="/static")
engine = HazardEngine()


@app.route("/")
@app.route("/start")
def index():
    engine.start()
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/logo.svg")
def logo():
    return send_from_directory(BASE_DIR, "yash_logo.svg")


@app.route("/video_feed")
def video_feed():
    def frames():
        last_id = -1
        while True:
            with engine.frame_cond:
                engine.frame_cond.wait_for(lambda: engine.frame_id != last_id, timeout=2)
                jpg, last_id = engine.frame_jpeg, engine.frame_id
            if jpg is None:
                continue
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n"
                   b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")

    return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-store"})


@app.route("/events")
def events():
    """Server-sent events: the engine state ~10x a second plus new log entries."""
    def stream():
        seq = max(0, engine.event_seq - 50)
        yield "retry: 1000\n\n"
        while True:
            for event in engine.events_since(seq):
                seq = event["id"]
                yield f"event: log\ndata: {json.dumps(event)}\n\n"
            yield f"event: state\ndata: {json.dumps(engine.snapshot())}\n\n"
            time.sleep(0.1)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/state")
def state():
    return jsonify(engine.snapshot())


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


@app.route("/api/zone", methods=["POST", "DELETE"])
def zone():
    if request.method == "DELETE":
        engine.clear_zone()
        return jsonify(zone=[])
    points = (request.get_json(silent=True) or {}).get("points", [])
    try:
        engine.set_zone(points)
    except (TypeError, ValueError) as e:
        return jsonify(error=str(e)), 400
    return jsonify(zone=[list(p) for p in engine.zone])


@app.post("/api/settings")
def settings():
    try:
        return jsonify(engine.update_settings(request.get_json(silent=True) or {}))
    except (TypeError, ValueError) as e:
        return jsonify(error=str(e)), 400


@app.get("/api/serial/ports")
def serial_ports():
    return jsonify(ports=SerialLink.available_ports())


@app.post("/api/buzzer/test")
def buzzer_test():
    if not engine.test_buzzer():
        return jsonify(error="Buzzer is already sounding"), 409
    return jsonify(ok=True)


@app.post("/api/sim")
def sim():
    data = request.get_json(silent=True) or {}
    if data.get("mode") == "auto":
        engine.simulate()
    else:
        try:
            engine.simulate(float(data["x"]), float(data["y"]))
        except (KeyError, TypeError, ValueError):
            return jsonify(error="x and y are required"), 400
    return jsonify(ok=True)


if __name__ == "__main__":
    host = os.environ.get("HAZARD_HOST", "127.0.0.1")
    port = int(os.environ.get("HAZARD_PORT", "8765"))
    engine.start()
    app.run(host=host, port=port, threaded=True)
