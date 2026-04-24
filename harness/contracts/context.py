"""
Claim-aware context provider Protocol for the harness.

MAF supplies its own ContextProvider base class for injecting context into agent prompts.
This Protocol defines an additional, orthogonal shape: a provider that is claim-aware,
meaning it can render context scoped to a specific claim number.

We deliberately do not import MAF here. Importing MAF in the contracts layer would couple
our interface definitions to a framework version, making them harder to test in isolation
and violating the contracts layer's role as pure, dependency-free vocabulary. Implementations
can satisfy both interfaces simultaneously — Python's structural typing makes that free.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ClaimAwareContextProvider(Protocol):
    """A context provider that supplies claim-specific context.

    Implementations MUST be idempotent: same claim_number -> same context.
    Implementations MUST be read-only with respect to the claim.
    """

    def context_for_claim(self, claim_number: str) -> str:
        """Return a rendered string of context for the given claim.

        May be empty if no context is available. Never raises
        for a missing claim; returns empty instead. Callers must
        distinguish 'no context' from 'error' through other means.
        """
        ...
