# Dictionary Data Operations

Language Coach uses layered open data. No single source is presented as a complete commercial dictionary.

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

The importer accepts JSONL or JSONL.GZ and streams records instead of loading the dump into memory:

```powershell
python .\scripts\import_kaikki.py --jsonl .\artifacts\kaikki-english.jsonl.gz
```

For a controlled first import, create a UTF-8 target list and filter the dump:

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

## wordfreq

Purpose: commonness ordering only. It does not supply definitions.

Source: [wordfreq](https://github.com/rspeer/wordfreq). The code is Apache-2.0, while frequency data includes multiple upstream licenses. Preserve the upstream NOTICE and data-source attribution when creating a distributable TSV.

Import a UTF-8 tab-separated file with `term` and `Zipf frequency`:

```powershell
python .\scripts\import_word_frequency.py --tsv .\artifacts\wordfreq-en.tsv
```

The UI labels general frequency and local article frequency separately. Local occurrence counts never masquerade as general language frequency.

## Verification

Restart the scheduled backend after schema or bulk data changes, then verify:

```powershell
Stop-ScheduledTask -TaskName "Language Coach - Daily Content"
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName "Language Coach - Daily Content"
Start-Sleep -Seconds 4
Invoke-RestMethod http://127.0.0.1:8766/api/version
Invoke-RestMethod http://127.0.0.1:8766/api/dictionary/status
```

Expected version compatibility for this release is schema 6. Query history remains private local data and must not be bundled with dictionary exports. Data quality must be checked with representative polysemous words, phrases, Chinese queries and uncommon terms before a source is declared production-ready.
