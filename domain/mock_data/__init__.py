"""This module loads the seed mock data shipped in policies.json and claims.json.

Used by tests, evals, and the dev-time agent. Not for production data — the API
surface is identical, but the underlying source would change.
"""

import json
from pathlib import Path

from domain.models import Claim, Policy

__all__ = ["load_claims", "load_policies"]

_HERE = Path(__file__).parent


def load_policies(path: Path | None = None) -> list[Policy]:
    """Load policies from the bundled policies.json (or a custom path).

    Args:
        path: optional override; defaults to policies.json next to this module.

    Returns:
        List of Policy instances.

    Raises:
        FileNotFoundError if the file is missing.
        pydantic.ValidationError if any record fails to parse.
    """
    resolved = path if path is not None else _HERE / "policies.json"
    raw = resolved.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {resolved}, got {type(data).__name__}")
    return [Policy.model_validate(item) for item in data]


def load_claims(path: Path | None = None) -> list[Claim]:
    """Load claims from the bundled claims.json (or a custom path).

    Args:
        path: optional override; defaults to claims.json next to this module.

    Returns:
        List of Claim instances.

    Raises:
        FileNotFoundError if the file is missing.
        pydantic.ValidationError if any record fails to parse.
    """
    resolved = path if path is not None else _HERE / "claims.json"
    raw = resolved.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {resolved}, got {type(data).__name__}")
    return [Claim.model_validate(item) for item in data]
