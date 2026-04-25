"""Agent surface the eval runner drives.

Defines EvalAgent, the minimal protocol that both real agents (MAF-backed,
Stage 1+) and stub agents (null/baseline) must satisfy. The runner imports
only this module; it never depends directly on MAF's Agent type.

Keeping this boundary means:
- Evals can run against any conforming implementation, including non-MAF baselines.
- MAF version changes do not require rewriting the runner.
- Unit tests can provide trivial in-process stubs without importing MAF at all.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from evals.scenarios import ExpectedDecision, ExpectedTier, Scenario


class AgentRunResult(BaseModel):
    """Structured output from a single scenario run."""

    model_config = ConfigDict(frozen=True)

    tier_assigned: ExpectedTier | None = None
    decision: ExpectedDecision | None = None
    payout_amount: Decimal | None = None
    tool_calls_made: list[str] = Field(default_factory=list)
    reasoning: str = ""
    error: str | None = None


@runtime_checkable
class EvalAgent(Protocol):
    """Minimal interface the eval runner drives.

    Real agents (MAF-backed) and stub agents both implement this.
    No MAF types appear here.
    """

    async def run_scenario(self, scenario: Scenario) -> AgentRunResult: ...
