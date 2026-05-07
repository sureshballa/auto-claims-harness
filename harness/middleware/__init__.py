"""Harness middleware — helpers that shape agent behavior.

ResponseNormalizer cleans weak-model JSON output before validation.
extract_tool_call_names extracts tool-call names from an AgentResponse.
Both are used directly by the agent rather than registered as MAF middleware.
"""

from harness.middleware.response_normalizer import ResponseNormalizer
from harness.middleware.tool_call_extractor import extract_tool_call_names

__all__ = ["ResponseNormalizer", "extract_tool_call_names"]
