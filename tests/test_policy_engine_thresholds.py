"""Tests for harness/policy_engine/thresholds_loader.py.

Unit tests use tmp_path-isolated YAML fixtures; they never read
config/thresholds.yaml. One integration test at the end verifies the
real product config file remains parseable.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from harness.policy_engine import ThresholdsConfigError, load_thresholds

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_YAML = """\
green_max_damage: 500
yellow_max_damage: 5000
red_max_damage: 25000
"""


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Unit tests — all use tmp_path, never config/thresholds.yaml
# ---------------------------------------------------------------------------


def test_loads_valid_thresholds(tmp_path: Path) -> None:
    """A well-formed ascending YAML produces the correct frozen TierThresholds."""
    f = _write(tmp_path / "thresholds.yaml", _VALID_YAML)
    t = load_thresholds(f)

    assert t.green_max_damage == Decimal("500")
    assert t.yellow_max_damage == Decimal("5000")
    assert t.red_max_damage == Decimal("25000")


def test_rejects_missing_file(tmp_path: Path) -> None:
    """A path that does not exist raises FileNotFoundError with the path in the message."""
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError) as exc_info:
        load_thresholds(missing)

    assert str(missing.resolve()) in str(exc_info.value)


def test_rejects_non_dict_yaml(tmp_path: Path) -> None:
    """A YAML list is not a valid thresholds mapping."""
    f = _write(tmp_path / "thresholds.yaml", "- foo\n- bar\n")
    with pytest.raises(ThresholdsConfigError):
        load_thresholds(f)


def test_rejects_missing_required_key(tmp_path: Path) -> None:
    """YAML that omits red_max_damage raises ThresholdsConfigError naming the missing key."""
    f = _write(tmp_path / "thresholds.yaml", "green_max_damage: 500\nyellow_max_damage: 5000\n")
    with pytest.raises(ThresholdsConfigError) as exc_info:
        load_thresholds(f)

    assert "red_max_damage" in str(exc_info.value)


def test_rejects_unexpected_key(tmp_path: Path) -> None:
    """An unrecognised key raises ThresholdsConfigError naming the offending key."""
    yaml = _VALID_YAML + "purple_max_damage: 100\n"
    f = _write(tmp_path / "thresholds.yaml", yaml)
    with pytest.raises(ThresholdsConfigError) as exc_info:
        load_thresholds(f)

    assert "purple_max_damage" in str(exc_info.value)


def test_rejects_non_ascending(tmp_path: Path) -> None:
    """Thresholds where yellow < green violate the strictly-ascending constraint."""
    yaml = "green_max_damage: 5000\nyellow_max_damage: 500\nred_max_damage: 25000\n"
    f = _write(tmp_path / "thresholds.yaml", yaml)
    with pytest.raises(ThresholdsConfigError):
        load_thresholds(f)


def test_rejects_negative_value(tmp_path: Path) -> None:
    """A negative threshold value is not a meaningful tier boundary."""
    yaml = "green_max_damage: -500\nyellow_max_damage: 5000\nred_max_damage: 25000\n"
    f = _write(tmp_path / "thresholds.yaml", yaml)
    with pytest.raises(ThresholdsConfigError):
        load_thresholds(f)


# ---------------------------------------------------------------------------
# Integration test — reads the real product config
# ---------------------------------------------------------------------------


def test_loads_real_config_file() -> None:
    """The product config/thresholds.yaml must remain parseable and produce positive values."""
    real_config = Path(__file__).parent.parent / "config" / "thresholds.yaml"
    t = load_thresholds(real_config)

    assert t.green_max_damage >= Decimal("0")
    assert t.yellow_max_damage >= Decimal("0")
    assert t.red_max_damage >= Decimal("0")
