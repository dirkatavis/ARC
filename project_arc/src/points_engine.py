"""Core points calculation logic for ARC."""

from __future__ import annotations

from dataclasses import dataclass


class PointsConfigError(ValueError):
    """Raised when points configuration is invalid."""


@dataclass(frozen=True)
class PointAwardEvent:
    """Represents a single awarded point event."""

    awarded_point_number: int
    callout_count_at_award: int
    awarded_at: str


def calculate_points(total_callouts: int, callouts_per_point: int) -> int:
    """Return total points earned from total call-outs.

    Args:
        total_callouts: Running call-out count for an employee.
        callouts_per_point: Number of call-outs required to earn one point.

    Returns:
        Integer total points earned.

    Raises:
        PointsConfigError: If callouts_per_point is not a positive integer.
    """
    if callouts_per_point <= 0:
        raise PointsConfigError("callouts_per_point must be greater than zero")
    if total_callouts <= 0:
        return 0
    return total_callouts // callouts_per_point


def build_incremental_award_events(
    previous_total_points: int,
    new_total_points: int,
    callouts_per_point: int,
    awarded_at: str,
) -> list[PointAwardEvent]:
    """Build award events for newly crossed point thresholds."""
    if new_total_points <= previous_total_points:
        return []

    events: list[PointAwardEvent] = []
    for point_number in range(previous_total_points + 1, new_total_points + 1):
        events.append(
            PointAwardEvent(
                awarded_point_number=point_number,
                callout_count_at_award=point_number * callouts_per_point,
                awarded_at=awarded_at,
            )
        )
    return events
