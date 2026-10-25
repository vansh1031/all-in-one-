# 🚨 Hazardous Zone Detector

AI-powered Hazardous Zone Detection system using MediaPipe, OpenCV & Arduino buzzer on NVIDIA Jetson Orin.

## 📌 Overview
This system detects human presence (hands, face, body) in a defined hazardous zone using computer vision and triggers an Arduino buzzer as an alert.

## 🛠️ Tech Stack
- **Platform:** NVIDIA Jetson Orin
- **Language:** Python 3.12
- **Libraries:** OpenCV, MediaPipe, Tkinter, Flask, PySerial
- **Hardware:** Arduino (buzzer), USB Camera

## 📁 Project Structure
Hazardous Zone/
├── launcher.py          # Tkinter UI launcher
├── buzzer_detector.py   # Main OpenCV + MediaPipe detector
├── hazard_server.py     # Flask web server for dashboard
├── start_server.sh      # Shell script to start server
├── main.py              # Entry point
├── hand_landmarker.task # MediaPipe hand model
├── face_detector.tflite # MediaPipe face model
├── yash_logo.png        # Logo
└── README.md            # This file
## 🚀 Setup & Installation

### 1. Clone Repository
```bash
git clone https://github.com/Somya170/Hazardous-Zone-Detector.git
cd Hazardous-Zone-Detector
```

### 2. Install Dependencies
```bash
pip install opencv-python mediapipe flask pyserial
```

### 3. Run Manually
```bash
python3 launcher.py
```

## ⚙️ Auto-Start on Boot (Systemd)
The system is configured to auto-start on Jetson boot using systemd services.

```bash
# Check status
sudo systemctl status hazard-detector.servicedd
sudo systemctl status hazard-server.service

# Restart
sudo systemctl restart hazard-detector.service
sudo systemctl restart hazard-server.service
```

## 🌐 Web Dashboard Integration
The Flask server runs on port `8765`. Use this URL in your dashboard:http://127.0.0.1:8765/start
Clicking this URL will launch the Hazardous Zone Detector window.

## 🔌 Hardware Setup
| Device | Port |
|--------|------|
| Arduino (Buzzer) | `/dev/ttyACM0` → `/dev/ttyACM1` → `/dev/ttyUSB0` (auto-detect) |
| USB Camera | `/dev/video0` |

## 👤 Author
**Somya** — NVIDIA Jetson Orin Project
