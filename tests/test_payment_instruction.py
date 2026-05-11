"""Tests for tools/payment_instruction.py."""

from __future__ import annotations

from decimal import Decimal

from tools.payment_instruction import PaymentInstructionRecorder, make_payment_instruction


def test_returns_acknowledgement_with_claim_number_and_amount() -> None:
    """Tool returns acknowledged=True with the claim number and amount."""
    recorder = PaymentInstructionRecorder()
    tool = make_payment_instruction(recorder)
    result = tool(claim_number="CLM-00001", amount=500.0)

    assert result["acknowledged"] is True
    assert result["claim_number"] == "CLM-00001"
    assert result["amount"] == "500.0"


def test_amount_is_returned_as_decimal_string_not_float_repr() -> None:
    """Decimal(str(amount)) at the boundary prevents float-representation drift."""
    recorder = PaymentInstructionRecorder()
    tool = make_payment_instruction(recorder)
    result = tool(claim_number="CLM-00001", amount=0.1)

    # If we had used str(float) directly we'd get the full float repr.
    # Decimal(str(0.1)) == Decimal("0.1"), so str() of that is "0.1".
    assert result["amount"] == "0.1"
    assert isinstance(result["amount"], str)


def test_records_each_invocation_to_recorder() -> None:
    """Every tool call is appended to the recorder in call order."""
    recorder = PaymentInstructionRecorder()
    tool = make_payment_instruction(recorder)
    tool(claim_number="CLM-00001", amount=100.0)
    tool(claim_number="CLM-00002", amount=200.0)

    calls = recorder.calls
    assert len(calls) == 2
    assert calls[0]["claim_number"] == "CLM-00001"
    assert calls[1]["claim_number"] == "CLM-00002"


def test_recorder_calls_property_returns_defensive_copy() -> None:
    """Mutating the returned calls list does not corrupt the recorder's internal state."""
    recorder = PaymentInstructionRecorder()
    tool = make_payment_instruction(recorder)
    tool(claim_number="CLM-00001", amount=100.0)

    first_snapshot = recorder.calls
    first_snapshot.pop()  # mutate the snapshot

    assert len(recorder.calls) == 1  # internal state unchanged


def test_recorded_amount_is_decimal_not_float() -> None:
    """The recorder stores Decimal, not the raw float passed by the model."""
    recorder = PaymentInstructionRecorder()
    tool = make_payment_instruction(recorder)
    tool(claim_number="CLM-00001", amount=100.0)

    assert isinstance(recorder.calls[0]["amount"], Decimal)
    assert recorder.calls[0]["amount"] == Decimal("100")


def test_two_factories_with_separate_recorders_are_independent() -> None:
    """Each factory closure captures its own recorder; calls don't bleed across."""
    recorder_a = PaymentInstructionRecorder()
    recorder_b = PaymentInstructionRecorder()
    tool_a = make_payment_instruction(recorder_a)
    tool_b = make_payment_instruction(recorder_b)

    tool_a(claim_number="CLM-00001", amount=100.0)
    tool_b(claim_number="CLM-00002", amount=200.0)

    assert len(recorder_a.calls) == 1
    assert recorder_a.calls[0]["claim_number"] == "CLM-00001"
    assert len(recorder_b.calls) == 1
    assert recorder_b.calls[0]["claim_number"] == "CLM-00002"
