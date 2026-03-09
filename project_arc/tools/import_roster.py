"""CLI utility for ARC admin roster CSV import."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from src.admin_import import import_employee_roster
from src.database import DatabaseManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Import employee roster CSV into ARC database")
    parser.add_argument("--db", required=True, help="Path to SQLite database file")
    parser.add_argument("--csv", required=True, help="Path to roster CSV file")
    args = parser.parse_args()

    db_path = Path(args.db)
    csv_path = Path(args.csv)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    manager = DatabaseManager(connection)
    manager.initialize_schema()

    result = import_employee_roster(manager, csv_path)
    connection.close()

    print(
        "Import complete: "
        f"inserted={result['inserted']} "
        f"updated={result['updated']} "
        f"skipped={result['skipped']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
