"""Tests for harness/policy_engine/permissions_loader.py.

Unit tests use tmp_path-isolated YAML fixtures; they never read
config/permissions.yaml. One integration test at the end verifies the
real product config file remains parseable and matches known policy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.scenarios import ExpectedDecision
from harness.policy_engine import PermissionsConfigError, load_permissions

# ---------------------------------------------------------------------------
# Reusable YAML building blocks
# ---------------------------------------------------------------------------

_VALID_TIER_AUTHORITY = """\
tier_authority:
  green:
    allowed_decisions: [approve, deny, escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: false
    flag_for_investigation: false
  yellow:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
  red:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
  black:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: true
"""

_VALID_RESPONSE_NORMALIZER = """\
response_normalizer:
  field_aliases:
    amount_paid: payout_amount
    reason: reasoning
  drop_fields:
    - claim_id
    - claim_number
  defaults:
    payout_amount: 0.0
    reasoning: "(no reasoning provided by model)"
"""

_VALID_YAML = _VALID_TIER_AUTHORITY + _VALID_RESPONSE_NORMALIZER


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_loads_valid_permissions(tmp_path: Path) -> None:
    """A complete valid YAML produces a correctly-typed PermissionsConfig."""
    f = _write(tmp_path / "permissions.yaml", _VALID_YAML)
    config = load_permissions(f)

    # All four tiers present
    assert config.tier_authority.green is not None
    assert config.tier_authority.yellow is not None
    assert config.tier_authority.red is not None
    assert config.tier_authority.black is not None

    # Green allows all three decisions
    assert ExpectedDecision.APPROVE in config.tier_authority.green.allowed_decisions
    assert ExpectedDecision.DENY in config.tier_authority.green.allowed_decisions
    assert ExpectedDecision.ESCALATE in config.tier_authority.green.allowed_decisions

    # yellow/red/black allow only escalate
    assert config.tier_authority.yellow.allowed_decisions == frozenset({ExpectedDecision.ESCALATE})
    assert config.tier_authority.black.flag_for_investigation is True

    # Normalizer config
    assert isinstance(config.response_normalizer.field_aliases, dict)
    assert config.response_normalizer.field_aliases["amount_paid"] == "payout_amount"
    assert config.response_normalizer.field_aliases["reason"] == "reasoning"
    assert isinstance(config.response_normalizer.drop_fields, frozenset)
    assert "claim_id" in config.response_normalizer.drop_fields


# ---------------------------------------------------------------------------
# Top-level adversarial
# ---------------------------------------------------------------------------


def test_rejects_missing_file(tmp_path: Path) -> None:
    """A path that does not exist raises FileNotFoundError with the path in the message."""
    missing = tmp_path / "not_there.yaml"
    with pytest.raises(FileNotFoundError) as exc_info:
        load_permissions(missing)
    assert str(missing.resolve()) in str(exc_info.value)


def test_rejects_non_dict_yaml(tmp_path: Path) -> None:
    """A YAML list is not a valid permissions mapping."""
    f = _write(tmp_path / "permissions.yaml", "- foo\n- bar\n")
    with pytest.raises(PermissionsConfigError):
        load_permissions(f)


def test_rejects_missing_tier_authority(tmp_path: Path) -> None:
    """YAML with only response_normalizer must raise with 'tier_authority' in the message."""
    f = _write(tmp_path / "permissions.yaml", _VALID_RESPONSE_NORMALIZER)
    with pytest.raises(PermissionsConfigError) as exc_info:
        load_permissions(f)
    assert "tier_authority" in str(exc_info.value)


def test_rejects_missing_response_normalizer(tmp_path: Path) -> None:
    """YAML with only tier_authority must raise with 'response_normalizer' in the message."""
    f = _write(tmp_path / "permissions.yaml", _VALID_TIER_AUTHORITY)
    with pytest.raises(PermissionsConfigError) as exc_info:
        load_permissions(f)
    assert "response_normalizer" in str(exc_info.value)


def test_rejects_unexpected_top_level_key(tmp_path: Path) -> None:
    """An unknown top-level key raises PermissionsConfigError naming it."""
    yaml = _VALID_YAML + "extra_section:\n  foo: bar\n"
    f = _write(tmp_path / "permissions.yaml", yaml)
    with pytest.raises(PermissionsConfigError) as exc_info:
        load_permissions(f)
    assert "extra_section" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Tier-level adversarial
# ---------------------------------------------------------------------------


def test_rejects_missing_tier(tmp_path: Path) -> None:
    """YAML missing the yellow tier must raise with 'yellow' in the message."""
    tier_authority_no_yellow = """\
tier_authority:
  green:
    allowed_decisions: [approve, deny, escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: false
    flag_for_investigation: false
  red:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
  black:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: true
"""
    f = _write(tmp_path / "permissions.yaml", tier_authority_no_yellow + _VALID_RESPONSE_NORMALIZER)
    with pytest.raises(PermissionsConfigError) as exc_info:
        load_permissions(f)
    assert "yellow" in str(exc_info.value)


def test_rejects_extra_tier(tmp_path: Path) -> None:
    """A 'purple' tier in tier_authority is unexpected and must be named in the error."""
    extra = _VALID_TIER_AUTHORITY + """\
  purple:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
"""
    f = _write(tmp_path / "permissions.yaml", extra + _VALID_RESPONSE_NORMALIZER)
    with pytest.raises(PermissionsConfigError) as exc_info:
        load_permissions(f)
    assert "purple" in str(exc_info.value)


def test_rejects_missing_tier_field(tmp_path: Path) -> None:
    """Green tier missing allowed_decisions must name it in the error."""
    tier_authority_bad_green = """\
tier_authority:
  green:
    on_disallowed_decision: escalate
    zero_payout_on_override: false
    flag_for_investigation: false
  yellow:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
  red:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
  black:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: true
"""
    f = _write(tmp_path / "permissions.yaml", tier_authority_bad_green + _VALID_RESPONSE_NORMALIZER)
    with pytest.raises(PermissionsConfigError) as exc_info:
        load_permissions(f)
    assert "allowed_decisions" in str(exc_info.value)


def test_rejects_extra_tier_field(tmp_path: Path) -> None:
    """An extra field inside a tier dict must be named in the error."""
    tier_authority_extra_field = """\
tier_authority:
  green:
    allowed_decisions: [approve, deny, escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: false
    flag_for_investigation: false
    extra_field: surprise
  yellow:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
  red:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
  black:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: true
"""
    yaml = tier_authority_extra_field + _VALID_RESPONSE_NORMALIZER
    f = _write(tmp_path / "permissions.yaml", yaml)
    with pytest.raises(PermissionsConfigError) as exc_info:
        load_permissions(f)
    assert "extra_field" in str(exc_info.value)


def test_rejects_invalid_decision_in_allowed(tmp_path: Path) -> None:
    """An unrecognized value in allowed_decisions fails Pydantic enum validation."""
    tier_authority_bad_decision = """\
tier_authority:
  green:
    allowed_decisions: [approve, fly_to_moon]
    on_disallowed_decision: escalate
    zero_payout_on_override: false
    flag_for_investigation: false
  yellow:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
  red:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
  black:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: true
"""
    yaml = tier_authority_bad_decision + _VALID_RESPONSE_NORMALIZER
    f = _write(tmp_path / "permissions.yaml", yaml)
    with pytest.raises(PermissionsConfigError):
        load_permissions(f)


def test_rejects_empty_allowed_decisions(tmp_path: Path) -> None:
    """An empty allowed_decisions list fails the min_length=1 constraint."""
    tier_authority_empty = """\
tier_authority:
  green:
    allowed_decisions: []
    on_disallowed_decision: escalate
    zero_payout_on_override: false
    flag_for_investigation: false
  yellow:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
  red:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: false
  black:
    allowed_decisions: [escalate]
    on_disallowed_decision: escalate
    zero_payout_on_override: true
    flag_for_investigation: true
"""
    f = _write(tmp_path / "permissions.yaml", tier_authority_empty + _VALID_RESPONSE_NORMALIZER)
    with pytest.raises(PermissionsConfigError):
        load_permissions(f)


# ---------------------------------------------------------------------------
# Normalizer-level adversarial
# ---------------------------------------------------------------------------


def test_rejects_missing_normalizer_field(tmp_path: Path) -> None:
    """response_normalizer missing field_aliases must name it in the error."""
    normalizer_no_aliases = """\
response_normalizer:
  drop_fields:
    - claim_id
  defaults:
    payout_amount: 0.0
    reasoning: "(no reasoning)"
"""
    f = _write(tmp_path / "permissions.yaml", _VALID_TIER_AUTHORITY + normalizer_no_aliases)
    with pytest.raises(PermissionsConfigError) as exc_info:
        load_permissions(f)
    assert "field_aliases" in str(exc_info.value)


def test_rejects_extra_normalizer_field(tmp_path: Path) -> None:
    """An unexpected key in response_normalizer must be named in the error."""
    normalizer_extra = """\
response_normalizer:
  field_aliases:
    amount_paid: payout_amount
  drop_fields:
    - claim_id
  defaults:
    payout_amount: 0.0
    reasoning: "(no reasoning)"
  extra_normalizer_key: surprise
"""
    f = _write(tmp_path / "permissions.yaml", _VALID_TIER_AUTHORITY + normalizer_extra)
    with pytest.raises(PermissionsConfigError) as exc_info:
        load_permissions(f)
    assert "extra_normalizer_key" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Integration test — reads the real product config
# ---------------------------------------------------------------------------


def test_loads_real_config_file() -> None:
    """The product config/permissions.yaml must parse cleanly and match known policy."""
    real_config = Path(__file__).parent.parent / "config" / "permissions.yaml"
    config = load_permissions(real_config)

    # Green allows all three decisions
    assert config.tier_authority.green.allowed_decisions == frozenset(
        {ExpectedDecision.APPROVE, ExpectedDecision.DENY, ExpectedDecision.ESCALATE}
    )

    # Yellow, red, black allow only escalate
    for tier_rule in (
        config.tier_authority.yellow,
        config.tier_authority.red,
        config.tier_authority.black,
    ):
        assert tier_rule.allowed_decisions == frozenset({ExpectedDecision.ESCALATE})

    # Black is flagged for investigation; others are not
    assert config.tier_authority.black.flag_for_investigation is True
    assert config.tier_authority.green.flag_for_investigation is False
    assert config.tier_authority.yellow.flag_for_investigation is False
    assert config.tier_authority.red.flag_for_investigation is False
