@echo off
chcp 65001 >nul
title Range Intelligence -- Unified Local Runner
cls
echo ==========================================================================
echo       RANGE INTELLIGENCE -- UNIFIED LOCAL DEVELOPMENT RUNNER
echo ==========================================================================
echo Starting FastAPI Backend (Port 8000) and Vite Frontend (Port 3000)...
echo Press Ctrl+C in this terminal to stop both servers cleanly.
echo.

:: 1. Detect Python executable (py -3.11 -> py -> python)
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py -3.11 -c "import sys" >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PY_CMD=py -3.11"
    ) else (
        set "PY_CMD=py"
    )
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PY_CMD=python"
    ) else (
        echo [ERROR] Python not found on PATH. Please install Python 3.10+ and add to PATH.
        pause
        exit /b 1
    )
)

%PY_CMD% run_local.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [RUNNER] Process terminated. Press any key to exit.
    pause >nul
)
