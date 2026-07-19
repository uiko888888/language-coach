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

if (-not $Tatoeba -and -not $Wordfreq) {
    Write-Output "No download selected. Use -Tatoeba and/or -Wordfreq."
    Write-Output "Kaikki remains manual because the official dump can be multiple gigabytes:"
    Write-Output "https://kaikki.org/dictionary/English/index.html"
    exit 0
}

if ($Tatoeba) {
    $sentences = Join-Path $output "sentences_detailed.tar.bz2"
    $links = Join-Path $output "links.tar.bz2"
    Assert-Target $sentences
    Assert-Target $links
    Invoke-WebRequest "https://downloads.tatoeba.org/exports/sentences_detailed.tar.bz2" -OutFile $sentences
    Invoke-WebRequest "https://downloads.tatoeba.org/exports/links.tar.bz2" -OutFile $links
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
