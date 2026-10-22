# Windows PowerShell Startup Script for Local LinkedIn Publishing Agent
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting Local LinkedIn Publishing Agent (100% Local)   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check Python Virtual Environment
if (-not (Test-Path "$ScriptDir\.venv")) {
    Write-Host "[*] Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "[*] Installing dependencies..." -ForegroundColor Yellow
    .\.venv\Scripts\pip install -r requirements.txt
}

# Check Ollama service
try {
    $ollamaCheck = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 2 -ErrorAction Stop
    Write-Host "[+] Local Ollama service is ONLINE." -ForegroundColor Green
} catch {
    Write-Host "[!] Note: Ollama is offline. App will use deterministic local templates." -ForegroundColor Yellow
    Write-Host "    To enable local LLMs, start Ollama: 'ollama serve'" -ForegroundColor Gray
}

Write-Host "`n[*] Launching Streamlit web application on http://localhost:8501..." -ForegroundColor Green
.\.venv\Scripts\streamlit run app.py
