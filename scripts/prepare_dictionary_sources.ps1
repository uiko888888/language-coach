[CmdletBinding()]
param(
    [switch]$Tatoeba,
    [switch]$Wordfreq,
    [switch]$Force,
    [ValidateRange(25000, 1000000)]
    [int]$FrequencyLimit = 200000,
    [string]$OutputDirectory = "artifacts\dictionary-sources"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$output = [IO.Path]::GetFullPath((Join-Path $root $OutputDirectory))
New-Item -ItemType Directory -Path $output -Force | Out-Null

function Assert-Target([string]$Path) {
    if ((Test-Path -LiteralPath $Path) -and -not $Force) {
        throw "Source already exists: $Path. Use -Force to replace it."
    }
}

function Test-TarBzipArchive([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    $previousCheckPath = $env:LANGUAGE_COACH_ARCHIVE_CHECK
    try {
        $env:LANGUAGE_COACH_ARCHIVE_CHECK = $Path
        & python -c "import os, tarfile; archive=tarfile.open(os.environ['LANGUAGE_COACH_ARCHIVE_CHECK'], 'r:bz2'); next((item for item in archive if item.isfile()), None); archive.close()" 2>$null
        return $LASTEXITCODE -eq 0
    }
    finally {
        $env:LANGUAGE_COACH_ARCHIVE_CHECK = $previousCheckPath
    }
}

function Invoke-ResumableArchiveDownload([string]$Url, [string]$Target) {
    $partial = "$Target.part"
    if ($Force) {
        Remove-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
    }
    elseif (Test-TarBzipArchive $Target) {
        Write-Output "Verified existing source: $Target"
        return
    }
    elseif (Test-Path -LiteralPath $Target) {
        if ((Test-Path -LiteralPath $partial) -and
            (Get-Item -LiteralPath $partial).Length -ge (Get-Item -LiteralPath $Target).Length) {
            Remove-Item -LiteralPath $Target -Force
        }
        else {
            Move-Item -LiteralPath $Target -Destination $partial -Force
        }
    }

    $curlArguments = @(
        "--fail", "--location", "--retry", "8", "--retry-delay", "2", "--retry-all-errors",
        "--connect-timeout", "30", "--continue-at", "-", "--output", $partial, $Url
    )
    & curl.exe @curlArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Download interrupted after $((Get-Item -LiteralPath $partial -ErrorAction SilentlyContinue).Length) bytes. Re-run the same command to resume: $Url"
    }
    if (-not (Test-TarBzipArchive $partial)) {
        throw "Downloaded archive failed BZip2/TAR verification and remains available for retry: $partial"
    }
    Move-Item -LiteralPath $partial -Destination $Target -Force
    Write-Output "Downloaded and verified: $Target"
}

if (-not $Tatoeba -and -not $Wordfreq) {
    Write-Output "No download selected. Use -Tatoeba and/or -Wordfreq."
    Write-Output "Kaikki remains manual because the official dump can be multiple gigabytes:"
    Write-Output "https://kaikki.org/dictionary/English/index.html"
    exit 0
}

if ($Tatoeba) {
    $sentences = Join-Path $output "sentences_detailed.tar.bz2"
    $links = Join-Path $output "links.tar.bz2"
    Invoke-ResumableArchiveDownload "https://downloads.tatoeba.org/exports/sentences_detailed.tar.bz2" $sentences
    Invoke-ResumableArchiveDownload "https://downloads.tatoeba.org/exports/links.tar.bz2" $links
}

if ($Wordfreq) {
    $packageDirectory = Join-Path $output "python"
    $tsv = Join-Path $output "wordfreq-en.tsv"
    Assert-Target $tsv
    python -m pip install --disable-pip-version-check --target $packageDirectory wordfreq==3.1.1
    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = if ($previousPythonPath) { "$packageDirectory;$previousPythonPath" } else { $packageDirectory }
        python .\scripts\export_wordfreq.py --output $tsv --limit $FrequencyLimit
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
    }
}

Get-ChildItem -LiteralPath $output -File | ForEach-Object {
    [PSCustomObject]@{
        File = $_.Name
        Bytes = $_.Length
        SHA256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
} | Format-Table -AutoSize
