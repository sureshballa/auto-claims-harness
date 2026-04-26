"""Agent output contracts — shared structured-response schemas.

Agent implementations produce structured outputs that downstream harness
layers (middleware, evaluators, event log) need to validate and consume.
This file is where those output schemas live, so that no harness layer
has to import from agents/.

Currently scoped to FnolAgent's AgentDecision. As we add more agents,
their output schemas land here too.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AgentDecision(BaseModel):
    """Structured response we ask the LLM to produce.

    Uses plain str fields rather than domain enums because the LLM is more
    likely to comply with simple string constraints than with typed enum members.
    Callers map these strings back to domain types after parsing.

    payout_amount is float here because LLM JSON output has no Decimal type.
    It is immediately converted to Decimal(str(...)) in run_scenario — never
    stored or used as float in domain logic.
    """

    model_config = ConfigDict(frozen=True)

    tier: str = Field(description="One of: green, yellow, red, black. Lowercase.")
    decision: str = Field(description="One of: approve, deny, escalate. Lowercase.")
    payout_amount: float = Field(
        description="Amount the insurer should pay, in USD. Use 0 for denials or escalations."
    )
    reasoning: str = Field(description="One-paragraph explanation of how you decided.")
