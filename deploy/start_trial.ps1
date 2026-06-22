# ClawFans $0 trial launcher — backend + frontend (prod) + Cloudflare quick tunnel.
# Usage:  powershell -ExecutionPolicy Bypass -File deploy\start_trial.ps1
# Prereqs: ollama running w/ an abliterated model; `npm run build` done in frontend/;
#          cloudflared installed (winget install --id Cloudflare.cloudflared).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$py = Join-Path $backend "venv\Scripts\python.exe"

Write-Host "=== ClawFans trial launcher ===" -ForegroundColor Cyan

# Preflight: cloudflared present?
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
  Write-Host "cloudflared not found. Install it:  winget install --id Cloudflare.cloudflared" -ForegroundColor Red
  exit 1
}
# Preflight: frontend built?
if (-not (Test-Path (Join-Path $frontend ".next"))) {
  Write-Host "frontend/.next missing — run:  cd frontend; npm run build" -ForegroundColor Red
  exit 1
}

# 1. Backend (new window)
Write-Host "Starting backend on :8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "cd '$backend'; & '$py' -m uvicorn main:app --host 127.0.0.1 --port 8000"
)

# 2. Frontend production server (new window)
Write-Host "Starting frontend (prod) on :3000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "cd '$frontend'; npm start"
)

# Wait for the frontend to answer before opening the tunnel.
Write-Host "Waiting for frontend to come up ..." -ForegroundColor Green
for ($i = 0; $i -lt 40; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) { break }
  } catch { Start-Sleep -Seconds 1 }
}

# 3. Cloudflare quick tunnel (this window) — prints the public https URL.
Write-Host "Opening Cloudflare quick tunnel — share the https://*.trycloudflare.com URL below:" -ForegroundColor Cyan
cloudflared tunnel --url http://localhost:3000
