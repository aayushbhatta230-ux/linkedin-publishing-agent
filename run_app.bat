@echo off
cd /d "%~dp0"
title Local LinkedIn Publishing Agent
echo ==========================================================
echo   Starting Local LinkedIn Publishing Agent (100%% Local)
echo ==========================================================

if not exist ".venv" (
    echo [*] Creating virtual environment...
    python -m venv .venv
    echo [*] Installing dependencies...
    call .\.venv\Scripts\pip install -r requirements.txt
)

echo [*] Launching Streamlit interface on http://localhost:8501...
call .\.venv\Scripts\streamlit run app.py
pause
