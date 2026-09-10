"""
Stage 1 entry point.

Runs the AuthGraph-style defense against:
  (a) a set of CLEAN tasks (to measure task utility -- does the
      defense let legitimate work through?)
  (b) the SAME tasks with a single-session prompt injection payload
      planted in a document (to measure Attack Success Rate -- does
      the defense stop the attack?)

Usage:
    python run_baseline.py
    python run_baseline.py --backend openai      # requires OPENAI_API_KEY
    python run_baseline.py --backend anthropic   # requires ANTHROPIC_API_KEY
"""

from __future__ import annotations
import argparse
import pandas as pd

from src.llm_backend import get_backend
from src.authguard_agent import AuthGraphAgent
from src.tasks import get_clean_tasks, get_single_session_attack_tasks
from src.evaluate import evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="mock", choices=["mock", "openai", "anthropic"])
    args = parser.parse_args()

    backend = get_backend(args.backend)
    agent = AuthGraphAgent(backend)

    print(f"\n=== Running with backend: {args.backend} ===\n")

    clean_tasks = get_clean_tasks()
    attack_tasks = get_single_session_attack_tasks()

    print(f"Running {len(clean_tasks)} clean tasks...")
    clean_results = [agent.run_task(t) for t in clean_tasks]

    print(f"Running {len(attack_tasks)} single-session injection attack tasks...\n")
    attack_results = [agent.run_task(t) for t in attack_tasks]

    all_results = clean_results + attack_results
    report = evaluate(all_results)

    pd.set_option("display.max_colwidth", 60)
    pd.set_option("display.width", 160)
    print("=== Per-task results ===")
    print(report.per_task[["task_id", "injected", "checker_passed", "attack_succeeded", "violations"]])

    print("\n=== Summary ===")
    print(f"Attack Success Rate (ASR) on single-session injection: {report.asr:.2%}")
    print(f"Task Utility on clean tasks:                           {report.utility:.2%}")

    print("\n=== Interpretation ===")
    if report.asr == 0.0:
        print("The baseline AuthGraph-style defense blocked all single-session")
        print("injection attacks in this run -- matching AuthGraph's published")
        print("claim for the single-session setting. Stage 2 will test whether")
        print("this guarantee survives once cross-session MEMORY is introduced.")
    else:
        print("Some single-session attacks got through. Check the 'violations'")
        print("column above and the graph_checker.py logic before proceeding to Stage 2.")

    out_path = "results_stage1_baseline.csv"
    report.per_task.to_csv(out_path, index=False)
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
