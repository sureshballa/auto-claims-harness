"""Payment instruction tool — model-callable wrapper for issuing claim payments.

This is the blast-radius write tool: calling it represents a decision to disburse
money for a claim. The tool itself is a logged stub — it records invocations to a
PaymentInstructionRecorder and returns an acknowledgement, but does not actually
issue payment. Production implementations would integrate with payment
infrastructure here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from agent_framework import FunctionTool, tool


class PaymentInstructionRecorder:
    """In-memory log of payment_instruction invocations.

    The factory captures a reference; the tool appends each invocation.
    Calls accumulate across scenarios — construct a fresh recorder per
    session if isolation is needed.
    """

    def __init__(self) -> None:
        self._calls: list[dict[str, str | Decimal]] = []

    def record(self, claim_number: str, amount: Decimal) -> None:
        """Append one invocation record to the log."""
        self._calls.append({"claim_number": claim_number, "amount": amount})

    @property
    def calls(self) -> list[dict[str, str | Decimal]]:
        """Return a snapshot of all recorded invocations. Defensive copy."""
        return list(self._calls)


def make_payment_instruction(recorder: PaymentInstructionRecorder) -> FunctionTool:
    """Return a payment_instruction tool that records each invocation to the given recorder.

    Closure-bound recorder keeps the tool decoupled from agent state and matches
    the dependency-injection pattern used by other tools in this package.
    """

    @tool(
        name="payment_instruction",
        description=(
            "Issue a payment instruction for a claim. Use this tool only when a claim "
            "adjudication is finalized as APPROVE and the harness has computed a "
            "non-negative payout amount. Returns an acknowledgement that the payment "
            "instruction has been recorded."
        ),
    )
    def payment_instruction(claim_number: str, amount: float) -> dict[str, Any]:  # Any: MAF tool
        """Record a payment instruction. Returns acknowledgement metadata."""
        amount_decimal = Decimal(str(amount))
        recorder.record(claim_number, amount_decimal)
        return {
            "acknowledged": True,
            "claim_number": claim_number,
            "amount": str(amount_decimal),
        }

    return payment_instruction
