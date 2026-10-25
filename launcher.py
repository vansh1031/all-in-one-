import tkinter as tk
from tkinter import font as tkfont
import subprocess
import sys
import os

SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
DETECTOR_SCRIPT = os.path.join(SCRIPT_DIR, "buzzer_detector.py")
LOGO_PATH       = os.path.join(SCRIPT_DIR, "yash_logo.png")

BG       = "#0d0d14"
CARD_BG  = "#13131f"
RED      = "#d42b2b"
BLUE     = "#1a4f9c"
GOLD     = "#b8962e"
WHITE    = "#f2f2f2"
MUTED    = "#44445a"
BORDER_R = "#3a1515"
BORDER_B = "#0f2a55"
HAND_BG  = "#2a0d0d"
FACE_BG  = "#0a1a30"
BODY_BG  = "#1e1800"


class HazardLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hazardous Zone Detector — Yash Technologies")
        self.configure(bg=BG)
        self.resizable(False, False)

        W, H = 560, 620
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.W = W
        self.H = H

        self.f_title = tkfont.Font(family="Helvetica", size=17, weight="bold")
        self.f_badge = tkfont.Font(family="Helvetica", size=9,  weight="bold")
        self.f_btn   = tkfont.Font(family="Helvetica", size=13, weight="bold")
        self.f_sec   = tkfont.Font(family="Helvetica", size=11)
        self.f_small = tkfont.Font(family="Helvetica", size=9)
        self.f_stat  = tkfont.Font(family="Helvetica", size=14, weight="bold")

        self.canvas = tk.Canvas(self, width=W, height=H,
                                bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self._logo_img = None
        self._load_logo()
        self._build_ui()

    def _load_logo(self):
        try:
            from PIL import Image, ImageTk
            img = Image.open(LOGO_PATH).convert("RGBA")
            data = img.getdata()
            new_data = []
            for r, g, b, a in data:
                if r > 200 and g > 200 and b > 200:
                    new_data.append((13, 13, 31, 255))
                else:
                    new_data.append((r, g, b, a))
            img.putdata(new_data)
            img = img.resize((200, 88), Image.LANCZOS)
            self._logo_img = ImageTk.PhotoImage(img)
            print("Logo loaded!")
        except Exception as e:
            print(f"Logo error: {e}")

    def _rrect(self, x1, y1, x2, y2, r=12, **kw):
        pts = [
            x1+r, y1,   x2-r, y1,
            x2,   y1,   x2,   y1+r,
            x2,   y2-r, x2,   y2,
            x2-r, y2,   x1+r, y2,
            x1,   y2,   x1,   y2-r,
            x1,   y1+r, x1,   y1,
        ]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def _build_ui(self):
        c = self.canvas
        W = self.W
        H = self.H

        for x in range(0, W, 44):
            for y in range(0, H, 44):
                c.create_oval(x, y, x+1, y+1, fill="#1a1a26", outline="")

        c.create_rectangle(0, 0, W, 4, fill=BLUE, outline="")

        self._rrect(28, 24, W-28, H-24, r=18,
                    fill=CARD_BG, outline=BORDER_R, width=1)

        c.create_arc(260, 30, 560, 180, start=30, extent=120,
                     outline=BLUE, width=2, style="arc")

        if self._logo_img:
            c.create_image(W//2, 105, image=self._logo_img, anchor="center")
        else:
            c.create_text(W//2, 90, text="YASH", fill=RED,
                          font=tkfont.Font(family="Helvetica", size=36, weight="bold"))
            c.create_text(W//2, 125, text="Technologies", fill=GOLD,
                          font=tkfont.Font(family="Helvetica", size=16))

        c.create_line(80, 158, W-80, 158, fill=BORDER_R, width=1)

        c.create_text(W//2, 192, text="HAZARDOUS ZONE DETECTOR",
                      fill=WHITE, font=self.f_title, anchor="center")
        c.create_text(W//2, 218, text="Real-time AI Safety Monitoring System",
                      fill=GOLD, font=self.f_small, anchor="center")

        c.create_line(120, 238, W-120, 238, fill=BORDER_B, width=1)

        stats = [
            ("3",      "Detectors", WHITE),
            ("Active", "Status",    "#2ecc71"),
            ("AI",     "Engine",    "#4a9eff"),
        ]
        for (val, lbl, col), px in zip(stats, [W//2-130, W//2, W//2+130]):
            c.create_text(px, 268, text=val, fill=col,
                          font=self.f_stat, anchor="center")
            c.create_text(px, 288, text=lbl, fill=MUTED,
                          font=self.f_small, anchor="center")

        badge_data = [
            ("HAND", RED,  HAND_BG, 100),
            ("FACE", BLUE, FACE_BG, 210),
            ("BODY", GOLD, BODY_BG, 320),
        ]
        for label, border_col, fill_col, bx in badge_data:
            self._rrect(bx, 308, bx+90, 332, r=6,
                        fill=fill_col, outline=border_col, width=1)
            c.create_text(bx+45, 320, text=label, fill=border_col,
                          font=self.f_badge, anchor="center")

        self.btn_launch = tk.Button(
            self, text="  LAUNCH DETECTOR  ",
            font=self.f_btn, bg=RED, fg=WHITE,
            activebackground="#b01a1a", activeforeground=WHITE,
            relief="flat", cursor="hand2",
            command=self._launch_detector, bd=0)
        c.create_window(W//2, 390, window=self.btn_launch,
                        width=360, height=52)

        sec = [("Settings", self._open_settings),
               ("Logs",     self._view_logs),
               ("About",    self._about)]
        bw = 110; gap = 12
        sx = (W - (len(sec)*bw + (len(sec)-1)*gap)) // 2
        for i, (txt, cmd) in enumerate(sec):
            bx = sx + i * (bw + gap)
            btn = tk.Button(self, text=txt, font=self.f_sec,
                            bg=CARD_BG, fg="#7777aa",
                            activebackground="#1e1e30",
                            activeforeground=WHITE,
                            relief="flat", cursor="hand2",
                            command=cmd, bd=0)
            c.create_window(bx + bw//2, 455, window=btn,
                            width=bw, height=36)

        self.status_lbl = tk.Label(
            self, text="System ready — touch Launch to begin",
            bg=CARD_BG, fg=MUTED, font=self.f_small)
        c.create_window(W//2, 508, window=self.status_lbl, width=460)

        c.create_line(80, 530, W-80, 530, fill=BORDER_R, width=1)
        c.create_text(W//2, 552,
                      text="Yash Technologies  —  Industrial Safety AI",
                      fill=MUTED, font=self.f_small, anchor="center")
        c.create_rectangle(0, H-4, W, H, fill=BLUE, outline="")

    def _launch_detector(self):
        self._set_status("Launching...", "#f0a020")
        if not os.path.exists(DETECTOR_SCRIPT):
            self._set_status("Error: buzzer_detector.py nahi mila!", RED)
            return
        try:
            proc = subprocess.Popen([sys.executable, DETECTOR_SCRIPT],
                                    cwd=SCRIPT_DIR)
            self._set_status(f"Detector launched! PID {proc.pid}", "#2ecc71")
        except Exception as e:
            self._set_status(f"Launch failed: {e}", RED)

    def _open_settings(self):
        win = tk.Toplevel(self)
        win.title("Settings")
        win.configure(bg=BG)
        win.geometry("400x340")
        win.resizable(False, False)
        tk.Label(win, text="Detector Settings", bg=BG, fg=WHITE,
                 font=tkfont.Font(family="Helvetica", size=14, weight="bold")
                 ).pack(pady=(18, 8))
        fields = [("Serial Port", "/dev/ttyACM0"), ("Baud Rate", "9600"),
                  ("Camera Index", "0"), ("Grace Frames", "5"),
                  ("Res Width", "1200"), ("Res Height", "690")]
        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="x", padx=24)
        for i, (lbl, val) in enumerate(fields):
            tk.Label(frame, text=lbl, bg=BG, fg="#888899",
                     font=self.f_small, width=14, anchor="w"
                     ).grid(row=i, column=0, pady=5, sticky="w")
            e = tk.Entry(frame, bg="#1c1c2e", fg=WHITE,
                         insertbackground=WHITE, relief="flat",
                         font=self.f_small)
            e.insert(0, val)
            e.grid(row=i, column=1, padx=8, pady=5, sticky="ew")
        tk.Button(win, text="Save & Close", bg=RED, fg=WHITE,
                  font=self.f_sec, relief="flat",
                  command=win.destroy).pack(pady=14, ipadx=20, ipady=6)

    def _view_logs(self):
        win = tk.Toplevel(self)
        win.title("Detection Logs")
        win.configure(bg=BG)
        win.geometry("500x340")
        txt = tk.Text(win, bg="#0d0d18", fg="#aaaacc",
                      font=("Courier", 10), relief="flat")
        txt.pack(fill="both", expand=True, padx=16, pady=16)
        log_file = os.path.join(SCRIPT_DIR, "hazard_log.txt")
        if os.path.exists(log_file):
            with open(log_file) as f:
                txt.insert("end", f.read())
        else:
            txt.insert("end", "No logs for now.\nMeanwhile start detector, Alerts will be visible here.\n")
        txt.config(state="disabled")

    def _about(self):
        win = tk.Toplevel(self)
        win.title("About")
        win.configure(bg=BG)
        win.geometry("360x240")
        win.resizable(False, False)
        infos = [
            ("Hazardous Zone Detector", WHITE, 15, "bold"),
            ("v2.0  —  Yash Technologies", GOLD, 11, "normal"),
            ("", "", 4, "normal"),
            ("Detectors:  Hand  |  Face  |  Body", "#888899", 10, "normal"),
            ("Platform:  NVIDIA Jetson Orin", "#555566", 10, "normal"),
            ("Serial:  Arduino /dev/ttyACM0", "#555566", 10, "normal"),
            ("", "", 4, "normal"),
            ("AI Engine:  MediaPipe + HOG", "#555566", 10, "normal"),
        ]
        for (text, col, size, wt) in infos:
            if not text:
                tk.Frame(win, bg=BG, height=size).pack()
                continue
            tk.Label(win, text=text, bg=BG, fg=col,
                     font=tkfont.Font(family="Helvetica",
                                      size=size, weight=wt)).pack()

    def _set_status(self, msg, color=MUTED):
        self.status_lbl.config(text=msg, fg=color)
        print(f"[STATUS] {msg}")


if __name__ == "__main__":
    app = HazardLauncher()
    app.mainloop()