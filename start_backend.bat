@echo off
echo ========================================
echo   SynClub Local - Backend Server
echo ========================================
echo.

cd /d "%~dp0backend"

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Start FastAPI server
echo Starting FastAPI server on http://localhost:8000 ...
echo.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause

