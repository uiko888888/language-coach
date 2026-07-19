import argparse
import csv
import gzip
import json
import math
import tarfile
from pathlib import Path


def validate_archive(path: Path) -> dict:
    files = bytes_read = 0
    with tarfile.open(path, "r:bz2") as archive:
        for member in archive:
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"Cannot read archive member: {member.name}")
            files += 1
            with extracted:
                while chunk := extracted.read(1024 * 1024):
                    bytes_read += len(chunk)
    if files < 1 or bytes_read < 1:
        raise ValueError("Archive contains no readable data file")
    return {"kind": "tar.bz2", "files": files, "uncompressed_bytes": bytes_read}


def validate_frequency(path: Path, minimum_rows: int = 25_000) -> dict:
    rows = valid = rejected = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.reader(stream, delimiter="\t"):
            rows += 1
            if len(row) < 2 or not row[0].strip():
                rejected += 1
                continue
            try:
                score = float(row[1])
            except ValueError:
                rejected += 1
                continue
            if not math.isfinite(score) or not 0 <= score <= 8:
                rejected += 1
                continue
            valid += 1
    if valid < minimum_rows or rejected:
        raise ValueError(f"Frequency TSV has {valid} valid rows and {rejected} rejected rows")
    return {"kind": "frequency-tsv", "rows": rows, "valid_rows": valid, "rejected": rejected}


def validate_kaikki(path: Path, minimum_rows: int = 25_000) -> dict:
    rows = valid = invalid_json = ignored = 0
    opener = gzip.open if ".gz" in path.suffixes else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            rows += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                invalid_json += 1
                continue
            if (
                not isinstance(item, dict)
                or not str(item.get("word") or "").strip()
                or item.get("lang_code") not in {None, "en"}
            ):
                ignored += 1
                continue
            valid += 1
    if valid < minimum_rows or invalid_json:
        raise ValueError(
            f"Kaikki JSONL has {valid} valid English rows, {ignored} ignored metadata/non-English rows "
            f"and {invalid_json} invalid JSON rows"
        )
    return {
        "kind": "kaikki-jsonl",
        "rows": rows,
        "valid_rows": valid,
        "ignored_metadata_or_non_english": ignored,
        "invalid_json_rows": invalid_json,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a downloaded dictionary source file")
    parser.add_argument("--kind", choices=("archive", "frequency", "kaikki"), required=True)
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--minimum-rows", type=int, default=25_000)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    try:
        if args.kind == "archive":
            result = validate_archive(args.path)
        elif args.kind == "frequency":
            result = validate_frequency(args.path, args.minimum_rows)
        else:
            result = validate_kaikki(args.path, args.minimum_rows)
    except (OSError, EOFError, ValueError, tarfile.TarError) as exc:
        if not args.quiet:
            print(json.dumps({"valid": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        raise SystemExit(1)
    if not args.quiet:
        print(json.dumps({"valid": True, **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
