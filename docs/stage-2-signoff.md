# Stage 2 Sign-Off

Stage 2 ("Minimal harness") is complete as of May 5th, 2026. This document records what Stage 2 delivered, what diverged from the original Stage 2 plan, what was deliberately deferred, and the entry conditions for Stage 3.

## What Stage 2 delivered

### Lesson 2.1 — Response normalizer

- **`harness/middleware/response_normalizer.py`** — `ResponseNormalizer` class. Strips markdown fences, strips the GPT-OSS Harmony prefix (`<|channel|>final <|constrain|>JSON<|message|>...`), applies field aliasing (e.g., `amount_paid` → `payout_amount`, `reason` → `reasoning`), returns cleaned JSON text or `None`.
- The Stage 1 patches (markdown-fence stripping, manual JSON fallback) are now removed from `agents/fnol_agent.py`.
- **Architectural decision: not MAF middleware.** MAF's structured-output parser runs inside `call_next()` before any post-next middleware code executes. Both `AgentMiddleware` and `ChatMiddleware` attempts failed (confirmed via `runs_processed: 0`). Solution: drop `response_format=` entirely; the agent calls `ResponseNormalizer.normalize(text)` directly after `await self._agent.run(prompt)`.

### Lesson 2.2 — Authority enforcement

- **`harness/policy_engine/authority.py`** — `AuthorityEngine` class. Tier-aware decision override: yellow/red/black tiers force `escalate` regardless of model proposal; green tier grants the model full authority.
- **Generalizable principle: "model proposes, harness answers, both visible."** `AuthorityRuling` records both the model's proposed values and the harness's final values, plus an `overridden` flag. Audits can reconstruct exactly what was proposed and where the harness disagreed.
- **Architectural decision: regular class, not MAF middleware.** Authority enforcement is domain-specific logic, not cross-cutting. Documented in `docs/maf-mapping.md`.
- **Tier is computed deterministically by the harness**, not trusted from the model. `assign_tier(claim, thresholds)` is the source of truth; the model's claimed tier is recorded for audit only.

### Lesson 2.3 — Externalized policy

- **`config/permissions.yaml`** — single combined file with two top-level sections: `tier_authority` (per-tier allowed decisions) and `response_normalizer` (field aliases, default values).
- **`harness/policy_engine/permissions_loader.py`** — strict loader. Rejects unexpected keys at every level. No silent acceptance of typos or stray fields.
- **`config/thresholds.yaml`** — tier thresholds (Green/Yellow/Red/Black damage cutoffs) live here, loaded via `load_thresholds`.
- Mechanism stays in code; semantics live in YAML.

### Lesson 2.4 — Concrete `ClaimDecisionEngine` behind Protocol

- **`harness/contracts/claim_decisions.py`** — `ClaimDecisionRequest`, `ClaimDecisionRuling`, and the `ClaimDecisionEngine` Protocol. Distinct from `PolicyEngine` (tool-call gating, Stage 3) — two contracts, two concerns.
- **`harness/contracts/policy_repository.py`** — `PolicyRepository` Protocol with single method `get_by_number(policy_number) -> Policy | None`.
- **`harness/policy_engine/mock_repository.py`** — `MockDataPolicyRepository`. Eager-loads policies into a dict for O(1) lookup. Structural conformance, no inheritance.
- **`harness/policy_engine/engine.py`** — `HarnessPolicyEngine`. Composes `AuthorityEngine` (decision-level) with `domain.calculations.coverage_applies` + `calculate_payout` (amount-level). Model's proposed payout is recorded for audit but never executed; the harness computes the authoritative amount from first principles.
- **`agents/fnol_agent.py`** — refactored. Constructor requires `claim_decision_engine: ClaimDecisionEngine` and `policy_repository: PolicyRepository`. Composition root moved to `__main__` blocks (agent script-mode entry, `evals/runner.py` `fnol` branch).
- **Generalized "model proposes, harness answers"** to two independent flags: `overridden` (decision-level disagreement) and `payout_overridden` (amount-level disagreement). Audits can distinguish "model chose wrong action" from "model chose right action but fabricated the amount."
- **`PolicyRepository` belongs to the agent, not the engine.** `ClaimDecisionRequest` carries the resolved `Policy | None` as input; the engine is pure on its inputs and performs no I/O.

