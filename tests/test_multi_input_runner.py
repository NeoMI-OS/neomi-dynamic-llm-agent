"""
Unit tesztek a run_experiment_series_multi_input ciklushoz.
Az experiment_runner.run_experiment mockolva van (monkeypatch) — nincs élő
LLM-hívás, nincs valódi pipeline-futás. A diversity_metrics.embed_text is
mockolva fix, szöveg-alapú vektorokkal.
"""
import sys
import os
import csv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import experiment_runner as er
import diversity_metrics
from experiment_logger import ExperimentLogger


def _fake_run_experiment(logs_dir, cost=0.5):
    def _fn(experiment_id, input_document, purpose, auto_evaluate=True, tags=None, input_id=None):
        record = {
            "run_id": f"run-{experiment_id}-{input_id}",
            "experiment_id": experiment_id,
            "input_id": input_id,
            "experiment_name": f"Fake {experiment_id}",
            "optimization_strategy": "fake",
            "started_at": "2026-07-08T00:00:00Z",
            "metrics": {"total_cost_usd": cost, "total_latency_seconds": 10, "total_tokens": 100},
            "outputs": {"content": f"fake content {experiment_id} {input_id} " * 5},
            "evaluation": {
                "composite_score": 70.0,
                "dimension_scores": {"quality": 80, "cost": 70, "latency": 60, "robustness": 90, "diversity": 50.0},
                "critic_issues_count": 0,
                "pareto_dominated": None,
            },
            "errors": [],
        }
        ExperimentLogger(logs_dir).log(record)
        return record
    return _fn


