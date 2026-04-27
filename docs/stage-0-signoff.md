# Stage 0 Sign-Off

Stage 0 ("Scaffold and Foundations") is complete as of [today's date].
This document records what Stage 0 delivered, what it deliberately deferred,
and the entry conditions for Stage 1.

## What Stage 0 delivered

The full deliverables list is in this commit's diff against the project's
initial commit. Headlines:

- Pure-Python domain layer (models, tiers, deterministic calculations) with full test coverage
- Externalized tier-threshold policy via `config/thresholds.yaml` + strict loader
- 50 policies and 20 claims as reproducible mock data, including 3 adversarial cases
- Harness contracts (Principal, PolicyEngine, EventLog, ClaimAwareContextProvider) as Python Protocols, with structural-conformance verification
- Provider factory supporting LM Studio (local) / Anthropic / OpenAI, verified end-to-end against real GPT-OSS 20B
- Eval skeleton: scenario format, runner, metrics, null agent baseline (~67% decision accuracy on the seed scenarios)
- `CLAUDE.md` as a living dev-loop policy file with rules accumulated through Stage 0
- `/harness-check` slash command for AI-assisted architectural review
- Documentation: principles reference, MAF mapping with version-pinned learnings

## What Stage 0 deliberately deferred

These are scoped technical debt — known, named, scheduled.

### Deferred to Stage 1

- **The agent itself.** Stage 0 ships no LLM-backed agent. Stage 1's first task is making `agents/` non-empty.
- **An `EvalAgent` adapter for MAF agents.** The null agent satisfies the protocol; a real wrapper around `client.as_agent(...)` is Stage 1's job.
- **First real tools.** Currently `tools/` is empty save for `__init__.py`. Stage 1 introduces the first `@tool` functions wrapping `domain/` calls.

### Deferred to Stage 2

- **Concrete `PolicyEngine` implementation.** Contract exists; no implementation.
- **Middleware: principal injection, function gates, audit chat middleware.** All planned, none built.
- **Tool `approval_mode` policies per blast radius.**
- **Permissions config (`config/permissions.yaml`) and tool allowlists (`config/tool_allowlist.yaml`).** Currently only `thresholds.yaml` exists.

### Deferred to Stage 3

- **Real `ClaimAwareContextProvider` implementations.** Contract exists; no implementation.
- **Context compaction strategies.** MAF gives us hooks; we haven't used them.
- **MCP integration for any tool.** Currently all tools planned as in-process Python.

### Deferred to Stage 4

- **Concrete `EventLog` implementation.** Contract exists; no implementation.
- **OpenTelemetry wiring.** MAF emits OTel natively; we haven't piped it anywhere.
- **Eval scenarios beyond 3.** Three was the minimum to validate the skeleton; coverage growth is part of Stage 4's eval-and-governance work.

### Deferred to Stage 5

- **Multi-agent workflows via MAF Workflow primitives.**
- **Subagent permission isolation.**
- **Comparative study against `agent_framework_claude.ClaimAgent` (Option B).**

### Known issues to revisit

- **MAF GitHub issue #1772**: `ChatMiddleware` with local OpenAI-compat models doubles system instructions. Will hit at Stage 2 when we add chat middleware. Revisit then.
- **MAF API drift between docs and 1.1.x.** Documented in `maf-mapping.md`. Re-verify when we bump the MAF version constraint.
- **GPT-OSS 20B sometimes fails simple instruction-following** (e.g., "reply in three words" returned four). Mitigation is harness validation of agent output, not prompt tweaking.
### Recovery: missing thresholds loader (discovered Stage 2.2)

The `harness/policy_engine/thresholds_loader.py` module and 
`config/thresholds.yaml` file were originally specified in Lesson 0.6 
and listed in Stage 0's sign-off checklist as delivered. They were 
discovered missing at the start of Lesson 2.2 — likely never committed 
in the original Stage 0 work, despite tests passing in some form during 
that lesson.

Both files were recreated as a prerequisite for Lesson 2.2:
- `config/thresholds.yaml` — externalized tier thresholds (500 / 5000 / 25000)
- `harness/policy_engine/thresholds_loader.py` — strict YAML loader with 
  validation
- `tests/test_policy_engine_thresholds.py` — 8 tests covering happy path 
  and adversarial inputs

This is recorded honestly because the staged-debt discipline requires 
acknowledging gaps explicitly, even when they appeared after-the-fact. 
The Stage 0 tag `stage-0` reflects the project state as it actually was 
when tagged, not as the sign-off described it.

Lesson learned: future stage sign-offs should verify each checklist item 
is actually present in the committed tree, not just that it was created 
at some point during the stage.

## Entry conditions for Stage 1

Stage 1 may begin when, and only when:

- [ ] All checkboxes in `tests/`, `evals/`, lint, type-check are green
- [ ] `python -m evals.runner` produces the null-baseline report without error
- [ ] Live-model smoke test against LM Studio + GPT-OSS 20B completes a round-trip
- [ ] This sign-off file is committed
- [ ] Stage 0 has been merged to `main` (single commit or otherwise)

## Stage 1's first concrete task

Build `agents/fnol_agent.py` containing a class `FnolAgent` that:

1. Constructs a MAF agent via `harness.providers.build_chat_client()` and `.as_agent(...)`
2. Satisfies the `EvalAgent` protocol (`async def run_scenario(self, scenario) -> AgentRunResult`)
3. Reads the claim referenced by `scenario.claim_number` from `domain.mock_data`
4. Sends a structured prompt to the model asking for tier and decision
5. Returns an `AgentRunResult` with the LLM's tier/decision parsed back into our types

The success criterion: `python -m evals.runner` (with `FnolAgeKnown issues to revisitnt` swapped in for `NullAgent`) produces a higher decision-accuracy score than the null baseline, on at least the green-001 scenario.

That's Stage 1's day-one target.