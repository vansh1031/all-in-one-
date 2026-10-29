"""Edge AI predictive maintenance engine.

Reads machine sensors (vibration, temperature, motor current, speed) from an
Arduino over serial, or from the built-in machine simulator, and runs an
anomaly model on the device:

1. Learn   - while the machine is known to be healthy, collect feature
             windows and fit a baseline (mean + covariance).
2. Score   - every half second, compute the Mahalanobis distance of the
             current window from that baseline and turn it into a 0-100
             health index.
3. Predict - fit a trend to the recent health index and extrapolate when it
             will cross the critical line (estimated time to maintenance).
4. Explain - rank which features moved furthest from normal and map them to
             a likely fault (bearing wear, overheating, electrical overload).

Only numpy is needed, so it runs on the Jetson CPU without a GPU model.
"""

import collections
import glob
import json
import math
import os
import random
import threading
import time

import numpy as np

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = list_ports = None

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR    = os.path.join(BASE_DIR, "config")
LOG_DIR       = os.path.join(BASE_DIR, "logs")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
MODEL_FILE    = os.path.join(CONFIG_DIR, "pm_model.json")
LOG_FILE      = os.path.join(LOG_DIR, "pm_log.txt")

SAMPLE_HZ      = 10           # simulator sample rate
SCORE_EVERY    = 0.5          # seconds between model evaluations
WINDOW_SECONDS = 3.0          # feature window length
HISTORY_SECONDS = 15 * 60     # kept in memory for the charts and CSV export

DEFAULT_SETTINGS = {
    "source":          "simulator",   # "simulator" | "serial"
    "serial_port":     "auto",
    "baud":            115200,
    "learn_seconds":   90,
    "warn_health":     70,
    "critical_health": 35,
    "trend_seconds":   120,
}

# Features computed over each window, in model order.
FEATURES = [
    ("vib_rms",   "Vibration RMS",  "mm/s"),
    ("vib_peak",  "Vibration peak", "mm/s"),
    ("temp",      "Temperature",    "°C"),
    ("temp_rate", "Heating rate",   "°C/min"),
    ("current",   "Motor current",  "A"),
    ("speed",     "Shaft speed",    "rpm"),
]

FAULTS = {
    "bearing":    {"name": "Bearing wear / imbalance",
                   "action": "Inspect and lubricate the bearings, check shaft alignment",
                   "features": {"vib_rms": 1.0, "vib_peak": 1.0, "speed": 0.4}},
    "thermal":    {"name": "Overheating",
                   "action": "Check cooling fan, airflow and lubrication",
                   "features": {"temp": 1.0, "temp_rate": 1.0}},
    "electrical": {"name": "Electrical overload",
                   "action": "Check the load, supply voltage and motor windings",
                   "features": {"current": 1.0, "speed": 0.6}},
}


# ─── SENSOR SOURCES ───────────────────────────────────────
class MachineSimulator:
    """A motor + pump with three fault modes that grow over a few minutes.

    Healthy readings follow a slow load cycle; an injected fault ramps up
    from zero so the health index, trend and diagnosis can be watched.
    """

    RAMP_SECONDS = 240       # healthy to fully failed

    def __init__(self):
        self.t0 = time.time()
        self.wear = {"bearing": 0.0, "thermal": 0.0, "electrical": 0.0}
        self.active = set()
        self.temp = 46.0
        self._last = time.time()

    def inject(self, fault):
        if fault in self.wear:
            self.active.add(fault)

    def repair(self):
        self.active.clear()
        for k in self.wear:
            self.wear[k] = 0.0

    def read(self):
        now = time.time()
        dt, self._last = min(now - self._last, 1.0), now
        for fault in self.active:
            self.wear[fault] = min(1.0, self.wear[fault] + dt / self.RAMP_SECONDS)
        b, th, el = self.wear["bearing"], self.wear["thermal"], self.wear["electrical"]
        t = now - self.t0
        load = 0.55 + 0.25 * math.sin(t / 11.0) + 0.05 * math.sin(t / 3.1)

        vib = 2.1 + 0.6 * load + 7.5 * b ** 2.2 + random.gauss(0, 0.12)
        if b > 0.5 and random.random() < 0.08 * b:
            vib += random.uniform(2, 6) * b          # impacts from a damaged race
        target_temp = 42 + 10 * load + 38 * th ** 1.4 + 6 * b + 5 * el
        self.temp += (target_temp - self.temp) * min(1.0, dt / 6.0)
        temp = self.temp + random.gauss(0, 0.15)
        current = 7.5 + 4.5 * load + 6.5 * el ** 1.3 + random.gauss(0, 0.15)
        if el > 0.3 and random.random() < 0.05:
            current += random.uniform(1, 3) * el
        speed = 1480 - 25 * load - 60 * el - 25 * b + random.gauss(0, 2.5)
        return {"vib": max(0.0, vib), "temp": temp, "current": max(0.0, current),
                "speed": speed}


