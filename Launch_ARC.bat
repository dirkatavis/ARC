@echo off
setlocal

REM One-click launcher for ARC on Windows.
cd /d "%~dp0"

set "VENV_DIR=.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo [ARC] Creating Python virtual environment...
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3 -m venv "%VENV_DIR%"
    ) else (
        where python >nul 2>nul
        if %errorlevel%==0 (
            python -m venv "%VENV_DIR%"
        ) else (
            echo [ARC] Python 3 was not found on this computer.
            echo [ARC] Install Python 3.11+ and run this file again.
            pause
            exit /b 1
        )
    )
)

echo [ARC] Running setup checks...
"%VENV_PYTHON%" "project_arc\tools\bootstrap_arc.py" --launch
set "ARC_EXIT=%errorlevel%"

if not "%ARC_EXIT%"=="0" (
    echo [ARC] Setup failed with exit code %ARC_EXIT%.
    pause
)

exit /b %ARC_EXIT%
