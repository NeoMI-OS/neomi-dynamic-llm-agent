"""
Unit tesztek a cross_judge_logged_runs függvényhez (Phase 2: másodlagos
LLM-judge kereszt-ellenőrzés). Az evaluate_run mockolva van -- nincs élő
LLM-hívás. A teszt azt ellenőrzi, hogy a kanonikus "evaluation" mezőt NEM
módosítja (dry-run), csak a visszaadott összehasonlító adatokban jelenik meg
a másodlagos judge eredménye.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import experiment_runner as er
from experiment_logger import ExperimentLogger


def _base_record(run_id="run-x", experiment_id="exp-001", input_id="in-1"):
    return {
        "run_id": run_id, "experiment_id": experiment_id, "input_id": input_id,
        "experiment_name": "T", "optimization_strategy": "s", "started_at": "2026-07-12T00:00:00Z",
        "outputs": {"context": "c", "needs": "n", "curriculum": "cu", "content": "co", "critic": "cr"},
        "purpose": "test",
        "metrics": {"total_cost_usd": 0.05, "total_latency_seconds": 60, "total_tokens": 1000},
        "evaluation": {
            "composite_score": 70.0,
            "dimension_scores": {"quality": 80.0, "cost": 60.0, "latency": 50.0, "robustness": 90.0, "diversity": 50.0},
            "node_quality_scores": {"content_writer": {"score": 80, "comment": "ok"}},
            "critic_issues_count": 1, "pareto_dominated": None,
        },
        "errors": [],
    }


class TestCrossJudgeLoggedRuns:
    def test_returns_primary_and_secondary_scores(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        logger = ExperimentLogger(tmp_path)
        logger.log(_base_record())

        def fake_evaluate_run(run_record, judge_cfg=None):
            assert judge_cfg == {"judge_provider": "openai", "judge_model": "gpt-4o"}
            return {
                "composite_score": 55.0,
                "dimension_scores": {"quality": 60.0, "cost": 60.0, "latency": 50.0, "robustness": 90.0, "diversity": 50.0},
                "node_quality_scores": {"content_writer": {"score": 55, "comment": "meh"}},
            }

        monkeypatch.setattr(er, "evaluate_run", fake_evaluate_run)

        result = er.cross_judge_logged_runs(["run-x"], judge_provider="openai", judge_model="gpt-4o")

        assert result["errors"] == []
        assert len(result["results"]) == 1
        r = result["results"][0]
        # load_all_runs() mindig újraszámolja a composite_score-t az aktuális
        # formulával a dimension_scores-ból (0.50*80 + 0.1875*50 + 0.1875*90 + 0.125*50 = 72.5),
        # nem a naplózott placeholder 70.0-t adja vissza -- ez a rendszer szándékos, dokumentált viselkedése.
        assert r["primary_composite_score"] == 72.5
        assert r["secondary_composite_score"] == 55.0
        assert r["primary_quality"] == 80.0
        assert r["secondary_quality"] == 60.0

    def test_does_not_mutate_canonical_evaluation(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        logger = ExperimentLogger(tmp_path)
        logger.log(_base_record())

        monkeypatch.setattr(er, "evaluate_run", lambda run_record, judge_cfg=None: {
            "composite_score": 1.0, "dimension_scores": {}, "node_quality_scores": {},
        })

        er.cross_judge_logged_runs(["run-x"], judge_provider="openai", judge_model="gpt-4o")

        run = logger.load_all_runs()[0]
        assert run["evaluation"]["composite_score"] == 72.5  # unchanged (recomputed from the ORIGINAL dimension_scores)

    def test_unknown_run_id_reported_as_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        ExperimentLogger(tmp_path)  # ensure dir exists

        result = er.cross_judge_logged_runs(["run-does-not-exist"])
        assert result["results"] == []
        assert len(result["errors"]) == 1
        assert "run-does-not-exist" in result["errors"][0]

    def test_evaluate_run_exception_captured_as_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        logger = ExperimentLogger(tmp_path)
        logger.log(_base_record())

        def raising_evaluate_run(run_record, judge_cfg=None):
            raise RuntimeError("judge API failure")

        monkeypatch.setattr(er, "evaluate_run", raising_evaluate_run)

        result = er.cross_judge_logged_runs(["run-x"])
        assert result["results"] == []
        assert "judge API failure" in result["errors"][0]
