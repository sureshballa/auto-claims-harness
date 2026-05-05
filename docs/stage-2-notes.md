# Stage 2 — Notes from the minimal harness

This document accumulates lesson notes for Stage 2. Stage 2's goal is to
wrap the naive Stage 1 agent in enough deterministic harness to make it
safe to run: response normalization, authority enforcement, externalized
policy, and a concrete ClaimDecisionEngine behind a Protocol.

---

## Lesson 2.4 — Concrete ClaimDecisionEngine behind Protocol

### What was built

**`harness/contracts/claim_decisions.py`**
: `ClaimDecisionRequest`, `ClaimDecisionRuling`, and the
`ClaimDecisionEngine` Protocol. `ClaimDecisionRequest` carries the
resolved `Policy | None` as an input field so the engine is pure on
its inputs — no I/O at evaluate-time. `ClaimDecisionRuling` records
both the model's proposal and the harness's final decision, including
two independent audit flags (`overridden`, `payout_overridden`) that
surface decision-level vs amount-level disagreement separately.

**`harness/contracts/policy_repository.py`**
: `PolicyRepository` Protocol. Single method: `get_by_number(policy_number) -> Policy | None`.
`None` is a first-class return value, not an exception — adversarial
claims referencing non-existent policies are expected in normal operation.

**`harness/policy_engine/mock_repository.py`** — `MockDataPolicyRepository`
: Eager-loads all policies at construction, builds a `dict[str, Policy]`
for O(1) lookup by policy number. Satisfies `PolicyRepository`
structurally; does not declare it as a base class.

**`harness/policy_engine/engine.py`** — `HarnessPolicyEngine`
: Concrete `ClaimDecisionEngine`. Composes `AuthorityEngine`
(decision-level logic) with `domain.calculations.coverage_applies` +
`calculate_payout` (amount-level logic). The model's proposed payout
is recorded for audit but never executed; the harness always computes
the authoritative amount from first principles.

**`agents/fnol_agent.py`** — refactored
: `FnolAgent.__init__` now requires `claim_decision_engine:
ClaimDecisionEngine` and `policy_repository: PolicyRepository`.
Thresholds and `AuthorityEngine` construction moved out of the agent
into the composition root (`__main__` block and `evals/runner.py`).
Policy lookup migrated from `load_policies()` linear scan to
`self._policy_repository.get_by_number(claim.policy_number)`.
`[PAYOUT_OVERRIDDEN]` marker added to reasoning when `ruling.payout_overridden`.

**`evals/runner.py`** — patched
: The `fnol` branch of the `__main__` block now constructs
`HarnessPolicyEngine` and `MockDataPolicyRepository` and injects them
into `FnolAgent(decision_engine, repository)`.

### Key architectural decisions

**Two distinct Protocols, not one.**
`PolicyEngine` (tool-call gating, Stage 3) and `ClaimDecisionEngine`
(claim adjudication, Stage 2) are separate concerns with separate
contracts. Merging them would have coupled adjudication authority to
tool authorization — two problems that change independently and for
different reasons.

**PolicyRepository belongs to the agent, not the engine.**
`ClaimDecisionRequest` carries the resolved `Policy | None` as an
input field; the engine is pure on its inputs and performs no I/O.
This makes `HarnessPolicyEngine` fully testable without mocking a
repository, and keeps the "look up the policy" concern at the
agent-orchestration layer where it belongs.

**Structural typing only — no inheritance from Protocol.**
`HarnessPolicyEngine` and `MockDataPolicyRepository` satisfy their
respective Protocols structurally. Declaring an explicit base class
would add runtime coupling with no type-safety benefit.

**"Model proposes, harness answers, both visible" — generalized.**
Stage 2.2's `AuthorityRuling.overridden` flag was the first instance
of this pattern. Lesson 2.4 extends it: `ClaimDecisionRuling` carries
*two* independent override flags — `overridden` for the decision and
`payout_overridden` for the amount. Both can be set simultaneously or
independently, letting auditors distinguish "model chose the wrong
action" from "model chose correctly but fabricated the amount."

### Eval findings

**Setup**
- Model: GPT-OSS 20B via LM Studio
- Scenarios: 3 (green-001-clean-collision, yellow-001, adversarial-001)
- N = 5 runs per scenario

**Yellow-tier and adversarial scenarios: stable.**
Both scenarios produced consistent results across all 5 runs. The
harness imposes the decision on yellow-tier (APPROVE overridden to
ESCALATE) and on adversarial (policy=None → payout=0). Model variance
is invisible at the output layer for these cases.

**Green-tier scenario (CLM-00001): variance observed.**
Approximately 80/20 deny/approve across 5 runs. This is the scenario
the harness does not override — green tier, model has full authority.

**Root cause: seed-data design + prompt silence.**
Green-tier claims in the seed data have damage amounts of $100–$450
against a $500 collision deductible. The prompt instructions describe
tier thresholds and decision options but say nothing about how to
label sub-deductible damage. Both "deny — not covered, damage below
deductible" and "approve $0" are defensible from the model's
perspective. The model flips between them.

**Generalizable harness principle.**
A harness's deterministic guarantees are tier-relative. Higher-stakes
tiers are stable because the harness overrides model decisions;
lower-stakes tiers reveal model variance precisely because the model
has authority there. This is the harness working as designed — it
exposes model unreliability where the model holds authority rather
than hiding it. The appropriate response is to either sharpen the
prompt (so the model has less ambiguity) or expand the test suite
(so per-scenario variance doesn't dominate aggregate metrics).

**Decision: not in scope for 2.4.** Recorded here as a finding.

### Carry-forward items (not fixed in 2.4)

**Prompt sharpening — sub-deductible case.**
Add explicit instructions for how to handle damage that falls below
the deductible: either "deny if damage < deductible" or "approve $0
with explanation." Either is correct; the model needs a rule.
→ Stage 2 polish ticket.

**Eval suite expansion.**
N=3 with one inherently variable scenario produces noisy aggregate
metrics (green-001's variance swamps the 67% accuracy baseline from
the null agent). Expanding to 10+ scenarios, including more green-tier
cases with unambiguous expected outcomes, would yield stable metrics.
→ Stage 3 eval-expansion ticket.

**`HarnessPolicyEngine.__init__` stores `thresholds` separately.**
`thresholds` is stored on the engine and passed through to
`AuthorityEngine.evaluate()` on every call — a legacy of
`AuthorityEngine`'s original per-call signature. Candidate cleanup:
move `thresholds` into `AuthorityEngine.__init__` so the engine
constructs with everything it needs. Blocked by the 19-test suite
for `AuthorityEngine`, which would need updating.
→ Stage 2 cleanup ticket.

**Runner observability.**
The eval runner emits only aggregate metrics. Diagnosing the green-001
variance required an ad-hoc inline script to capture per-run results.
Per-scenario detail should be available from the runner directly,
not require external tooling.
→ Stage 3 ticket.
