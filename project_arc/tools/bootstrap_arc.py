"""Bootstrap ARC for first-time local setup.

This script installs runtime dependencies, initializes the database,
optionally seeds sample data, and can launch the desktop UI.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database import DatabaseManager


def _run_command(args: list[str]) -> None:
    subprocess.run(args, check=True)


def install_runtime_dependencies() -> None:
    requirements_file = PROJECT_ROOT / "requirements.txt"
    if not requirements_file.exists():
        raise FileNotFoundError(f"Missing requirements file: {requirements_file}")

    print("[ARC] Installing runtime dependencies...")
    _run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    _run_command([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)])


def initialize_database(db_path: Path) -> None:
    print(f"[ARC] Initializing database at {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        db = DatabaseManager(connection)
        db.initialize_schema()
    finally:
        connection.close()


def seed_sample_data(db_path: Path, reset: bool) -> None:
    print("[ARC] Seeding sample data...")
    from tools.seed_sample_data import seed_database

    result = seed_database(db_path=db_path, reset=reset)
    print(
        "[ARC] Seed complete: "
        f"employees={result['total_employees']} "
        f"call_outs={result['total_call_outs']}"
    )


def launch_arc() -> int:
    print("[ARC] Launching ARC...")
    run = subprocess.run([sys.executable, str(PROJECT_ROOT / "main.py")])
    return int(run.returncode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="First-run setup for ARC desktop app")
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "data" / "arc_data.db"),
        help="Path to SQLite DB file (default: project_arc/data/arc_data.db)",
    )
    parser.add_argument(
        "--seed-sample-data",
        action="store_true",
        help="Seed database with demo employees and call-outs",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset employees/call_outs before sample seeding",
    )
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Launch ARC after setup",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)

    try:
        install_runtime_dependencies()
        initialize_database(db_path=db_path)
        if args.seed_sample_data:
            seed_sample_data(db_path=db_path, reset=args.reset)
        if args.launch:
            return launch_arc()
    except subprocess.CalledProcessError as exc:
        print(f"[ARC] Command failed with exit code {exc.returncode}")
        return int(exc.returncode)
    except Exception as exc:  # defensive top-level error boundary
        print(f"[ARC] Setup failed: {exc}")
        return 1

    print("[ARC] Setup complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
