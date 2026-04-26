"""Harness middleware — helpers that shape agent behavior.

ResponseNormalizer cleans weak-model JSON output before validation.
It is used directly by the agent rather than registered as MAF middleware.
"""

from harness.middleware.response_normalizer import ResponseNormalizer

__all__ = ["ResponseNormalizer"]
