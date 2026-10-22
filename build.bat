@echo off
rem Baut dist\Wispher\Wispher.exe (ohne Terminal). config.yaml landet neben der EXE.
cd /d "%~dp0"
python -m PyInstaller --noconfirm --noconsole --onedir --name Wispher --icon assets\icon.ico ^
  --add-data "assets;assets" --collect-all faster_whisper --collect-all ctranslate2 --collect-binaries nvidia ^
  wispher_app.py
copy /y config.yaml dist\Wispher\config.yaml
