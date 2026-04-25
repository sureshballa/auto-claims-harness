"""YAML scenario schema for the evaluation harness.

A scenario is a self-contained test case stored on disk as a YAML file.
The runner loads scenarios, drives an agent through the described input,
and verifies the agent's output against the expected fields defined here.

YAML scenario files live in evals/scenario_files/. This module defines
the schema only; it contains no data files.

Schema is intentionally independent of domain/ so that evals remain valid
spec documents even as internal domain types evolve.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class ScenarioParseError(ValueError):
    """Raised when a scenario file cannot be loaded or fails schema validation."""


class ExpectedTier(StrEnum):
    """Routing tier vocabulary for scenario specs.

    Mirrors domain.tiers.Tier intentionally — kept separate so evals/ does not
    import domain/ and the spec vocabulary can evolve independently.
    """

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    BLACK = "black"


class ExpectedDecision(StrEnum):
    """Adjudication decision vocabulary for scenario specs."""

    APPROVE = "approve"
    DENY = "deny"
    ESCALATE = "escalate"


class PayoutRange(BaseModel):
    """Inclusive bounds on an expected payout amount."""

    model_config = ConfigDict(frozen=True)

    min_payout: Decimal = Field(ge=Decimal("0"))
    max_payout: Decimal

    @model_validator(mode="after")
    def max_must_be_at_least_min(self) -> PayoutRange:
        """A range where max < min is an authoring mistake, not a valid expectation."""
        if self.max_payout < self.min_payout:
            raise ValueError(
                f"max_payout ({self.max_payout}) must be >= min_payout ({self.min_payout})"
            )
        return self


class ToolCallExpectation(BaseModel):
    """Declares that a named tool must or must not be invoked during a scenario run."""

    model_config = ConfigDict(frozen=True)

    tool_name: str
    must_be_called: bool


class Scenario(BaseModel):
    """A single evaluation scenario loaded from a YAML file."""

    model_config = ConfigDict(frozen=True)

    # Identity
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)

    # Input
    claim_number: str
    claimant_message: str | None = None

    # Expected outputs
    expected_tier: ExpectedTier
    expected_decision: ExpectedDecision
    expected_payout_range: PayoutRange | None = None
    tool_call_expectations: list[ToolCallExpectation] = Field(default_factory=list)


def load_scenario(path: Path | str) -> Scenario:
    """Load a scenario from a YAML file.

    Raises:
        ScenarioParseError: if the file cannot be read, is not valid YAML,
            or does not conform to the Scenario schema.
    """
    resolved = Path(path)
    try:
        raw: Any = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ScenarioParseError(f"Cannot read scenario file {resolved}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ScenarioParseError(f"Invalid YAML in {resolved}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ScenarioParseError(
            f"Scenario file {resolved} must contain a YAML mapping, got {type(raw).__name__}"
        )

    try:
        return Scenario.model_validate(raw)
    except ValidationError as exc:
        raise ScenarioParseError(f"Schema validation failed for {resolved}:\n{exc}") from exc


def load_all_scenarios(directory: Path | str) -> list[Scenario]:
    """Load every *.yaml file under directory as a Scenario, sorted by id.

    Raises:
        ScenarioParseError: if any file fails to parse.
    """
    root = Path(directory)
    paths = sorted(root.glob("*.yaml"))
    return sorted((load_scenario(p) for p in paths), key=lambda s: s.id)
