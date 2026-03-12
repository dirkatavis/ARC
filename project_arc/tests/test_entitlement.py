"""Unit tests for the ARC EntitlementEngine (Module 07)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from src.entitlement import (
    TRIAL_DAYS,
    EntitlementEngine,
    EntitlementState,
    generate_license_key,
    verify_license_key,
)


# ── Fixtures ───────────────────────────────────────────────────────────────


def _make_engine(machine_id: str = "TEST-MACHINE-001") -> tuple[sqlite3.Connection, EntitlementEngine]:
    """Return a fresh in-memory entitlement engine with a deterministic machine ID."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    engine = EntitlementEngine(conn, machine_id=machine_id)
    return conn, engine


def _backdate_install(conn: sqlite3.Connection, days: int) -> None:
    """Rewrite install_date to simulate *days* elapsed since installation."""
    past_date = (date.today() - timedelta(days=days)).isoformat()
    conn.execute("UPDATE sys_entitlement SET install_date = ? WHERE id = 1", (past_date,))
    conn.commit()


# ── Key derivation tests ───────────────────────────────────────────────────


def test_generate_license_key_produces_hyphenated_12_char_format() -> None:
    key = generate_license_key("MACHINE-A")
    parts = key.split("-")
    assert len(parts) == 3, "Expected XXXX-XXXX-XXXX format"
    assert all(len(p) == 4 for p in parts)
    assert key == key.upper()


def test_generate_license_key_is_deterministic() -> None:
    key1 = generate_license_key("MACHINE-B")
    key2 = generate_license_key("MACHINE-B")
    assert key1 == key2


def test_generate_license_key_differs_per_machine() -> None:
    key_a = generate_license_key("MACHINE-A")
    key_b = generate_license_key("MACHINE-B")
    assert key_a != key_b


def test_verify_license_key_accepts_valid_key() -> None:
    machine_id = "MACHINE-VALID-001"
    key = generate_license_key(machine_id)
    assert verify_license_key(machine_id, key) is True


def test_verify_license_key_accepts_key_without_hyphens() -> None:
    machine_id = "MACHINE-NOHYPHEN"
    key = generate_license_key(machine_id).replace("-", "")
    assert verify_license_key(machine_id, key) is True


def test_verify_license_key_is_case_insensitive() -> None:
    machine_id = "MACHINE-CASE"
    key = generate_license_key(machine_id).lower()
    assert verify_license_key(machine_id, key) is True


def test_verify_license_key_rejects_wrong_machine() -> None:
    key_for_a = generate_license_key("MACHINE-A")
    assert verify_license_key("MACHINE-B", key_for_a) is False


def test_verify_license_key_rejects_garbage_input() -> None:
    assert verify_license_key("MACHINE-X", "XXXX-XXXX-XXXX") is False
    assert verify_license_key("MACHINE-X", "") is False
    assert verify_license_key("MACHINE-X", "BAD") is False


# ── State machine: TRIAL ───────────────────────────────────────────────────


def test_fresh_installation_starts_in_trial_state() -> None:
    _conn, engine = _make_engine()
    assert engine.get_state() == EntitlementState.TRIAL


def test_trial_state_within_15_days() -> None:
    conn, engine = _make_engine()
    _backdate_install(conn, TRIAL_DAYS - 1)
    assert engine.get_state() == EntitlementState.TRIAL


def test_trial_days_remaining_counts_down() -> None:
    conn, engine = _make_engine()
    _backdate_install(conn, 5)
    assert engine.days_remaining() == TRIAL_DAYS - 5


# ── State machine: EXPIRED ─────────────────────────────────────────────────


def test_state_expires_after_trial_period() -> None:
    conn, engine = _make_engine()
    _backdate_install(conn, TRIAL_DAYS + 1)
    assert engine.get_state() == EntitlementState.EXPIRED


def test_state_exactly_one_day_after_trial_is_expired() -> None:
    conn, engine = _make_engine()
    _backdate_install(conn, TRIAL_DAYS + 1)
    assert engine.get_state() == EntitlementState.EXPIRED


def test_days_remaining_is_zero_when_expired() -> None:
    conn, engine = _make_engine()
    _backdate_install(conn, TRIAL_DAYS + 5)
    assert engine.days_remaining() == 0


# ── State machine: LICENSED ────────────────────────────────────────────────


