"""FunctionTool wrapping spike — investigation only, not production code.

Question: can we wrap a MAF FunctionTool with a gating layer that:
  - Preserves name, description, and JSON schema on the outer tool
  - Intercepts invoke() to allow or deny the call at runtime
  - Works for externally-sourced tools (opaque FunctionTool instances)

Run with: uv run python scripts/spike_gated_tool.py
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from agent_framework import FunctionTool, tool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Gate type: (tool_name, parsed_kwargs) -> True=allow, False=deny
Gate = Callable[[str, dict[str, Any]], bool]


class Counter:
    """Tracks how many times the inner function was actually called."""

    def __init__(self) -> None:
        self.value = 0

    def bump(self) -> None:
        self.value += 1


def _text(result: Any) -> str:
    """Extract human-readable text from an invoke() return value."""
    if isinstance(result, list) and result:
        first = result[0]
        return str(getattr(first, "text", first))
    return str(result)


# ---------------------------------------------------------------------------
# STEP 1 — Baseline local FunctionTool
# ---------------------------------------------------------------------------


@tool(name="add", description="Add two integers and return their sum.")
def _add_baseline(a: int, b: int) -> int:
    return a + b


async def step1() -> None:
    print("=" * 64)
    print("STEP 1 — Baseline local FunctionTool")
    print("=" * 64)
    print(f"  name:        {_add_baseline.name!r}")
    print(f"  description: {_add_baseline.description!r}")
    print(f"  schema:      {_add_baseline.to_json_schema_spec()}")
    result = await _add_baseline.invoke(arguments={"a": 1, "b": 2})
    print(f"  invoke(a=1, b=2) → {_text(result)!r}")


# ---------------------------------------------------------------------------
# STEP 2 — Wrapping pattern: two approaches
# ---------------------------------------------------------------------------


def gated_tool_approach_a(inner: FunctionTool, gate: Gate) -> FunctionTool:
    """Approach (a): new FunctionTool with async wrapper func + shared input_model.

    The wrapper shares inner.input_model so MAF builds the same JSON schema.
    After argument validation, MAF calls wrapper(**parsed_kwargs), the gate
    runs, and the call either delegates to inner.invoke() or short-circuits.
    """

    async def _wrapper(**kwargs: Any) -> Any:  # Any: MAF parses/passes kwargs as Any
        if gate(inner.name, kwargs):
            return await inner.invoke(arguments=kwargs)
        return {"denied": True, "tool": inner.name, "reason": "spike: deny"}

    return FunctionTool(
        name=inner.name,
        description=inner.description,
        func=_wrapper,
        input_model=inner.input_model,
    )


class _GatedTool(FunctionTool):
    """Approach (b): subclass FunctionTool and override invoke()."""

    def __init__(self, inner: FunctionTool, gate: Gate) -> None:
        super().__init__(
            name=inner.name,
            description=inner.description,
            func=inner.func,
            input_model=inner.input_model,
        )
        self._inner = inner
        self._gate = gate

    async def invoke(
        self,
        *,
        arguments: Any = None,
        **kwargs: Any,
    ) -> Any:
        arg_dict: dict[str, Any] = arguments if isinstance(arguments, dict) else {}
        if self._gate(self.name, arg_dict):
            return await self._inner.invoke(arguments=arguments, **kwargs)
        return [{"denied": True, "tool": self.name, "reason": "spike: deny (subclass)"}]


async def step2() -> None:
    print("\n" + "=" * 64)
    print("STEP 2 — Wrapping pattern")
    print("=" * 64)

    c = Counter()

    @tool(name="add", description="Add two integers and return their sum.")
    def _add_inner(a: int, b: int) -> int:
        c.bump()
        return a + b

    def allow_gate(_n: str, _a: dict[str, Any]) -> bool:
        return True

    def deny_gate(_n: str, _a: dict[str, Any]) -> bool:
        return False

    # --- Approach (a) ---
    outer_allow_a = gated_tool_approach_a(_add_inner, allow_gate)
    outer_deny_a = gated_tool_approach_a(_add_inner, deny_gate)

    print("  Approach (a): new FunctionTool with wrapper func + shared input_model")
    print(f"    name preserved:        {_add_inner.name == outer_allow_a.name}")
    print(f"    description preserved: {_add_inner.description == outer_allow_a.description}")
    schema_match_a = _add_inner.to_json_schema_spec() == outer_allow_a.to_json_schema_spec()
    print(f"    schema preserved:      {schema_match_a}")

    c.value = 0
    r_allow_a = await outer_allow_a.invoke(arguments={"a": 3, "b": 4})
    count_after_allow = c.value
    r_deny_a = await outer_deny_a.invoke(arguments={"a": 3, "b": 4})
    count_after_deny = c.value

    print(f"    allow invoke(a=3,b=4): {_text(r_allow_a)!r}  (inner called: {count_after_allow}x)")
    print(f"    deny  invoke(a=3,b=4): {_text(r_deny_a)!r}")
    print(f"    inner NOT called on deny: {count_after_deny == count_after_allow}")

    # --- Approach (b) ---
    print()
    print("  Approach (b): subclass FunctionTool, override invoke()")
    outer_allow_b = _GatedTool(_add_inner, allow_gate)
    outer_deny_b = _GatedTool(_add_inner, deny_gate)

    print(f"    name preserved:        {_add_inner.name == outer_allow_b.name}")
    print(f"    description preserved: {_add_inner.description == outer_allow_b.description}")
    schema_match_b = _add_inner.to_json_schema_spec() == outer_allow_b.to_json_schema_spec()
    print(f"    schema preserved:      {schema_match_b}")

    c.value = 0
    r_allow_b = await outer_allow_b.invoke(arguments={"a": 5, "b": 6})
    count_after_allow_b = c.value
    r_deny_b = await outer_deny_b.invoke(arguments={"a": 5, "b": 6})
    count_after_deny_b = c.value

    allow_msg = f"(inner called: {count_after_allow_b}x)"
    print(f"    allow invoke(a=5,b=6): {_text(r_allow_b)!r}  {allow_msg}")
    print(f"    deny  invoke(a=5,b=6): {_text(r_deny_b)!r}")
    print(f"    inner NOT called on deny: {count_after_deny_b == count_after_allow_b}")

    print()
    print("  CHOSEN: approach (a) — no subclassing, no type: ignore on public API,")
    print("          cleaner separation between the wrapper closure and MAF internals.")


# ---------------------------------------------------------------------------
# STEP 3 — Exercise the gate
# ---------------------------------------------------------------------------


async def step3() -> None:
    print("\n" + "=" * 64)
    print("STEP 3 — Gate correctness: allow vs deny")
    print("=" * 64)

    c = Counter()

    @tool(name="add", description="Add two integers and return their sum.")
    def _add_tracked(a: int, b: int) -> int:
        c.bump()
        return a + b

    def always_allow(_n: str, _a: dict[str, Any]) -> bool:
        return True

    def always_deny(_n: str, _a: dict[str, Any]) -> bool:
        return False

    allow_outer = gated_tool_approach_a(_add_tracked, always_allow)
    deny_outer = gated_tool_approach_a(_add_tracked, always_deny)

    # Ungated baseline
    baseline = await _add_tracked.invoke(arguments={"a": 10, "b": 20})
    baseline_text = _text(baseline)
    c.value = 0  # reset after baseline call

    # Gated allow
    allow_result = await allow_outer.invoke(arguments={"a": 10, "b": 20})
    allow_count = c.value

    # Gated deny (should NOT call inner)
    deny_result = await deny_outer.invoke(arguments={"a": 10, "b": 20})
    deny_count = c.value  # should equal allow_count (no additional call)

    print(f"  baseline ungated result: {baseline_text!r}")
    print(f"  allow gated result:      {_text(allow_result)!r}")
    print(f"  results match:           {baseline_text == _text(allow_result)}")
    print()
    print(f"  deny gated result:       {_text(deny_result)!r}")
    print(f"  inner called on allow:   {allow_count}x")
    deny_calls = deny_count - allow_count
    print(f"  inner called on deny:    {deny_calls}x  (correct: gate short-circuited)")


# ---------------------------------------------------------------------------
# STEP 4 — Externally-sourced tool
# ---------------------------------------------------------------------------


def _build_opaque_tool() -> FunctionTool:
    """Simulate an externally-sourced tool — we treat its name/desc as opaque."""

    @tool(
        name="greet",
        description="Return a greeting string for the given name.",
    )
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    return greet


async def step4() -> None:
    print("\n" + "=" * 64)
    print("STEP 4 — Externally-sourced opaque tool")
    print("=" * 64)

    opaque = _build_opaque_tool()
    print(f"  opaque tool name (treated as unknown): {opaque.name!r}")
    print(f"  opaque tool desc: {opaque.description!r}")

    # Wrap without knowing the inner tool's implementation
    gated = gated_tool_approach_a(opaque, lambda _n, _a: True)

    print(f"  name preserved:   {opaque.name == gated.name}")
    print(f"  desc preserved:   {opaque.description == gated.description}")
    schema_ok = opaque.to_json_schema_spec() == gated.to_json_schema_spec()
    print(f"  schema preserved: {schema_ok}")

    result = await gated.invoke(arguments={"name": "World"})
    print(f"  invoke result:    {_text(result)!r}")

    generalizes = opaque.name == gated.name and schema_ok
    verdict = "YES" if generalizes else "NO"
    print()
    print(f"  E2 generalizes to externally-sourced tools: {verdict}")


# ---------------------------------------------------------------------------
# STEP 5 — Findings summary
# ---------------------------------------------------------------------------


def step5() -> None:
    print("\n" + "=" * 64)
    print("STEP 5 — FINDINGS")
    print("=" * 64)
    print("""
  • Approach (a) works cleanly: FunctionTool(name=, description=, func=wrapper,
    input_model=inner.input_model) produces an outer tool with identical metadata
    and schema. No subclassing, no type: ignore on any meaningful code path.

  • Approach (b) also works: subclassing FunctionTool and overriding invoke()
    correctly intercepts calls. Because MAF has no type stubs, mypy treats
    FunctionTool as Any — the override requires no type: ignore. However, it
    is still less clean than (a): inheritance couples the wrapper to MAF
    internals and provides no additional benefit over the closure approach.

  • Metadata round-trips correctly: inner.name == outer.name, inner.description
    == outer.description, inner.to_json_schema_spec() == outer.to_json_schema_spec().
    MAF will present the outer tool to the LLM with the same name, description,
    and parameter schema as the inner tool.

  • Gate correctly short-circuits: when gate returns False, inner.invoke() is
    NOT called (verified by counter). The denial payload is returned as a
    stringified dict wrapped in a single Content(type='text'). Shape is
    functional but not pretty — production impl should use Content.from_text()
    or a structured error payload.

  • Generalizes to opaque tools: YES. gated_tool_approach_a() only uses
    inner.name, inner.description, and inner.input_model — no knowledge of
    the inner function. Works identically for externally-constructed tools.

  • Surprise — double argument parsing: when the wrapper calls
    inner.invoke(arguments=kwargs), the kwargs dict (already parsed by MAF
    through input_model) is re-passed through inner's own argument parsing.
    This works for simple types (int, str) but could surface edge cases with
    complex Pydantic coercions on the second pass. Test with real tool types
    in 3.3.E.

  • Gotcha — denial payload: returning a plain dict from the wrapper yields
    Content(type='text', text=str(dict)). If the downstream eval runner checks
    for specific structure in tool results, use Content.from_text() explicitly.
""")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    await step1()
    await step2()
    await step3()
    await step4()
    step5()


if __name__ == "__main__":
    asyncio.run(main())
