"""
Wispher – Local Push-to-Talk STT Daemon
Listens on TCP localhost:9901 for START/STOP commands from AutoHotkey,
records audio, transcribes with faster-whisper, and injects text via Ctrl+V.
"""

import os
import sys
import time
import queue
import threading
import socket
import logging
import tempfile
import ctypes
from pathlib import Path

import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import pyperclip
import yaml
from faster_whisper import WhisperModel

# Als EXE (--noconsole) gibt es kein stdout -> Log in Datei neben der EXE/dem Skript
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout) if sys.stdout else logging.FileHandler(APP_DIR / "wispher.log", encoding="utf-8")
    ],
)
log = logging.getLogger("wispher")

# pip-installierte CUDA-DLLs (nvidia-*-cu12) liegen nicht im Suchpfad
try:
    import nvidia
    for _p in nvidia.__path__:
        for _bin in Path(_p).glob("*/bin"):
            os.add_dll_directory(str(_bin))
            os.environ["PATH"] = str(_bin) + os.pathsep + os.environ["PATH"]
except ImportError:
    pass


class Config:
    def __init__(self, path: str = "config.yaml"):
        config_path = Path(path)
        if not config_path.is_absolute():
            config_path = APP_DIR / path
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.language: str = data.get("language", "de")
        self.model: str = data.get("model", "small")
        self.max_recording_seconds: int = data.get("max_recording_seconds", 60)
        self.auto_paste: bool = data.get("auto_paste", True)
        self.use_gpu: bool = data.get("use_gpu", True)
        self.socket_host: str = str(data.get("socket_host", "127.0.0.1"))
        self.socket_port: int = int(data.get("socket_port", 9901))
        self.beep_on_start: bool = data.get("beep_on_start", False)
        self.beep_on_end: bool = data.get("beep_on_end", False)
        self.hotkey: str = str(data.get("hotkey", "F12"))
        self.initial_prompt: str | None = data.get("initial_prompt") or None

        raw_temp = data.get("temp_dir", "%TEMP%\\stt")
        self.temp_dir: Path = Path(os.path.expandvars(raw_temp))
        self.temp_dir.mkdir(parents=True, exist_ok=True)


class STTEngine:
    def __init__(self, config: Config):
        device = "cuda" if config.use_gpu else "cpu"
        compute = "float16" if config.use_gpu else "int8"
        log.info("Loading Whisper model '%s' on %s …", config.model, device)
        try:
            self.model = WhisperModel(config.model, device=device, compute_type=compute)
            # Verify GPU works with a tiny encode to catch missing DLL errors early
            if device == "cuda":
                list(self.model.transcribe(np.zeros(16000, dtype=np.float32))[0])
        except Exception as e:
            log.warning("GPU init failed (%s), falling back to CPU.", e)
            self.model = WhisperModel(config.model, device="cpu", compute_type="int8")
        self.language = config.language
        self.initial_prompt = config.initial_prompt
        log.info("Whisper model ready.")

    def transcribe(self, wav_path: Path) -> str:
        segments, _ = self.model.transcribe(
            str(wav_path),
            language=self.language,
            beam_size=5,
            vad_filter=True,
            initial_prompt=self.initial_prompt,
            condition_on_previous_text=False,
        )
        return " ".join(seg.text for seg in segments)


class AudioRecorder:
    SAMPLE_RATE = 16000

    def __init__(self, config: Config):
        self.temp_dir = config.temp_dir
        self.max_seconds = config.max_recording_seconds
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._lock = threading.Lock()

    # Mindestdauer in Sekunden – Aufnahmen kürzer als dieser Wert werden verworfen
    MIN_DURATION_S = 0.4

    def start(self):
        with self._lock:
            if self._recording:
                return
            self._frames = []
            self._recording = True
            self._start_time = time.monotonic()
            log.info("Recording started.")

        def callback(indata, frames, time_info, status):
            if status:
                log.warning("Audio status: %s", status)
            with self._lock:
                if self._recording:
                    self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()
        # Kurzes Warten damit sounddevice den Stream stabil initialisiert
        time.sleep(0.05)

    def stop(self) -> Path | None:
        with self._lock:
            if not self._recording:
                return None
            self._recording = False
            duration = time.monotonic() - self._start_time

        self._stream.stop()
        self._stream.close()
        log.info("Recording stopped. %d chunks captured.", len(self._frames))

        if duration < self.MIN_DURATION_S:
            log.warning(
                "Aufnahme zu kurz (%.0f ms < %.0f ms Minimum), wird verworfen.",
                duration * 1000,
                self.MIN_DURATION_S * 1000,
            )
            return None

        if not self._frames:
            return None

        audio = np.concatenate(self._frames, axis=0).flatten()
        # Convert float32 → int16
        audio_int16 = (audio * 32767).astype(np.int16)

        out_path = self.temp_dir / f"rec_{int(time.time())}.wav"
        wav.write(str(out_path), self.SAMPLE_RATE, audio_int16)
        log.info("WAV written: %s", out_path)
        return out_path


