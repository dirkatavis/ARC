"""Developer utility: adjust the ARC trial age for manual testing.

Sets the recorded install_date in sys_entitlement so the entitlement engine
sees the installation as N days old.  Use this to simulate any trial state
without waiting real time.

Examples
--------
Simulate day 0 (brand new install):
    python tools/ArcTrialPeriodAdjuster.py --days 0

Simulate day 10 (5 days remaining in a 15-day trial):
    python tools/ArcTrialPeriodAdjuster.py --days 10

Simulate an expired trial (16 days elapsed):
    python tools/ArcTrialPeriodAdjuster.py --days 16

Use a specific database file:
    python tools/ArcTrialPeriodAdjuster.py --days 10 --db path/to/arc_data.db
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _default_db_path() -> Path:
    """Mirror the runtime DB path logic from src/ui.py."""
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "ARC" / "data" / "arc_data.db"
    return Path.home() / "AppData" / "Local" / "ARC" / "data" / "arc_data.db"


def set_trial_age(db_path: Path, days: int) -> None:
    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        print("Launch ARC once to create it, or pass --db with the correct path.")
        sys.exit(1)

    install_date = (date.today() - timedelta(days=days)).isoformat()

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT id FROM sys_entitlement WHERE id = 1").fetchone()
        if row is None:
            print("ERROR: sys_entitlement row not found. Launch ARC once to initialise it.")
            sys.exit(1)

        conn.execute(
            "UPDATE sys_entitlement SET install_date = ? WHERE id = 1",
            (install_date,),
        )
        conn.commit()
    finally:
        conn.close()

    from project_arc.src.entitlement import TRIAL_DAYS
    days_remaining = max(0, TRIAL_DAYS - days)
    if days > TRIAL_DAYS:
        state = "EXPIRED"
    elif days == TRIAL_DAYS:
        state = "EXPIRED (boundary – exactly at limit)"
    else:
        state = f"TRIAL ({days_remaining} day{'s' if days_remaining != 1 else ''} remaining)"

    print(f"Database : {db_path}")
    print(f"install_date set to : {install_date}  ({days} day{'s' if days != 1 else ''} ago)")
    print(f"Effective state     : {state}")
    print()
    print("Relaunch ARC to see the updated entitlement state.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set the ARC trial age (days elapsed since install) for manual testing."
    )
    parser.add_argument(
        "--days",
        type=int,
        required=True,
        help="Number of days to simulate since installation (0 = brand new, 16+ = expired).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to arc_data.db. Defaults to the standard runtime location.",
    )
    args = parser.parse_args()

    if args.days < 0:
        parser.error("--days must be 0 or greater.")

    db_path = args.db if args.db is not None else _default_db_path()
    set_trial_age(db_path, args.days)


if __name__ == "__main__":
    main()
