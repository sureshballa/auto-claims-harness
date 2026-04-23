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

## Design principle references

This project is organized around 13 harness-engineering principles. See `docs/principles.md`. When proposing a non-trivial design change, reference the principle(s) it serves.

## How to work in this repo

- Python 3.12+, strict type hints, Pydantic v2 for domain models.
- Dependency and environment management via `uv`. Never use raw `pip` or virtualenv commands.
- Run `uv run pytest` before claiming a change is done.
- Format and lint with `uv run ruff format` and `uv run ruff check`.
- Type-check with `uv run mypy`.
- Prefer small, reviewable changes over sweeping rewrites.

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

We are at **Stage 0: Scaffold & Foundations**. The insurance agent does not yet exist. MAF code has not yet been written. We are building the deterministic foundation that Stages 1 through 5 will sit on. Do not reference Stage 1+ capabilities as if they exist.
