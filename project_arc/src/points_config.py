"""Runtime config loader for ARC points settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import configparser

from src.points_engine import PointsConfigError


DEFAULT_CALLOUTS_PER_POINT = 3


@dataclass(frozen=True)
class PointsConfig:
    """Points feature configuration loaded from config.ini."""

    callouts_per_point: int = DEFAULT_CALLOUTS_PER_POINT


_DEFAULT_CONFIG_TEXT = """[PointsSystem]\ncallouts_per_point = 3\n"""


def ensure_config_file(config_path: Path) -> None:
    """Create a default config.ini when missing."""
    if config_path.exists():
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_DEFAULT_CONFIG_TEXT, encoding="utf-8")


def load_points_config(config_path: Path) -> PointsConfig:
    """Load points configuration from config.ini using configparser."""
    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")

    if not parser.has_section("PointsSystem"):
        return PointsConfig()

    raw_value = parser.get("PointsSystem", "callouts_per_point", fallback=str(DEFAULT_CALLOUTS_PER_POINT))

    try:
        callouts_per_point = int(raw_value)
    except ValueError as exc:
        raise PointsConfigError("callouts_per_point must be an integer") from exc

    if callouts_per_point <= 0:
        raise PointsConfigError("callouts_per_point must be greater than zero")

    return PointsConfig(callouts_per_point=callouts_per_point)
