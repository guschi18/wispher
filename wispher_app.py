"""Wispher – GUI-App: Tray-Icon + Fenster mit Klick-zum-Kopieren. Start: Wispher.exe"""
import ctypes
import os
import queue
import socket
import sys
import threading
import tkinter as tk
from pathlib import Path

import pyperclip
import pystray
from PIL import Image, ImageDraw, ImageTk

import wispher
from wispher import APP_DIR, Config, HotkeyServer, log

RES = Path(getattr(sys, "_MEIPASS", APP_DIR))  # gebündelte Dateien (assets/)
BG, CARD, CARD_HOVER = "#1b1511", "#2a2019", "#37291f"
TEXT, MUTED, ACCENT, ACCENT_TEXT = "#f6ece1", "#a3917f", "#ff8a4c", "#2a1608"
FONT = "Segoe UI Variable Display"
W = 392  # Kartenbreite
STATES = {  # state -> (Statustext, Punktfarbe)
    "loading": ("Modell lädt …", "#8a7b6e"),
    "ready": ("Bereit – F12 halten zum Sprechen", "#8fd694"),
    "recording": ("Nimmt auf …", "#ff5a4d"),
    "transcribing": ("Transkribiere …", "#ffc24d"),
}
HISTORY_MAX = 6  # 1 großer + 5 im Verlauf


def rounded(w, h, r, fill):
    """Anti-aliased Rundrechteck (4x supersampled) als Tk-Bild."""
    k = 4
    im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * k - 1, h * k - 1), r * k, fill=fill)
    return ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS))


class Card(tk.Canvas):
    """Klickbare Karte mit runden Ecken und Hover-Effekt."""

    def __init__(self, parent, h, r, on_click):
        super().__init__(parent, width=W, height=h, bg=BG, highlightthickness=0, cursor="hand2")
        self._normal, self._hover = rounded(W, h, r, CARD), rounded(W, h, r, CARD_HOVER)
        self._bg = self.create_image(0, 0, anchor="nw", image=self._normal)
        self.bind("<Enter>", lambda _e: self.itemconfig(self._bg, image=self._hover))
        self.bind("<Leave>", lambda _e: self.itemconfig(self._bg, image=self._normal))
        self.bind("<Button-1>", lambda _e: on_click())


def clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


