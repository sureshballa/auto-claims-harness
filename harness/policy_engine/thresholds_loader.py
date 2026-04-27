"""Tier thresholds loader for the auto-claims harness.

Reads tier threshold configuration from a YAML file (typically
config/thresholds.yaml), validates it strictly, and returns a frozen
TierThresholds instance. Intended to be called once at process startup;
the loader treats the file as a snapshot. To change thresholds, edit the
file and restart the process — there is no hot-reload.

Design choice: the loader is a pure function from path to TierThresholds.
Caching, singletons, and reload schedules are the caller's concern.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import ValidationError

from domain.tiers import TierThresholds

_REQUIRED_KEYS = frozenset({"green_max_damage", "yellow_max_damage", "red_max_damage"})


class ThresholdsConfigError(ValueError):
    """Raised when the thresholds YAML file is malformed, missing required
    keys, contains unexpected keys, or fails schema validation (e.g.,
    non-ascending thresholds).
    """


def load_thresholds(path: Path | str) -> TierThresholds:
    """Load tier thresholds from a YAML file.

    Args:
        path: Path to the YAML file (typically config/thresholds.yaml).

    Returns:
        A frozen TierThresholds instance.

    Raises:
        FileNotFoundError: if the file does not exist.
        ThresholdsConfigError: if the YAML is malformed, missing required
            keys, contains unexpected keys, or fails Pydantic validation.
    """
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Thresholds file not found: {resolved}")

    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ThresholdsConfigError(f"Malformed YAML in {resolved}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ThresholdsConfigError(
            f"Expected a YAML mapping in {resolved}, got {type(raw).__name__}"
        )

    present = frozenset(raw.keys())
    missing = _REQUIRED_KEYS - present
    if missing:
        raise ThresholdsConfigError(
            f"Missing required key(s) in {resolved}: {', '.join(sorted(missing))}"
        )

    unexpected = present - _REQUIRED_KEYS
    if unexpected:
        raise ThresholdsConfigError(
            f"Unexpected key(s) in {resolved}: {', '.join(sorted(unexpected))} "
            f"(valid keys: {', '.join(sorted(_REQUIRED_KEYS))})"
        )

    decimals: dict[str, Decimal] = {}
    for key in _REQUIRED_KEYS:
        value = raw[key]
        if not isinstance(value, (int, float)):
            raise ThresholdsConfigError(
                f"Key {key!r} in {resolved} must be a number, got {type(value).__name__}"
            )
        # String conversion preserves the written value without float precision artifacts.
        decimals[key] = Decimal(str(value))

    try:
        return TierThresholds(
            green_max_damage=decimals["green_max_damage"],
            yellow_max_damage=decimals["yellow_max_damage"],
            red_max_damage=decimals["red_max_damage"],
        )
    except ValidationError as exc:
        raise ThresholdsConfigError(
            f"Threshold values in {resolved} failed validation: {exc}"
        ) from exc
