@echo off
title Sprint Health Agent - All Teams Report
color 0A

echo.
echo  ========================================
echo   Sprint Health Agent - All Teams
echo   %date% %time%
echo  ========================================
echo.

REM Change to SprintHealth directory
cd /d C:\Automation_MYB\postpaymentFulfilment\ancillaryfulfilment-baggage-service\SprintHealth

echo  Generating sprint health reports for all teams...
echo.

REM Run the analysis and export HTML for all teams
python -m src.main export-all

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
echo   Reports generated successfully!
echo   Check your browser for the combined report.
echo  ========================================
echo.
echo  Press any key to close...
pause > nul

