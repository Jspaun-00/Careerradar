@echo off
:: Career Radar v4.0 - Windows Desktop Launcher
title Career Radar v4.0
cd /d "%~dp0"

echo ==================================================
echo Starting Career Radar v4.0 (Enterprise Radar)...
echo ==================================================

netstat -ano | find "8050" | find "LISTENING" >nul
if %errorlevel% equ 0 (
    echo Career Radar server is already running on http://127.0.0.1:8050
) else (
    echo Launching Career Radar server in background...
    if exist .venv\Scripts\python.exe (
        start /b "" .venv\Scripts\python.exe app.py
    ) else (
        start /b "" python app.py
    )
    timeout /t 2 /nobreak >nul
)

echo Opening Dashboard in default browser...
start http://127.0.0.1:8050

echo Ready! Dashboard running at http://127.0.0.1:8050

