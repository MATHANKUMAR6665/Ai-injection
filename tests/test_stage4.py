"""Tests for Stage 4 metrics and evidence generation."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from run_stage4_evidence import CHART_OUTPUT, SUMMARY_RESULTS, generate_evidence


def test_stage4_generates_expected_comparison():
    summary = generate_evidence()

    assert summary["condition"].tolist() == [
        "Stage 2 baseline",
        "Stage 3 provenance defense",
    ]
    assert summary["asr"].tolist() == [1.0, 0.0]
    assert summary["utility"].tolist() == [1.0, 1.0]
    assert SUMMARY_RESULTS.exists()
    assert CHART_OUTPUT.exists()
    assert CHART_OUTPUT.stat().st_size > 0