class App:
    def __init__(self):
        self.events: queue.Queue = queue.Queue()
        self.history: list[str] = []
        self.base_icon = Image.open(RES / "assets" / "icon.png").convert("RGBA")

        self.root = tk.Tk()
        self.root.title("Wispher")
        self.root.configure(bg=BG)
        self.root.geometry("432x640")
        self.root.resizable(False, False)
        self.root.iconbitmap(str(RES / "assets" / "icon.ico"))
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)  # X = in den Tray
        self._dark_titlebar()
        self._build_ui()

        self.tray = pystray.Icon("Wispher", self._tray_image("loading"), "Wispher", pystray.Menu(
            pystray.MenuItem("Öffnen", self._show, default=True),
            pystray.MenuItem("Beenden", self.quit),
        ))
        self.tray.run_detached()
        threading.Thread(target=self._load_engine, daemon=True).start()
        self.root.after(100, self._poll)

    def _dark_titlebar(self):
        try:
            self.root.update()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)
        except Exception:
            pass  # ältere Windows-Version: heller Titelbalken

    def _build_ui(self):
        r = self.root
        head = tk.Frame(r, bg=BG)
        head.pack(fill="x", padx=20, pady=(22, 0))
        self.logo = ImageTk.PhotoImage(self.base_icon.resize((44, 44), Image.LANCZOS))
        tk.Label(head, image=self.logo, bg=BG).pack(side="left")
        col = tk.Frame(head, bg=BG)
        col.pack(side="left", padx=12)
        tk.Label(col, text="Wispher", bg=BG, fg=TEXT, font=(FONT, 17, "bold")).pack(anchor="w")
        self.status = tk.Canvas(col, width=300, height=18, bg=BG, highlightthickness=0)
        self.status.pack(anchor="w")
        self.dot = self.status.create_oval(1, 5, 11, 15, fill=MUTED, outline="")
        self.status_text = self.status.create_text(19, 10, anchor="w", fill=MUTED, font=(FONT, 10))

        tk.Label(r, text="LETZTER TEXT", bg=BG, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w", padx=22, pady=(24, 6))
        self.main = Card(r, 214, 22, lambda: self._copy(self.history[0] if self.history else ""))
        self.main.pack(padx=20)
        self.body = self.main.create_text(20, 20, anchor="nw", width=W - 40, fill=MUTED, font=(FONT, 12),
                                          text="Halte F12 und sprich – der Text erscheint hier.")
        self._chip_img = rounded(112, 32, 16, ACCENT)
        self.main.create_image(W - 20, 214 - 18, anchor="se", image=self._chip_img)
        self.chip = self.main.create_text(W - 20 - 56, 214 - 18 - 16, fill=ACCENT_TEXT, font=(FONT, 10, "bold"), text="Kopieren")

        tk.Label(r, text="VERLAUF", bg=BG, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w", padx=22, pady=(22, 6))
        self.list_frame = tk.Frame(r, bg=BG)
        self.list_frame.pack(fill="x", padx=20)
        self.status.itemconfig(self.status_text, text=STATES["loading"][0])
        self.status.itemconfig(self.dot, fill=STATES["loading"][1])

    def _set_state(self, state: str):
        text, color = STATES[state]
        self.status.itemconfig(self.status_text, text=text)
        self.status.itemconfig(self.dot, fill=color)
        self.tray.icon = self._tray_image(state)

    def _tray_image(self, state: str) -> Image.Image:
        img = self.base_icon.copy()
        ImageDraw.Draw(img).ellipse((600, 600, 940, 940), fill=STATES[state][1], outline=BG, width=40)
        return img

    def _copy(self, text: str):
        if not text:
            return
        pyperclip.copy(text)
        self.main.itemconfig(self.chip, text="Kopiert ✓")
        self.root.after(1500, lambda: self.main.itemconfig(self.chip, text="Kopieren"))

    def _add_text(self, text: str):
        self.history.insert(0, text)
        del self.history[HISTORY_MAX:]
        self.main.itemconfig(self.body, text=clip(text, 260), fill=TEXT)
        for w in self.list_frame.winfo_children():
            w.destroy()
        for t in self.history[1:]:
            row = Card(self.list_frame, 44, 14, lambda t=t: self._copy(t))
            row.create_text(16, 22, anchor="w", width=W - 32, fill=TEXT, font=(FONT, 10), text=clip(t, 58))
            row.pack(pady=3)

    # --- Engine (Thread) -> GUI (Tk-Thread) über Queue ---
    def _load_engine(self):
        self.events.put(("state", "loading"))
        try:
            server = HotkeyServer(Config())
        except Exception as e:
            log.exception("Engine-Start fehlgeschlagen")
            self.events.put(("fatal", str(e)))
            return
        server.on_state = lambda s: self.events.put(("state", s))
        server.on_text = lambda t: self.events.put(("text", t))
        server.start_hotkey()
        self.events.put(("state", "ready"))

    def _poll(self):
        while not self.events.empty():
            kind, val = self.events.get()
            if kind == "state":
                self._set_state(val)
            elif kind == "text":
                self._add_text(val)
            elif kind == "fatal":
                self.status.itemconfig(self.status_text, text=f"Fehler: {clip(val, 40)}")
        self.root.after(100, self._poll)

    def _show(self, *_):
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))

    def quit(self, *_):
        self.tray.stop()
        os._exit(0)  # beendet auch Engine-/Hotkey-Threads sofort

    def run(self):
        self.root.mainloop()


def single_instance_lock():
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 9902))
    except OSError:
        sys.exit(0)  # läuft schon
    return s


if __name__ == "__main__":
    _lock = single_instance_lock()
    App().run()
