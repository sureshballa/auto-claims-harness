# Stage 1 Sign-Off

Stage 1 ("Bare agent") is complete as of April, 25th, 2026. This document records what Stage 1 delivered, what it deliberately deferred, and the entry conditions for Stage 2.

## What Stage 1 delivered

- **`agents/fnol_agent.py`** — the first MAF-backed agent. Constructs a chat client via the Stage 0 provider factory, calls `as_agent(...)`, requests structured output via `response_format=AgentDecision`, parses the result, and returns an `AgentRunResult` that satisfies the `EvalAgent` protocol.
- **End-to-end integration verified** — the agent successfully calls GPT-OSS 20B via LM Studio, the model responds, and the response flows through our protocol.
- **First eval against a real LLM** — three scenarios (green-001, yellow-001, adversarial-001) run through the agent. All three errored on schema validation.
- **Documented failure modes** — `docs/stage-1-notes.md` captures three distinct failure patterns observed during the runs, each with a Stage 2 design driver attached.
- **Two Stage-1 patches applied** — markdown-fence stripping with manual JSON fallback. Both marked `# STAGE 1 PATCH` in code, scheduled for migration to middleware in Stage 2.

## What Stage 1 deliberately deferred

These are scoped technical debt — known, named, scheduled.

### Deferred to Stage 2

- **Migrate Stage 1 patches to middleware.** The fence-stripping fallback belongs in function middleware, not in the agent file.
- **Schema field-name normalization.** `amount_paid` → `payout_amount`, `reason` → `reasoning`, etc. As config-driven middleware.
- **Authority enforcement.** Override unilateral `deny` decisions on Yellow/Red/Black tiers to `escalate`, regardless of what the model produced.
- **First real tools.** `tools/` is still empty. Stage 2 introduces tool wrappers around `domain/` functions (policy_lookup, vehicle_valuation) so the model can ground its reasoning in real data rather than hallucinating.
- **Permissions config.** `config/permissions.yaml` to externalize who-can-do-what.
- **Tool allowlist config.** `config/tool_allowlist.yaml` for the deny-first tool gating.

### Deferred to Stage 3

- **Concrete `ClaimAwareContextProvider`.** Currently the agent receives the full claim+policy in a single rendered prompt; in Stage 3 we'll separate context provision from prompt construction.
- **Context compaction.** When claims grow long histories, summarization strategies live here.
- **MCP integration.** Currently all tools planned as in-process Python; MCP-served tools come at Stage 3.

### Deferred to Stage 4

- **Concrete `EventLog` implementation.** Stage 1 has no audit trail beyond stdout. Stage 2's middleware will start emitting events; Stage 4's event log captures them durably.
- **OpenTelemetry wiring.**
- **Eval scenario growth beyond 3.**

### Deferred to Stage 5

- **Multi-agent workflows.**
- **Subagent permission isolation.**
- **Comparative study against Claude Agent SDK (Option B).**

### Known model issues to navigate

- **GPT-OSS 20B's structured output is unreliable** — markdown fences, field renames, missing required fields. We will fix this with normalization middleware in Stage 2; we will NOT fix it by switching models. Working with weak-model behavior is part of the harness-engineering exercise.
- **MAF GitHub issue #1772** still applies for chat middleware (Stage 2+).
- **The `agent.run()` response object's exact shape** for `response_format` parsing varies by MAF version. Stage 1 introspected once; Stage 2's middleware will need to handle this carefully.

## Entry conditions for Stage 2

Stage 2 may begin when, and only when:

- [ ] All Stage 0 verifications still pass (pytest, ruff, mypy, runner)
- [ ] Stage 1 patches are committed
- [ ] `docs/stage-1-notes.md` documents the observed failures
- [ ] This sign-off file is committed
- [ ] Stage 1 has been tagged

## Stage 2's first concrete task

Build `harness/middleware/response_normalizer.py` containing a MAF function middleware that:

1. Catches the raw model response before Pydantic validation
2. Strips markdown fences (migrated from `agents/fnol_agent.py`)
3. Maps known field aliases (loaded from `config/response_aliases.yaml`)
4. Fills missing optional fields with reasonable defaults
5. Re-validates against `AgentDecision`
6. If validation still fails, returns a structured error so the agent can record it without crashing

The success criterion: `python -m evals.runner fnol` produces non-erroring AgentRunResults on at least the green-001 scenario, beating the null baseline on decision accuracy.

That's Stage 2's day-one target.
