"""
Unit teszt a postprocess_diversity_for_run_groups függvényhez: diverzitás-
számítás EXPLICIT run_id-csoportokra, nem input_id alapú csoportosítással.

Kontextus: egy hibás pilot-batch részleges javító-újrafuttatása miatt
néhány pár "-v3fix" toldalékos input_id-t kapott (hogy a resume-logika ne
keverje össze a régi, hibás rekorddal), miközben a többi pár a régi
"-v2maxtok" input_id alatt maradt. A szokásos, input_id szerint csoportosító
diverzitás-számítás emiatt nem tudná helyesen összehasonlítani a logikailag
egy dokumentumhoz tartozó 10 kombinációt -- ez a függvény explicit run_id-
listákkal kerüli ezt meg. Nincs valódi embedding-hívás -- compute_diversity_for_input
mockolva van.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import experiment_runner as er
from experiment_logger import ExperimentLogger


def _base_record(run_id, experiment_id, input_id, content):
    return {
        "run_id": run_id, "experiment_id": experiment_id, "input_id": input_id,
        "experiment_name": "T", "optimization_strategy": "s", "started_at": "2026-07-11T00:00:00Z",
        "outputs": {"context": "c", "needs": "n", "curriculum": "cu", "content": content, "critic": "cr"},
        "purpose": "test",
        "metrics": {"total_cost_usd": 0.05, "total_latency_seconds": 60, "total_tokens": 1000},
        "evaluation": {
            "composite_score": 50.0,
            "dimension_scores": {"quality": 80.0, "cost": 60.0, "latency": 50.0, "robustness": 80.0, "diversity": 50.0},
            "critic_issues_count": 1, "pareto_dominated": None,
        },
        "errors": [],
    }


class TestPostprocessDiversityForRunGroups:
    def test_patches_diversity_across_mismatched_input_ids(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        logger = ExperimentLogger(tmp_path)

        # Két run, LOGIKAILAG ugyanahhoz a dokumentumhoz tartozik, de eltérő
        # (szuffixált) input_id alatt van naplózva -- pont ez az eset, amit
        # a sima input_id-alapú postprocess nem tudna kezelni.
        logger.log(_base_record("run-a", "exp-001", "input-01-v2maxtok", "content A"))
        logger.log(_base_record("run-b", "exp-002", "input-01-v3fix", "content B"))

        def fake_compute_diversity_for_input(runs_same_input):
            assert len(runs_same_input) == 2
            return {
                "input_id": runs_same_input[0].get("input_id"),
                "pairwise_avg_similarity": 0.3,
                "per_experiment_diversity": {"exp-001": 0.7, "exp-002": 0.9},
            }

        monkeypatch.setattr(er, "compute_diversity_for_input", fake_compute_diversity_for_input)

        result = er.postprocess_diversity_for_run_groups([["run-a", "run-b"]])

        assert set(result["patched_run_ids"]) == {"run-a", "run-b"}
        assert result["errors"] == []

        runs = {r["run_id"]: r for r in logger.load_all_runs()}
        assert runs["run-a"]["evaluation"]["dimension_scores"]["diversity"] == 70.0
        assert runs["run-b"]["evaluation"]["dimension_scores"]["diversity"] == 90.0

    def test_group_with_single_run_is_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        logger = ExperimentLogger(tmp_path)
        logger.log(_base_record("run-a", "exp-001", "input-01-v2maxtok", "content A"))

        called = {"count": 0}

        def fake_compute_diversity_for_input(runs_same_input):
            called["count"] += 1
            return {"per_experiment_diversity": {}}

        monkeypatch.setattr(er, "compute_diversity_for_input", fake_compute_diversity_for_input)

        result = er.postprocess_diversity_for_run_groups([["run-a"]])

        assert called["count"] == 0
        assert result["patched_run_ids"] == []

    def test_unknown_run_id_in_group_is_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        logger = ExperimentLogger(tmp_path)
        logger.log(_base_record("run-a", "exp-001", "input-01-v2maxtok", "content A"))
        logger.log(_base_record("run-b", "exp-002", "input-01-v3fix", "content B"))

        def fake_compute_diversity_for_input(runs_same_input):
            assert len(runs_same_input) == 2
            return {"per_experiment_diversity": {"exp-001": 0.5, "exp-002": 0.6}}

        monkeypatch.setattr(er, "compute_diversity_for_input", fake_compute_diversity_for_input)

        result = er.postprocess_diversity_for_run_groups([["run-a", "run-b", "run-does-not-exist"]])
        assert set(result["patched_run_ids"]) == {"run-a", "run-b"}

    def test_multiple_independent_groups(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        logger = ExperimentLogger(tmp_path)
        logger.log(_base_record("run-a", "exp-001", "input-01-v2maxtok", "A"))
        logger.log(_base_record("run-b", "exp-002", "input-01-v3fix", "B"))
        logger.log(_base_record("run-c", "exp-001", "input-02-v2maxtok", "C"))
        logger.log(_base_record("run-d", "exp-002", "input-02-v3fix", "D"))

        def fake_compute_diversity_for_input(runs_same_input):
            ids = sorted(r["run_id"] for r in runs_same_input)
            if ids == ["run-a", "run-b"]:
                return {"per_experiment_diversity": {"exp-001": 0.1, "exp-002": 0.2}}
            if ids == ["run-c", "run-d"]:
                return {"per_experiment_diversity": {"exp-001": 0.3, "exp-002": 0.4}}
            raise AssertionError(f"unexpected group {ids}")

        monkeypatch.setattr(er, "compute_diversity_for_input", fake_compute_diversity_for_input)

        result = er.postprocess_diversity_for_run_groups([["run-a", "run-b"], ["run-c", "run-d"]])
        assert len(result["patched_run_ids"]) == 4

        runs = {r["run_id"]: r for r in logger.load_all_runs()}
        assert runs["run-a"]["evaluation"]["dimension_scores"]["diversity"] == 10.0
        assert runs["run-d"]["evaluation"]["dimension_scores"]["diversity"] == 40.0
