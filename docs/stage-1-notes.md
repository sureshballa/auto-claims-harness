# Stage 1 — Notes from the naive agent

This document records what we observed running the FnolAgent (Stage 1's
deliberately naive agent) against the eval scenarios. The point is not
to fix the failures here — it's to capture them as design input for
Stage 2's harness.

## Setup at time of observation

- **Model:** GPT-OSS 20B via LM Studio at http://localhost:1234
- **Agent:** `agents/fnol_agent.py` — no middleware, no tools, no policy enforcement
- **Scenarios:** 3 (green-001, yellow-001, adversarial-001)
- **Null-agent baseline:** 67% decision accuracy, 0% tier accuracy, 100% blast-radius compliance, 0% error rate
- **FnolAgent results:** 0% decision accuracy, 0% tier accuracy, 100% blast-radius compliance, 100% error rate

**Headline: the naive FnolAgent loses to the do-nothing NullAgent.** Every scenario errored on schema validation. Even though the model's substantive reasoning was correct on 2 of 3 scenarios, none of those decisions reached the eval scorer because schema validation failed first.

## Stage-1 patches applied

The following patches were applied to surface failures behind earlier failures. They are marked in code with `# STAGE 1 PATCH` and MUST migrate to `harness/middleware/` in Stage 2:

- **Markdown-fence stripping** in `agents/fnol_agent.py`. GPT-OSS 20B wraps structured-output JSON in ```json fences despite the `response_format` parameter. The patch falls back to a manual `agent.run()` without `response_format`, then strips fences and re-validates.

These patches are intentionally ugly. They live in the agent file rather than middleware so the migration burden is visible. Do not "improve" them at this stage.

## Observed failure modes

### Failure 1: Schema field-name divergence

- **Where seen:** all three scenarios
- **Symptom:** `AgentRunResult.error = "2 validation errors for AgentDecision"` — Pydantic rejects the parsed JSON
- **What the model actually did:**
  - green-001 returned: `{'decision': 'approve', 'tier': 'green', 'amount_paid': 0.0}`
  - yellow-001 returned: `{'claim_id': 'CLM-00006', 'tier': 'yellow', 'decision': 'deny'}`
  - adversarial-001 returned: `{'tier': 'black', 'decision': 'escalate'}`
- **Pattern:** the model paraphrases or invents field names (`amount_paid` instead of `payout_amount`, `claim_id` not in schema), and omits required fields (`payout_amount`, `reasoning`) when it has nothing meaningful to put there.
- **Root cause hypothesis:** GPT-OSS 20B does not respect schemas verbatim. Its training favors "be helpful by formatting nicely" over "match the schema exactly." A frontier model would not do this.
- **What would fix this in Stage 2:** A *function middleware* that:
  1. Catches the raw response before Pydantic validation
  2. Maps known field aliases (`amount_paid` → `payout_amount`, `reason` → `reasoning`)
  3. Fills missing optional fields with defaults
  4. Then validates
  This is policy applied to model output. The agent does not become smarter; the harness becomes more tolerant.

### Failure 2: Yellow-001 — model exceeded authority

- **Where seen:** yellow-001 specifically
- **Symptom:** model returned `decision: 'deny'` when scenario expected `escalate`
- **What the model actually did:** Made a unilateral negative decision on a mid-damage claim that should have been flagged for adjuster review. The instruction "if information is missing or unclear, ESCALATE rather than guess" was overridden by the model's "be helpful, give an answer" instinct.
- **Why this is the most important finding:** This is the *substantive* failure mode harness engineering exists to prevent. A confident wrong denial is worse than no decision: it produces a silent regulatory event (a customer who didn't get paid, an adjuster who never reviewed, an audit trail with no human sign-off). The blast radius is high, the reversibility is poor.
- **What would fix this in Stage 2:** *Agent middleware* that enforces tier-based authority:
  1. After the model produces its proposed decision, look up the claim's tier
  2. If decision is `deny` or `approve` on Yellow/Red/Black tier, override to `escalate`
  3. Log the original decision and the override as separate events for audit
  
  The model's say-so is insufficient at high-risk tiers. The harness must hold the line regardless of what the LLM produced. This is the *deny-first* principle applied to model output rather than tool calls.

### Failure 3: Schema strictness rejects near-misses

- **Where seen:** consequence of Failure 1, but worth naming separately
- **Symptom:** Pydantic's strict validation rejects the entire response when ANY field is wrong, even when the response is 80% correct
- **Root cause:** strict validation is the right default for a typed system, but it's the wrong default for LLM output where partial correctness is the norm
- **What would fix this in Stage 2:** A design call between two approaches:
  1. **Tolerant parsing layer** — accept near-miss output, normalize it, validate strictly only after normalization (preserves the strict downstream contract; adds tolerance at the edge)
  2. **Re-prompt loop** — when validation fails, send the model the validation error and ask it to fix its output (preserves strictness everywhere; adds latency and token cost)
  
  We will likely need both, applied selectively.

## Substantive observations beyond the schema layer

Even though the parse failures masked most behavior, the captured raw responses leak useful signal:

- **The model's tier assignment was correct on green-001** (`tier: 'green'`). Simple cases work.
- **The model's tier assignment was correct on yellow-001** (`tier: 'yellow'`). Damage-based tiering is something it can do.
- **The model's tier assignment on adversarial-001 was `black`** rather than the expected `yellow`. This is defensible — when the policy can't be found, treating it as the highest-risk tier is reasonable. The scenario's `expected_tier: yellow` reflects our `assign_tier` default behavior for un-assessable claims; the model's `black` reflects a stricter interpretation. Either could be argued. We may revisit the scenario's expected tier in Stage 2.
- **The model invented fields it thought should exist** (`claim_id`, `amount_paid`). This suggests it has a coherent mental model of "what fields a claim decision JSON should have" that diverges from our schema. In Stage 2, we can either teach it our schema better (longer instructions with examples) or normalize at the edge.
- **The model never called any tools** (correct — none exist yet). This means blast-radius compliance is trivially 100%. Once tools exist in Stage 2+, we'll need to verify the model doesn't call payment_instruction in scenarios where the expected_decision is escalate or deny.

## What this tells us about Stage 2's design

The naive agent's failures cluster into three Stage 2 concerns:

1. **Mechanical normalization** (markdown fences, field renames, missing fields)
   → response normalizer middleware (function middleware in MAF)
2. **Policy enforcement** (model exceeded authority on yellow-001)
   → authority-check middleware (agent middleware in MAF), driven by externalized config
3. **Strict-vs-tolerant boundary** (where does the harness accept near-misses?)
   → architectural decision documented per principle, with config-driven thresholds

Stage 2's first lesson should address #1 (it's blocking everything else). Stage 2's second lesson should address #2 (it's the most important substantive finding). Stage 2's third lesson should address #3 (it's the design conversation that ties them together).

## Numbers summary

| Metric | NullAgent | FnolAgent (Stage 1) |
|---|---|---|
| Decision accuracy | 67% (2/3 — escalation matches expected on yellow + adversarial) | 0% (3/3 errored on schema validation) |
| Tier accuracy | 0% (always None) | 0% (always None due to errors) |
| Blast-radius compliance | 100% (no tools called) | 100% (no tools to call) |
| Error rate | 0% | 100% |

**The naive agent does worse than doing nothing.** This is the expected, designed-for outcome of Stage 1. It motivates Stage 2 with concrete data.
