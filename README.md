<p align="center"><img src="assets/banner.svg" alt="Wispher — F12 halten, sprechen, loslassen" width="900"></p>

<p align="center">
<img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows&logoColor=white" alt="Windows 10 | 11">
<img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
<img src="https://img.shields.io/badge/faster--whisper-large--v3-ff8a4c" alt="faster-whisper large-v3">
<img src="https://img.shields.io/badge/100%25-offline-8fd694" alt="100 % offline">
<img src="https://img.shields.io/badge/Telemetrie-keine-8fd694" alt="Keine Telemetrie">
<a href="LICENSE"><img src="https://img.shields.io/badge/Lizenz-MIT-lightgrey" alt="MIT-Lizenz"></a>
</p>

<p align="center">
<a href="#schnellstart">Schnellstart</a> ·
<a href="#warum-wispher">Warum Wispher?</a> ·
<a href="#konfiguration-configyaml">Konfiguration</a> ·
<a href="#datenschutz">Datenschutz</a> ·
<a href="#fehlersuche">Fehlersuche</a>
</p>

# Wispher — Local Push-to-Talk Speech-to-Text

**F12 halten → sprechen → loslassen → der Text steht im aktiven Feld.**
100 % lokal. Keine Cloud. Kein API-Key. Kein Mikrofon-Bit, das dein Büro verlässt.

Wispher ist ein Windows-Tool für Push-to-Talk-Diktat: faster-whisper läuft
lokal (CUDA oder CPU), aufgenommene Audio-Rohdaten landen nur temporär im
`%TEMP%` und werden nach der Transkription gelöscht — die Sprache verlässt
den Rechner zu keinem Zeitpunkt.

<p align="center"><img src="assets/demo.svg" alt="Animation: F12 halten, sprechen, loslassen, der Text erscheint im Feld" width="900"></p>

<p align="center"><img src="assets/screenshot.png" alt="Wispher-Fenster" width="320"></p>

Wispher ist eine Windows-App mit Tray-Icon und kleinem Fenster. Das Fenster
zeigt den letzten Text — ein Klick auf **Kopieren** legt ihn in die
Zwischenablage, falls er nicht im Zielfeld gelandet ist.

```
 F12 (keyboard-Paket)        Wispher.exe (Python)                 Ziel-App
┌────────────────┐        ┌──────────────────────┐
│ halten = START │ ─────▶ │ AudioRecorder        │
│                │        │   ↓ WAV (nur %TEMP%) │
│                │        │ STTEngine            │
│                │        │   (faster-whisper,   │
│ loslassen=STOP │ ─────▶ │    CUDA/CPU-Fallback)│
│                │        │ TextProcessor        │
│                │        │   ↓                  │
│                │        │ TextInjector ── Ctrl+V ──▶  aktives Feld
└────────────────┘        └──────────────────────┘
                           Tray-Icon + Fenster (Kopieren-Button)
```

## Installation

**Voraussetzungen:** Python 3.10+, optional NVIDIA-GPU + CUDA (ohne GPU fällt
Wispher automatisch auf CPU zurück, `use_gpu` in der `config.yaml`).

```bash
pip install -r requirements.txt
python wispher_app.py    # aus dem Quellcode starten
build.bat                # baut dist\Wispher\Wispher.exe (ca. 3 GB mit CUDA-Libs)
```

Die EXE braucht den Ordner `_internal` und `config.yaml` daneben.
`make_icon.py` erzeugt das Icon in `assets/`.

**Benutzung:** `Wispher.exe` starten, F12 halten, sprechen, loslassen. Beenden
über das Tray-Icon (Rechtsklick → Beenden). Logs: `wispher.log` neben der EXE.

## Konfiguration (`config.yaml`)

| Schlüssel | Vorgabe | Bedeutung |
|---|---|---|
| `language` | `de` | Whisper-Sprache |
| `hotkey` | `F12` | Push-to-Talk-Taste |
| `initial_prompt` | – | Hilft bei Fachbegriffen und englischen Wörtern im Satz |
| `model` | `large-v3` | faster-whisper-Modellgröße (`tiny` … `large-v3`) |
| `use_gpu` | `true` | CUDA nutzen, wenn verfügbar |
| `max_recording_seconds` | `60` | Fail-Safe gegen vergessene F12-Taste |
| `auto_paste` | `true` | Text per Ctrl+V einfügen (sonst nur Zwischenablage) |
| `beep_on_start` / `beep_on_end` | `false` | Audio-Feedback bei Aufnahmebeginn/-ende |

## Datenschutz

- Audio wird ausschließlich als temporäre WAV-Datei in `%TEMP%\stt`
  geschrieben und im `finally`-Block gelöscht — auch bei Fehlern.
- Transkription läuft vollständig offline über faster-whisper.
- Keine Telemetrie. Nur beim ersten Start lädt faster-whisper das Modell von Hugging Face herunter. Audio und Text verlassen den Rechner nie.

## Schriften

[Geist](https://github.com/vercel/geist-font) (Vercel) und [Instrument Serif](https://fonts.google.com/specimen/Instrument+Serif) (Google Fonts), beide unter der SIL Open Font License. Die Schriftdateien liegen in `assets/fonts/` und sind in die EXE gebündelt. Lizenztext: `assets/fonts/OFL-Geist.txt`.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
