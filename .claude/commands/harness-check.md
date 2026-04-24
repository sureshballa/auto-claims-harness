---
description: Audit the current codebase for harness engineering principle violations
---

Audit this codebase against the harness engineering principles and project hard rules.

Check these things and report any violations with the file path and line number:

**Purity violations:**
1. Any `import agent_framework` or other MAF imports inside `domain/` — must be zero.
2. Any LLM API calls inside `domain/` — must be zero.
3. Any `config` or YAML loads inside `domain/` — must be zero.
4. Any business logic in `tools/` (calculation, decision) — must be thin wrappers around `domain/`.

**Policy externalization:**
5. Any hard-coded dollar thresholds in Python code (the thresholds are config-driven). Look for numeric literals like 500, 5000, 25000 in non-test code.
6. Any hard-coded principal kinds or policy decisions (magic strings rather than enum use).

**Type and style:**
7. Any `Decimal(float_literal)` constructions — must be `Decimal("string_literal")`.
8. Any `float` used for money fields in models.
9. Any `datetime.now()` without a timezone — should be `datetime.now(UTC)` or equivalent.
10. Any mutable default arguments (`def foo(x=[])`) — must use `Field(default_factory=list)` for Pydantic or `None` sentinel for plain Python.

**Append-only:**
11. Any code path under `harness/event_log/` (when it exists) that mutates or deletes events.

For each violation found, show:
- File path and line number
- The offending code snippet
- Which hard rule or principle it violates

If no violations are found, state that clearly.

Do not fix anything. Only report.
