# 🚨 Hazardous Zone Detector

AI-powered hazardous zone detection using MediaPipe, OpenCV and an Arduino buzzer on NVIDIA Jetson Orin.

## 📌 Overview
The detector watches a danger zone you draw on the camera image. When a hand, face or body
enters the zone it sounds the Arduino buzzer, which stops the machine, and keeps it sounding
until the zone has been clear for a few frames.

Everything runs in **one browser screen**: live video, drawing the zone, alarm status, an
animated machine simulator, detection stats, the event log and settings. There are no separate
Tkinter or OpenCV windows.

## 🛠️ Tech Stack
- **Platform:** NVIDIA Jetson Orin
- **Language:** Python 3.12
- **Libraries:** OpenCV, MediaPipe, Flask, PySerial
- **Hardware:** Arduino (buzzer), USB camera

## 📁 Project Structure
```
Hazardous Zone/
├── hazard_server.py      # Flask server: serves the UI, video stream and API
├── detector_engine.py    # Camera/simulator capture, detectors, zone + buzzer logic
├── web/                  # Single-screen UI (index.html, style.css, app.js)
├── start_server.sh       # Starts the server (used by systemd)
├── hand_landmarker.task  # MediaPipe hand model
├── face_detector.tflite  # MediaPipe face model
├── zone_config.json      # Saved danger zone (created from the UI)
├── settings.json         # Saved settings (created from the UI)
└── hazard_log.txt        # Event log (alarms, zone changes, camera/serial events)
```

## 🚀 Setup
```bash
git clone https://github.com/vansh1031/hazardious.git
cd hazardious
pip install -r requirements.txt
./start_server.sh            # or: python3 hazard_server.py
```
Then open **http://127.0.0.1:8765/start**.

The server listens on `127.0.0.1` only. To open the screen from another machine, start it with
`HAZARD_HOST=0.0.0.0 ./start_server.sh`. Anyone who can reach the port can then control the detector.

## 🖥️ Using the screen
| Action | How |
|--------|-----|
| Draw / edit the danger zone | **Draw zone**, tap the corners, then tap the first corner or **Arm zone**. Drag corners to adjust. |
| Remove the zone | **Reset zone** (tap twice: this disarms monitoring) |
| Pause / resume monitoring | **Stop** (tap twice) / **Start** |
| Test without a camera | Switch the top bar to **Simulator**, then tap or drag on the video to move the worker, or press **Auto walk** |
| Camera, serial port, confidence, grace frames | ⚙️ **Settings**, which also has a 1-second **Test buzzer** button |
| Alarm sound in the browser | 🔊 button in the top bar |

The **machine simulator** card shows what the buzzer does to the machine. It runs while the zone
is clear, brakes to an emergency stop when someone enters, and spins back up once the zone is clear again.

### Safety behaviour
- If the camera disconnects while a zone is armed, the buzzer turns **on**, so the machine stays
  stopped until the camera is back. You can turn this off in Settings ("Fail-safe").
- If the detector crashes while a zone is armed, the buzzer also stays on.
- If the Arduino is unplugged and plugged back in during an alarm, the alarm is sent again.
- Resetting the zone or stopping monitoring turns the buzzer off.

## 🔌 Hardware
| Device | Port |
|--------|------|
| Arduino (buzzer) | auto-detect: `/dev/ttyACM0`, `/dev/ttyACM1`, `/dev/ttyUSB0`, `/dev/ttyUSB1` (or pick one in Settings) |
| USB camera | index `0` (`/dev/video0`), changeable in Settings |

Serial protocol at 9600 baud: `D\n` = person detected (buzzer on), `S\n` = safe (buzzer off).

## ⚙️ Auto-start on boot (systemd)
Only `hazard-server.service` is needed now. It should run `start_server.sh`. The old
`hazard-detector.service` started the Tkinter launcher, which no longer exists, so disable it:
```bash
sudo systemctl disable --now hazard-detector.service
sudo systemctl restart hazard-server.service
sudo systemctl status hazard-server.service
```

## 🌐 Dashboard integration
Keep the dashboard card pointing at **http://127.0.0.1:8765/start**. That URL now opens the full
application directly, instead of an "OK" page plus pop-up windows.

## 👤 Author
**Somya** — NVIDIA Jetson Orin Project
