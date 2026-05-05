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
from evals.metrics import EvalReport, aggregate, evaluate_scenario, report_summary
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
    import asyncio
    import sys

    from evals.metrics import report_summary

    async def main() -> None:
        agent_kind = sys.argv[1] if len(sys.argv) > 1 else "fnol"

        if agent_kind == "null":
            from evals.null_agent import NullAgent
            agent: EvalAgent = NullAgent()
        elif agent_kind == "fnol":
            from agents.fnol_agent import FnolAgent
            from harness.policy_engine import (
                AuthorityEngine,
                HarnessPolicyEngine,
                MockDataPolicyRepository,
                load_permissions,
                load_thresholds,
            )
            thresholds = load_thresholds(Path("config/thresholds.yaml"))
            permissions = load_permissions(Path("config/permissions.yaml"))
            authority = AuthorityEngine(permissions.tier_authority)
            decision_engine = HarnessPolicyEngine(authority, thresholds)
            repository = MockDataPolicyRepository()
            agent = FnolAgent(decision_engine, repository)
        else:
            print(f"Unknown agent: {agent_kind}. Use 'null' or 'fnol'.")
            sys.exit(1)

        report = await run_evaluation(agent, Path("evals/scenarios"))
        print(report_summary(report))

    asyncio.run(main())
