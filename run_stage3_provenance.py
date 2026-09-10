"""Stage 3 entry point for the provenance-tagged memory defense.

Runs the same cross-session scenarios as Stage 2, but filters memory at
read-time so content originating from external sources cannot reach the
trigger session's Planner prompt.
"""

from __future__ import annotations

import pandas as pd

from src.authguard_agent import AuthGraphAgent
from src.cross_session_scenarios import ALL_SCENARIOS
from src.llm_backend import get_backend
from src.memory import ProvenanceTaggedMemoryStore
from run_stage2_cross_session import calculate_stage2_asr, run_scenario


def main() -> None:
    agent = AuthGraphAgent(get_backend("mock"))
    memory_store = ProvenanceTaggedMemoryStore()
    rows = []

    for scenario in ALL_SCENARIOS:
        result = run_scenario(agent, memory_store, scenario)
        rows.append(result)
        if scenario.malicious:
            verdict = "Attack blocked" if not result["attack_succeeded"] else "ATTACK SUCCEEDED"
        else:
            verdict = (
                "Legitimate task completed normally"
                if result["legitimate_utility_ok"]
                else "Legitimate task was blocked"
            )
        print(f"{scenario.name}: {verdict}")

    pd.DataFrame(rows).drop(
        columns=["memory_saved", "trigger_prompt_seen_by_planner", "trigger_emails_sent", "violations"]
    ).to_csv("results_stage3_provenance.csv", index=False)

    successful, total, asr = calculate_stage2_asr(rows)
    benign_ok = next(row["legitimate_utility_ok"] for row in rows if not row["malicious"])
    print(f"Stage 3 ASR: {successful}/{total} = {asr:.1%}")
    print(f"Benign utility: {'pass' if benign_ok else 'fail'}")
    print("Full results written to results_stage3_provenance.csv")


if __name__ == "__main__":
    main()
