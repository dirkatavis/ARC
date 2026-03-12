"""CLI utility for ARC admin roster CSV import."""

from __future__ import annotations

import argparse
from importlib import import_module
import sqlite3
from pathlib import Path
import sys
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_import_dependencies() -> tuple[type[Any], Callable[[Any, Path], dict[str, int]]]:
    database_module = import_module("src.database")
    admin_import_module = import_module("src.admin_import")
    return database_module.DatabaseManager, admin_import_module.import_employee_roster


def main() -> int:
    """Import a roster CSV into the target ARC SQLite database."""
    database_manager_class, import_employee_roster = _load_import_dependencies()

    parser = argparse.ArgumentParser(description="Import employee roster CSV into ARC database")
    parser.add_argument("--db", required=True, help="Path to SQLite database file")
    parser.add_argument("--csv", required=True, help="Path to roster CSV file")
    args = parser.parse_args()

    db_path = Path(args.db)
    csv_path = Path(args.csv)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    manager = database_manager_class(connection)
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
