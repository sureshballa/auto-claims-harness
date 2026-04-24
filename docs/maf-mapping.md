# MAF Mapping

This document records which of the 13 harness engineering principles
(see `principles.md`) are served by Microsoft Agent Framework (MAF)
primitives vs. built in this project.

Status: **Stage 0 — early draft.** Expand as each stage lands.

## Principle → MAF mapping (coarse)

| # | Principle | MAF provides | This project builds |
|---|-----------|--------------|---------------------|
| 1 | Deny-first with human escalation | Tool `approval_mode`, `MiddlewareTermination` | `PolicyEngine` contract; Stage 2 impl |
| 2 | Graduated trust spectrum | Middleware scoping | Tier logic (`domain.tiers`), Principal kinds |
| 3 | Defense in depth | 3 middleware layers (agent / function / chat) | Policies at each layer |
| 4 | Externalized programmable policy | — | `config/*.yaml` + `policy_engine` loader |
| 5 | Context as scarce resource | Context providers, session | `ClaimAwareContextProvider` + Stage 3 compaction |
| 6 | Append-only durable state | Session (mutable), OTel traces (ephemeral) | `EventLog` contract; Stage 4 impl |
| 7 | Minimal scaffolding, maximal harness | Middleware-first design | Discipline in `CLAUDE.md` |
| 8 | Values over rules | — | Agent instructions + contracts |
| 9 | Composable multi-mechanism extensibility | Middleware chain, `@tool`, MCP, Workflows | How we wire them |
| 10 | Reversibility-weighted risk | — | Tier logic + per-tool `approval_mode` |
| 11 | Transparent file-based configuration | — | `config/*.yaml`, `CLAUDE.md`, this doc |
| 12 | Isolated subagent boundaries | Workflows (typed edges) | Permission isolation (Stage 5) |
| 13 | Graceful recovery and resilience | Middleware error handling | Retry + fallback policies |

Rough split: MAF provides the **mechanism** for ~8 of 13 principles.
This project provides the **policy** for all 13.

## Contracts as the stable boundary

`harness/contracts/` is the stable surface that the rest of the project
builds against. Concrete implementations can change without touching
contracts. Contracts can change only with deliberate cross-stage review.

Current contracts (Stage 0):

- `Principal`, `PrincipalKind`, factories — who is acting
- `PolicyEngine`, `PolicyRequest`, `PolicyRuling`, `PolicyDecision` — decision interface
- `Event`, `EventKind`, `EventLog` — append-only business events
- `ClaimAwareContextProvider` — claim-scoped context extension

## Open questions (track here, resolve per stage)

- **Stage 1**: Do we use MAF's `AgentSession` directly, or wrap it?
- **Stage 2**: Where does Tier→PolicyDecision mapping live — in the engine or in a policy file?
- **Stage 3**: MAF ContextProviders + our ClaimAwareContextProvider — one class implementing both, or composed?
- **Stage 4**: OTel traces vs. EventLog — overlap or strictly separate?
- **Stage 5**: Workflow edge permissions — MAF primitives sufficient, or do we add our own?

## Revision log

- Stage 0: initial mapping and contracts defined.
