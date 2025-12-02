@echo off
REM Desurvey GUI Launcher
REM Double-click this file to launch the desurvey GUI

REM Change to the directory where this script is located
cd /d "%~dp0"

echo.
echo ========================================
echo   Drill Hole Desurvey Tool
echo ========================================
echo.
echo Current directory: %CD%
echo.
echo Activating environment...

call "%~dp0venv_desurvey\Scripts\activate.bat"

if errorlevel 1 (
    echo.
    echo ERROR: Could not activate virtual environment
    echo Please run setup first: python -m venv venv_desurvey
    echo Then install dependencies: pip install -r requirements_standalone.txt
    pause
    exit /b 1
)

echo Environment activated
echo.
echo Launching GUI...
echo.

"%~dp0venv_desurvey\Scripts\python.exe" "%~dp0desurvey_gui.py"

if errorlevel 1 (
    echo.
    echo ERROR: Failed to launch GUI
    echo.
    pause
    exit /b 1
)

echo.
echo GUI closed.
pause
