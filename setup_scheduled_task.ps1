# Sprint Health Agent - Setup Scheduled Task
# Run this script as Administrator to create a daily scheduled task

$TaskName = "SprintHealthAgent-DailyReport"
$TaskPath = "C:\Automation_MYB\postpaymentFulfilment\ancillaryfulfilment-baggage-service\SprintHealth"
$BatchFile = "$TaskPath\run_daily_report.bat"

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Please run this script as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the scheduled task
Write-Host "Creating scheduled task: $TaskName" -ForegroundColor Cyan

# Action - run the batch file
$Action = New-ScheduledTaskAction -Execute $BatchFile -WorkingDirectory $TaskPath

# Trigger - every weekday at 8:45 AM
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 8:45AM

# Settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Create the task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Sprint Health Agent - Generates daily sprint health report before standup"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Scheduled Task Created Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Task Name: $TaskName"
Write-Host "Schedule:  Every weekday at 8:45 AM"
Write-Host "Action:    Opens HTML report in browser"
Write-Host ""
Write-Host "To test it now, run:" -ForegroundColor Yellow
Write-Host "  schtasks /run /tn `"$TaskName`""
Write-Host ""
Write-Host "To view/modify in Task Scheduler:" -ForegroundColor Yellow
Write-Host "  taskschd.msc"
Write-Host ""

