import argparse
import csv
import json
from pathlib import Path


QUALITY_GATE_TERMS = {
    "set", "run", "cast", "charge", "issue",
    "carry out", "look up", "in terms of", "as a result",
    "check", "inspect", "examine", "affect", "influence",
    "support", "back", "handle", "process", "deal",
    "improve", "raise", "enhance",
}


def build_target_words(frequency_path: Path, output_path: Path, limit: int = 60_000) -> dict:
    selected: list[str] = []
    seen: set[str] = set()
    with Path(frequency_path).open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.reader(stream, delimiter="\t"):
            term = str(row[0] if row else "").strip().casefold()
            if not term or term in seen:
                continue
            selected.append(term)
            seen.add(term)
            if len(selected) >= limit:
                break
    for term in sorted(QUALITY_GATE_TERMS):
        if term not in seen:
            selected.append(term)
            seen.add(term)
    if len(selected) < min(limit, 25_000):
        raise ValueError(f"Only {len(selected)} target words were produced")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(selected) + "\n", encoding="utf-8")
    return {
        "frequency_source": str(frequency_path),
        "output": str(output_path),
        "target_words": len(selected),
        "frequency_limit": limit,
        "quality_gate_terms": len(QUALITY_GATE_TERMS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reproducible Kaikki target-word list")
    parser.add_argument("--frequency", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=60_000)
    args = parser.parse_args()
    print(json.dumps(build_target_words(args.frequency, args.output, args.limit), indent=2))


if __name__ == "__main__":
    main()
