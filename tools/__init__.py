"""Model-callable tool wrappers around domain and repository functions.

Each tool is produced by a factory that captures its dependency (e.g.,
a PolicyRepository) via closure. The agent constructs tools at __init__
time with injected dependencies, then passes them to the MAF agent.
"""

from tools.policy_lookup_by_claimant import make_policy_lookup_by_claimant
from tools.policy_lookup_by_number import make_policy_lookup_by_number

__all__ = ["make_policy_lookup_by_claimant", "make_policy_lookup_by_number"]
