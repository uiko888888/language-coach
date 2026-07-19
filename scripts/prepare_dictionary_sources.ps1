[CmdletBinding()]
param(
    [switch]$Kaikki,
    [switch]$Tatoeba,
    [switch]$Wordfreq,
    [switch]$Force,
    [ValidateRange(25000, 1000000)]
    [int]$FrequencyLimit = 200000,
    [ValidateRange(25000, 200000)]
    [int]$KaikkiTargetLimit = 60000,
    [ValidatePattern('^https://kaikki\.org/')]
    [string]$KaikkiUrl = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl",
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
    & python .\scripts\validate_dictionary_source.py --kind archive --path $Path --quiet
    return $LASTEXITCODE -eq 0
}

function Test-FrequencyTsv([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    & python .\scripts\validate_dictionary_source.py --kind frequency --path $Path --quiet
    return $LASTEXITCODE -eq 0
}

function Test-KaikkiJsonl([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    & python .\scripts\validate_dictionary_source.py --kind kaikki --path $Path --quiet
    return $LASTEXITCODE -eq 0
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

function Invoke-ResumableKaikkiDownload([string]$Url, [string]$Target) {
    $partial = "$Target.part"
    if ($Force) {
        Remove-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
    }
    elseif (Test-KaikkiJsonl $Target) {
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
    if (-not (Test-KaikkiJsonl $partial)) {
        throw "Downloaded Kaikki JSONL failed full validation and remains available for inspection: $partial"
    }
    Move-Item -LiteralPath $partial -Destination $Target -Force
    Write-Output "Downloaded and verified: $Target"
}

if (-not $Kaikki -and -not $Tatoeba -and -not $Wordfreq) {
    Write-Output "No download selected. Use -Kaikki, -Tatoeba and/or -Wordfreq."
    exit 0
}

if ($Kaikki) {
    $extension = if ($KaikkiUrl.EndsWith(".gz")) { ".jsonl.gz" } else { ".jsonl" }
    $kaikki = Join-Path $output "kaikki-english$extension"
    $targets = Join-Path $output "kaikki-target-words.txt"
    $frequency = Join-Path $output "wordfreq-en.tsv"
    if (-not (Test-FrequencyTsv $frequency)) {
        throw "Validated wordfreq TSV required before building Kaikki targets: $frequency"
    }
    python .\scripts\build_kaikki_target_words.py --frequency $frequency --output $targets --limit $KaikkiTargetLimit
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build Kaikki target words."
    }
    Invoke-ResumableKaikkiDownload $KaikkiUrl $kaikki
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
    if ((-not $Force) -and (Test-FrequencyTsv $tsv)) {
        Write-Output "Verified existing source: $tsv"
    }
    else {
        Assert-Target $tsv
        python -m pip install --disable-pip-version-check --upgrade --target $packageDirectory wordfreq==3.1.1
        $previousPythonPath = $env:PYTHONPATH
        try {
            $env:PYTHONPATH = if ($previousPythonPath) { "$packageDirectory;$previousPythonPath" } else { $packageDirectory }
            python .\scripts\export_wordfreq.py --output $tsv --limit $FrequencyLimit
        }
        finally {
            $env:PYTHONPATH = $previousPythonPath
        }
    }
}

Get-ChildItem -LiteralPath $output -File | ForEach-Object {
    [PSCustomObject]@{
        File = $_.Name
        Bytes = $_.Length
        SHA256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
} | Format-Table -AutoSize
