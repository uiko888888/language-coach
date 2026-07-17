[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = $(if ($env:LANGUAGE_COACH_PORT) { [int]$env:LANGUAGE_COACH_PORT } else { 8765 })
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
python -u .\backend\server.py $Port
