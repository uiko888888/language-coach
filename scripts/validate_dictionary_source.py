import argparse
import csv
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a downloaded dictionary source file")
    parser.add_argument("--kind", choices=("archive", "frequency"), required=True)
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--minimum-rows", type=int, default=25_000)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    try:
        result = validate_archive(args.path) if args.kind == "archive" else validate_frequency(args.path, args.minimum_rows)
    except (OSError, EOFError, ValueError, tarfile.TarError) as exc:
        if not args.quiet:
            print(json.dumps({"valid": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        raise SystemExit(1)
    if not args.quiet:
        print(json.dumps({"valid": True, **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
