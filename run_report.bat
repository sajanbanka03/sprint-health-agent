@echo off
title Sprint Health Agent
color 0A

echo.
echo  ========================================
echo   Sprint Health Agent
echo   %date% %time%
echo  ========================================
echo.

REM Change to script directory
cd /d "%~dp0"

echo  Generating sprint health report...
echo.

REM Run the analysis and export HTML
python -m src.main export-html

if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo  ========================================
    echo   ERROR: Report generation failed!
    echo
    echo   Make sure you have:
    echo   1. Installed dependencies: pip install -r requirements.txt
    echo   2. Configured config/config.json
    echo  ========================================
    echo.
    pause
    exit /b 1
)

echo.
echo  ========================================
echo   Report generated successfully!
echo   Check your browser for the report.
echo  ========================================
echo.
echo  Press any key to close...
pause > nul

