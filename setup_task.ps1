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

# Workaround for uv bug https://github.com/astral-sh/uv/issues/19226 :
# uv generates pythonw.exe as a console trampoline (identical to python.exe),
# so it still pops up a console window. Replace it with the base interpreter's
# real GUI pythonw.exe, which correctly resolves this venv via pyvenv.cfg.
#
# The base pythonw.exe is the real interpreter (not a trampoline), so it loads
# python3*.dll from its own directory. After copying it into .venv\Scripts we
# must also copy those DLLs next to it, otherwise it fails to start with
# 0xC0000135 (STATUS_DLL_NOT_FOUND) and the scheduled task silently aborts.
$ScriptsDir = Join-Path $PSScriptRoot ".venv\Scripts"
$PyVenvCfg = Join-Path $PSScriptRoot ".venv\pyvenv.cfg"
$HomeLine = (Get-Content $PyVenvCfg | Select-String '^home = ').Line
if ($HomeLine) {
    $BaseDir = ($HomeLine -replace '^home = ', '').Trim()
    $BasePythonW = Join-Path $BaseDir "pythonw.exe"
    $Python = Join-Path $ScriptsDir "python.exe"
    $SameTrampoline = (Test-Path $Python) -and ((Get-FileHash $Python).Hash -eq (Get-FileHash $PythonW).Hash)
    if ($SameTrampoline -and (Test-Path $BasePythonW)) {
        Write-Host "Patching pythonw.exe (uv #19226 workaround)..."
        Copy-Item $BasePythonW $PythonW -Force
        # Copy the interpreter DLLs (python3.dll, python3XX.dll) that the real
        # pythonw.exe needs to load, since they live in the base interpreter dir.
        Get-ChildItem (Join-Path $BaseDir "python3*.dll") -ErrorAction SilentlyContinue | ForEach-Object {
            Copy-Item $_.FullName $ScriptsDir -Force
        }
    }
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
