@echo off
REM Restructure backend to use app folder

cd /d "%~dp0"

echo Creating directories...
mkdir app\config 2>nul
mkdir app\scanner 2>nul
mkdir app\fetcher 2>nul
mkdir app\orchestrator 2>nul
mkdir app\api 2>nul
mkdir tests 2>nul

echo.
echo Running Python restructuring script...
python restructure.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Backend restructuring complete!
    echo Next: python -m uvicorn app.main:app --reload
) else (
    echo.
    echo FAILED: Python script returned error
)

pause