class TextProcessor:
    @staticmethod
    def clean(text: str) -> str:
        import re
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text


class TextInjector:
    @staticmethod
    def inject(text: str):
        pyperclip.copy(text)
        time.sleep(0.05)  # small settle time
        u32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002
        VK_CONTROL = 0x11
        VK_V = 0x56
        u32.keybd_event(VK_CONTROL, 0, 0, 0)
        u32.keybd_event(VK_V, 0, 0, 0)
        u32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        u32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        log.info("Text injected (%d chars).", len(text))


class HotkeyServer:
    def __init__(self, config: Config):
        self.config = config
        self.recorder = AudioRecorder(config)
        self.stt = STTEngine(config)
        # Hooks für die GUI: on_state("recording"|"transcribing"|"ready"), on_text(text)
        self.on_state = lambda state: None
        self.on_text = lambda text: None
        self._fail_safe_timer: threading.Timer | None = None
        # Alle START/STOP-Befehle laufen serialisiert über diese Queue
        self._cmd_queue: queue.Queue[str] = queue.Queue()
        self._worker = threading.Thread(target=self._command_loop, daemon=True)
        self._worker.start()

    def _command_loop(self):
        """Verarbeitet START/STOP sequenziell – keine Race Conditions möglich."""
        while True:
            cmd = self._cmd_queue.get()
            try:
                if cmd == "START":
                    self._process_start()
                elif cmd == "STOP":
                    self._process_stop()
            except Exception as e:
                log.error("Fehler beim Verarbeiten von %r: %s", cmd, e)

    def _fail_safe(self):
        log.warning("Fail-safe triggered: stopping recording after %ds.", self.config.max_recording_seconds)
        self._cmd_queue.put("STOP")

    def _process_start(self):
        if self.config.beep_on_start:
            ctypes.windll.kernel32.Beep(880, 120)
        if self._fail_safe_timer:
            self._fail_safe_timer.cancel()
        self.recorder.start()
        self.on_state("recording")
        self._fail_safe_timer = threading.Timer(
            self.config.max_recording_seconds, self._fail_safe
        )
        self._fail_safe_timer.daemon = True
        self._fail_safe_timer.start()

    def _process_stop(self):
        if self._fail_safe_timer:
            self._fail_safe_timer.cancel()
            self._fail_safe_timer = None

        wav_path = self.recorder.stop()
        if wav_path is None:
            log.info("No audio captured, skipping transcription.")
            self.on_state("ready")
            return

        self.on_state("transcribing")
        try:
            text = self.stt.transcribe(wav_path)
            text = TextProcessor.clean(text)
            if not text:
                log.info("Empty transcription, nothing to inject.")
                return
            log.info("Transcribed: %r", text)
            self.on_text(text)
            if self.config.auto_paste:
                TextInjector.inject(text)
        finally:
            self.on_state("ready")
            try:
                wav_path.unlink()
            except OSError:
                pass

        if self.config.beep_on_end:
            ctypes.windll.kernel32.Beep(660, 120)

    def _handle_client(self, conn: socket.socket, addr):
        try:
            data = b""
            while True:
                chunk = conn.recv(64)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
            command = data.decode("utf-8").strip().upper()
            log.debug("Received command: %r from %s", command, addr)
            if command in ("START", "STOP"):
                self._cmd_queue.put(command)
            else:
                log.warning("Unknown command: %r", command)
        except Exception as e:
            log.error("Error handling client %s: %s", addr, e)
        finally:
            conn.close()

    def start_hotkey(self):
        """F12 halten = aufnehmen, loslassen = transkribieren (ersetzt wispher.ahk)."""
        import keyboard
        held = False

        def down(_):
            nonlocal held
            if not held:  # Auto-Repeat beim Halten ignorieren
                held = True
                self._cmd_queue.put("START")

        def up(_):
            nonlocal held
            held = False
            self._cmd_queue.put("STOP")

        keyboard.on_press_key(self.config.hotkey, down, suppress=True)
        keyboard.on_release_key(self.config.hotkey, up, suppress=True)

    def run(self):
        host = self.config.socket_host
        port = self.config.socket_port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((host, port))
            srv.listen(5)
            log.info("Wispher daemon listening on %s:%d – press F12 to record.", host, port)
            while True:
                try:
                    conn, addr = srv.accept()
                    threading.Thread(
                        target=self._handle_client, args=(conn, addr), daemon=True
                    ).start()
                except KeyboardInterrupt:
                    log.info("Shutting down.")
                    break


def main():
    config = Config()
    server = HotkeyServer(config)
    server.run()


if __name__ == "__main__":
    main()
