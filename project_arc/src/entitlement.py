"""Entitlement Engine for ARC – Module 07: License Fulfillment & Activation.

Implements a Hardware-Locked Challenge-Response licensing model with three
states: TRIAL, EXPIRED, and LICENSED.
"""

from __future__ import annotations

import hashlib
import hmac
import platform
import sqlite3
import uuid
from datetime import date
from enum import Enum
from pathlib import Path


TRIAL_DAYS = 15

# Internal validation constant – used to bind license keys to machine IDs.
_SALT = b"ARC-7f3a9d2c-LIC-4e8b1f6a"


class EntitlementState(Enum):
    """Possible license states for an ARC installation."""

    TRIAL = "TRIAL"
    EXPIRED = "EXPIRED"
    LICENSED = "LICENSED"


# ── Machine fingerprinting ─────────────────────────────────────────────────


def get_machine_id() -> str:
    """Return a stable, unique machine identifier.

    On Windows, derives the ID from the Windows MachineGUID registry value.
    On other platforms, falls back to a persistent UUID written to the user's
    home directory so the ID survives application updates.
    """
    if platform.system() == "Windows":
        try:
            import winreg  # noqa: PLC0415 – Windows only

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            return str(value).upper()
        except Exception:  # noqa: BLE001
            pass

    # Cross-platform fallback: persistent UUID file.
    uuid_path = Path.home() / ".arc_machine_id"
    if uuid_path.exists():
        stored = uuid_path.read_text().strip()
        if stored:
            return stored.upper()

    new_id = str(uuid.uuid4()).upper()
    uuid_path.write_text(new_id)
    return new_id


# ── Key derivation ─────────────────────────────────────────────────────────


def _derive_key_chars(machine_id: str) -> str:
    """Return the 12 uppercase hex chars used to form a license key."""
    digest = hmac.new(
        _SALT,
        machine_id.upper().encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return digest[:12].upper()


def generate_license_key(machine_id: str) -> str:
    """Generate the activation key for *machine_id* (developer utility).

    Output format: ``A1B2-C3D4-E5F6`` (12 alphanumeric chars, hyphenated).
    """
    chars = _derive_key_chars(machine_id)
    return f"{chars[:4]}-{chars[4:8]}-{chars[8:12]}"


def verify_license_key(machine_id: str, key: str) -> bool:
    """Return ``True`` when *key* is the valid activation key for *machine_id*."""
    normalized = key.upper().replace("-", "")
    if len(normalized) != 12:
        return False
    expected = _derive_key_chars(machine_id)
    return hmac.compare_digest(expected, normalized)


# ── Entitlement Engine ─────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sys_entitlement (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    install_date  TEXT    NOT NULL,
    machine_id    TEXT    NOT NULL,
    is_licensed   INTEGER NOT NULL DEFAULT 0,
    license_key   TEXT
);
"""


class EntitlementEngine:
    """Manages the ARC license lifecycle for a single SQLite database.

    State transitions
    -----------------
    UNINITIALIZED → TRIAL    : first launch; install_date and machine_id written.
    TRIAL         → EXPIRED  : more than ``TRIAL_DAYS`` days have elapsed.
    EXPIRED       → LICENSED : a valid activation key is entered.
    TRIAL         → LICENSED : a valid activation key is entered early.
    LICENSED      → EXPIRED  : stored key does not match current machine ID
                               (database copied to another computer).
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        machine_id: str | None = None,
    ) -> None:
        self.connection = connection
        self._machine_id: str = machine_id if machine_id is not None else get_machine_id()
        self._initialize_schema()
        self._initialize_record()

    # ── Internal helpers ───────────────────────────────────────────────────

    def _initialize_schema(self) -> None:
        self.connection.executescript(_SCHEMA_SQL)
        self.connection.commit()

    def _initialize_record(self) -> None:
        """Write the entitlement row on first launch."""
        row = self.connection.execute(
            "SELECT id FROM sys_entitlement WHERE id = 1"
        ).fetchone()
        if row is None:
            today = date.today().isoformat()
            self.connection.execute(
                """
                INSERT INTO sys_entitlement (id, install_date, machine_id, is_licensed)
                VALUES (1, ?, ?, 0)
                """,
                (today, self._machine_id),
            )
            self.connection.commit()

    # ── Public interface ───────────────────────────────────────────────────

    @property
    def machine_id(self) -> str:
        """Return the hardware fingerprint for this installation."""
        return self._machine_id

    def get_state(self) -> EntitlementState:
        """Compute and return the current entitlement state.

        Re-verifies any stored license key against the current machine ID on
        every call, preventing database-copy piracy.
        """
        row = self.connection.execute(
            "SELECT install_date, is_licensed, license_key FROM sys_entitlement WHERE id = 1"
        ).fetchone()

        if row is None:
            return EntitlementState.EXPIRED

        install_date_str, is_licensed_int, license_key = row[0], row[1], row[2]

        if is_licensed_int and license_key:
            # Security: re-validate key against current hardware on every boot.
            if verify_license_key(self._machine_id, str(license_key)):
                return EntitlementState.LICENSED
            # Key mismatch – database was moved to a different machine.
            return EntitlementState.EXPIRED

        try:
            install_date = date.fromisoformat(str(install_date_str))
        except ValueError:
            return EntitlementState.EXPIRED

        days_elapsed = (date.today() - install_date).days
        if days_elapsed > TRIAL_DAYS:
            return EntitlementState.EXPIRED
        return EntitlementState.TRIAL

    def days_remaining(self) -> int:
        """Return the number of full trial days remaining (0 when expired)."""
        row = self.connection.execute(
            "SELECT install_date, is_licensed FROM sys_entitlement WHERE id = 1"
        ).fetchone()
        if row is None:
            return 0
        install_date_str, is_licensed_int = row[0], row[1]
        if is_licensed_int:
            return TRIAL_DAYS  # licensed – show max
        try:
            install_date = date.fromisoformat(str(install_date_str))
        except ValueError:
            return 0
        elapsed = (date.today() - install_date).days
        return max(0, TRIAL_DAYS - elapsed)

    def activate(self, key: str) -> bool:
        """Attempt to activate the license with *key*.

        Returns ``True`` on success; ``False`` when the key is invalid.
        The method is deliberately silent about *why* the key failed.
        """
        if not verify_license_key(self._machine_id, key):
            return False

        normalized = key.upper().replace("-", "")
        formatted = f"{normalized[:4]}-{normalized[4:8]}-{normalized[8:12]}"
        self.connection.execute(
            "UPDATE sys_entitlement SET is_licensed = 1, license_key = ? WHERE id = 1",
            (formatted,),
        )
        self.connection.commit()
        return True
