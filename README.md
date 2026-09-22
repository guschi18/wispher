# Wispher — Local Push-to-Talk Speech-to-Text

**F12 halten → sprechen → loslassen → der Text steht im aktiven Feld.**
100 % lokal. Keine Cloud. Kein API-Key. Kein Mikrofon-Bit, das dein Büro verlässt.

Wispher ist ein Windows-Daemon für Push-to-Talk-Diktat: faster-whisper läuft
lokal (CUDA oder CPU), aufgenommene Audio-Rohdaten landen nur temporär im
`%TEMP%` und werden nach der Transkription gelöscht — die Sprache verlässt
den Rechner zu keinem Zeitpunkt.

```
 F12 (AutoHotkey)          Wispher-Daemon (Python)              Ziel-App
┌────────────────┐   TCP localhost:9901   ┌──────────────────────┐
│ START senden   │ ─────────────────────▶ │ AudioRecorder        │
│                │                        │   ↓ WAV (nur %TEMP%) │
│                │                        │ STTEngine            │
│                │                        │   (faster-whisper,   │
│                │                        │    CUDA/CPU-Fallback)│
│ STOP senden    │ ─────────────────────▶ │ TextProcessor        │
│                │                        │   ↓                  │
│ ◀ ── Ctrl+V ─────────────────────────── │ TextInjector         │
└────────────────┘                        └──────────────────────┘
```

## Warum AutoHotkey + TCP-Daemon?

Eine bewusste Design-Entscheidung, dokumentiert in der [PRD](PRD.md):

- **AutoHotkey** ist auf Windows der zuverlässigste Weg für einen globalen
  Hotkey, der in *jedem* fokussierten Fenster feuert — Python-Hotkey-Libraries
  kämpfen hier mit Fokus- und Elevated-Window-Problemen.
- **Der Python-Daemon** enthält die ganze Logik (Aufnahme, Transkription,
  Injektion) und lauscht auf `127.0.0.1:9901`. AHK und Python sind über eine
  winzige TCP-Nachricht entkoppelt — jede Seite kann separat neu gestartet
  werden.
- **Text-Injektion via Ctrl+V**: Tastatur-Emulation ist fragil, die
  Zwischenablage zu überschreiben radikal. Wispher sichert den alten
  Zwischenablage-Inhalt, fügt ein und stellt ihn wieder her.

## Installation

**Voraussetzungen:**

- Python 3.10+
- [AutoHotkey v1](https://www.autohotkey.com/) (für den globalen Hotkey)
- Optional NVIDIA-GPU + CUDA/cuDNN für faster-whisper — ohne GPU fällt der
  Daemon automatisch auf CPU zurück (`use_gpu` in der `config.yaml`)

**Setup:**

```bash
pip install -r requirements.txt
python wispher.py        # Daemon starten
start.bat                # oder: startet Daemon + AHK-Hotkey
```

**Benutzung:** F12 gedrückt halten, sprechen, loslassen. Der transkribierte
Text erscheint im aktiven Textfeld — Browser, IDE, Chat, egal wo.

## Konfiguration (`config.yaml`)

| Schlüssel | Vorgabe | Bedeutung |
|---|---|---|
| `language` | `de` | Whisper-Sprache |
| `model` | `small` | faster-whisper-Modellgröße (`tiny` … `large-v3`) |
| `use_gpu` | `false` | CUDA nutzen, wenn verfügbar |
| `max_recording_seconds` | `60` | Fail-Safe gegen vergessene F12-Taste |
| `auto_paste` | `true` | Text per Ctrl+V einfügen (sonst nur Zwischenablage) |
| `socket_host` / `socket_port` | `127.0.0.1` / `9901` | IPC-Endpoint (Loopback, absichtlich) |
| `beep_on_start` / `beep_on_end` | `false` | Audio-Feedback bei Aufnahmebeginn/-ende |

Der Daemon bindet sich bewusst nur an Loopback — der Steuerkanal ist von
außen nicht erreichbar.

## Datenschutz

- Audio wird ausschließlich als temporäre WAV-Datei in `%TEMP%\stt`
  geschrieben und im `finally`-Block gelöscht — auch bei Fehlern.
- Transkription läuft vollständig offline über faster-whisper.
- Keine Telemetrie, keine Updates, keine Netzwerkverbindung.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