def _fake_embed(text, model="text-embedding-3-small"):
    import hashlib
    h = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [(h % 1000) / 1000.0, ((h // 1000) % 1000) / 1000.0, ((h // 1000000) % 1000) / 1000.0]


class TestMultiInputLoop:
    def test_runs_all_input_x_experiment_combinations(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        monkeypatch.setattr(er, "run_experiment", _fake_run_experiment(tmp_path))
        monkeypatch.setattr(diversity_metrics, "embed_text", _fake_embed)
        monkeypatch.setattr(er, "compute_diversity_for_input", diversity_metrics.compute_diversity_for_input)

        inputs = [{"input_id": f"in-{i}", "input_document": f"doc{i}", "purpose": f"p{i}"} for i in range(1, 4)]
        experiment_ids = ["exp-A", "exp-B", "exp-C"]

        result = er.run_experiment_series_multi_input(
            inputs=inputs, experiment_ids=experiment_ids,
            cost_cap_usd=100.0, global_cost_cap_usd=100.0, delay_between_runs=0,
        )

        assert result["runs_completed"] == 9
        assert result["aborted"] is False

    def test_correct_input_id_experiment_id_tagging(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        monkeypatch.setattr(er, "run_experiment", _fake_run_experiment(tmp_path))
        monkeypatch.setattr(diversity_metrics, "embed_text", _fake_embed)
        monkeypatch.setattr(er, "compute_diversity_for_input", diversity_metrics.compute_diversity_for_input)

        inputs = [{"input_id": "in-1", "input_document": "d1", "purpose": "p1"},
                  {"input_id": "in-2", "input_document": "d2", "purpose": "p2"}]
        experiment_ids = ["exp-A", "exp-B"]

        er.run_experiment_series_multi_input(
            inputs=inputs, experiment_ids=experiment_ids,
            cost_cap_usd=100.0, global_cost_cap_usd=100.0, delay_between_runs=0,
        )

        with open(tmp_path / "experiment_summary.csv") as f:
            rows = list(csv.DictReader(f))
        pairs = {(r["experiment_id"], r["input_id"]) for r in rows}
        assert pairs == {("exp-A", "in-1"), ("exp-A", "in-2"), ("exp-B", "in-1"), ("exp-B", "in-2")}

    def test_aggregate_has_one_row_per_experiment_with_correct_n_inputs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        monkeypatch.setattr(er, "run_experiment", _fake_run_experiment(tmp_path))
        monkeypatch.setattr(diversity_metrics, "embed_text", _fake_embed)
        monkeypatch.setattr(er, "compute_diversity_for_input", diversity_metrics.compute_diversity_for_input)

        inputs = [{"input_id": f"in-{i}", "input_document": f"d{i}", "purpose": f"p{i}"} for i in range(1, 4)]
        experiment_ids = ["exp-A", "exp-B", "exp-C"]

        er.run_experiment_series_multi_input(
            inputs=inputs, experiment_ids=experiment_ids,
            cost_cap_usd=100.0, global_cost_cap_usd=100.0, delay_between_runs=0,
        )

        with open(tmp_path / "experiment_robustness_aggregate.csv") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3
        assert all(r["n_inputs"] == "3" for r in rows)

    def test_diversity_score_no_longer_flat_placeholder(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        monkeypatch.setattr(er, "run_experiment", _fake_run_experiment(tmp_path))
        monkeypatch.setattr(diversity_metrics, "embed_text", _fake_embed)
        monkeypatch.setattr(er, "compute_diversity_for_input", diversity_metrics.compute_diversity_for_input)

        inputs = [{"input_id": "in-1", "input_document": "d1", "purpose": "p1"}]
        experiment_ids = ["exp-A", "exp-B", "exp-C"]

        er.run_experiment_series_multi_input(
            inputs=inputs, experiment_ids=experiment_ids,
            cost_cap_usd=100.0, global_cost_cap_usd=100.0, delay_between_runs=0,
        )

        with open(tmp_path / "experiment_summary.csv") as f:
            rows = list(csv.DictReader(f))
        diversities = {r["diversity_score"] for r in rows}
        assert diversities != {"50.0"}


class TestCostCapAbort:
    def test_stops_once_cap_reached_but_keeps_completed_runs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        calls = []

        def counting_run_experiment(experiment_id, input_document, purpose, auto_evaluate=True, tags=None, input_id=None):
            calls.append((experiment_id, input_id))
            fn = _fake_run_experiment(tmp_path, cost=2.0)
            return fn(experiment_id, input_document, purpose, auto_evaluate, tags, input_id)

        monkeypatch.setattr(er, "run_experiment", counting_run_experiment)
        monkeypatch.setattr(diversity_metrics, "embed_text", _fake_embed)
        monkeypatch.setattr(er, "compute_diversity_for_input", diversity_metrics.compute_diversity_for_input)

        inputs = [{"input_id": f"in-{i}", "input_document": f"d{i}", "purpose": f"p{i}"} for i in range(1, 4)]
        experiment_ids = ["exp-A", "exp-B", "exp-C"]

        # $2/run, cap=$5: pre-check passes at $0, $2, $4 (3 runs happen, total $6),
        # 4th call's pre-check at $6 >= $5 aborts before starting.
        result = er.run_experiment_series_multi_input(
            inputs=inputs, experiment_ids=experiment_ids,
            cost_cap_usd=5.0, global_cost_cap_usd=100.0, delay_between_runs=0,
        )

        assert result["aborted"] is True
        assert len(calls) == 3
        assert result["runs_completed"] == 3
        # already-completed, already-paid-for results are preserved, not discarded
        assert len(result["runs"]) == 3

    def test_global_cap_already_exceeded_aborts_before_starting(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        # pre-seed a summary CSV that already shows the daily budget blown
        with open(tmp_path / "experiment_summary.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["run_id", "total_cost_usd"])
            writer.writeheader()
            writer.writerow({"run_id": "prior-run", "total_cost_usd": "999.0"})

        calls = []
        monkeypatch.setattr(er, "run_experiment", lambda **kw: calls.append(kw))

        result = er.run_experiment_series_multi_input(
            inputs=[{"input_id": "in-1", "input_document": "d", "purpose": "p"}],
            experiment_ids=["exp-A"],
            cost_cap_usd=10.0, global_cost_cap_usd=100.0, delay_between_runs=0,
        )

        assert result["aborted"] is True
        assert len(calls) == 0
