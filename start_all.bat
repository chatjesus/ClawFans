@echo off
echo ========================================
echo   ClawFans - Starting All Services
echo ========================================
echo.

:: Check if Ollama is running
echo [1/3] Checking Ollama...
ollama list >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama service...
    start "" ollama serve
    timeout /t 3 >nul
) else (
    echo Ollama is already running.
)

:: Check if model is available
echo.
echo [2/3] Checking model...
ollama list | findstr "qwen2.5" >nul 2>&1
if errorlevel 1 (
    echo Model not found. Pulling qwen2.5:14b...
    start "Ollama Pull" cmd /c "ollama pull qwen2.5:14b"
) else (
    echo Model is ready!
)

:: Start backend
echo.
echo [3/3] Starting servers...
start "ClawFans Backend" cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 >nul

:: Start frontend
start "ClawFans Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo   ClawFans is starting!
echo   App:      http://localhost:3000
echo   API:      http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo ========================================
echo.
echo Press any key to exit this window...
pause >nul
