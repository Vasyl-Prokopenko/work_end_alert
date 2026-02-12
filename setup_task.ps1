# Helper script to schedule the task
param (
    [double]$TargetHours = 8.0,
    [int]$CheckIntervalMinutes = 5,
    [string]$SnoozeOptions = "15,30,60"
)

# Convert hours to minutes for the script
$TargetMinutes = [math]::Round($TargetHours * 60)

$TaskName = "ActivityWatchActiveTimeCheck"
$ScriptPath = Join-Path $PSScriptRoot "main.py"

# Verify uv exists
if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found. Attempting to install via winget..."
    winget install --id astral-sh.uv --source winget --accept-package-agreements --accept-source-agreements
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install uv via winget. Please install it manually."
        exit 1
    }
    
    # Refresh PATH from registry so we can find uv immediately
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    
    if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
        Write-Error "uv installed but not found in PATH. Please restart your terminal."
        exit 1
    }
}

# Sync dependencies to ensure .venv exists
Write-Host "Syncing environment with uv..."
uv sync

# Use pythonw.exe from the local .venv to run silently (no console window)
$PythonW = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $PythonW)) {
    Write-Error "pythonw.exe not found at $PythonW. Please ensure .venv exists."
    exit 1
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
$Action = New-ScheduledTaskAction -Execute $PythonW -Argument "`"$ScriptPath`" --target $TargetMinutes --snooze-options `"$SnoozeOptions`"" -WorkingDirectory $PSScriptRoot
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $CheckIntervalMinutes)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes $CheckIntervalMinutes) -MultipleInstances Parallel
Register-ScheduledTask -Action $Action -Trigger $Trigger -Settings $Settings -TaskName $TaskName -Description "Checks ActivityWatch for >8h active work time." -Force | Out-Null

Write-Host "Task '$TaskName' registered successfully."
Write-Host "----------------------------------------"
Write-Host "Target Work Hours:    $TargetHours"
Write-Host "Check Interval:       $CheckIntervalMinutes minutes"
Write-Host "Snooze Options:       $SnoozeOptions"
Write-Host  -ForegroundColor DarkGray "Runs: $PythonW `"$ScriptPath`""
Write-Host "----------------------------------------"
