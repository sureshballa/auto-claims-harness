"""Tool-call name extractor for post-run agent response observation.

Parallel to ResponseNormalizer in purpose: an observation utility applied
to an agent run result, not part of the adjudication pipeline. Lives in
middleware/ because it sits between the raw MAF AgentResponse and the
harness's AgentRunResult, shaping what the harness records.

Single observation path for both in-process function calls and MCP server
tool calls — callers don't need to know which transport was used.
"""

from __future__ import annotations

from agent_framework import AgentResponse


def extract_tool_call_names(response: AgentResponse) -> list[str]:
    """Return the name of each tool call observed in the response, in call order.

    Walks all messages in the response and collects names from content blocks
    whose type is "function_call" (in-process tools) or "mcp_server_tool_call"
    (MCP server tools). All other content types are silently skipped.

    Returns an empty list if the response contains no messages or no tool calls.
    """
    names: list[str] = []
    for message in response.messages:
        for content in message.contents:
            if content.type == "function_call" and content.name is not None:
                names.append(content.name)
            elif content.type == "mcp_server_tool_call" and content.tool_name is not None:
                names.append(content.tool_name)
    return names
