"""
Unit tesztek a build_blind_rows függvényhez (Phase 2 vak human-eval export):
az azonosító mezők (experiment_name, optimization_strategy) csak a key_rows-ban
szerepelnek, a blind_rows-ban NEM -- ez a vakság lényege.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from export_blind_human_eval import build_blind_rows, BLIND_COLUMNS


def _run(run_id, experiment_id, experiment_name, strategy, input_id, content):
    return {
        "run_id": run_id, "experiment_id": experiment_id, "experiment_name": experiment_name,
        "optimization_strategy": strategy, "input_id": input_id,
        "outputs": {"context": "c", "needs": "n", "curriculum": "cu", "content": content, "critic": "cr"},
    }


class TestBuildBlindRows:
    def test_blind_rows_do_not_leak_identifying_fields(self):
        runs = [_run("run-1", "exp-006", "Deliberate Mismatch", "deliberate_mismatch", "input-03", "text A")]
        blind_rows, key_rows = build_blind_rows(runs)
        blind_str = str(blind_rows)
        assert "exp-006" not in blind_str
        assert "Deliberate Mismatch" not in blind_str
        assert "deliberate_mismatch" not in blind_str

    def test_key_rows_contain_real_identifiers(self):
        runs = [_run("run-1", "exp-006", "Deliberate Mismatch", "deliberate_mismatch", "input-03", "text A")]
        _, key_rows = build_blind_rows(runs)
        assert key_rows[0]["experiment_id"] == "exp-006"
        assert key_rows[0]["run_id"] == "run-1"

    def test_blind_and_key_rows_have_matching_blind_ids(self):
        runs = [
            _run("run-1", "exp-001", "A", "s1", "input-01", "text A"),
            _run("run-2", "exp-002", "B", "s2", "input-01", "text B"),
        ]
        blind_rows, key_rows = build_blind_rows(runs)
        assert [r["blind_id"] for r in blind_rows] == [r["blind_id"] for r in key_rows]
        assert {r["blind_id"] for r in blind_rows} == {"B001", "B002"}

    def test_blank_rating_columns_present(self):
        runs = [_run("run-1", "exp-001", "A", "s1", "input-01", "text A")]
        blind_rows, _ = build_blind_rows(runs)
        for col in ["rating_completeness", "rating_coherence", "rating_usability",
                    "rating_maturity_alignment", "rating_risk_coverage", "evaluator_notes"]:
            assert blind_rows[0][col] == ""
            assert col in BLIND_COLUMNS

    def test_same_seed_produces_same_order(self):
        runs = [_run(f"run-{i}", f"exp-{i:03d}", f"N{i}", f"s{i}", "input-01", f"text {i}") for i in range(5)]
        blind_a, _ = build_blind_rows(runs, seed=7)
        blind_b, _ = build_blind_rows(runs, seed=7)
        assert [r["content"] for r in blind_a] == [r["content"] for r in blind_b]

    def test_content_fields_preserved(self):
        runs = [_run("run-1", "exp-001", "A", "s1", "input-01", "the actual curriculum text")]
        blind_rows, _ = build_blind_rows(runs)
        assert blind_rows[0]["content"] == "the actual curriculum text"
