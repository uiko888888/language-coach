# Dictionary Data Operations

Language Coach uses layered open data. No single source is presented as a complete commercial dictionary.

## Private Local MOBI Dictionaries

User-owned commercial dictionaries may be indexed for private local lookup only. They are ignored by Git and excluded from public question generation, model training and open dictionary exports.

```powershell
python .\scripts\import_private_mobi.py `
  --mobi ".\data\private-dictionaries\imports\my-dictionary.mobi" `
  --name "My private dictionary" `
  --kind bilingual_dictionary `
  --priority 10
```

The built-in importer accepts unencrypted PalmDOC or uncompressed MOBI files. DRM is rejected. HUFF/CDIC files remain `conversion_required` until converted through a trusted local tool and validated; they are never partially promoted to a ready index. Encyclopedia sources use `--kind encyclopedia` and appear as context rather than bilingual definitions.

## Installed Baseline

Open English WordNet is the semantic baseline. Check the running database with:

```powershell
Invoke-RestMethod http://127.0.0.1:8766/api/dictionary/status
```

The response reports actual row counts. A layer is `installed: true` only when its source metadata and data rows both exist.

## Working Directory

Run every command from the project root:

```powershell
cd "C:\Users\hususu\Documents\Codex\2026-07-15\new-chat\outputs\language-coach-v2"
```

Do not run `python .\scripts\...` from `C:\Users\hususu`; that directory does not contain the project scripts.

## Kaikki / Wiktionary

Purpose: pronunciation, forms, English glosses, Chinese translations when present, etymology, related words and phrases.

Source: [Kaikki English dictionary extract](https://kaikki.org/dictionary/English/index.html). Wiktionary attribution and CC BY-SA/GFDL obligations apply.

The importer accepts JSONL or JSONL.GZ and streams records instead of loading the dump into memory. Prepare a reproducible 60,000-word target list and resumably download the official dump with:

```powershell
.\scripts\prepare_dictionary_sources.ps1 -Kaikki
```

The default URL is the official English JSONL endpoint. If Kaikki changes the dated download link, copy the current `kaikki.org` link from the discovery page and pass it explicitly:

```powershell
.\scripts\prepare_dictionary_sources.ps1 `
  -Kaikki `
  -KaikkiUrl "https://kaikki.org/path/from-the-official-index.jsonl.gz"
```

The downloader keeps interrupted data as `.part`, resumes with `curl`, and promotes the source only after every JSON line and at least 25,000 English records validate. It does not modify the production database.

Large sources may be stored on another local drive. `-OutputDirectory` accepts an absolute path, for example `D:\language-coach-dictionary`; pass the resulting absolute source path to the candidate importer.

For a faster, still low-memory download, install aria2 and use two connections:

```powershell
winget install --id aria2.aria2 -e
.\scripts\prepare_dictionary_sources.ps1 `
  -Kaikki `
  -Downloader aria2 `
  -ParallelConnections 2 `
  -OutputDirectory "D:\language-coach-dictionary"
```

Run the filtered import and all production gates against an isolated database candidate first:

```powershell
python .\scripts\stage_kaikki_candidate.py `
  --source .\artifacts\dictionary-sources\kaikki-english.jsonl `
  --words .\artifacts\dictionary-sources\kaikki-target-words.txt `
  --source-version downloaded-2026-07-19
```

The command always leaves the production database unchanged. It exits with code `2` when any source count, metadata, probe group or SQLite integrity gate fails, while preserving the candidate and JSON report for inspection.

For a custom controlled import, provide another UTF-8 target list:

```powershell
python .\scripts\import_kaikki.py `
  --jsonl .\artifacts\kaikki-english.jsonl.gz `
  --words .\artifacts\target-words.txt
```

Do not commit the multi-gigabyte source dump or generated database.

## Tatoeba

Purpose: attributable English-Chinese sentence pairs. Personal article contexts remain a separate local layer.

Source: [Tatoeba downloads](https://tatoeba.org/en/downloads). Text sentences use CC BY 2.0 FR; sentence-level authors must be retained. Audio has separate licenses and is not imported here.

Use the detailed sentence export containing the username column and the links export:

```powershell
python .\scripts\import_tatoeba.py `
  --sentences .\artifacts\sentences_detailed.tar.bz2 `
  --links .\artifacts\links.tar.bz2 `
  --limit 200000
```

Rows without both English and Chinese authors are rejected. Length and basic quality filters run before insertion.

Use the resumable downloader when network access is available:

```powershell
.\scripts\prepare_dictionary_sources.ps1 -Tatoeba
```

Interrupted archives remain as `.part` files and the same command resumes them. A file is promoted to its final name only after a complete BZip2/TAR read succeeds.

## wordfreq

Purpose: commonness ordering only. It does not supply definitions.

Source: [wordfreq](https://github.com/rspeer/wordfreq). The code is Apache-2.0, while frequency data includes multiple upstream licenses. Preserve the upstream NOTICE and data-source attribution when creating a distributable TSV.

Import a UTF-8 tab-separated file with `term` and `Zipf frequency`:

```powershell
python .\scripts\import_word_frequency.py --tsv .\artifacts\wordfreq-en.tsv
```

The pinned package can be prepared explicitly when network access is available:

```powershell
.\scripts\prepare_dictionary_sources.ps1 -Wordfreq
python .\scripts\import_word_frequency.py `
  --tsv .\artifacts\dictionary-sources\wordfreq-en.tsv `
  --source-version 3.1.1
```

The UI labels general frequency and local article frequency separately. Local occurrence counts never masquerade as general language frequency.

## Verification

Before a layer is called production-ready, run the representative quality audit:

```powershell
python .\scripts\audit_dictionary_data.py `
  --database .\data\language_coach.sqlite `
  --report .\artifacts\dictionary-quality.json `
  --strict
```

The strict gate requires at least 25,000 rows in each open layer, complete source metadata, and at least 60% coverage in every probe group: polysemy, phrases, Chinese reverse lookup, attributable examples and frequency ordering. An imported layer may be displayed before it passes, but it remains labeled `待验证`.

Restart the scheduled backend after schema or bulk data changes, then verify:

```powershell
Stop-ScheduledTask -TaskName "Language Coach - Daily Content"
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName "Language Coach - Daily Content"
Start-Sleep -Seconds 4
Invoke-RestMethod http://127.0.0.1:8766/api/version
Invoke-RestMethod http://127.0.0.1:8766/api/dictionary/status
```

Expected application compatibility is currently schema 16. Query history and review history remain private local data and must not be bundled with dictionary exports. Data quality must pass the executable audit before a source is declared production-ready.