def test_activate_with_valid_key_returns_true() -> None:
    machine_id = "LICENSE-MACHINE-001"
    _conn, engine = _make_engine(machine_id=machine_id)
    key = generate_license_key(machine_id)
    assert engine.activate(key) is True


def test_state_becomes_licensed_after_activation() -> None:
    machine_id = "LICENSE-MACHINE-002"
    _conn, engine = _make_engine(machine_id=machine_id)
    key = generate_license_key(machine_id)
    engine.activate(key)
    assert engine.get_state() == EntitlementState.LICENSED


def test_licensed_state_bypasses_date_check() -> None:
    """A licensed app must stay LICENSED regardless of elapsed days."""
    machine_id = "LICENSE-MACHINE-003"
    conn, engine = _make_engine(machine_id=machine_id)
    key = generate_license_key(machine_id)
    engine.activate(key)
    _backdate_install(conn, TRIAL_DAYS + 100)  # far into the future
    assert engine.get_state() == EntitlementState.LICENSED


def test_activate_from_expired_state_transitions_to_licensed() -> None:
    machine_id = "LICENSE-MACHINE-004"
    conn, engine = _make_engine(machine_id=machine_id)
    _backdate_install(conn, TRIAL_DAYS + 10)
    assert engine.get_state() == EntitlementState.EXPIRED

    key = generate_license_key(machine_id)
    result = engine.activate(key)

    assert result is True
    assert engine.get_state() == EntitlementState.LICENSED


# ── Security: activation failure ──────────────────────────────────────────


def test_activate_with_invalid_key_returns_false() -> None:
    _conn, engine = _make_engine(machine_id="MACHINE-INVALID")
    assert engine.activate("XXXX-XXXX-XXXX") is False


def test_state_unchanged_after_failed_activation() -> None:
    conn, engine = _make_engine(machine_id="MACHINE-UNCHANGED")
    _backdate_install(conn, TRIAL_DAYS + 1)
    engine.activate("XXXX-XXXX-XXXX")  # invalid key
    assert engine.get_state() == EntitlementState.EXPIRED


# ── Security: database copy prevention ────────────────────────────────────


def test_key_from_machine_a_rejected_on_machine_b() -> None:
    """Acceptance criterion 2: a key for Computer A is rejected by Computer B."""
    key_for_a = generate_license_key("MACHINE-A")
    assert verify_license_key("MACHINE-B", key_for_a) is False


def test_licensed_db_copied_to_other_machine_reverts_to_expired() -> None:
    """A licensed database moved to a different machine must revert to EXPIRED."""
    machine_a_id = "ORIGINAL-MACHINE-A"
    conn, engine_a = _make_engine(machine_id=machine_a_id)
    key = generate_license_key(machine_a_id)
    engine_a.activate(key)
    assert engine_a.get_state() == EntitlementState.LICENSED

    # Simulate opening the same DB file on a different machine.
    engine_b = EntitlementEngine(conn, machine_id="DIFFERENT-MACHINE-B")
    assert engine_b.get_state() == EntitlementState.EXPIRED


# ── Schema initialisation ──────────────────────────────────────────────────


def test_sys_entitlement_table_created_on_init() -> None:
    conn, _engine = _make_engine()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sys_entitlement'"
    ).fetchall()
    assert rows, "sys_entitlement table must be created"


def test_entitlement_record_has_install_date_and_machine_id() -> None:
    machine_id = "SCHEMA-TEST-MACHINE"
    conn, _engine = _make_engine(machine_id=machine_id)
    row = conn.execute(
        "SELECT install_date, machine_id, is_licensed FROM sys_entitlement WHERE id = 1"
    ).fetchone()
    assert row is not None
    assert row["install_date"] == date.today().isoformat()
    assert row["machine_id"] == machine_id
    assert row["is_licensed"] == 0


def test_second_engine_reuses_existing_record() -> None:
    """A second EntitlementEngine on the same connection must not overwrite the record."""
    conn, _engine1 = _make_engine(machine_id="PERSISTENT-MACHINE")
    _backdate_install(conn, 3)

    engine2 = EntitlementEngine(conn, machine_id="PERSISTENT-MACHINE")
    row = conn.execute("SELECT install_date FROM sys_entitlement WHERE id = 1").fetchone()
    expected_date = (date.today() - timedelta(days=3)).isoformat()
    assert row["install_date"] == expected_date, "Existing install_date must not be overwritten"
