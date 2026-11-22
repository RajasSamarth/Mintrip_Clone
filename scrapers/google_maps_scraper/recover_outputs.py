"""Recover deleted outputs from Apify local storage.

Reads business records from storage/datasets/default/*.json and re-exports
them to output/ as CSV and XLSX using the project's own exporters.
Also copies storage/key_value_stores/default/OUTPUT.xlsx to output/.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.services.csv_exporter import export_to_csv
from app.services.excel_exporter import export_to_excel
from app.schemas import BusinessRecord, SearchInfo

ROOT = Path(__file__).resolve().parent
DATASET_DIR = ROOT / "storage" / "datasets" / "default"
KVSTORE_DIR = ROOT / "storage" / "key_value_stores" / "default"
OUTPUT_DIR = ROOT / "output"


def load_records() -> list[BusinessRecord]:
    records: list[BusinessRecord] = []
    for path in sorted(DATASET_DIR.glob("*.json")):
        if path.name == "__metadata__.json":
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        records.append(BusinessRecord(**data))
    return records


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = load_records()
    print(f"Found {len(records)} records in storage/datasets/default/")
    if not records:
        print("Nothing to recover.")
        return

    search_info = SearchInfo(
        query="recovered",
        location="recovered_from_storage",
        timestamp="2026-10-17",
        total_results=len(records),
    )

    csv_path = export_to_csv(records, search_info, output_dir=OUTPUT_DIR)
    xlsx_path = export_to_excel(records, search_info, output_dir=OUTPUT_DIR)
    print("Wrote CSV :", csv_path)
    print("Wrote XLSX:", xlsx_path)

    # Also recover the Apify OUTPUT.xlsx (the "@output" key) if present.
    src_xlsx = KVSTORE_DIR / "OUTPUT.xlsx"
    if src_xlsx.exists():
        dst = OUTPUT_DIR / "RECOVERED_OUTPUT.xlsx"
        shutil.copy2(src_xlsx, dst)
        print("Copied Apify OUTPUT.xlsx ->", dst)


if __name__ == "__main__":
    main()
