[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$taskName = "Language Coach - Daily Content"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Removed '$taskName'. The currently running backend was left untouched."
}
else {
    Write-Host "'$taskName' is not installed."
}
