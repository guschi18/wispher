# PRD – Lokale Push-to-Talk Speech-to-Text App (Windows)

 

## 1. Ziel & Zweck

 

### Ziel

Entwicklung einer **lokalen Windows-Anwendung**, die es ermöglicht, **systemweit per Hotkey (F12)** Sprache aufzunehmen, **lokal zu transkribieren (Whisper)** und den Text **automatisch in das aktuell aktive Textfeld einzufügen**, unabhängig von der verwendeten Anwendung (z. B. Claude Code, Antigravity, Browser, IDEs).

 

### Zweck / Nutzen

- Zeitersparnis gegenüber Tippen

- Keine laufenden Kosten (keine Whisper API)

- Volle Datenhoheit (offline)

- Systemweit nutzbar, ohne App-spezifische Integration

 

---

 

## 2. Scope

 

### In Scope ✅

- Windows-only

- Push-to-Talk per **F12**

- Audioaufnahme über Standardmikrofon

- Lokale Speech-to-Text Transkription mit GPU (CUDA)

- Automatisches Einfügen des Textes ins aktive Fenster

- Deutsche Sprache als Default

- Hintergrunddienst ohne sichtbare UI

 

### Out of Scope ❌

- Cloud- oder API-basierte STT

- Verkauf oder Distribution

- Mobile Nutzung

- Multi-User-Betrieb

- Training oder Fine-Tuning von Modellen

- Permanentes Live-Streaming während der Aufnahme

 

---

 

## 3. Zielnutzer

 

### Primärer Nutzer

- Einzelperson (Developer / Power User)

- Arbeitet regelmäßig mit textbasierten Tools

- Typische Anwendungen:

  - Claude Code

  - Antigravity

  - VS Code / IDEs

  - Browser-Chats

  - E-Mail, Dokumente

 

---

 

## 4. User Journey (Happy Path)

 

1. Nutzer fokussiert ein beliebiges Textfeld

2. Nutzer hält **F12 gedrückt**

3. Audioaufnahme startet

4. Nutzer spricht

5. Nutzer lässt **F12 los**

6. Aufnahme stoppt

7. Whisper transkribiert Audio lokal

8. Text wird:

   - in die Zwischenablage kopiert

   - automatisch per **CTRL + V** eingefügt

9. Cursor verbleibt im aktiven Textfeld

 

---

 

## 5. Functional Requirements

 

### FR-1: Globaler Hotkey

- **F12** ist systemweit aktiv

- Funktioniert unabhängig vom Fokus der Anwendung

- Kein UI-Fokuswechsel

 

### FR-2: Push-to-Talk Steuerung

- Aufnahme startet bei **Key Down**

- Aufnahme endet bei **Key Up**

- Maximale Aufnahmezeit: **60 Sekunden** (Fail-Safe)

 

### FR-3: Audioaufnahme

- Mono

- Abtastrate: 16 kHz oder 44.1 kHz

- WAV-Format

- Nutzung des Windows-Default-Mikrofons

 

### FR-4: Speech-to-Text

- Lokale Transkription via **Whisper**

- GPU-Beschleunigung (CUDA)

- Konfigurierbares Modell (Default: `small` oder `medium`)

- Sprache: Deutsch (`language="de"`)

 

### FR-5: Text Injection

- Transkription wird in die Zwischenablage kopiert

- Automatische Ausführung von **CTRL + V**

- Funktioniert in beliebigen Anwendungen

 

### FR-6: Fehlerhandling

- Kein Audio → kein Einfügen

- STT-Fehler → kein Einfügen

- Optional: akustisches Feedback bei Fehlern (Beep)

 

---

 

## 6. Non-Functional Requirements

 

### Performance

- Transkription ≤ **2 Sekunden** für **10 Sekunden** Audio (GPU)

- Keine Blockierung des aktiven Fensters

 

### Zuverlässigkeit

- Hotkey darf nicht hängen bleiben

- Aufnahme muss deterministisch starten und stoppen

- Stabiler Dauerbetrieb ohne Memory-Leaks

 

### Sicherheit & Datenschutz

- **Keine Netzwerkverbindungen**

- **Keine permanente Speicherung** von Audio oder Text

- **Temporäre Dateien werden gelöscht** nach Verarbeitung

 

---

 

## 7. Technische Architektur

 

### Übersicht

 

[F12 Hotkey Listener]

↓

[Audio Recorder]

↓

[Whisper STT (GPU)]

↓

[Text Post-Processing]

↓

[Clipboard Manager]

↓

[CTRL + V Injection]

 

### Datenfluss (Detail)

1. **Hotkey-Event (F12 Down)** → Recorder startet Aufnahme.

2. **Hotkey-Event (F12 Up)** → Recorder stoppt, speichert temporäre WAV.

3. **STT** lädt/verwaltet Whisper-Modell (GPU initialisiert beim Start).

4. **Transkript** wird normalisiert (Trim, Whitespace, optional: Zeichensetzung).

5. **Clipboard** setzt Text → **Input Injection** sendet `CTRL+V`.

 

---

 

## 8. Technologie-Stack (empfohlen)

 

### Sprache / Runtime

- **Python 3.10+**

 

### Speech-to-Text

- **faster-whisper**

- CUDA (NVIDIA GPU)

 

### Audio

- `sounddevice`

- `numpy`

- `scipy`

 

### Hotkey / Input

- **AutoHotkey** (Windows) für robuste globale Hotkeys 

  _Alternative_: Python `keyboard` (erfordert Admin-Rechte; AHK bevorzugt)

 

### Clipboard & Input Injection

- `pyperclip`

- `keyboard` (oder AHK `Send ^v`)

 

---

 

## 9. Komponentenbeschreibung

 

### 9.1 Hotkey Listener

- Implementiert über **AutoHotkey**.

- Erkennt **Key Down** und **Key Up** von **F12**.

- Triggert Python-Logik (Start/Stop Aufnahme) über Prozessaufruf oder IPC.

 

### 9.2 Audio Recorder

- Startet/stopt Aufnahme basierend auf Hotkey.

- Schreibt temporäre **WAV**-Datei in `%TEMP%`.

- Max. Aufnahmedauer (Fail-Safe) = 60s.

 

### 9.3 STT Engine

- **Whisper-Modell** wird beim Start geladen (persistenter Prozess empfohlen).

- **GPU** wird einmalig initialisiert, um Latenz zu minimieren.

- Transkription in Deutsch, Modell `small`/`medium`.

 

### 9.4 Text Processor (optional)

- Entfernt führende/anhängende Leerzeichen.

- Normalisiert Mehrfach-Leerzeichen.

- (Optional) Entfernt Füllwörter / „ähm“.

 

### 9.5 Output Injector

- Kopiert Text in die Zwischenablage.

- Sendet **CTRL + V** an das aktive Fenster.

- Kein Fokusverlust; keine App-spezifische Integration nötig.

 

---

 

## 10. Konfiguration

 

```yaml

hotkey: F12

language: de

model: small

max_recording_seconds: 60

auto_paste: true

use_gpu: true

temp_dir: "%TEMP%\\stt"

beep_on_start: false

beep_on_end: false

```

11. MVP-Definition

Das MVP gilt als erfüllt, wenn:

 

✅ F12 startet und stoppt die Aufnahme

✅ Gesprochener Text wird korrekt transkribiert

✅ Text erscheint im aktuell fokussierten Textfeld

✅ Funktioniert in Browser, IDE und Chat-Tools

✅ Läuft vollständig offline (ohne Netzwerkzugriffe)

✅ Keine weitere Interaktion außer F12 erforderlich