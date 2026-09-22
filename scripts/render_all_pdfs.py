#!/usr/bin/env python3
"""
Builds a PDF for every article in _articles/, into a given output directory,
using the exact same build() function as render_pdf.py -- so the batch build
and the single-file build can never drift apart.

Usage: python scripts/render_all_pdfs.py OUTPUT_DIR
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render_pdf import build  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/render_all_pdfs.py OUTPUT_DIR")
    out_dir = pathlib.Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    articles = sorted((ROOT / "_articles").glob("*.md"))
    failures = []
    for path in articles:
        out_path = out_dir / f"{path.stem}.pdf"
        try:
            build(str(path), str(out_path))
            print(f"OK    {path.name} -> {out_path.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_path}")
        except Exception as exc:  # noqa: BLE001 -- one bad article should not stop the rest
            failures.append((path.name, str(exc)))
            print(f"FAIL  {path.name}: {exc}", file=sys.stderr)

    print(f"\nBuilt {len(articles) - len(failures)} of {len(articles)} PDF(s).")
    if failures:
        print("Failures:", file=sys.stderr)
        for name, err in failures:
            print(f"  {name}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
