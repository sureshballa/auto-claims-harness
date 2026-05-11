"""Tool allowlist config loader for the auto-claims harness.

Reads tool-call authorization policy from a YAML file (typically
config/tool_allowlist.yaml), validates it strictly at every level, and
returns frozen Pydantic models. Intended to be called once at process
startup — a load-once snapshot.

Key design discipline: every YAML level is validated for BOTH missing
required keys AND unexpected keys. An unexpected key is almost always a
typo; silently ignoring it would let a misspelled policy key go undetected
until a live run.

The loader does not know which tools exist; the engine will fail closed
on unknown tools via `default_decision`. Tool names in the YAML are
therefore free-form strings validated only at the engine level.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# ---------------------------------------------------------------------------
# Schema types
# ---------------------------------------------------------------------------

_REQUIRED_TOP_KEYS: frozenset[str] = frozenset({"default_decision", "tools"})
_REQUIRED_TOOL_KEYS: frozenset[str] = frozenset({"default", "tier_rules"})
_ALLOWED_TIER_NAMES: frozenset[str] = frozenset({"green", "yellow", "red", "black"})


class ToolDecision(StrEnum):
    """Whether a tool call is permitted or denied."""

    ALLOW = "allow"
    DENY = "deny"


class ToolAllowlistRule(BaseModel):
    """Authorization rule for a single tool."""

    model_config = ConfigDict(frozen=True)

    default: ToolDecision = Field(
        description="Baseline decision applied when no tier-specific rule matches.",
    )
    tier_rules: dict[str, ToolDecision] = Field(
        description=(
            "Per-tier overrides. Keys must be tier names (green, yellow, red, black); "
            "absent tiers fall through to `default`. May be empty."
        ),
    )


class ToolAllowlistConfig(BaseModel):
    """Top-level tool allowlist config."""

    model_config = ConfigDict(frozen=True)

    default_decision: ToolDecision = Field(
        description=(
            "Fallback decision for any tool not listed under `tools`. "
            "Currently locked to 'deny' — the engine fails closed on unknown tools."
        ),
    )
    tools: dict[str, ToolAllowlistRule] = Field(
        description="Per-tool authorization rules, keyed by tool name.",
    )


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class ToolAllowlistConfigError(ValueError):
    """Raised when the tool allowlist YAML is malformed, has missing/extra keys,
    or fails schema validation.
    """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_keys(
    actual: dict[str, object],
    required: frozenset[str],
    allowed: frozenset[str],
    context: str,
) -> None:
    """Assert that `actual` has exactly the expected keys.

    Raises ToolAllowlistConfigError naming the offending keys and the context.
    """
    present = frozenset(actual.keys())
    missing = required - present
    unexpected = present - allowed
    if missing:
        raise ToolAllowlistConfigError(
            f"[{context}] Missing required key(s): {', '.join(sorted(missing))}"
        )
    if unexpected:
        raise ToolAllowlistConfigError(
            f"[{context}] Unexpected key(s): {', '.join(sorted(unexpected))} "
            f"(valid: {', '.join(sorted(allowed))})"
        )


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


def load_tool_allowlist(path: Path | str) -> ToolAllowlistConfig:
    """Load tool allowlist config from a YAML file.

    Args:
        path: Path to the YAML file (typically config/tool_allowlist.yaml).

    Returns:
        A frozen ToolAllowlistConfig.

    Raises:
        FileNotFoundError: if the file does not exist.
        ToolAllowlistConfigError: if YAML is malformed, missing required keys,
            contains unexpected keys at any level, or fails Pydantic validation.
    """
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Tool allowlist file not found: {resolved}")

    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ToolAllowlistConfigError(f"Malformed YAML in {resolved}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ToolAllowlistConfigError(
            f"Expected a YAML mapping in {resolved}, got {type(raw).__name__}"
        )

    _check_keys(raw, _REQUIRED_TOP_KEYS, _REQUIRED_TOP_KEYS, "top-level")

    # Lock-it-now: default_decision must be "deny" — the engine fails closed.
    if raw["default_decision"] != "deny":
        raise ToolAllowlistConfigError(
            f"[top-level] default_decision must be 'deny', "
            f"got {raw['default_decision']!r}"
        )

    tools_raw = raw["tools"]
    if not isinstance(tools_raw, dict):
        raise ToolAllowlistConfigError(
            f"[tools] Expected a mapping, got {type(tools_raw).__name__}"
        )

    for tool_name, tool_entry in tools_raw.items():
        if not isinstance(tool_entry, dict):
            raise ToolAllowlistConfigError(
                f"[tools.{tool_name}] Expected a mapping, "
                f"got {type(tool_entry).__name__}"
            )
        _check_keys(
            tool_entry,
            _REQUIRED_TOOL_KEYS,
            _REQUIRED_TOOL_KEYS,
            f"tools.{tool_name}",
        )

        tier_rules = tool_entry["tier_rules"]
        if not isinstance(tier_rules, dict):
            raise ToolAllowlistConfigError(
                f"[tools.{tool_name}.tier_rules] Expected a mapping, "
                f"got {type(tier_rules).__name__}"
            )
        _check_keys(
            tier_rules,
            frozenset(),
            _ALLOWED_TIER_NAMES,
            f"tools.{tool_name}.tier_rules",
        )

    try:
        return ToolAllowlistConfig.model_validate(raw)
    except ValidationError as exc:
        raise ToolAllowlistConfigError(
            f"Schema validation failed for {resolved}: {exc}"
        ) from exc
