[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = $(if ($env:LANGUAGE_COACH_PORT) { [int]$env:LANGUAGE_COACH_PORT } else { 8765 })
)

$taskName = "Language Coach - Daily Content"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$taskInfo = if ($task) { Get-ScheduledTaskInfo -TaskName $taskName } else { $null }
$healthy = $false
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
    $healthy = $health.ok -eq $true
}
catch {}

[PSCustomObject]@{
    TaskInstalled = $null -ne $task
    TaskState = if ($task) { $task.State } else { "NotInstalled" }
    LastRunTime = if ($taskInfo) { $taskInfo.LastRunTime } else { $null }
    LastTaskResult = if ($taskInfo) { $taskInfo.LastTaskResult } else { $null }
    BackendHealthy = $healthy
    Address = "http://127.0.0.1:$Port/"
} | Format-List
