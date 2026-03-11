"""CLI utility for ARC admin roster CSV import."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from project_arc.src.admin_import import import_employee_roster
from project_arc.src.database import DatabaseManager


def main() -> int:
    """Import a roster CSV into the target ARC SQLite database."""
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