class SerialSensors:
    """Reads lines of `vibration,temperature,current[,speed]` from an Arduino."""

    AUTO_PORTS = ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyUSB1"]

    def __init__(self, port, baud, log):
        self.wanted, self.baud, self.log = port, baud, log
        self.ser, self.port = None, None
        self._last_try = 0.0

    @staticmethod
    def available_ports():
        """Serial ports present now: COM3, COM4... on Windows, /dev/tty* on Linux."""
        ports = [p.device for p in list_ports.comports()] if list_ports else []
        if os.name != "nt":
            ports += glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
        return sorted(set(ports))

    @classmethod
    def auto_ports(cls):
        """Ports to try on "auto": USB serial devices only (the sensor board)."""
        if os.name == "nt":
            return [p.device for p in list_ports.comports() if p.vid is not None] if list_ports else []
        return cls.AUTO_PORTS + [p for p in cls.available_ports()
                                 if p not in cls.AUTO_PORTS and ("ACM" in p or "USB" in p)]

    @property
    def connected(self):
        return self.ser is not None and self.ser.is_open

    def close(self):
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser, self.port = None, None

    def _connect(self):
        if serial is None or time.time() - self._last_try < 5:
            return
        self._last_try = time.time()
        for port in (self.auto_ports() if self.wanted == "auto" else [self.wanted]):
            try:
                self.ser = serial.Serial(port=port, baudrate=self.baud, timeout=0.5)
                self.port = port
                self.log("ok", f"Sensor board connected on {port}")
                return
            except Exception:
                continue

    def read(self):
        if not self.connected:
            self._connect()
            if not self.connected:
                time.sleep(0.2)
                return None
        try:
            line = self.ser.readline().decode("ascii", "ignore").strip()
        except Exception as e:
            self.log("warn", f"Sensor board disconnected ({e})")
            self.close()
            return None
        try:
            values = [float(v) for v in line.split(",")]
        except ValueError:
            return None
        if len(values) < 3:
            return None
        return {"vib": values[0], "temp": values[1], "current": values[2],
                "speed": values[3] if len(values) > 3 else float("nan")}


# ─── MODEL ────────────────────────────────────────────────
class BaselineModel:
    """Mahalanobis-distance anomaly model fitted on healthy feature windows."""

    def __init__(self):
        self.mean = None
        self.std = None
        self.inv_cov = None
        self.trained_at = None
        self.samples = 0

    @property
    def ready(self):
        return self.mean is not None

    def fit(self, rows):
        x = np.asarray(rows, dtype=float)
        mean = x.mean(axis=0)
        std = x.std(axis=0)
        # Floor the spread so a sensor that barely moved while learning
        # (or is missing) does not explode the score later.
        floor = np.maximum(np.abs(mean) * 0.02, 0.05)
        std = np.maximum(std, floor)
        z = (x - mean) / std
        cov = np.cov(z, rowvar=False) + np.eye(x.shape[1]) * 0.05
        self.mean, self.std = mean, std
        self.inv_cov = np.linalg.inv(cov)
        self.trained_at = time.time()
        self.samples = len(rows)

    def score(self, row):
        """Returns (distance, per-feature z-scores)."""
        z = (np.asarray(row, dtype=float) - self.mean) / self.std
        z = np.nan_to_num(z)
        d = float(math.sqrt(max(0.0, z @ self.inv_cov @ z) / len(z)))
        return d, z

    def to_json(self):
        return {"mean": self.mean.tolist(), "std": self.std.tolist(),
                "inv_cov": self.inv_cov.tolist(), "trained_at": self.trained_at,
                "samples": self.samples, "features": [f[0] for f in FEATURES]}

    @classmethod
    def from_json(cls, data):
        if data.get("features") != [f[0] for f in FEATURES]:
            raise ValueError("model was trained on different features")
        m = cls()
        m.mean = np.array(data["mean"])
        m.std = np.array(data["std"])
        m.inv_cov = np.array(data["inv_cov"])
        m.trained_at = data["trained_at"]
        m.samples = data["samples"]
        return m


HEALTHY_DISTANCE = 1.6    # healthy windows sit around d ~ 1
FAILED_DISTANCE  = 40.0


