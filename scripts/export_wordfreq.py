import argparse
import importlib.metadata
import json
from pathlib import Path


def export_wordfreq(output: Path, limit: int) -> dict:
    try:
        from wordfreq import top_n_list, zipf_frequency
    except ImportError as exc:
        raise RuntimeError("Install the pinned wordfreq package before exporting") from exc
    version = importlib.metadata.version("wordfreq")
    terms = top_n_list("en", limit, wordlist="best", ascii_only=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        for term in terms:
            stream.write(f"{term}\t{zipf_frequency(term, 'en', wordlist='best'):.4f}\n")
    return {"package": "wordfreq", "version": version, "terms": len(terms), "output": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a licensed local wordfreq installation to TSV")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=200000)
    args = parser.parse_args()
    if not 25_000 <= args.limit <= 1_000_000:
        parser.error("--limit must be between 25000 and 1000000")
    print(json.dumps(export_wordfreq(args.output, args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
