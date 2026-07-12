"""
Unit teszt a log_rejudge_patch mechanizmushoz: a diverzitás megőrződik a
korábbi diversity-patch-ből, miközben a többi dimenzió (és node_quality_scores)
a rejudge-patch-ből frissül, és a composite_score újraszámolódik.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from experiment_logger import ExperimentLogger


def _base_record(run_id="run-x"):
    return {
        "run_id": run_id, "experiment_id": "exp-001", "input_id": "in-1",
        "experiment_name": "T", "optimization_strategy": "s", "started_at": "2026-07-10T00:00:00Z",
        "outputs": {"context": "c", "needs": "n", "curriculum": "cu", "content": "co", "critic": "cr"},
        "purpose": "test",
        "metrics": {"total_cost_usd": 0.05, "total_latency_seconds": 60, "total_tokens": 1000},
        "evaluation": {
            "composite_score": 50.0,
            "dimension_scores": {"quality": 85.0, "cost": 69.8, "latency": 44.9, "robustness": 90.0, "diversity": 50.0},
            "critic_issues_count": 2, "pareto_dominated": None,
        },
        "errors": [],
    }


class TestRejudgePatch:
    def test_diversity_preserved_across_rejudge(self, tmp_path):
        logger = ExperimentLogger(tmp_path)
        logger.log(_base_record())
        logger.log_diversity_patch("run-x", 0.42)

        new_evaluation = {
            "composite_score": 999,
            "dimension_scores": {"quality": 88.0, "cost": 60.0, "latency": 40.0, "robustness": 90.0, "diversity": 999.0},
            "node_quality_scores": {
                "context_analyst": {"score": 90, "comment": "x"},
                "content_writer": {"score": 82, "comment": "w"},
            },
            "critic_issues_count": 1, "pareto_dominated": None,
        }
        logger.log_rejudge_patch("run-x", new_evaluation)

        run = logger.load_all_runs()[0]
        assert run["evaluation"]["dimension_scores"]["diversity"] == 42.0
        assert run["evaluation"]["dimension_scores"]["quality"] == 88.0
        assert run["evaluation"]["node_quality_scores"]["content_writer"]["score"] == 82

    def test_composite_recomputed_after_rejudge(self, tmp_path):
        logger = ExperimentLogger(tmp_path)
        logger.log(_base_record())
        logger.log_diversity_patch("run-x", 0.42)
        logger.log_rejudge_patch("run-x", {
            "composite_score": 12345,  # stale placeholder, must be overwritten
            "dimension_scores": {"quality": 100.0, "cost": 0.0, "latency": 100.0, "robustness": 100.0, "diversity": 0.0},
            "node_quality_scores": {}, "critic_issues_count": 0, "pareto_dominated": None,
        })
        run = logger.load_all_runs()[0]
        assert run["evaluation"]["composite_score"] != 12345

    def test_rejudge_without_prior_diversity_patch_keeps_rejudge_value(self, tmp_path):
        # ha sosem volt diverzitás-patch, a rejudge saját (akár placeholder) értéke marad
        logger = ExperimentLogger(tmp_path)
        logger.log(_base_record())
        logger.log_rejudge_patch("run-x", {
            "composite_score": 0,
            "dimension_scores": {"quality": 80.0, "cost": 50.0, "latency": 50.0, "robustness": 90.0, "diversity": 33.3},
            "node_quality_scores": {}, "critic_issues_count": 0, "pareto_dominated": None,
        })
        run = logger.load_all_runs()[0]
        assert run["evaluation"]["dimension_scores"]["diversity"] == 33.3

    def test_novelty_score_preserved_across_rejudge(self, tmp_path):
        logger = ExperimentLogger(tmp_path)
        logger.log(_base_record())
        logger.log_novelty_patch("run-x", 0.65)

        logger.log_rejudge_patch("run-x", {
            "composite_score": 0,
            "dimension_scores": {"quality": 90.0, "cost": 50.0, "latency": 50.0, "robustness": 90.0, "diversity": 50.0},
            "node_quality_scores": {}, "critic_issues_count": 0, "pareto_dominated": None,
        })
        run = logger.load_all_runs()[0]
        assert run["evaluation"]["novelty_score"] == 65.0

    def test_unrelated_run_untouched(self, tmp_path):
        logger = ExperimentLogger(tmp_path)
        logger.log(_base_record("run-a"))
        logger.log(_base_record("run-b"))
        logger.log_rejudge_patch("run-a", {
            "composite_score": 0,
            "dimension_scores": {"quality": 1.0, "cost": 1.0, "latency": 1.0, "robustness": 1.0, "diversity": 1.0},
            "node_quality_scores": {}, "critic_issues_count": 0, "pareto_dominated": None,
        })
        runs = {r["run_id"]: r for r in logger.load_all_runs()}
        assert runs["run-a"]["evaluation"]["dimension_scores"]["quality"] == 1.0
        assert runs["run-b"]["evaluation"]["dimension_scores"]["quality"] == 85.0
