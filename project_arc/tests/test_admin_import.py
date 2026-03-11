"""TDD tests for admin roster CSV import utility."""

# pylint: disable=redefined-outer-name

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.admin_import import import_employee_roster
from src.database import DatabaseManager


@pytest.fixture
def db_manager() -> DatabaseManager:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    manager = DatabaseManager(connection)
    manager.initialize_schema()
    yield manager
    connection.close()


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_import_roster_inserts_new_employees(tmp_path: Path, db_manager: DatabaseManager) -> None:
    csv_path = tmp_path / "roster.csv"
    _write_csv(
        csv_path,
        "employee_id,first_name,last_name\n1001,Ari,Cole\n1002,Nia,Bishop\n",
    )

    result = import_employee_roster(db_manager, csv_path)

    assert result == {"inserted": 2, "updated": 0, "skipped": 0}
    employee = db_manager.fetch_employee(1002)
    assert employee is not None
    assert employee["first_name"] == "Nia"


def test_import_roster_updates_existing_employee(tmp_path: Path, db_manager: DatabaseManager) -> None:
    db_manager.insert_employee(1001, "Ari", "Cole")

    csv_path = tmp_path / "roster.csv"
    _write_csv(
        csv_path,
        "employee_id,first_name,last_name\n1001,Ariana,Coleman\n",
    )

    result = import_employee_roster(db_manager, csv_path)

    assert result == {"inserted": 0, "updated": 1, "skipped": 0}
    employee = db_manager.fetch_employee(1001)
    assert employee is not None
    assert employee["first_name"] == "Ariana"
    assert employee["last_name"] == "Coleman"


def test_import_roster_skips_invalid_rows(tmp_path: Path, db_manager: DatabaseManager) -> None:
    csv_path = tmp_path / "roster.csv"
    _write_csv(
        csv_path,
        "employee_id,first_name,last_name\nabc,Ari,Cole\n1003,,Bishop\n1004,Ray,Holt\n",
    )

    result = import_employee_roster(db_manager, csv_path)

    assert result == {"inserted": 1, "updated": 0, "skipped": 2}
    assert db_manager.fetch_employee(1004) is not None
    assert db_manager.fetch_employee(1003) is None


def test_import_roster_raises_for_missing_csv(db_manager: DatabaseManager) -> None:
    with pytest.raises(FileNotFoundError):
        import_employee_roster(db_manager, Path("missing_roster.csv"))
