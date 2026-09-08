"""
Process a whole folder: extract, validate, route.

    python run.py samples

Clean documents land in   out/clean.csv
Flagged ones land in      out/review_queue.json
Raw extractions cache in  out/raw/  so re-running never re-charges you.

That cache matters. Extraction costs money; validation is free. Once a
document is extracted you can change every rule in validate.py and re-run
the whole folder for nothing. Use --refresh to force a re-extract.
"""

import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

import anthropic

from extract import MEDIA_TYPES, build_client, extract
from schema import Invoice
from validate import needs_review, validate

OUT = Path("out")
RAW = OUT / "raw"
FIELDS = ("supplier_name", "invoice_number", "invoice_date",
          "currency", "subtotal", "tax", "total")


def process(path: Path, client, refresh: bool = False) -> tuple[Invoice, float]:
    """Extract one document, using the cache unless told otherwise."""
    cached = RAW / f"{path.stem}.json"
    if cached.exists() and not refresh:
        return Invoice.model_validate_json(cached.read_text(encoding="utf-8")), 0.0

    invoice, cost = extract(path, client=client)
    RAW.mkdir(parents=True, exist_ok=True)
    cached.write_text(invoice.model_dump_json(indent=2), encoding="utf-8")
    return invoice, cost


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--refresh"]
    refresh = "--refresh" in sys.argv
    folder = Path(args[0]) if args else Path("samples")

    docs = sorted(p for p in folder.iterdir() if p.suffix.lower() in MEDIA_TYPES)
    if not docs:
        print(f"No documents found in {folder}/", file=sys.stderr)
        return 1

    OUT.mkdir(exist_ok=True)
    client = build_client()
    clean_rows, review_items, spent = [], [], 0.0

    for path in docs:
        try:
            invoice, cost = process(path, client, refresh)
        except anthropic.APIError as err:
            print(f"  FAILED  {path.name}: {err}", file=sys.stderr)
            continue

        spent += cost
        flags = validate(invoice)
        row = {"source_file": path.name}
        row.update({name: getattr(invoice, name).value for name in FIELDS})

        if needs_review(flags):
            review_items.append({
                "source_file": path.name,
                "flags": [asdict(f) for f in flags],
                "extracted": invoice.model_dump(),
            })
            blockers = sum(1 for f in flags if f.severity == "block")
            print(f"  REVIEW  {path.name}  ({blockers} blocking)")
            for f in flags:
                if f.severity == "block":
                    print(f"            - {f.field}: {f.message[:78]}")
        else:
            clean_rows.append(row)
            print(f"  CLEAN   {path.name}")

    if clean_rows:
        with (OUT / "clean.csv").open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=["source_file", *FIELDS])
            writer.writeheader()
            writer.writerows(clean_rows)

    (OUT / "review_queue.json").write_text(
        json.dumps(review_items, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    total = len(clean_rows) + len(review_items)
    rate = (len(clean_rows) / total * 100) if total else 0.0
    print(f"\n{total} document(s): {len(clean_rows)} clean, "
          f"{len(review_items)} need review  ({rate:.0f}% straight-through)")
    print(f"Spent this run: ${spent:.4f}"
          + ("  (rest served from cache)" if spent == 0 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
