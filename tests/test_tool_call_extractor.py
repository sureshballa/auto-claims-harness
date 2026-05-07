"""Tests for harness/middleware/tool_call_extractor.py."""

from __future__ import annotations

from agent_framework import AgentResponse, Content, Message

from harness.middleware.tool_call_extractor import extract_tool_call_names


def test_extract_returns_empty_when_messages_is_none() -> None:
    """AgentResponse constructed with messages=None normalizes to an empty list."""
    response = AgentResponse(messages=None)
    assert extract_tool_call_names(response) == []


def test_extract_returns_empty_when_no_tool_calls() -> None:
    """A message containing only text content produces no tool-call names."""
    message = Message(
        role="assistant",
        contents=[Content.from_text("Here is my analysis.")],
    )
    response = AgentResponse(messages=[message])
    assert extract_tool_call_names(response) == []


def test_extract_single_function_call() -> None:
    """One function_call content block returns a single-element list."""
    message = Message(
        role="assistant",
        contents=[Content.from_function_call(call_id="c1", name="lookup_policy", arguments={})],
    )
    response = AgentResponse(messages=[message])
    assert extract_tool_call_names(response) == ["lookup_policy"]


def test_extract_multiple_function_calls_preserves_order() -> None:
    """Multiple function_call blocks return names in the order they were called."""
    message = Message(
        role="assistant",
        contents=[
            Content.from_function_call(call_id="c1", name="first_tool", arguments={}),
            Content.from_function_call(call_id="c2", name="second_tool", arguments={}),
            Content.from_function_call(call_id="c3", name="third_tool", arguments={}),
        ],
    )
    response = AgentResponse(messages=[message])
    assert extract_tool_call_names(response) == ["first_tool", "second_tool", "third_tool"]


def test_extract_handles_single_message_not_sequence() -> None:
    """AgentResponse with a single Message (not a list) still extracts correctly."""
    message = Message(
        role="assistant",
        contents=[Content.from_function_call(call_id="c1", name="my_tool", arguments={})],
    )
    # MAF normalizes single Message to [message] internally
    response = AgentResponse(messages=message)
    assert extract_tool_call_names(response) == ["my_tool"]


def test_extract_skips_string_and_mapping_contents() -> None:
    """Non-tool-call content blocks (e.g. text) alongside a function_call are skipped.

    MAF does not store raw strings or dicts in message.contents — they are parsed
    into Content objects at construction time. This test uses Content.from_text()
    as the real-API equivalent of "non-tool-call content" alongside a function_call.
    """
    message = Message(
        role="assistant",
        contents=[
            Content.from_text("Checking the policy now."),
            Content.from_function_call(call_id="c1", name="lookup_policy", arguments={}),
            Content.from_text("Done."),
        ],
    )
    response = AgentResponse(messages=[message])
    assert extract_tool_call_names(response) == ["lookup_policy"]


def test_extract_handles_mcp_server_tool_call() -> None:
    """MCP server tool calls are extracted via content.tool_name, not content.name."""
    message = Message(
        role="assistant",
        contents=[
            Content.from_mcp_server_tool_call(
                call_id="c1",
                tool_name="mcp_lookup",
                server_name="policy-server",
            )
        ],
    )
    response = AgentResponse(messages=[message])
    assert extract_tool_call_names(response) == ["mcp_lookup"]