def health_from_distance(d):
    """Map a normalised Mahalanobis distance to a 0-100 health index.

    The scale is logarithmic: early, small deviations already cost points,
    while a badly failed machine does not slam straight to zero.
    """
    if d <= HEALTHY_DISTANCE:
        return 100.0
    span = math.log(FAILED_DISTANCE / HEALTHY_DISTANCE)
    return max(0.0, 100.0 * (1 - math.log(d / HEALTHY_DISTANCE) / span))


# ─── ENGINE ───────────────────────────────────────────────
class MaintenanceEngine:
    def __init__(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None

        self.events = collections.deque(maxlen=200)
        self.event_seq = 0
        self.settings = self._load_settings()

        self.sim = MachineSimulator()
        self.sensors = None
        self._source_dirty = True

        maxlen = int(HISTORY_SECONDS * SAMPLE_HZ * 1.5)
        self.samples = collections.deque(maxlen=maxlen)     # (t, vib, temp, current, speed)
        self.scores = collections.deque(maxlen=int(HISTORY_SECONDS / SCORE_EVERY))
        self.sample_seq = 0
        self.score_seq = 0

        self.model = self._load_model()
        self.learning = None            # {"started": t, "rows": [...]} while learning
        self.health = None
        self.distance = None
        self.zscores = None
        self.features = None
        self.status = "starting"
        self.rul_seconds = None
        self.trend_per_min = None
        self.diagnosis = None
        self.connected = False
        self.started_at = None
        self._last_status = None

    # ── Persistence & log ─────────────────────────────────
    @staticmethod
    def _load_settings():
        settings = dict(DEFAULT_SETTINGS)
        try:
            with open(SETTINGS_FILE) as f:
                settings.update({k: v for k, v in json.load(f).items() if k in DEFAULT_SETTINGS})
        except (OSError, ValueError):
            pass
        return settings

    def _load_model(self):
        try:
            with open(MODEL_FILE) as f:
                return BaselineModel.from_json(json.load(f))
        except (OSError, ValueError, KeyError):
            return BaselineModel()

    def log(self, level, msg):
        with self._lock:
            self.event_seq += 1
            event = {"id": self.event_seq, "t": time.time(), "level": level, "msg": msg}
            self.events.append(event)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(event["t"]))
        print(f"[{level.upper()}] {msg}")
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{stamp}  {level.upper():5}  {msg}\n")
        except OSError:
            pass

    def events_since(self, seq):
        with self._lock:
            return [e for e in self.events if e["id"] > seq]

    # ── Control ───────────────────────────────────────────
    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        with self._lock:
            if self.running:
                return
            self._stop.clear()
            self.started_at = time.time()
            self._thread = threading.Thread(target=self._run, name="pm-engine", daemon=True)
            self._thread.start()
        if not self.model.ready:
            self.learn()
        self.log("info", "Monitoring started")

    def stop(self):
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=5)
        self._thread = None
        self.log("info", "Monitoring stopped")

    def learn(self):
        with self._lock:
            self.learning = {"started": time.time(), "rows": []}
        self.log("info", f"Learning the healthy baseline ({self.settings['learn_seconds']} s)"
                         " - keep the machine running normally")

    def inject(self, fault):
        if fault == "repair":
            self.sim.repair()
            self.log("ok", "Simulator: machine repaired")
        elif fault in FAULTS:
            self.sim.inject(fault)
            self.log("warn", f"Simulator: {FAULTS[fault]['name'].lower()} fault injected")
        else:
            raise ValueError("unknown fault")

    def update_settings(self, changes):
        with self._lock:
            old = dict(self.settings)
            for key, value in changes.items():
                if key in DEFAULT_SETTINGS:
                    self.settings[key] = type(DEFAULT_SETTINGS[key])(value)
            if self.settings["source"] not in ("simulator", "serial"):
                self.settings["source"] = old["source"]
            # The baseline must span at least one full load cycle of the machine.
            self.settings["learn_seconds"] = max(60, self.settings["learn_seconds"])
            if any(self.settings[k] != old[k] for k in ("source", "serial_port", "baud")):
                self._source_dirty = True
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.settings, f, indent=2)
        if self.settings["source"] != old["source"]:
            self.log("info", f"Sensor source: {self.settings['source']}")
        return dict(self.settings)

    # ── Data for the UI ───────────────────────────────────
    def snapshot(self, sample_seq=0, score_seq=0):
        """Engine state plus any samples / scores newer than the given cursors."""
        with self._lock:
            new_samples = list(self.samples)[-max(0, min(self.sample_seq - sample_seq,
                                                         len(self.samples))):] \
                if self.sample_seq > sample_seq else []
            new_scores = list(self.scores)[-max(0, min(self.score_seq - score_seq,
                                                       len(self.scores))):] \
                if self.score_seq > score_seq else []
            learn = None
            if self.learning:
                elapsed = time.time() - self.learning["started"]
                learn = {"progress": min(1.0, elapsed / self.settings["learn_seconds"]),
                         "remaining": max(0.0, self.settings["learn_seconds"] - elapsed)}
            feats = None
            if self.features is not None:
                feats = []
                for i, (key, label, unit) in enumerate(FEATURES):
                    entry = {"key": key, "label": label, "unit": unit,
                             "value": _num(self.features[i])}
                    if self.model.ready:
                        entry["z"] = _num(self.zscores[i]) if self.zscores is not None else None
                        entry["normal"] = [_num(self.model.mean[i] - 3 * self.model.std[i]),
                                           _num(self.model.mean[i] + 3 * self.model.std[i])]
                    feats.append(entry)
            return {
                "running":    self.running,
                "status":     self.status,
                "source":     self.settings["source"],
                "connected":  self.connected,
                "port":       self.sensors.port if self.sensors else None,
                "health":     _num(self.health),
                "distance":   _num(self.distance),
                "rul_seconds": _num(self.rul_seconds),
                "trend_per_min": _num(self.trend_per_min),
                "diagnosis":  self.diagnosis,
                "features":   feats,
                "learning":   learn,
                "model":      {"ready": self.model.ready, "trained_at": self.model.trained_at,
                               "samples": self.model.samples},
                "sim":        {"wear": dict(self.sim.wear), "active": sorted(self.sim.active)},
                "settings":   dict(self.settings),
                "uptime":     time.time() - self.started_at if self.running else 0,
                "samples":    new_samples,
                "scores":     new_scores,
                "sample_seq": self.sample_seq,
                "score_seq":  self.score_seq,
                "server_time": time.time(),
            }

    def history_csv(self):
        with self._lock:
            rows = list(self.samples)
        lines = ["time,vibration_mm_s,temperature_c,current_a,speed_rpm"]
        for t, vib, temp, cur, spd in rows:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) + f".{int(t * 10) % 10}"
            lines.append(f"{stamp},{vib:.3f},{temp:.2f},{cur:.3f},{spd:.1f}")
        return "\n".join(lines) + "\n"

    # ── Internals ─────────────────────────────────────────
    def _features(self, now):
        cutoff = now - WINDOW_SECONDS
        window = [s for s in self.samples if s[0] >= cutoff]
        if len(window) < 5:
            return None
        arr = np.array(window)
        vib = arr[:, 1]
        # Heating rate from a straight-line fit over the last 30 s
        recent = np.array([s for s in self.samples if s[0] >= now - 30])
        rate = 0.0
        if len(recent) >= 10 and np.ptp(recent[:, 0]) > 5:
            rate = float(np.polyfit(recent[:, 0] - recent[0, 0], recent[:, 2], 1)[0] * 60)
        speed = arr[:, 4]
        speed = float(np.nanmean(speed)) if not np.all(np.isnan(speed)) else float("nan")
        return np.array([math.sqrt(float(np.mean(vib ** 2))), float(vib.max()),
                         float(arr[:, 2].mean()), rate, float(arr[:, 3].mean()), speed])

    def _diagnose(self, z):
        pos = np.clip(z, 0, None)               # only "higher than normal" counts...
        keys = [f[0] for f in FEATURES]
        pos[keys.index("speed")] = max(0.0, -z[keys.index("speed")])   # ...except speed drops
        scores = {}
        for fault, spec in FAULTS.items():
            scores[fault] = sum(w * pos[keys.index(k)] for k, w in spec["features"].items()) \
                / sum(spec["features"].values())
        best = max(scores, key=scores.get)
        total = sum(scores.values()) or 1.0
        if scores[best] < 1.5:
            return None
        return {"fault": best, "name": FAULTS[best]["name"], "action": FAULTS[best]["action"],
                "confidence": round(scores[best] / total, 2)}

    def _trend(self, now):
        horizon = self.settings["trend_seconds"]
        pts = [(t, h) for t, h, _ in self.scores if t >= now - horizon]
        if len(pts) < 20:
            return None, None
        t = np.array([p[0] for p in pts]) - now
        h = np.array([p[1] for p in pts])
        slope = np.polyfit(t, h, 1)[0]
        per_min = float(slope * 60)
        critical = self.settings["critical_health"]
        if self.health <= critical:
            return 0.0, per_min
        recent = t >= -30
        recovering = recent.sum() >= 10 and np.polyfit(t[recent], h[recent], 1)[0] > 0.05
        if slope > -0.01 or recovering:          # flat or improving: no failure ahead
            return None, per_min
        return float((self.health - critical) / -slope), per_min

    def _set_status(self, status):
        self.status = status
        if status == self._last_status:
            return
        prev, self._last_status = self._last_status, status
        messages = {
            "healthy":  ("ok",    "Machine healthy"),
            "warning":  ("warn",  "Health degrading - plan maintenance"),
            "critical": ("alarm", "Health critical - stop the machine for maintenance"),
            "offline":  ("warn",  "No sensor data"),
        }
        if status not in messages:
            return
        if status == "healthy" and prev in (None, "learning", "starting"):
            return                               # nothing worth announcing
        level, msg = messages[status]
        if status == "warning" and prev == "critical":
            level, msg = "info", "Health recovering"
        elif self.diagnosis and status in ("warning", "critical"):
            msg += f" (likely {self.diagnosis['name'].lower()})"
        self.log(level, msg)

    def _score(self, now):
        feats = self._features(now)
        if feats is None:
            return
        self.features = feats
        model_row = np.nan_to_num(feats, nan=0.0)

        if self.learning is not None:
            self.learning["rows"].append(model_row)
            if now - self.learning["started"] >= self.settings["learn_seconds"]:
                rows = self.learning["rows"]
                self.learning = None
                if len(rows) < 20:
                    self.log("warn", "Not enough data to learn a baseline - try again")
                else:
                    self.model.fit(rows)
                    with open(MODEL_FILE, "w") as f:
                        json.dump(self.model.to_json(), f)
                    self.scores.clear()
                    self.log("ok", f"Baseline learned from {len(rows)} windows - model ready")
            else:
                self._set_status("learning")
                return
        if not self.model.ready:
            self._set_status("learning")
            return

        d, z = self.model.score(model_row)
        h = health_from_distance(d)
        # Smooth the index so one noisy window does not flip the status.
        self.health = h if self.health is None else self.health * 0.8 + h * 0.2
        self.distance, self.zscores = d, z
        self.scores.append((now, round(self.health, 2), round(d, 3)))
        self.score_seq += 1
        self.diagnosis = self._diagnose(z) if self.health < 90 else None
        self.rul_seconds, self.trend_per_min = self._trend(now)

        # Hysteresis: worsen as soon as a level is crossed, but only improve
        # once health is clearly back above it, so the status does not flicker.
        s, h, prev = self.settings, self.health, self.status
        margin = 5
        if h < s["critical_health"] or (prev == "critical" and h < s["critical_health"] + margin):
            status = "critical"
        elif h < s["warn_health"] or (prev in ("warning", "critical") and h < s["warn_health"] + margin):
            status = "warning"
        else:
            status = "healthy"
        self._set_status(status)

    def _run(self):
        next_score = time.time()
        try:
            while not self._stop.is_set():
                with self._lock:
                    if self._source_dirty:
                        if self.sensors:
                            self.sensors.close()
                        self.sensors = None
                        if self.settings["source"] == "serial":
                            self.sensors = SerialSensors(self.settings["serial_port"],
                                                         self.settings["baud"], self.log)
                        self._source_dirty = False
                    source = self.settings["source"]

                if source == "simulator":
                    reading = self.sim.read()
                    self._stop.wait(1.0 / SAMPLE_HZ)
                else:
                    reading = self.sensors.read()

                now = time.time()
                with self._lock:
                    self.connected = source == "simulator" or (self.sensors and self.sensors.connected)
                    if reading is not None:
                        self.samples.append((now, round(reading["vib"], 3), round(reading["temp"], 2),
                                             round(reading["current"], 3), round(reading["speed"], 1)))
                        self.sample_seq += 1
                    # Drop samples older than the history window.
                    while self.samples and self.samples[0][0] < now - HISTORY_SECONDS:
                        self.samples.popleft()
                    if now >= next_score:
                        next_score = now + SCORE_EVERY
                        if self.connected:
                            self._score(now)
                        else:
                            self._set_status("offline")
        except Exception as e:
            self.log("alarm", f"Engine crashed: {e}")
            raise
        finally:
            if self.sensors:
                self.sensors.close()
            self.status = "stopped"


def _num(v):
    """JSON-safe float (NaN/inf become None)."""
    if v is None:
        return None
    v = float(v)
    return round(v, 3) if math.isfinite(v) else None
