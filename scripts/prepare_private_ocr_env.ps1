param(
    [string]$Python = "",
    [string]$Environment = "artifacts\private-ocr\python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EnvironmentPath = [System.IO.Path]::GetFullPath((Join-Path $Root $Environment))
$Requirements = Join-Path $Root "requirements-ocr.txt"

if (-not $Python) {
    $BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $BundledPython -PathType Leaf) {
        $Python = $BundledPython
    } else {
        $Python = (Get-Command python -ErrorAction Stop).Source
    }
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python executable not found: $Python"
}

$PythonVersion = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($PythonVersion -ne "3.12") {
    throw "The pinned Paddle environment requires Python 3.12; found $PythonVersion at $Python"
}

if (-not (Test-Path -LiteralPath (Join-Path $EnvironmentPath "Scripts\python.exe"))) {
    & $Python -m venv $EnvironmentPath
}

$EnvironmentPython = Join-Path $EnvironmentPath "Scripts\python.exe"
& $EnvironmentPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to prepare pip in the private OCR environment"
}
& $EnvironmentPython -m pip install --requirement $Requirements
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install the pinned Paddle OCR dependencies"
}
& $EnvironmentPython -c "import importlib.metadata as m; print('paddlepaddle', m.version('paddlepaddle')); print('paddleocr', m.version('paddleocr'))"
if ($LASTEXITCODE -ne 0) {
    throw "Paddle OCR dependency verification failed"
}

Write-Host "Private OCR environment ready: $EnvironmentPython"
