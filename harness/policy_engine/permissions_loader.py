"""Permissions config loader for the auto-claims harness.

Reads harness policy from a YAML file (typically config/permissions.yaml),
validates it strictly at every level, and returns frozen Pydantic models.
Intended to be called once at process startup — a load-once snapshot.

Two kinds of policy live here:
  tier_authority       — which decisions each tier permits the model to make,
                         and what the harness substitutes on violations.
  response_normalizer  — how the normalizer maps model field-name variations
                         to the canonical AgentDecision schema.

Key design discipline: every YAML level is validated for BOTH missing required
keys AND unexpected keys. An unexpected key is almost always a typo; silently
ignoring it would let a misspelled policy key go undetected until a live run.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from evals.scenarios import ExpectedDecision

# ---------------------------------------------------------------------------
# Schema types
# ---------------------------------------------------------------------------

_REQUIRED_TIER_KEYS: frozenset[str] = frozenset(
    {"allowed_decisions", "on_disallowed_decision", "zero_payout_on_override",
     "flag_for_investigation"}
)
_REQUIRED_TIER_NAMES: frozenset[str] = frozenset({"green", "yellow", "red", "black"})
_REQUIRED_TOP_KEYS: frozenset[str] = frozenset({"tier_authority", "response_normalizer"})
_REQUIRED_NORMALIZER_KEYS: frozenset[str] = frozenset(
    {"field_aliases", "drop_fields", "defaults"}
)


class TierAuthorityRule(BaseModel):
    """Authority configuration for a single tier."""

    model_config = ConfigDict(frozen=True)

    allowed_decisions: frozenset[ExpectedDecision] = Field(
        min_length=1,
        description="Decisions the model is permitted to make on this tier.",
    )
    on_disallowed_decision: ExpectedDecision = Field(
        description="What the harness substitutes when the model proposes a "
                    "decision not in allowed_decisions.",
    )
    zero_payout_on_override: bool = Field(
        description="If True, force payout to 0 when overriding the model.",
    )
    flag_for_investigation: bool = Field(
        description="If True, the reason text flags this as needing investigation.",
    )


class TierAuthorityConfig(BaseModel):
    """Authority configuration across all four tiers."""

    model_config = ConfigDict(frozen=True)

    green: TierAuthorityRule
    yellow: TierAuthorityRule
    red: TierAuthorityRule
    black: TierAuthorityRule


class ResponseNormalizerConfig(BaseModel):
    """Normalizer configuration."""

    model_config = ConfigDict(frozen=True)

    field_aliases: dict[str, str] = Field(
        description="Map of model-emitted field names to canonical schema names.",
    )
    drop_fields: frozenset[str] = Field(
        description="Field names the model invents that should be dropped.",
    )
    defaults: dict[str, str | float | int | bool] = Field(
        description="Default values applied when canonical fields are missing.",
    )


class PermissionsConfig(BaseModel):
    """Top-level permissions config — both authority and normalizer."""

    model_config = ConfigDict(frozen=True)

    tier_authority: TierAuthorityConfig
    response_normalizer: ResponseNormalizerConfig


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class PermissionsConfigError(ValueError):
    """Raised when the permissions YAML is malformed, has missing/extra keys,
    or fails schema validation.
    """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_keys(
    actual: dict,  # type: ignore[type-arg]
    required: frozenset[str],
    allowed: frozenset[str],
    context: str,
) -> None:
    """Assert that `actual` has exactly the expected keys.

    Raises PermissionsConfigError naming the offending keys and the context.
    """
    present = frozenset(actual.keys())
    missing = required - present
    unexpected = present - allowed
    if missing:
        raise PermissionsConfigError(
            f"[{context}] Missing required key(s): {', '.join(sorted(missing))}"
        )
    if unexpected:
        raise PermissionsConfigError(
            f"[{context}] Unexpected key(s): {', '.join(sorted(unexpected))} "
            f"(valid: {', '.join(sorted(allowed))})"
        )


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


def load_permissions(path: Path | str) -> PermissionsConfig:
    """Load permissions config from a YAML file.

    Args:
        path: Path to the YAML file (typically config/permissions.yaml).

    Returns:
        A frozen PermissionsConfig.

    Raises:
        FileNotFoundError: if the file does not exist.
        PermissionsConfigError: if YAML is malformed, missing required keys,
            contains unexpected keys at any level, or fails Pydantic validation.
    """
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Permissions file not found: {resolved}")

    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PermissionsConfigError(f"Malformed YAML in {resolved}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PermissionsConfigError(
            f"Expected a YAML mapping in {resolved}, got {type(raw).__name__}"
        )

    _check_keys(raw, _REQUIRED_TOP_KEYS, _REQUIRED_TOP_KEYS, "top-level")

    # --- tier_authority ---
    tier_authority_raw = raw["tier_authority"]
    if not isinstance(tier_authority_raw, dict):
        raise PermissionsConfigError(
            f"[tier_authority] Expected a mapping, got {type(tier_authority_raw).__name__}"
        )
    _check_keys(tier_authority_raw, _REQUIRED_TIER_NAMES, _REQUIRED_TIER_NAMES, "tier_authority")

    for tier_name in _REQUIRED_TIER_NAMES:
        tier_raw = tier_authority_raw[tier_name]
        if not isinstance(tier_raw, dict):
            raise PermissionsConfigError(
                f"[tier_authority.{tier_name}] Expected a mapping, "
                f"got {type(tier_raw).__name__}"
            )
        _check_keys(
            tier_raw,
            _REQUIRED_TIER_KEYS,
            _REQUIRED_TIER_KEYS,
            f"tier_authority.{tier_name}",
        )

    # --- response_normalizer ---
    normalizer_raw = raw["response_normalizer"]
    if not isinstance(normalizer_raw, dict):
        raise PermissionsConfigError(
            f"[response_normalizer] Expected a mapping, got {type(normalizer_raw).__name__}"
        )
    _check_keys(
        normalizer_raw,
        _REQUIRED_NORMALIZER_KEYS,
        _REQUIRED_NORMALIZER_KEYS,
        "response_normalizer",
    )

    try:
        return PermissionsConfig.model_validate(raw)
    except ValidationError as exc:
        raise PermissionsConfigError(
            f"Schema validation failed for {resolved}: {exc}"
        ) from exc
