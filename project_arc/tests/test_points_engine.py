"""Unit tests for ARC points calculation logic."""

from __future__ import annotations

import pytest

from src.points_engine import PointsConfigError, build_incremental_award_events, calculate_points


def test_zero_callouts_returns_zero_points() -> None:
    assert calculate_points(total_callouts=0, callouts_per_point=3) == 0


def test_exact_threshold_awards_one_point() -> None:
    assert calculate_points(total_callouts=3, callouts_per_point=3) == 1


def test_below_threshold_awards_no_points() -> None:
    assert calculate_points(total_callouts=2, callouts_per_point=3) == 0


def test_multiple_thresholds_accumulate_correctly() -> None:
    assert calculate_points(total_callouts=9, callouts_per_point=3) == 3


def test_non_divisible_callouts_floor_correctly() -> None:
    assert calculate_points(total_callouts=8, callouts_per_point=3) == 2


def test_points_are_cumulative_across_sessions() -> None:
    previous_total_points = calculate_points(total_callouts=3, callouts_per_point=3)
    assert previous_total_points == 1

    new_total_points = calculate_points(total_callouts=8, callouts_per_point=3)
    assert new_total_points == 2

    awards = build_incremental_award_events(
        previous_total_points=previous_total_points,
        new_total_points=new_total_points,
        callouts_per_point=3,
        awarded_at="2026-03-13 09:00:00",
    )
    assert len(awards) == 1
    assert awards[0].awarded_point_number == 2
    assert awards[0].callout_count_at_award == 6


def test_config_change_recalculates_correctly() -> None:
    # Same callout total with different config yields different totals.
    assert calculate_points(total_callouts=9, callouts_per_point=3) == 3
    assert calculate_points(total_callouts=9, callouts_per_point=4) == 2


def test_invalid_callouts_per_point_raises_config_error() -> None:
    with pytest.raises(PointsConfigError):
        calculate_points(total_callouts=3, callouts_per_point=0)
