[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = $(if ($env:LANGUAGE_COACH_PORT) { [int]$env:LANGUAGE_COACH_PORT } else { 8765 }),
    [ValidateRange(5, 120)]
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$taskName = "Language Coach - Daily Content"
$projectRoot = Split-Path -Parent $PSScriptRoot
$expectedVersion = (Get-Content -LiteralPath (Join-Path $projectRoot "VERSION") -Raw).Trim()
$versionUrl = "http://127.0.0.1:$Port/api/version"
$healthUrl = "http://127.0.0.1:$Port/api/health"

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Warning "Scheduled task '$taskName' is not visible to this PowerShell context. Installing/updating it for the current user."
    & (Join-Path $PSScriptRoot "install_windows_autostart.ps1") -Port $Port
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $task) {
        throw "Scheduled task '$taskName' could not be installed in the current context."
    }
}

Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName $taskName -ErrorAction Stop

$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
$version = $null
do {
    Start-Sleep -Milliseconds 500
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        if ($health.ok -eq $true) {
            $version = Invoke-RestMethod -Uri $versionUrl -TimeoutSec 2
        }
    }
    catch {
        $version = $null
    }
} while ($null -eq $version -and [DateTime]::UtcNow -lt $deadline)

if ($null -eq $version) {
    throw "Language Coach did not become healthy at $healthUrl within $TimeoutSeconds seconds."
}
if ($version.app_version -ne $expectedVersion -or -not $version.compatible) {
    throw "Version check failed. Expected $expectedVersion/schema $($version.schema_version), got $($version.app_version)/schema $($version.database_schema_version)."
}

[PSCustomObject]@{
    TaskName = $taskName
    TaskState = (Get-ScheduledTask -TaskName $taskName).State
    Address = "http://127.0.0.1:$Port/"
    AppVersion = $version.app_version
    SchemaVersion = $version.database_schema_version
    Compatible = $version.compatible
} | Format-List
