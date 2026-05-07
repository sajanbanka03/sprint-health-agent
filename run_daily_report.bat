@echo off
title Sprint Health Agent - Daily Report
color 0A

echo.
echo  ========================================
echo   Sprint Health Agent - Daily Report
echo   %date% %time%
echo  ========================================
echo.

REM Change to SprintHealth directory
cd /d C:\Automation_MYB\postpaymentFulfilment\ancillaryfulfilment-baggage-service\SprintHealth

echo  Generating sprint health report...
echo.

REM Run the analysis and export HTML
python -m src.main export-html

if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo  ========================================
    echo   ERROR: Report generation failed!
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

