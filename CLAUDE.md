# Auto Claims Harness — Claude Code instructions

## What this project is

A learning repository for enterprise-grade AI agent harness engineering, built around an auto-insurance claims use case: FNOL (First Notice of Loss) intake and claims adjudication.

The pedagogical goal is harness engineering using Microsoft Agent Framework (MAF) with Python. The insurance domain is a vehicle for exercising the 13 design principles documented in `docs/principles.md` (from Liu et al., "Dive into Claude Code," arXiv 2604.14228, 2026).

## The prime directive

Mature agent systems are ~98% deterministic harness and ~2% LLM decision logic. Respect this ratio. If you catch yourself writing LLM-backed code to do something deterministic code could do, stop and reconsider.

## Repo structure

- `harness/` — the deterministic infrastructure around the LLM (middleware, contracts, policy engine, event log, telemetry, context providers). Peer to `agents/`, never nested inside it.
- `domain/` — pure Python domain models and calculations. No LLM calls. No MAF imports.
- `tools/` — thin wrappers exposing `domain/` functions to the agent via MAF's `@tool` decorator.
- `agents/` — MAF Agent and Workflow definitions. Currently empty; populated from Stage 1 onward.
- `config/` — externalized policy as YAML. Threshold values, permissions, tool allowlists.
- `evals/` — scenario-driven evaluation harness.
- `docs/` — principles, MAF mapping, design notes.
- `tests/` — pytest suite.

## Hard rules — never violate

- **Never move real money or call real external APIs.** All payment and external service calls remain mocked.
- **Never put business logic inside `tools/`.** Tools are thin wrappers around `domain/`. Calculation or decision logic in tool code is a bug.
- **Never put LLM calls or MAF imports inside `domain/`.** Domain is pure Python.
- **Never hard-code thresholds or policy values.** These live in `config/`.
- **Never bypass `harness/contracts/` Protocols.** Every harness component satisfies a defined interface.
- **Append-only for `harness/event_log/`.** Never edit or delete events. Corrections are new events referencing old ones.
- **Never commit secrets.** `.env`, `.env.local`, API keys, credentials — never. `.env.example` (template with empty values) is the only env file that goes in git.
- **Never add `# type: ignore` comments preemptively.** Write code first, run `uv run mypy` to find actual type errors, only suppress with `# type: ignore[specific-error-code]` if mypy genuinely complains AND the type error is unfixable in our code. The same applies to `# noqa` for ruff and `# pragma: no cover` for coverage. Strict mode rejects unused suppressions. Earn every suppression.
- **Never silently swallow exceptions** with `except Exception: pass` or `except: pass`. Either handle the exception with a logged action, or let it propagate. The bare `pass` after `except` is a bug.
- **Never use `Any` as a function parameter or return type** unless interfacing with a third-party library whose own types are `Any`. If `Any` appears, justify it inline with a comment naming the library and the reason. Our types are precise; their types may not be.
- **Never merge a Python module with a data directory of the same name.** If you want a directory of data files alongside related Python code, the directory and the module file MUST have different names. A directory containing a `__init__.py` is a Python package; mixing data files with package code is a structural smell.
- **Never construct typed Pydantic models by unpacking untyped dicts** (`Model(**some_dict)`). Mypy cannot verify field types through dict unpacking and will produce confusing `arg-type` errors. Use explicit named keyword arguments: `Model(field=value, ...)`. The exception: `Model.model_validate(dict)` is fine — Pydantic does runtime validation and the static type is preserved.
- **Functions that read from filesystem, network, environment, or system 
  time MUST make this visible at the call site** — either via an explicit 
  parameter (e.g., `path: Path`), or via a clearly-named opt-out parameter 
  (e.g., `load_env: bool = True`). Hidden side effects break test isolation 
  and surprise callers who must construct their own environment.

## Design principle references

This project is organized around 13 harness-engineering principles. See `docs/principles.md`. When proposing a non-trivial design change, reference the principle(s) it serves.

## How to work in this repo

- Python 3.12+, strict type hints, Pydantic v2 for domain models.
- Dependency and environment management via `uv`. Never use raw `pip` or virtualenv commands.
- Run `uv run pytest` before claiming a change is done.
- Format and lint with `uv run ruff format` and `uv run ruff check`.
- Type-check with `uv run mypy`.
- Prefer small, reviewable changes over sweeping rewrites.
- After writing or editing any Python file, run `uv run mypy <path>` and `uv run ruff check <path>` before claiming the work is done. If suppressions are needed, add them only with the specific error code (e.g., `# type: ignore[arg-type]`, `# noqa: E501`) — never bare `# type: ignore` or bare `# noqa`.

## Ask me before doing

- Any change to files under `config/` (thresholds, permissions, allowlists).
- Any new dependency added to `pyproject.toml`.
- Any change to Protocols under `harness/contracts/`.
- Any deletion of seed data or event-log entries.
- Any new external service dependency.

## Do without asking

- Edits within `domain/`, `tools/`, `agents/`, `evals/` that respect existing contracts and hard rules.
- Running `pytest`, `ruff`, `mypy`, `uv` commands.
- Reading any file in the repo.
- Creating new scenario files under `evals/scenarios/`.
- Creating new seed records that don't conflict with existing IDs.

## Style

- No comments that restate what the code does. Comments explain *why*.
- Docstrings on every public function; short, factual, honest.
- Line length 100.
- Never silently swallow exceptions. Either handle them meaningfully or let them propagate.

## Current stage

**Stage 0 is complete and signed off** (see `docs/stage-0-signoff.md`).
**Stage 1 is complete and signed off** (see `docs/stage-1-signoff.md` and `docs/stage-1-notes.md`).

We are now entering **Stage 2: Minimal harness**. The first middleware components are
being built in `harness/middleware/` — response normalization, policy enforcement,
audit logging — to address the failure modes documented in `docs/stage-1-notes.md`.

The first goal is to migrate the Stage 1 patches in `agents/fnol_agent.py` into
proper MAF function middleware, eliminating the schema-validation errors and
allowing the FnolAgent to finally produce non-erroring `AgentRunResult` values.

**Stage 2 design drivers (from Stage 1 observations):**

- Mechanical normalization of LLM output (field aliases, missing field defaults, fence stripping)
- Policy enforcement at high-risk tiers (model cannot unilaterally deny Yellow/Red claims)
- Externalized policy (aliases, authority rules, etc. live in `config/`, not code)

Stages 3 through 5 still do not exist. Continue to refuse work that depends on
capabilities planned for those stages.
