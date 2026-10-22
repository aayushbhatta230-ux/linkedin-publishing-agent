@echo off
title aayushifty's LinkedIn Agent
cd /d "%~dp0"

:: Check if server is already running on port 8501
netstat -ano | findstr :8501 | findstr LISTENING >nul
if %errorlevel% neq 0 (
    echo [*] Starting aayushifty's LinkedIn Agent server...
    start /b "" ".\.venv\Scripts\pythonw.exe" -m streamlit run app.py --server.port 8501 --server.headless true
    timeout /t 2 /nobreak >nul
)

:: Launch as a Standalone Native App Window via Chrome or Edge
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://localhost:8501
) else if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app=http://localhost:8501
) else (
    start http://localhost:8501
)