### Lesson 2.5 — Sign-off (this lesson)

- **Prompt sharpening for sub-deductible damage.** `agents/fnol_agent.py` `INSTRUCTIONS` now explicitly directs `approve` with payout 0 when damage is below the deductible. The `approve`/`deny` definitions also tightened for coherence.
- **Stability eval.** N=5 runs across all 3 scenarios after the prompt fix.
  - `green-001-clean-collision`: 5/5 approve (was ~80/20 deny/approve before fix).
  - `yellow-001-needs-adjuster`: 5/5 escalate (harness override consistently fires).
  - `adversarial-001-unknown-policy`: 5/5 escalate.
  - Aggregate decision accuracy: 15/15 = 100%.
- **Generalizable harness principle recorded:** a harness's deterministic guarantees are tier-relative. Higher-stakes tiers are stable because the harness overrides; lower-stakes tiers reveal model variance because the model holds authority. The harness exposes — rather than hides — model unreliability where the model decides.

### Eval infrastructure

- Scenarios live at `evals/scenarios/` (3 scenarios end of Stage 2: `green-001-clean-collision`, `yellow-001-needs-adjuster`, `adversarial-001-unknown-policy`).
- Scored by `evals/runner.py`, invoked via `uv run python -m evals.runner fnol`.
- All eval runs hit GPT-OSS 20B via LM Studio at `http://localhost:1234`.

## What diverged from the original Stage 2 plan

The plan recorded in `docs/stage-1-signoff.md` listed `tools/` work and `config/tool_allowlist.yaml` as Stage 2 deferrals. **Neither was delivered in Stage 2.** Both are re-deferred to Stage 3. The Stage 2 slot was used instead for `ClaimDecisionEngine` Protocol + `HarnessPolicyEngine` + `PolicyRepository`, which were not on the original Stage 2 plan but became the natural "concrete implementation behind a contract" goal once 2.1–2.3 were in place.

## What Stage 2 deliberately deferred

### Deferred to Stage 3

- **`tools/` — first real tools.** Tool wrappers around `domain/` functions (policy_lookup, vehicle_valuation). Was on the original Stage 2 plan; did not happen. `tools/` directory remains empty.
- **`config/tool_allowlist.yaml` for deny-first tool gating.** Depends on `tools/` work.
- **Concrete `PolicyEngine` implementation** (the tool-call authorization gate from `harness/contracts/policy.py`). Distinct from `ClaimDecisionEngine`. Stage 3 concern.
- **Concrete `ClaimAwareContextProvider`.** Currently the agent receives full claim+policy in a single rendered prompt; Stage 3 separates context provision from prompt construction.
- **Context compaction.** Long-history summarization strategies.
- **MCP integration.** All current tools planned in-process; MCP-served tools come at Stage 3.
- **Eval runner observability.** Currently emits aggregate-only output; per-scenario detail required ad-hoc inline scripts during 2.4 diagnosis. Per-scenario detail should come from the runner directly.
- **Prompt sharpening — additional sub-deductible scenarios.** 2.5 fixed the green-001 case; other potentially-ambiguous scenarios are not yet exercised.

### Deferred to Stage 4

- **Concrete `EventLog` implementation.** Stage 2 has middleware that could emit events but no durable capture layer.
- **OpenTelemetry wiring.**
- **Eval scenario growth beyond 3.** N=3 with one inherently variable scenario produces noisy aggregate metrics. Stable headline numbers require more scenarios with unambiguous expected outcomes.

### Deferred to Stage 5

- **Multi-agent workflows.**

### Stage 2 cleanup (not stage-aligned)

- **`HarnessPolicyEngine.__init__` stores `thresholds` separately** and passes through to `AuthorityEngine.evaluate()` on every call — a legacy of `AuthorityEngine`'s original per-call signature. Cleanup: move `thresholds` into `AuthorityEngine.__init__`. Blocked by the existing 19-test `AuthorityEngine` suite, which would need updating.

## Entry conditions for Stage 3

- All Stage 2 contracts in place and exercised by evals.
- Three scenarios passing 5/5 against GPT-O