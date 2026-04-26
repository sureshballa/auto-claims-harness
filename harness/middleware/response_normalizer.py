"""Response normalizer for the FNOL adjudication agent.

Cleans weak-model JSON output before validation. Used directly by the agent,
not registered as MAF middleware. Two previous attempts at MAF middleware
interception (AgentMiddleware, ChatMiddleware) failed because MAF's
response_format parsing runs in a location neither layer could reach. This
class is a plain helper that the agent calls explicitly.

Handles three failure modes observed with GPT-OSS 20B and similar open-weight
models that nominally support structured output but occasionally deviate:

  1. Markdown-fence wrapping — model wraps JSON in ```json ... ``` despite
     response_format being set.
  2. Field-name divergence — model uses synonyms ("reason" instead of
     "reasoning", "amount" instead of "payout_amount").
  3. Missing required fields — model omits fields with obvious defaults (e.g.,
     payout_amount for an escalation).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

_MARKDOWN_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
_HARMONY_PREFIX_RE = re.compile(
    r"^<\|channel\|>\s*\w+\s*(?:<\|constrain\|>\s*\w+\s*)?<\|message\|>",
    re.IGNORECASE,
)

_FIELD_ALIASES: dict[str, str | None] = {
    "amount_paid": "payout_amount",
    "amount": "payout_amount",
    "claim_amount": "payout_amount",
    "reason": "reasoning",
    "explanation": "reasoning",
    "rationale": "reasoning",
    "claim_id": None,    # invented field — not part of AgentDecision schema
    "claimId": None,
    "claim_number": None,
}

_DEFAULT_VALUES: dict[str, Any] = {
    "payout_amount": 0.0,
    "reasoning": "(no reasoning provided by model)",
}

logger = logging.getLogger(__name__)


class ResponseNormalizer:
    """Normalize raw LLM text into a clean JSON string parseable as AgentDecision.

    Handles markdown-fence wrapping, field-name divergence, and missing
    required fields observed with GPT-OSS 20B and similar open-weight models.

    Stateful: the run/fence/rename/drop/default/success/failure counters
    accumulate across calls. Construct a fresh instance to reset all counts.
    """

    def __init__(self) -> None:
        self.runs_processed: int = 0
        self.fence_strips: int = 0
        self.harmony_prefix_strips: int = 0
        self.field_renames: int = 0
        self.field_drops: int = 0
        self.field_defaults_applied: int = 0
        self.normalizations_succeeded: int = 0
        self.normalizations_failed: int = 0

    def normalize(self, text: str) -> str | None:
        """Normalize raw LLM text into a clean JSON string parseable as AgentDecision.

        Returns None if normalization is not possible (e.g., text is not
        JSON-shaped at all). Updates stat counters on every call.
        """
        self.runs_processed += 1
        result = self._normalize_text(text)
        if result is None:
            self.normalizations_failed += 1
        else:
            self.normalizations_succeeded += 1
        return result

    def _normalize_text(self, text: str) -> str | None:
        """Strip fences, rename aliased fields, apply defaults. Return cleaned JSON or None."""
        stripped = text.strip()

        # Strip Harmony-format wrapper if present (used by GPT-OSS family)
        harmony_match = _HARMONY_PREFIX_RE.match(stripped)
        if harmony_match:
            stripped = stripped[harmony_match.end():].strip()
            self.harmony_prefix_strips += 1

        match = _MARKDOWN_FENCE_RE.match(stripped)
        if match:
            stripped = match.group(1)
            self.fence_strips += 1

        try:
            parsed: Any = json.loads(stripped)
        except json.JSONDecodeError:
            return None

        if not isinstance(parsed, dict):
            return None

        # Iterate over a snapshot — we mutate parsed in the loop.
        for key in list(parsed.keys()):
            if key in _FIELD_ALIASES:
                new_name = _FIELD_ALIASES[key]
                if new_name is None:
                    del parsed[key]
                    self.field_drops += 1
                    logger.debug("ResponseNormalizer: dropped invented field %r", key)
                else:
                    parsed[new_name] = parsed.pop(key)
                    self.field_renames += 1
                    logger.debug(
                        "ResponseNormalizer: renamed field %r -> %r", key, new_name
                    )

        for field, default in _DEFAULT_VALUES.items():
            if field not in parsed:
                parsed[field] = default
                self.field_defaults_applied += 1
                logger.debug("ResponseNormalizer: applied default for missing field %r", field)

        return json.dumps(parsed)
