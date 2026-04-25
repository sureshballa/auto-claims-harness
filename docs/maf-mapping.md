# MAF Mapping

This document records our project's relationship with Microsoft Agent Framework (MAF):
which of the 13 harness engineering principles MAF primitives serve, which we build,
and what we've learned about MAF's actual behavior in the version we use.

**Pinned MAF version: `>=1.1,<2.0`** (currently 1.1.1 at time of writing).
Re-verify the version-specific notes when this constraint is bumped.

Reference: Liu et al., "Dive into Claude Code: The Design Space of Today's and
Future AI Agent Systems," arXiv 2604.14228, 2026. See `principles.md`.

## Principle → MAF mapping

| # | Principle | MAF provides | This project builds |
|---|-----------|--------------|---------------------|
| 1 | Deny-first with human escalation | Tool `approval_mode`, `MiddlewareTermination` exception | `PolicyEngine` contract; concrete impl at Stage 2 |
| 2 | Graduated trust spectrum | Middleware scoping per agent run | Tier logic in `domain.tiers`; `Principal` kinds with differing authority |
| 3 | Defense in depth with layered mechanisms | 3 middleware layers (agent, function, chat) | Concrete policies at each layer |
| 4 | Externalized programmable policy | — | `config/*.yaml` + loaders in `harness.policy_engine` |
| 5 | Context as scarce resource | Context providers, `AgentSession` | `ClaimAwareContextProvider`; compaction logic at Stage 3 |
| 6 | Append-only durable state | `AgentSession` (mutable), OTel traces (ephemeral) | `EventLog` contract; concrete impl at Stage 4 |
| 7 | Minimal scaffolding, maximal harness | The middleware-first design | Discipline in `CLAUDE.md`; code organization (`harness/` peer to `agents/`) |
| 8 | Values over rules | — | Agent instructions and contract design |
| 9 | Composable multi-mechanism extensibility | Middleware chain, `@tool`, MCP, Workflows | How we wire and compose them |
| 10 | Reversibility-weighted risk | — | Tier logic + per-tool `approval_mode` + middleware gates |
| 11 | Transparent file-based configuration | — | `config/*.yaml`, `CLAUDE.md`, this file, scenarios as YAML |
| 12 | Isolated subagent boundaries | Workflows (typed edges, graph orchestration) | Permission isolation across edges (Stage 5) |
| 13 | Graceful recovery and resilience | Middleware error handling, retry hooks | Specific retry/fallback policies; eval scenarios for adversarial cases |

**Rough split: MAF provides the *mechanism* for ~8 of 13 principles. This project provides the *policy* for all 13.**

## Why we use MAF the way we do

### Provider path: Option A (chat client + our harness), not Option B (Claude Agent SDK wrapped)

**Decision:** We use MAF's `OpenAIChatClient` and `AnthropicClient` as plain chat clients,
and build the harness ourselves on top of MAF's middleware/contract surface. We do NOT
use the Claude Agent SDK integration (`agent_framework_claude.ClaudeAgent`).

**Rationale:** Option A maximizes harness learning. We're studying how to build the
98% of an agent system that isn't the model — defining policies, contracts, event logs,
context strategies. Option B would have used Claude Code's harness wrapped in MAF;
that's a study path, not a build path.

**Trade-off accepted:** Option A doesn't work with cloud-only Claude (the SDK is required).
Option A does work with any chat-model provider, including local LM Studio, which is
how we develop. We may add Option B at Stage 5 as a comparative reference, not as the
primary path.

### Provider factory: returns MAF clients directly, no wrapper

**Decision:** `harness/providers.py` returns the MAF chat-client instance unchanged.
We do not wrap it in our own type.

**Rationale:** Wrapping requires knowing what concerns to wrap. We don't yet. Concerns
that might justify wrapping (retries, cost tracking, circuit-breaking) more naturally
belong in middleware, which is MAF's primary extensibility surface. Premature wrapping
introduces a layer that has to be maintained without earning its keep.

**Re-evaluate when:** We hit a class of concern that doesn't fit middleware, or MAF's
chat-client API churns enough that an adapter layer would insulate us.

### Eval surface separated from MAF

**Decision:** `evals/agent_protocol.py` defines `EvalAgent` — a minimal protocol with
just `run_scenario(scenario) -> AgentRunResult`. The eval runner uses this protocol,
not MAF's `Agent` type directly.

