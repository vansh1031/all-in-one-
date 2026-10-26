# 🏭 Industrial Safety & Maintenance AI

Two edge-AI applications for the NVIDIA Jetson Orin, each running on one browser screen:

| App | What it does | URL |
|-----|--------------|-----|
| 🚨 **Hazardous Zone Detector** | Camera AI (MediaPipe + OpenCV) spots a hand, face or body inside a danger zone and sounds the Arduino buzzer to stop the machine | http://127.0.0.1:8765/start |
| 🔧 **Edge AI Predictive Maintenance** | Learns a machine's normal vibration, temperature, current and speed, scores its health 0–100, estimates the time left before maintenance, and names the likely fault | http://127.0.0.1:8766/start |

Both apps include a built-in **simulator**, so you can run and demo them without a camera, sensors or an Arduino.

## 📁 Project Structure
```
hazardious/
├── hazard_zone/                  # 🚨 Hazardous Zone Detector
│   ├── hazard_server.py          #   web server: UI, video stream, API (port 8765)
│   ├── detector_engine.py        #   camera/simulator, detectors, zone + buzzer logic
│   ├── web/                      #   single-screen UI (index.html, style.css, app.js)
│   ├── models/                   #   MediaPipe models (hand_landmarker.task, face_detector.tflite)
│   ├── config/                   #   zone_config.json, settings.json (created from the UI)
│   └── logs/                     #   hazard_log.txt (created at runtime)
├── predictive_maintenance/       # 🔧 Edge AI Predictive Maintenance
│   ├── pm_server.py              #   web server: UI, live data stream, API (port 8766)
│   ├── pm_engine.py              #   sensors/simulator, anomaly model, health, prediction
│   ├── web/                      #   single-screen dashboard
│   ├── config/                   #   settings.json, pm_model.json (created at runtime)
│   └── logs/                     #   pm_log.txt (created at runtime)
├── assets/                       # shared branding (YASH logo)
├── scripts/
│   ├── start_hazard_zone.sh
│   └── start_predictive_maintenance.sh
├── start_server.sh               # kept for the existing systemd service, starts the hazard detector
└── requirements.txt
```

## 🛠️ Tech Stack
- **Platform:** NVIDIA Jetson Orin
- **Language:** Python 3.12
- **Libraries:** OpenCV, MediaPipe, NumPy, Flask, PySerial
- **Hardware:** Arduino (buzzer / sensor board), USB camera

## 🚀 Setup
```bash
git clone https://github.com/vansh1031/hazardious.git
cd hazardious
pip install -r requirements.txt

./scripts/start_hazard_zone.sh              # → http://127.0.0.1:8765/start
./scripts/start_predictive_maintenance.sh   # → http://127.0.0.1:8766/start
```
Both servers accept connections from the Jetson itself only. To open them from another
machine, set `HAZARD_HOST=0.0.0.0` or `PM_HOST=0.0.0.0` before starting. Anyone who can
reach the port can then control the app.

---

## 🚨 Hazardous Zone Detector

| Action | How |
|--------|-----|
| Draw / edit the danger zone | **Draw zone**, tap the corners, then tap the first corner or **Arm zone**. Drag corners to adjust. |
| Remove the zone | **Reset zone** (tap twice: this disarms monitoring) |
| Pause / resume monitoring | **Stop** (tap twice) / **Start** |
| Test without a camera | Top bar → **Simulator**. Tap or drag on the video to move the worker, or press **Auto walk** |
| Camera, serial port, confidence, grace frames | ⚙️ **Settings**, which also has a 1-second **Test buzzer** button |

The machine simulator card shows what the buzzer does to the machine: it runs while the zone is
clear and brakes to an emergency stop when someone enters.

**Safety behaviour**
- If the camera disconnects while a zone is armed, the buzzer turns **on**, so the machine stays
  stopped until the camera is back. You can turn this off in Settings ("Fail-safe").
- If the detector crashes while a zone is armed, the buzzer also stays on.
- If the Arduino is unplugged and plugged back in during an alarm, the alarm is sent again.
- Resetting the zone or stopping monitoring turns the buzzer off.

**Arduino buzzer** (9600 baud, auto-detects `/dev/ttyACM0`, `/dev/ttyACM1`, `/dev/ttyUSB0`, `/dev/ttyUSB1`):
`D\n` = person detected (buzzer on), `S\n` = safe (buzzer off).

---

## 🔧 Edge AI Predictive Maintenance

**How the AI works.** It runs on the Jetson CPU and only needs NumPy:
1. **Learn:** for the first 90 s (configurable), the machine runs normally and the app learns
   its healthy baseline from 3-second feature windows: vibration RMS and peak, temperature,
   heating rate, current and speed.
2. **Score:** every 0.5 s it measures how far the current window is from that baseline
   (Mahalanobis distance) and turns that into a **health index from 0 to 100**.
3. **Predict:** a trend fitted to the last 2 minutes of health gives the **estimated time
   to maintenance**, meaning when health will reach the critical level.
4. **Explain:** the features furthest from normal (measured in σ) point to the likely fault:
   **bearing wear**, **overheating** or **electrical overload**, along with a recommended action.

| Action | How |
|--------|-----|
| Try it without hardware | Top bar → **Simulator**, then inject **Bearing wear**, **Overheating** or **Overload**, and press **Repair** to reset |
| Change the time range | **Last 1 / 5 / 15 min** above the charts |
| See the raw numbers | **Table** view, or **Export CSV** |
| Re-train after maintenance | **Re-learn baseline** (tap twice, and only while the machine is healthy) |
| Thresholds, learning time, serial port | ⚙️ **Settings** |

**Sensor board** (default 115200 baud): send one line per reading, around 10 per second:
```
vibration_mm_s,temperature_c,current_a,speed_rpm
2.41,47.8,9.62,1462
```
The speed value is optional.

---

## ⚙️ Auto-start on boot (systemd)
`hazard-server.service` can keep running `start_server.sh`; it now starts the detector from its
new folder. The old `hazard-detector.service` started the Tkinter launcher, which no longer
exists, so disable it:
```bash
sudo systemctl disable --now hazard-detector.service
sudo systemctl restart hazard-server.service
```
To start predictive maintenance on boot, create a second service with (the quotes matter because of the space):
```ini
ExecStart="/home/jetiot/Downloads/Hazardous Zone/scripts/start_predictive_maintenance.sh"
```

## 🌐 Dashboard integration
- Hazardous Zone Detector card → `http://127.0.0.1:8765/start`
- Predictive Maintenance card → `http://127.0.0.1:8766/start`

## 👤 Author
**Somya** — NVIDIA Jetson Orin Project
