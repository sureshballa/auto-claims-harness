# Stage 1 — Notes from the naive agent

This document records what we observed running the FnolAgent (Stage 1's
deliberately naive agent) against the eval scenarios. The findings here
are the design input for Stage 2.

## Setup

- Model: GPT-OSS 20B via LM Studio at http://localhost:1234
- Agent: agents/fnol_agent.py — no middleware, no tools, no policy enforcement
- Scenarios: 3 (green-001, yellow-001, adversarial-001)
- Null-agent baseline (for comparison): ~67% decision accuracy

## Headline result

The naive FnolAgent scored **0%** on decision accuracy across all three
scenarios — worse than the do-nothing null baseline. Every scenario
errored at the schema-validation layer before substantive scoring could
occur.

This is the expected, designed-for outcome of Stage 1. The naive agent
exists to expose failure modes. It exposed them.

## Stage-1 patches applied

The following patches were added to `agents/fnol_agent.py` to make
later failures visible behind earlier ones. They are marked with
`# STAGE 1 PATCH` and MUST migrate to harness/middleware/ in Stage 2:

- **Markdown-fence stripping fallback.** GPT-OSS 20B wraps structured
  output in ```json fences despite `response_format`. Patch strips
  fences and re-validates.

## Observed failure modes

### Failure 1: Schema field divergence

- **Where seen:** all three scenarios
- **Symptom:** `2 validation errors for AgentDecision` — Pydantic rejects
  the cleaned JSON because required fields are missing or renamed.
- **What the model actually did:**
  - green-001 → `{"decision":"approve","tier":"green","amount_paid":0.0}`
    (renamed `payout_amount` to `amount_paid`; omitted `reasoning`)
  - yellow-001 → `{"claim_id":"CLM-00006","tier":"yellow","decision":"deny"}`
    (invented `claim_id`; omitted `payout_amount` and `reasoning`)
  - adversarial-001 → `{"tier":"black","decision":"escalate"}`
    (omitted `payout_amount` and `reasoning`)
- **Root cause:** GPT-OSS 20B paraphrases schema field names, omits
  fields it can't fill, and invents fields it thinks should exist.
  Schema fidelity is intent-level, not character-level.
- **Stage 2 fix:** Function-middleware response normalizer that aliases
  known field-name variants and supplies defaults for missing fields,
  applied before Pydantic validation.

### Failure 2: Substantive over-reach (the yellow-001 deny)

- **Where seen:** yellow-001
- **Symptom:** Model returned `decision: "deny"` for a claim that
  required adjuster escalation.
- **What the model actually did:** Made a unilateral denial on a
  $2,800 collision claim — a Yellow-tier action that should have been
  escalated to a human adjuster.
- **Root cause:** The model's instruction to "escalate when unclear"
  is a soft constraint. The model's training-time bias toward "be
  helpful by giving an answer" overrides the instruction at runtime.
- **Stage 2 fix:** Agent-middleware authority enforcement. If the model
  proposes deny/approve on a tier above its authority, the harness
  overrides to escalate regardless of model output. The model's
  proposed decision goes into the audit trail; the actual decision is
  what the harness allows.
- **Severity:** This is the highest-severity failure observed. In
  production, an agent that confidently denies claims it should have
  escalated produces silent regulatory violations, financial harm to
  policyholders, and an audit trail with no human sign-off. This is
  exactly the failure mode harness engineering exists to prevent.

### Failure 3: Mock policy was provided but the model's behavior varied

- **Where seen:** all three scenarios, but most clearly green-001
  and yellow-001
- **Symptom:** The model sometimes claimed missing information when
  the prompt contained full policy details.
- **Root cause hypothesis:** The model either (a) didn't read the
  prompt carefully, (b) chose escalation as a default safe behavior,
  or (c) hallucinated missing information to justify the answer it
  intended to give.
- **Stage 2 fix candidate:** Tools that ground the model in real data.
  Instead of pasting policy details into the prompt, the model calls
  a `policy_lookup` tool. The tool's result is verifiable; the model
  cannot claim "policy not found" unless the tool actually returned that.
  This converts a soft constraint (read the prompt) into a hard one
  (call the tool to know the answer).
- **Note:** This finding will only become actionable after the schema
  failures are fixed. Until then, every response is a parse error and
  the substantive layer is masked.

## Substantive observations (model reasoning quality, where visible)

Looking at the captured raw responses (truncated in the error messages):

- **green-001** — the model said `approve, green` — substantively correct.
  Schema-renaming was the only blocker. **A fully-working harness should
  pass this scenario.**
- **yellow-001** — the model said `deny`. Substantively wrong. Even with
  a perfect schema layer, this scenario will fail without authority
  enforcement.
- **adversarial-001** — the model said `escalate, black`. Decision was
  correct (escalate); tier was defensible-but-different from the scenario's
  `yellow` expectation. Suggests we should accept tier `black` as a valid
  outcome for unknown-policy adversarial cases (or document the
  distinction). Possibly an eval refinement, not a harness gap.

## What this tells us about Stage 2's design

Three priorities, in order:

1. **Response-normalization middleware** (mechanical layer). Without
   this, nothing else matters because every response is a parse error.
   Stage 2 Lesson 2.1 territory.
2. **Authority-enforcement middleware** (policy layer). This is where
   harness engineering proves its value — preventing the model from
   exceeding its authority on yellow-001-style cases. Stage 2 Lesson
   2.2 territory.
3. **Externalized policy configuration**. Aliases, authority mappings,
   tier-decision rules — all in YAML, not code. Stage 2 Lesson 2.3
   territory.

A note on what we're NOT considering yet: tools that ground the model
in real data (policy_lookup, vehicle_valuation). These will help with
Failure 3 but are Stage 3 work — the harness layer comes before the
extensibility layer.

## Numbers

- **Null baseline:** ~67% decision accuracy (escalate-only)
- **FnolAgent (Stage 1, naive):** 0% decision accuracy
- **Headline:** The naive agent loses to the do-nothing baseline.
  This is the motivation for Stage 2.
