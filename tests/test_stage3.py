"""Correctness tests for Stage 3 provenance-tagged memory."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from run_stage2_cross_session import calculate_stage2_asr, run_scenario
from src.authguard_agent import AuthGraphAgent
from src.cross_session_scenarios import BENIGN_SCENARIO, MALICIOUS_SCENARIOS
from src.llm_backend import get_backend
from src.memory import ProvenanceTaggedMemoryStore


USER_ID = "stage3_test_user"


def _fresh_agent_and_memory():
    return AuthGraphAgent(get_backend("mock")), ProvenanceTaggedMemoryStore()


def test_provenance_store_blocks_all_cross_session_attacks():
    agent, memory_store = _fresh_agent_and_memory()
    results = [run_scenario(agent, memory_store, scenario) for scenario in MALICIOUS_SCENARIOS]

    successful, total, asr = calculate_stage2_asr(results)

    assert total == len(MALICIOUS_SCENARIOS)
    assert successful == 0
    assert asr == 0.0
    assert all(not result["attack_succeeded"] for result in results)


def test_provenance_store_preserves_benign_utility():
    agent, memory_store = _fresh_agent_and_memory()
    result = run_scenario(agent, memory_store, BENIGN_SCENARIO)

    assert result["legitimate_utility_ok"] is True


def test_tampered_provenance_entry_is_excluded_on_read():
    memory_store = ProvenanceTaggedMemoryStore()
    memory_store.write(USER_ID, "trusted preference", origin="trusted_user")
    memory_store.write(USER_ID, "untrusted preference", origin="untrusted:document")

    memory_store._entries[USER_ID][0].content = "tampered preference"

    assert memory_store.read_all(USER_ID) == []
    assert memory_store.read_as_text(USER_ID) == ""
