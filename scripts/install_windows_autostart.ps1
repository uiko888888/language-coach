[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = $(if ($env:LANGUAGE_COACH_PORT) { [int]$env:LANGUAGE_COACH_PORT } else { 8765 })
)

$ErrorActionPreference = "Stop"
$taskName = "Language Coach - Daily Content"
$projectRoot = Split-Path -Parent $PSScriptRoot
$serverPath = Join-Path $projectRoot "backend\server.py"
$pythonPath = if ($env:LANGUAGE_COACH_PYTHON) { $env:LANGUAGE_COACH_PYTHON } else { (Get-Command python -ErrorAction Stop).Source }

if (-not (Get-Command Register-ScheduledTask -ErrorAction SilentlyContinue)) {
    throw "Windows Scheduled Tasks cmdlets are unavailable on this system."
}

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Python executable not found: $pythonPath"
}
if (-not (Test-Path -LiteralPath $serverPath -PathType Leaf)) {
    throw "Language Coach backend not found: $serverPath"
}

$actionArguments = "-u `"$serverPath`" $Port"
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $actionArguments -WorkingDirectory $projectRoot -ErrorAction Stop
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME -ErrorAction Stop
$trigger.Delay = "PT30S"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -ErrorAction Stop
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited -ErrorAction Stop

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Description "Starts Language Coach after sign-in so public feeds can refresh automatically." `
    -Force -ErrorAction Stop | Out-Null

Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
$healthUrl = "http://127.0.0.1:$Port/api/health"
$healthy = $false
$deadline = [DateTime]::UtcNow.AddSeconds(20)
do {
    Start-Sleep -Milliseconds 500
    try {
        $healthy = (Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2).ok -eq $true
    }
    catch {
        $healthy = $false
    }
} while (-not $healthy -and [DateTime]::UtcNow -lt $deadline)

if (-not $healthy) {
    throw "The task was installed, but Language Coach did not become healthy at $healthUrl."
}
Write-Host "Installed '$taskName'. Language Coach will start 30 seconds after sign-in."
Write-Host "Current address: http://127.0.0.1:$Port/"
