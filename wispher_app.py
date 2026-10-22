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
from PIL import Image, ImageDraw, ImageFont, ImageTk

import wispher
from wispher import APP_DIR, Config, HotkeyServer, log

RES = Path(getattr(sys, "_MEIPASS", APP_DIR))  # gebündelte Dateien (assets/)
BG, CARD, CARD_HOVER = "#1b1511", "#2a2019", "#37291f"
TEXT, MUTED, ACCENT, ACCENT_HOVER, ACCENT_TEXT = "#f6ece1", "#a3917f", "#ff8a4c", "#ffa070", "#2a1608"
BORDER = "#43301f"
W = 392  # Kartenbreite
BTN_W, BTN_H = 150, 46  # runder Kopieren-Button
STATES = {  # state -> (Statustext, Punktfarbe)
    "loading": ("Modell lädt …", "#8a7b6e"),
    "ready": ("Bereit – F12 halten zum Sprechen", "#8fd694"),
    "recording": ("Nimmt auf …", "#ff5a4d"),
    "transcribing": ("Transkribiere …", "#ffc24d"),
}


def rounded(w, h, r, fill, outline=None):
    """Anti-aliased Rundrechteck (4x supersampled) als Tk-Bild."""
    k = 4
    im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * k - 1, h * k - 1), r * k, fill=fill, outline=outline, width=k)
    return ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS))


FONT_FILES = {  # Geist (OFL) + Instrument Serif liegen in assets/fonts; sonst Segoe UI als Fallback
    "regular": "Geist-Regular.ttf", "medium": "Geist-Medium.ttf", "semibold": "Geist-SemiBold.ttf",
    "serif": "InstrumentSerif-Regular.ttf",
}
_fonts: dict = {}
K = 1  # 1 = native FreeType-Hinting (schärfer als Supersampling)


def font(kind: str, px: int) -> ImageFont.FreeTypeFont:
    if (kind, px) not in _fonts:
        for path in (RES / "assets" / "fonts" / FONT_FILES[kind], Path("C:/Windows/Fonts/SegUIVar.ttf")):
            try:
                _fonts[kind, px] = ImageFont.truetype(str(path), px)
                break
            except OSError:
                continue
        else:
            _fonts[kind, px] = ImageFont.load_default(px)
    return _fonts[kind, px]


