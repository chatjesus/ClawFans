@echo off
echo ========================================
echo   SynClub Local - Frontend (Next.js)
echo ========================================
echo.

cd /d "%~dp0frontend"

echo Starting Next.js dev server on http://localhost:3000 ...
echo.
npm run dev

pause

