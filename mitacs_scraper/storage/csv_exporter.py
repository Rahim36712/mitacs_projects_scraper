"""
CSV/JSON export helpers.
"""
from typing import List, Dict
import csv
import json


def export_csv(records: List[Dict], path: str, fieldnames: List[str] = None) -> None:
    if not records:
        # create an empty file with headers if provided
        if fieldnames:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
        else:
            open(path, "w", encoding="utf-8").close()
        return

    if not fieldnames:
        # use keys from first record
        fieldnames = list(records[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow({k: (v if v is not None else "") for k, v in r.items()})


def export_json(records: List[Dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
