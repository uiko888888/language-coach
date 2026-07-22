from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.dictionary_ocr import annotation_template, load_json, sha256_file, validate_sample_manifest, write_json


def ensure_annotation_file(path: Path, manifest: dict, source_hash: str) -> None:
    expected = annotation_template(manifest, source_hash)
    if not path.exists():
        write_json(path, expected)
        return
    existing = load_json(path)
    expected_pages = [item["page"] for item in expected["pages"]]
    existing_pages = [item.get("page") for item in existing.get("pages", [])]
    if existing_pages == expected_pages and existing.get("source_sha256") == source_hash:
        return
    if all(item.get("status") == "pending" for item in existing.get("pages", [])):
        write_json(path, expected)
        return
    raise ValueError(
        "The sample manifest or source changed after manual review began; preserve the old gold file "
        "and choose a new output directory."
    )


def find_pdftoppm(explicit: Path | None) -> Path:
    if explicit:
        path = explicit.resolve()
        if path.is_file():
            return path
        raise ValueError(f"pdftoppm not found: {path}")
    discovered = shutil.which("pdftoppm")
    if not discovered:
        raise ValueError("pdftoppm is required; pass --pdftoppm with the Poppler executable")
    return Path(discovered)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the gated 20-page private dictionary OCR sample.")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, default=ROOT / "config/private_ocr/dk_oxford_20_pages.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/private-ocr/dk-oxford-20-pages-v1")
    parser.add_argument("--pdftoppm", type=Path)
    args = parser.parse_args()
    if not args.pdf.is_file():
        parser.error(f"PDF file not found: {args.pdf}")
    manifest = validate_sample_manifest(load_json(args.manifest))
    output = args.output.resolve()
    pages_dir = output / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    tool = find_pdftoppm(args.pdftoppm)
    expected_images = {f"page-{int(item['page']):04d}.png" for item in manifest["pages"]}
    for stale_image in pages_dir.glob("page-*.png"):
        if stale_image.name not in expected_images:
            stale_image.unlink()
    for item in manifest["pages"]:
        page = int(item["page"])
        prefix = pages_dir / f"page-{page:04d}"
        target = prefix.with_suffix(".png")
        if target.is_file():
            continue
        subprocess.run([
            str(tool), "-f", str(page), "-l", str(page), "-png", "-r",
            str(int(manifest.get("render_dpi", 300))), "-singlefile", str(args.pdf), str(prefix),
        ], check=True)
    source_hash = sha256_file(args.pdf)
    annotation_path = output / "gold-annotations.json"
    ensure_annotation_file(annotation_path, manifest, source_hash)
    rendered_pages = [
        {
            **item,
            "image": str((pages_dir / f"page-{int(item['page']):04d}.png").resolve()),
            "image_sha256": sha256_file(pages_dir / f"page-{int(item['page']):04d}.png"),
        }
        for item in manifest["pages"]
    ]
    write_json(output / "sample-run.json", {
        "sample_id": manifest["sample_id"],
        "source_path": str(args.pdf.resolve()),
        "source_sha256": source_hash,
        "render_dpi": manifest["render_dpi"],
        "pages": rendered_pages,
        "gold_annotations": str(annotation_path),
    })
    print(f"Rendered {len(manifest['pages'])} pages to {pages_dir}")
    print(f"Manual gold file: {annotation_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
