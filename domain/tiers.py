"""Claim tier classification for the auto-insurance adjudication pipeline.

A tier is a routing label that determines which adjudication path a claim
follows. Tiers are assigned deterministically from claim data and
caller-supplied thresholds; no LLM logic lives here.

Thresholds are intentionally passed in rather than loaded from config/
so this module stays a pure calculation layer with no I/O dependencies.
Callers (tools, harness, evals) are responsible for loading thresholds
from the appropriate config source before calling assign_tier.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from domain.models import Claim


class Tier(StrEnum):
    """Routing tier for a claim, from lowest to highest severity."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    BLACK = "black"


class TierThresholds(BaseModel):
    """Externalized tier boundary configuration.

    All three boundaries must be strictly ascending and positive.
    Damage amounts are compared inclusive of each boundary:
    <= green_max → GREEN, <= yellow_max → YELLOW, <= red_max → RED, else BLACK.
    """

    model_config = ConfigDict(frozen=True)

    green_max_damage: Decimal
    yellow_max_damage: Decimal
    red_max_damage: Decimal

    @field_validator("green_max_damage", "yellow_max_damage", "red_max_damage")
    @classmethod
    def must_be_positive(cls, v: Decimal) -> Decimal:
        """Tier boundaries of zero or below have no meaningful interpretation."""
        if v <= 0:
            raise ValueError("threshold must be > 0")
        return v

    @model_validator(mode="after")
    def must_be_strictly_ascending(self) -> "TierThresholds":
        """GREEN < YELLOW < RED is required; equal boundaries collapse a tier to dead code."""
        if not (self.green_max_damage < self.yellow_max_damage < self.red_max_damage):
            raise ValueError(
                "thresholds must be strictly ascending: "
                "green_max_damage < yellow_max_damage < red_max_damage"
            )
        return self


_ESCALATION: dict[Tier, Tier] = {
    Tier.GREEN: Tier.YELLOW,
    Tier.YELLOW: Tier.RED,
    Tier.RED: Tier.BLACK,
    Tier.BLACK: Tier.BLACK,
}


def assign_tier(claim: Claim, thresholds: TierThresholds) -> Tier:
    """Return the routing tier for a claim given caller-supplied thresholds.

    Injury escalation is applied after the damage-based classification:
    an injury bumps the tier up one level (GREEN→YELLOW, YELLOW→RED,
    RED→BLACK, BLACK stays BLACK).
    """
    if claim.damage is None:
        tier = Tier.YELLOW
    else:
        amount: Decimal = claim.damage.assessed_amount
        if amount <= thresholds.green_max_damage:
            tier = Tier.GREEN
        elif amount <= thresholds.yellow_max_damage:
            tier = Tier.YELLOW
        elif amount <= thresholds.red_max_damage:
            tier = Tier.RED
        else:
            tier = Tier.BLACK

    if claim.incident.injuries_reported:
        tier = _ESCALATION[tier]

    return tier