**Rationale:** Decouples eval infrastructure from MAF's specific agent surface. Lets
us drive evals against the null agent (Stage 0), real MAF-backed agents (Stage 1+),
or alternative implementations for comparison (Stage 4+) with the same runner.

## What we've learned about MAF 1.1.x specifically

These notes are pinned to MAF >=1.1,<2.0. They may not apply to future versions;
re-verify when the version constraint is bumped.

### API surface differs from current Microsoft Learn docs

The Microsoft Learn docs at
`learn.microsoft.com/en-us/python/api/agent-framework-core/` describe a slightly
newer API than what's installed in 1.1.1. Specific deltas we hit:

- The agent factory method on `OpenAIChatClient` is `as_agent(...)`, not the
  documented `create_agent(...)`. The docs apparently track unreleased changes.
- `service_url()` returns the literal string `"Unknown"` for OpenAI-compat
  clients with custom `base_url` (e.g., LM Studio). Use `client.base_url`
  directly to introspect endpoint.

**Implication:** Verify any MAF API surface against installed behavior
(`dir(client)`, `inspect.signature(...)`) before relying on docs.

### Construction is side-effect-free

`OpenAIChatClient(...)` and `AnthropicClient(...)` do not make network calls
during construction. This means our factory tests can construct real client
instances without mocking the network.

**Implication:** Tests for `harness/providers.py` use real MAF construction
and verify type/state without needing a live endpoint.

### Known issues we'll have to navigate

- **Issue [microsoft/agent-framework #1772]** (Oct 2025): `OpenAIChatClient` with
  Ollama-style local endpoints inserts system instructions twice when ChatContext
  middleware is used. Affects local-model dev once we add chat middleware (Stage 2+).
  Workaround unclear; will revisit at Stage 2.

- **Issue #4328** (Feb 2026): `AnthropicClient` streaming agent fails with HTTP 400
  on consecutive tool calls. Affects Stage 5 multi-agent workflows if we use
  Anthropic provider and streaming. Not blocking now.

## Contracts as the stable boundary

`harness/contracts/` is the stable surface that the rest of the project builds against.
Concrete implementations may change (we may swap event-log backends, policy engines,
context provider implementations). Contracts change only with deliberate cross-stage
review.

Current contracts (Stage 0):

- `Principal`, `PrincipalKind`, factories — who is acting
- `PolicyEngine`, `PolicyRequest`, `PolicyRuling`, `PolicyDecision` — decision interface
- `Event`, `EventKind`, `EventLog` — append-only business events
- `ClaimAwareContextProvider` — claim-scoped context extension

Eval-side contracts (also stable):

- `EvalAgent` (in `evals/agent_protocol.py`) — minimal interface for runnability
- `Scenario`, `AgentRunResult`, `EvalReport` — eval value types

## Open questions (track here, resolve per stage)

- **Stage 1**: Do we use MAF's `AgentSession` directly for conversational state,
  or wrap it behind a session abstraction we control?
- **Stage 1**: How do we surface the MAF `Agent` behind our `EvalAgent` protocol —
  thin adapter, subclass, composition? (Lean toward composition.)
- **Stage 2**: Where does Tier→PolicyDecision mapping live — inside the policy engine,
  or as a separate config-driven layer the engine consumes?
- **Stage 2**: How do we adjudicate between MAF's tool `approval_mode` and our
  custom function middleware? Both can gate; running both is redundant; running
  neither is unsafe.
- **Stage 3**: MAF ContextProviders + our `ClaimAwareContextProvider` — one class
  implementing both, or composed?
- **Stage 4**: OTel traces (operational) vs. our `EventLog` (audit). Where's the
  overlap, and which signals belong in which?
- **Stage 5**: MAF Workflow edge permissions — primitives sufficient, or do we
  add a workflow-level policy layer?

## Revision log

- **Stage 0, Lesson 0.8**: Initial mapping and contracts defined.
- **Stage 0, Lesson 0.11**: Expanded with provider-factory rationale, eval surface
  notes, MAF 1.1.x API drift discoveries (`as_agent`, `service_url` quirk),
  known MAF issues, and per-stage open questions refined.


## Verification Stack

  The project's verification stack combines deterministic fitness functions (mypy strict mode, ruff rule sets), AI-assisted architectural review (/harness-check), unit-level correctness (pytest), and behavioral fitness measurement (eval suite). Rules expressible as deterministic checks should be promoted from the AI-assisted layer to the mechanical layer over time.