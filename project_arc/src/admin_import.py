"""Admin tooling for bulk employee roster import."""

from __future__ import annotations

import csv
from pathlib import Path

from src.database import DatabaseManager


def import_employee_roster(db_manager: DatabaseManager, csv_path: Path) -> dict[str, int]:
    """Import or update employee rows from a CSV file.

    CSV header must include: employee_id, first_name, last_name
    Returns a summary with inserted/updated/skipped counts.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Roster file not found: {csv_path}")

    inserted = 0
    updated = 0
    skipped = 0

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            employee_id_raw = (row.get("employee_id") or "").strip()
            first_name = (row.get("first_name") or "").strip()
            last_name = (row.get("last_name") or "").strip()

            if not employee_id_raw.isdigit() or not first_name or not last_name:
                skipped += 1
                continue

            employee_id = int(employee_id_raw)
            existing = db_manager.fetch_employee(employee_id)

            db_manager.upsert_employee(employee_id, first_name, last_name)

            if existing is None:
                inserted += 1
            else:
                updated += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
    }