def render_text(text, kind, size, color, width=None, max_lines=None) -> ImageTk.PhotoImage:
    """Text mit Pillow in 4-facher Auflösung zeichnen und glatt herunterskalieren (statt Tk-Text)."""
    f = font(kind, size * K)
    lines, limit = [], (width or 10**6) * K
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            test = f"{cur} {word}".strip()
            if cur and f.getlength(test) > limit:
                lines.append(cur)
                cur = word
            else:
                cur = test
        lines.append(cur)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and f.getlength(lines[-1] + "…") > limit:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip() + "…"
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * 1.3)
    w = int(max(f.getlength(l) for l in lines)) + 2 * K
    im = Image.new("RGBA", (w, lh * len(lines) + 2 * K), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for n, line in enumerate(lines):
        d.text((K, K + n * lh), line, font=f, fill=color)
    return ImageTk.PhotoImage(im.resize((im.width // K, im.height // K), Image.LANCZOS))


class Surface(tk.Canvas):
    """Canvas mit scharfem Pillow-Text; add_text/set_text statt create_text."""

    def __init__(self, parent, w, h, **kw):
        super().__init__(parent, width=w, height=h, bg=BG, highlightthickness=0, **kw)
        self._t: dict = {}

    def add_text(self, x, y, text, kind, size, color, width=None, max_lines=None, anchor="nw") -> int:
        item = self.create_image(x, y, anchor=anchor)
        self._t[item] = dict(kind=kind, size=size, color=color, width=width, max_lines=max_lines)
        self.set_text(item, text)
        return item

    def set_text(self, item, text, color=None):
        p = self._t[item]
        p["color"] = color or p["color"]
        p["img"] = render_text(text, p["kind"], p["size"], p["color"], p["width"], p["max_lines"])
        self.itemconfig(item, image=p["img"])


class Card(Surface):
    """Karte mit runden Ecken und dünnem Rand, Höhe per fit() variabel."""

    def __init__(self, parent, h, r):
        super().__init__(parent, W, h)
        self.r = r
        self._bg = self.create_image(0, 0, anchor="nw")
        self.tag_lower(self._bg)
        self.fit(h)

    def fit(self, h):
        """Kartenhöhe an den Inhalt anpassen."""
        self.config(height=h)
        self._img = rounded(W, h, self.r, CARD, BORDER)
        self.itemconfig(self._bg, image=self._img)


def label(parent, text, kind, size, color, w=W, h=None) -> Surface:
    s = Surface(parent, w, h or int(size * 1.5))
    s.add_text(0, 0, text, kind, size, color)
    return s


class App:
    def __init__(self):
        self.events: queue.Queue = queue.Queue()
        self.history: list[str] = []
        self.base_icon = Image.open(RES / "assets" / "icon.png").convert("RGBA")

        self.root = tk.Tk()
        self.root.title("Wispher")
        self.root.configure(bg=BG)
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
        label(col, "Wispher", "serif", 34, TEXT, 300, 44).pack(anchor="w")
        self.status = Surface(col, 300, 20)
        self.status.pack(anchor="w")
        self.dot = self.status.create_image(1, 5, anchor="nw")
        self.status_text = self.status.add_text(18, 1, "", "regular", 13, MUTED)

        label(r, "LETZTER TEXT", "semibold", 11, MUTED).pack(anchor="w", padx=22, pady=(24, 8))
        self.main = Card(r, 160, 30)
        self.main.pack(padx=20, pady=(0, 22))
        self.body = self.main.add_text(24, 22, "", "regular", 16, MUTED, width=W - 48, max_lines=8)
        self._btn_img, self._btn_hover = rounded(BTN_W, BTN_H, BTN_H // 2, ACCENT), rounded(BTN_W, BTN_H, BTN_H // 2, ACCENT_HOVER)
        self.btn = self.main.create_image(W // 2, 0, anchor="n", image=self._btn_img)
        self.chip = self.main.add_text(W // 2, 0, "Kopieren", "semibold", 15, ACCENT_TEXT, anchor="center")
        for item in (self.btn, self.chip):
            self.main.tag_bind(item, "<Button-1>", lambda _e: self._copy(self.history[0] if self.history else ""))
            self.main.tag_bind(item, "<Enter>", lambda _e: (self.main.itemconfig(self.btn, image=self._btn_hover), self.main.config(cursor="hand2")))
            self.main.tag_bind(item, "<Leave>", lambda _e: (self.main.itemconfig(self.btn, image=self._btn_img), self.main.config(cursor="")))
        self._show_text("Halte F12 und sprich – der Text erscheint hier.", MUTED)
        self._set_status("loading")

    def _set_status(self, state: str):
        text, color = STATES[state]
        self.status.set_text(self.status_text, text)
        self._dot_img = rounded(10, 10, 5, color)
        self.status.itemconfig(self.dot, image=self._dot_img)

    def _set_state(self, state: str):
        self._set_status(state)
        self.tray.icon = self._tray_image(state)

    def _tray_image(self, state: str) -> Image.Image:
        img = self.base_icon.copy()
        ImageDraw.Draw(img).ellipse((600, 600, 940, 940), fill=STATES[state][1], outline=BG, width=40)
        return img

    def _copy(self, text: str):
        if not text:
            return
        pyperclip.copy(text)
        self.main.set_text(self.chip, "Kopiert")
        self.root.after(1500, lambda: self.main.set_text(self.chip, "Kopieren"))

    def _show_text(self, text: str, color=TEXT):
        """Text setzen; Karte wächst mit, Button sitzt immer mittig unter dem Text."""
        self.main.set_text(self.body, text, color)
        th = self.main._t[self.body]["img"].height()
        y = 22 + th + 20
        self.main.fit(y + BTN_H + 24)
        self.main.coords(self.btn, W // 2, y)
        self.main.coords(self.chip, W // 2, y + BTN_H // 2)

    def _add_text(self, text: str):
        self.history = [text]
        self._show_text(text)

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
                self.status.set_text(self.status_text, f"Fehler: {val[:40]}")
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
