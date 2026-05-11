"""Tests for harness/policy_engine/tool_allowlist_loader.py.

Unit tests use tmp_path-isolated YAML fixtures; they never read a product
config file (none exists yet for the tool allowlist).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.policy_engine.tool_allowlist_loader import (
    ToolAllowlistConfigError,
    ToolDecision,
    load_tool_allowlist,
)

# ---------------------------------------------------------------------------
# Reusable YAML building blocks
# ---------------------------------------------------------------------------

_MINIMAL_VALID = """\
default_decision: deny
tools:
  policy_lookup_by_number:
    default: allow
    tier_rules: {}
"""

_WITH_TIER_RULES = """\
default_decision: deny
tools:
  payment_instruction:
    default: deny
    tier_rules:
      green: allow
"""


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_loads_valid_minimal_config(tmp_path: Path) -> None:
    """A minimal valid YAML (one tool, empty tier_rules) loads correctly."""
    f = _write(tmp_path / "allowlist.yaml", _MINIMAL_VALID)
    config = load_tool_allowlist(f)

    assert config.default_decision == ToolDecision.DENY
    assert "policy_lookup_by_number" in config.tools
    rule = config.tools["policy_lookup_by_number"]
    assert rule.default == ToolDecision.ALLOW
    assert rule.tier_rules == {}


def test_loads_valid_config_with_tier_rules(tmp_path: Path) -> None:
    """A config with tier_rules parses tier entries into ToolDecision values."""
    f = _write(tmp_path / "allowlist.yaml", _WITH_TIER_RULES)
    config = load_tool_allowlist(f)

    rule = config.tools["payment_instruction"]
    assert rule.default == ToolDecision.DENY
    assert rule.tier_rules["green"] == ToolDecision.ALLOW


# ---------------------------------------------------------------------------
# Top-level adversarial
# ---------------------------------------------------------------------------


def test_rejects_missing_default_decision(tmp_path: Path) -> None:
    """YAML without default_decision raises ToolAllowlistConfigError naming the missing key."""
    yaml = "tools:\n  my_tool:\n    default: allow\n    tier_rules: {}\n"
    f = _write(tmp_path / "allowlist.yaml", yaml)
    with pytest.raises(ToolAllowlistConfigError) as exc_info:
        load_tool_allowlist(f)
    assert "default_decision" in str(exc_info.value)


def test_rejects_extra_top_level_key(tmp_path: Path) -> None:
    """An unexpected top-level key raises ToolAllowlistConfigError naming it."""
    yaml = _MINIMAL_VALID + "extra_section: surprise\n"
    f = _write(tmp_path / "allowlist.yaml", yaml)
    with pytest.raises(ToolAllowlistConfigError) as exc_info:
        load_tool_allowlist(f)
    assert "extra_section" in str(exc_info.value)


def test_rejects_default_decision_allow(tmp_path: Path) -> None:
    """default_decision: allow is not permitted — the loader locks it to 'deny'."""
    yaml = "default_decision: allow\ntools:\n  my_tool:\n    default: allow\n    tier_rules: {}\n"
    f = _write(tmp_path / "allowlist.yaml", yaml)
    with pytest.raises(ToolAllowlistConfigError) as exc_info:
        load_tool_allowlist(f)
    assert "deny" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Tool-entry adversarial
# ---------------------------------------------------------------------------


def test_rejects_tool_entry_missing_tier_rules(tmp_path: Path) -> None:
    """A tool entry without tier_rules raises ToolAllowlistConfigError naming the missing key."""
    yaml = "default_decision: deny\ntools:\n  my_tool:\n    default: allow\n"
    f = _write(tmp_path / "allowlist.yaml", yaml)
    with pytest.raises(ToolAllowlistConfigError) as exc_info:
        load_tool_allowlist(f)
    assert "tier_rules" in str(exc_info.value)


def test_rejects_tool_entry_extra_key(tmp_path: Path) -> None:
    """An unexpected key inside a tool entry raises ToolAllowlistConfigError naming it."""
    yaml = (
        "default_decision: deny\n"
        "tools:\n"
        "  my_tool:\n"
        "    default: allow\n"
        "    tier_rules: {}\n"
        "    surprise_key: oops\n"
    )
    f = _write(tmp_path / "allowlist.yaml", yaml)
    with pytest.raises(ToolAllowlistConfigError) as exc_info:
        load_tool_allowlist(f)
    assert "surprise_key" in str(exc_info.value)


# ---------------------------------------------------------------------------
# tier_rules adversarial
# ---------------------------------------------------------------------------


def test_rejects_unknown_tier_in_tier_rules(tmp_path: Path) -> None:
    """An unknown tier name like 'purple' in tier_rules raises ToolAllowlistConfigError."""
    yaml = (
        "default_decision: deny\n"
        "tools:\n"
        "  my_tool:\n"
        "    default: deny\n"
        "    tier_rules:\n"
        "      purple: allow\n"
    )
    f = _write(tmp_path / "allowlist.yaml", yaml)
    with pytest.raises(ToolAllowlistConfigError) as exc_info:
        load_tool_allowlist(f)
    assert "purple" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Value validation adversarial
# ---------------------------------------------------------------------------


def test_rejects_invalid_default_value(tmp_path: Path) -> None:
    """A `default` value that is neither 'allow' nor 'deny' fails Pydantic validation."""
    yaml = (
        "default_decision: deny\n"
        "tools:\n"
        "  my_tool:\n"
        "    default: maybe\n"
        "    tier_rules: {}\n"
    )
    f = _write(tmp_path / "allowlist.yaml", yaml)
    with pytest.raises(ToolAllowlistConfigError):
        load_tool_allowlist(f)


def test_rejects_invalid_tier_rule_decision_value(tmp_path: Path) -> None:
    """A decision value in tier_rules that is neither 'allow' nor 'deny' fails validation."""
    yaml = (
        "default_decision: deny\n"
        "tools:\n"
        "  my_tool:\n"
        "    default: deny\n"
        "    tier_rules:\n"
        "      green: sometimes\n"
    )
    f = _write(tmp_path / "allowlist.yaml", yaml)
    with pytest.raises(ToolAllowlistConfigError):
        load_tool_allowlist(f)


# ---------------------------------------------------------------------------
# File-level adversarial
# ---------------------------------------------------------------------------


def test_rejects_missing_file(tmp_path: Path) -> None:
    """A path that does not exist raises FileNotFoundError with the path in the message."""
    missing = tmp_path / "not_there.yaml"
    with pytest.raises(FileNotFoundError) as exc_info:
        load_tool_allowlist(missing)
    assert str(missing.resolve()) in str(exc_info.value)


def test_rejects_malformed_yaml(tmp_path: Path) -> None:
    """Unparseable YAML raises ToolAllowlistConfigError wrapping the parse error."""
    f = _write(tmp_path / "allowlist.yaml", "key: [unclosed\n")
    with pytest.raises(ToolAllowlistConfigError):
        load_tool_allowlist(f)


def test_rejects_list_root(tmp_path: Path) -> None:
    """A YAML list at the root (not a mapping) raises ToolAllowlistConfigError."""
    f = _write(tmp_path / "allowlist.yaml", "- foo\n- bar\n")
    with pytest.raises(ToolAllowlistConfigError):
        load_tool_allowlist(f)
