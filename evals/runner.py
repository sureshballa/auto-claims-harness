"""Eval runner — integration point between scenarios, agents, and metrics.

Loads scenarios from disk, drives any EvalAgent through each one, scores the
results, and returns an EvalReport. The runner knows nothing about what kind of
agent it is driving: NullAgent, a MAF-backed agent (Stage 1+), or any other
conforming implementation can be substituted without touching this file.

Responsibilities:
    - Scenario loading (delegated to evals.scenarios)
    - Per-scenario error isolation (a crashing scenario does not abort the run)
    - Result scoring (delegated to evals.metrics)
    - Aggregation (delegated to evals.metrics)

Not responsible for:
    - Concurrency — runs are sequential for deterministic ordering. Parallelism
      is a future optimization; correctness comes first.
    - Reporting format — callers receive an EvalReport and choose how to render it.
"""

from __future__ import annotations

import asyncio
import traceback
from pathlib import Path

from evals.agent_protocol import AgentRunResult, EvalAgent
from evals.metrics import EvalReport, aggregate, evaluate_scenario
from evals.scenarios import Scenario, load_all_scenarios


async def run_evaluation(
    agent: EvalAgent,
    scenario_dir: Path | str,
) -> EvalReport:
    """Load all scenarios from scenario_dir, run the agent on each, return a scored report.

    Scenarios run sequentially in id-sorted order. If running a scenario raises
    an unhandled exception, the error is captured into AgentRunResult.error and
    the runner continues with the next scenario. Individual failures do not abort
    the evaluation.
    """
    scenarios: list[Scenario] = load_all_scenarios(scenario_dir)
    outcomes = []

    for scenario in scenarios:
        try:
            result = await agent.run_scenario(scenario)
        except Exception:
            result = AgentRunResult(
                error=traceback.format_exc(),
                reasoning="",
            )

        outcomes.append(evaluate_scenario(scenario, result))

    return aggregate(outcomes)


if __name__ == "__main__":
    from evals.metrics import report_summary
    from evals.null_agent import NullAgent

    report = asyncio.run(run_evaluation(NullAgent(), "evals/scenarios"))
    print(report_summary(report))
