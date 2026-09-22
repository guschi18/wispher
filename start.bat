@echo off
setlocal

:: ── Wispher Launcher ────────────────────────────────────────────────────────
:: Starts the AutoHotkey hotkey handler and the Python STT daemon.

set "SCRIPT_DIR=%~dp0"

:: Find AutoHotkey (try common install paths)
set "AHK_EXE="
if exist "C:\Program Files\AutoHotkey\AutoHotkey.exe" (
    set "AHK_EXE=C:\Program Files\AutoHotkey\AutoHotkey.exe"
) else if exist "C:\Program Files\AutoHotkey\v1\AutoHotkey.exe" (
    set "AHK_EXE=C:\Program Files\AutoHotkey\v1\AutoHotkey.exe"
) else if exist "C:\Program Files (x86)\AutoHotkey\AutoHotkey.exe" (
    set "AHK_EXE=C:\Program Files (x86)\AutoHotkey\AutoHotkey.exe"
)

if "%AHK_EXE%"=="" (
    echo [ERROR] AutoHotkey not found. Please install AutoHotkey v1 from https://www.autohotkey.com/
    pause
    exit /b 1
)

echo [Wispher] Starting AutoHotkey hotkey handler...
start /min "" "%AHK_EXE%" "%SCRIPT_DIR%wispher.ahk"

echo [Wispher] Starting Python STT daemon...
echo [Wispher] Press Ctrl+C in this window to stop.
echo.
python "%SCRIPT_DIR%wispher.py"

endlocal
