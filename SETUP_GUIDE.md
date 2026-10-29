# Setup & Run Guide: Windows and Jetson

This guide gets both apps running on a **Windows PC** or the **NVIDIA Jetson Orin** (any Linux PC works the same way).

| App | Address once running |
|-----|----------------------|
| 🚨 Hazardous Zone Detector | http://127.0.0.1:8765/start |
| 🔧 Predictive Maintenance | http://127.0.0.1:8766/start |

Both apps have a **Simulator** mode, so you can check that everything works before connecting the camera or Arduino.

---

## 🪟 Windows

### One-time setup
1. **Install Python 3.12 (64-bit)** from https://www.python.org/downloads/.
   On the first installer screen, tick **"Add python.exe to PATH"**.
2. **Download the project.** On https://github.com/vansh1031/visual-inspection click
   **Code → Download ZIP** and unzip it, for example to `C:\visual-inspection`.
   With Git installed, you can run `git clone https://github.com/vansh1031/visual-inspection.git` instead.
3. **Double-click `install_windows.bat`.** It creates a private Python environment (`.venv`),
   installs the libraries (the first time takes about 5 minutes) and runs a setup check.
   The check should end with `Result: ready to run`.

### Every day
- Double-click **`start_all.bat`**. Two windows open, one per app, and the browser opens both apps.
- To run only one app, double-click `scripts\start_hazard_zone.bat` or `scripts\start_predictive_maintenance.bat`.
- **To stop:** close the black window(s).

### Windows notes
- The Arduino appears as a **COM port** (for example `COM3`). Auto-detect finds it; to choose it
  yourself, open ⚙️ Settings in the app.
- **Close the Arduino IDE's Serial Monitor** before starting, because only one program can use a COM port.
- If the laptop's built-in camera shows instead of the USB camera, set **Camera index** to `1` in ⚙️ Settings.
- If Windows Firewall asks about network access, you can click **Cancel**. The apps only listen on this PC.

---

## 🟩 Jetson Orin (or any Linux PC)

### One-time setup
```bash
cd ~
git clone https://github.com/vansh1031/visual-inspection.git
cd visual-inspection
./install_jetson.sh
```
The installer uses your Python 3.12, creates `.venv`, installs the libraries and runs the setup check.

**Arduino permission (once):** if the check prints a `dialout` warning, run the following, then log out and back in:
```bash
sudo usermod -aG dialout $USER
```

### Every day
```bash
./start_all.sh        # starts both apps and opens the browser; Ctrl+C stops both
```
To run only one app, use `./scripts/start_hazard_zone.sh` or `./scripts/start_predictive_maintenance.sh`.

### Start automatically on boot
```bash
./install_jetson.sh --service
```
This creates `hazard-server` and `pm-server` systemd services and starts them. It backs up the
old `hazard-server.service` and turns off the old `hazard-detector.service`, which opened the
Tkinter pop-up windows. Useful commands:
```bash
systemctl status hazard-server pm-server     # are they running?
sudo systemctl restart hazard-server          # restart after an update
journalctl -u hazard-server -f                # live log
```

### Moving from the old "Hazardous Zone" folder
The old setup lived in `/home/jetiot/Downloads/Hazardous Zone`. After installing the new
folder, you can bring your saved danger zone across:
```bash
cp "/home/jetiot/Downloads/Hazardous Zone/zone_config.json" ~/visual-inspection/hazard_zone/config/
```
The zone converts to the new format automatically the first time the camera runs.
The dashboard card address (`http://127.0.0.1:8765/start`) stays the same.

### Updating to a newer version
```bash
cd ~/visual-inspection
git pull
./install_jetson.sh             # picks up any new libraries
sudo systemctl restart hazard-server pm-server    # only if you use the services
```
On Windows, download the ZIP again (keep your `hazard_zone\config` folder) and run `install_windows.bat`.

---

## 🖥️ Screens and kiosk mode
The layout adapts to the screen. It was tested on 7" (800×480) and 10" (1024×600) touchscreens,
laptops (1366×768), Full HD, QHD and 4K monitors, tablets and phones.
- **Landscape screens** keep the status panel beside the video or charts, so nothing needs scrolling.
- **Portrait tablets and phones** stack the panels; scroll down for the status and log.
- **Very large screens** at 100% scaling are enlarged automatically so the text stays readable.

For a dedicated screen, press the ⛶ **Full screen** button in the top bar. To open straight into
full screen on the Jetson (press Alt+F4 to leave):
```bash
chromium-browser --kiosk http://127.0.0.1:8765/start
```
On Windows, press **F11** in the browser.

---

## ✅ First-run checklist

**Hazardous Zone Detector**
1. Switch to **Simulator** at the top and draw a zone: **Draw zone**, tap the corners, then **Arm zone**.
   Drag the worker into the zone; the alarm, red screen and E-STOP should appear.
2. Switch to **Camera**. If the picture is wrong or missing, change **Camera index** in ⚙️ Settings.
3. With the Arduino plugged in, the top bar should show **Arduino: COM3** (Windows) or
   **ttyACM0** (Jetson). Press **Test buzzer** in ⚙️ Settings.
4. Draw the real danger zone on the camera picture.

**Predictive Maintenance**
1. In **Simulator** mode, wait for **Learning** to reach 100% (90 seconds).
2. Press **Bearing wear**. Within about 1–2 minutes the health should drop and the diagnosis should
   say *Bearing wear / imbalance*. Press **Repair** to reset.
3. For a real machine, switch to **Sensors**, let it learn while the machine runs normally, and only
   press **Re-learn baseline** when the machine is known to be healthy.

---

## 🔍 Check the setup any time
```bash
.venv/bin/python scripts/check_setup.py          # Jetson / Linux
.venv\Scripts\python scripts\check_setup.py      # Windows
```
It checks Python, the libraries, the AI models, cameras, serial ports and the web ports.
It changes nothing, and it prints a hint next to anything that is wrong.

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `Python was not found` (Windows) | Install Python 3.12 and tick "Add python.exe to PATH", then run `install_windows.bat` again |
| `python3 -m venv` fails (Jetson) | `sudo apt install python3-venv`, then run `./install_jetson.sh` again |
| MediaPipe will not install | Use Python **3.12**. Newer versions may not have a MediaPipe build yet. The apps still run without it (body detection only) |
| Page does not open / "can't reach this page" | The server isn't running: start it again and wait about 5 seconds. Make sure nothing else uses ports 8765/8766 |
| "CAMERA NOT AVAILABLE" | Plug in the camera, close other apps using it (Zoom, Teams, Camera app), or try another **Camera index** |
| Arduino shows "offline" | Check the USB cable; close the Arduino Serial Monitor; on Jetson add yourself to `dialout`; pick the port in ⚙️ Settings |
| Buzzer sounds when nobody is there | The camera was lost and the fail-safe kept the machine stopped. Fix the camera, or turn off **Fail-safe** in ⚙️ Settings |
| Predictive maintenance warns on a healthy machine | The baseline was too short or was learned during unusual operation. Press **Re-learn baseline** while the machine runs normally through a full cycle |
| Old Tkinter pop-up still appears on boot (Jetson) | `sudo systemctl disable --now hazard-detector.service` |
| Want to open the apps from another computer | Start with `HAZARD_HOST=0.0.0.0` / `PM_HOST=0.0.0.0`. Only do this on a trusted network, because anyone on the network can then control the apps |
