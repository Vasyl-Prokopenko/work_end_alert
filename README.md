# Work End Alert

**Work End Alert** is a forceful work-life balance enforcer for Windows users. It monitors your active computer usage via [ActivityWatch](https://activitywatch.net/) and blocks your screen when you've exceeded your daily work limit.

## Features

- **Activity Tracking**: Uses your local ActivityWatch server to calculate "not-afk" time since midnight.
- **Intrusive Alert**: When time is up, a full-screen blocking window appears on ALL monitors.
- **Snooze Options**: You can snooze for 15, 30, or 60 minutes if you really need to finish something.
- **Background Execution**: Runs silently as a Windows Scheduled Task.

## Prerequisites

1. **Windows OS**: This tool relies on PowerShell and Windows Task Scheduler.
2. **ActivityWatch**: You must have [ActivityWatch](https://activitywatch.net/) installed and running.
    - The tool monitors the `aw-watcher-afk_{hostname}` bucket.
3. **uv**: The project uses `uv` for dependency management (installs automatically if missing).

## Installation

The installation is automated via PowerShell.

1. Clone the repository.
2. Open a PowerShell terminal in the project directory.
3. Run the setup script:

    ```powershell
    .\setup_task.ps1
    ```

This script will:

- Install `uv` (if not found).
- Create a virtual environment and install dependencies.
- Register a scheduled task named `ActivityWatchActiveTimeCheck` that runs every 5 minutes.

## Configuration

You can customize the work duration and check frequency by passing parameters to the setup script.

### Parameters

- `-TargetHours`: The number of hours you want to work (default: `8`).
- `-CheckIntervalMinutes`: How often the tool checks your time (default: `5`).
- `-SnoozeOptions`: Comma-separated list of snooze minutes (default: `"15,30,60"`).

### Examples

**Set a 7.5 hour workday and check every 10 minutes instead of 5:**

```powershell
.\setup_task.ps1 -TargetHours 7.5 -CheckIntervalMinutes 10
```

**Customize snooze buttons:**

```powershell
.\setup_task.ps1 -SnoozeOptions "5,10,15,30,45,60"
```

## How It Works

1. The scheduled task runs `main.py` in the background (using `pythonw` to avoid popup windows).
2. `main.py` queries `http://localhost:5600/api/0/query` to calculate total active time for today.
3. If `Active Time > Target Time`, the alert window launches.
4. If you click **"Snooze"**, the alert closes and remains suppressed for the selected duration (15, 30, or 60 minutes). The background checks will continue but will not trigger the alert again until the snooze timer expires.

## Development

To test the alert manually without waiting for the schedule:

```powershell
# Run the script via uv with a low target to trigger immediately (e.g., 1 minute)
uv run main.py --target 1

# Force the alert to show even if snoozed
uv run main.py --target 1 --force

# Use custom snooze buttons (e.g., 5, 10, 15, 30, 45, and 60 minutes)
uv run main.py --target 1 --snooze-options "5,10,15,30,45,60"
```
