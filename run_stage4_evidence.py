"""Stage 4 evidence generation.

Reads the reproducible Stage 2 and Stage 3 result CSVs, computes comparable
ASR and benign task utility metrics, and writes a summary table plus chart.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parent
BASELINE_RESULTS = ROOT / "results_stage2_cross_session.csv"
PROVENANCE_RESULTS = ROOT / "results_stage3_provenance.csv"
SUMMARY_RESULTS = ROOT / "stage4_metrics.csv"
CHART_OUTPUT = ROOT / "stage4_asr_utility.png"


def _load_results(path: Path) -> pd.DataFrame:
    results = pd.read_csv(path)
    required = {"malicious", "attack_succeeded", "legitimate_utility_ok"}
    missing = required - set(results.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    results["malicious"] = results["malicious"].astype(bool)
    return results


def calculate_metrics(results: pd.DataFrame, condition: str) -> dict[str, object]:
    attacks = results[results["malicious"]]
    benign = results[~results["malicious"]]
    attack_successes = attacks["attack_succeeded"].fillna(False).astype(bool).sum()
    utility_successes = benign["legitimate_utility_ok"].fillna(False).astype(bool).sum()
    return {
        "condition": condition,
        "successful_attacks": int(attack_successes),
        "total_attacks": int(len(attacks)),
        "asr": attack_successes / len(attacks) if len(attacks) else 0.0,
        "successful_benign_tasks": int(utility_successes),
        "total_benign_tasks": int(len(benign)),
        "utility": utility_successes / len(benign) if len(benign) else 0.0,
    }


def generate_evidence() -> pd.DataFrame:
    baseline = calculate_metrics(_load_results(BASELINE_RESULTS), "Stage 2 baseline")
    provenance = calculate_metrics(_load_results(PROVENANCE_RESULTS), "Stage 3 provenance defense")
    summary = pd.DataFrame([baseline, provenance])
    summary.to_csv(SUMMARY_RESULTS, index=False)

    labels = summary["condition"].tolist()
    x_positions = range(len(labels))
    width = 0.36

    figure, axis = plt.subplots(figsize=(8, 5))
    axis.bar(
        [position - width / 2 for position in x_positions],
        summary["asr"] * 100,
        width,
        label="Attack Success Rate",
        color="#c94c4c",
    )
    axis.bar(
        [position + width / 2 for position in x_positions],
        summary["utility"] * 100,
        width,
        label="Benign Task Utility",
        color="#3c8d70",
    )
    axis.set_ylabel("Percentage")
    axis.set_title("AuthGuard Stage 2 vs. Stage 3")
    axis.set_xticks(list(x_positions), labels)
    axis.set_ylim(0, 105)
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(CHART_OUTPUT, dpi=160)
    plt.close(figure)

    return summary


def main() -> None:
    summary = generate_evidence()
    print(summary.to_string(index=False))
    print(f"Summary written to {SUMMARY_RESULTS.name}")
    print(f"Chart written to {CHART_OUTPUT.name}")


if __name__ == "__main__":
    main()
