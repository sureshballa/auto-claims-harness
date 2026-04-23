# Auto Claims Harness

A learning repository for enterprise-grade AI agent harness engineering. Built around an auto-insurance claims case study (FNOL intake + claims adjudication) using Microsoft Agent Framework (MAF) on Python.

The pedagogical goal is harness engineering. The insurance domain is a vehicle for exercising the 13 design principles documented in `docs/principles.md` (Liu et al., "Dive into Claude Code: The Design Space of Today's and Future AI Agent Systems," arXiv 2604.14228, 2026).

## Status

Stage 0 of 5: scaffold and foundations. The agent itself does not yet exist.

## Setup

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and (for runtime) [LM Studio](https://lmstudio.ai/) hosting GPT-OSS 20B at `http://localhost:1234`.

```bash
cp .env.example .env
uv sync
uv run pytest
```

## Layout

- `harness/` — deterministic infrastructure (middleware, contracts, policy engine, event log, telemetry).
- `domain/` — pure-Python domain models and calculations. No LLM, no MAF.
- `tools/` — thin MAF tool wrappers around `domain/` functions.
- `agents/` — MAF Agent and Workflow definitions.
- `config/` — externalized policy (thresholds, permissions, allowlists).
- `evals/` — scenario-driven evaluation harness.
- `docs/` — principles and design notes.
- `tests/` — pytest suite.

## Working in this repo

Read `CLAUDE.md` first. It is the dev-loop contract.
