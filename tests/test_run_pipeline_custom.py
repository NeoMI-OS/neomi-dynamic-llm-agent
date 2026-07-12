"""
Unit tesztek a run_pipeline_custom függvényhez (Phase 2 node-swap sensitivity
analízis): egyedi, ad-hoc pipeline-futtatás explicit node_configs-szal,
YAML-fájl nélkül. A pipeline.run_pipeline és evaluate_run mockolva van --
nincs élő LLM-hívás.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import experiment_runner as er
from experiment_logger import ExperimentLogger


def _fake_pipeline_result():
    return {
        "context_output": "c", "needs_output": "n", "curriculum_output": "cu",
        "content_output": "co", "critic_output": "cr",
        "node_timings": {"context_analyst": 1.0}, "node_tokens": {"context_analyst": 100},
        "node_costs_usd": {"context_analyst": 0.001},
        "total_tokens": 100, "total_cost_usd": 0.001, "total_latency_seconds": 1.0,
        "errors": [],
    }


class TestRunPipelineCustom:
    def test_logs_under_custom_label_not_yaml_experiment_id(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        monkeypatch.setattr(er, "run_pipeline", lambda **kwargs: _fake_pipeline_result())
        monkeypatch.setattr(er, "evaluate_run", lambda run_record, judge_cfg=None: {
            "composite_score": 60.0, "dimension_scores": {"quality": 60.0}, "node_quality_scores": {},
        })

        record = er.run_pipeline_custom(
            input_document="doc", purpose="purpose",
            node_configs={"content_writer": {"provider": "openai", "model": "gpt-4o", "temperature": 0.5}},
            input_id="input-03", label="exp-006-swap-content_writer",
        )

        assert record["experiment_id"] == "exp-006-swap-content_writer"
        assert record["optimization_strategy"] == "custom_node_swap"
        assert record["outputs"]["content"] == "co"
        assert record["evaluation"]["composite_score"] == 60.0

        logged = ExperimentLogger(tmp_path).load_all_runs()
        assert len(logged) == 1
        assert logged[0]["run_id"] == record["run_id"]

    def test_auto_evaluate_false_skips_judge(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        monkeypatch.setattr(er, "run_pipeline", lambda **kwargs: _fake_pipeline_result())

        def fail_evaluate(run_record, judge_cfg=None):
            raise AssertionError("should not be called")

        monkeypatch.setattr(er, "evaluate_run", fail_evaluate)

        record = er.run_pipeline_custom(
            input_document="doc", purpose="purpose", node_configs={}, input_id="input-03",
            label="exp-006-swap-critic", auto_evaluate=False,
        )
        assert record["evaluation"] is None

    def test_passes_node_configs_through_to_run_pipeline(self, tmp_path, monkeypatch):
        monkeypatch.setattr(er, "LOGS_DIR", tmp_path)
        captured = {}

        def fake_run_pipeline(input_document, purpose, node_configs, experiment_id):
            captured["node_configs"] = node_configs
            captured["experiment_id"] = experiment_id
            return _fake_pipeline_result()

        monkeypatch.setattr(er, "run_pipeline", fake_run_pipeline)
        monkeypatch.setattr(er, "evaluate_run", lambda run_record, judge_cfg=None: {
            "composite_score": 1.0, "dimension_scores": {}, "node_quality_scores": {},
        })

        node_configs = {"critic": {"provider": "google", "model": "gemini-2.5-pro", "temperature": 0.1}}
        er.run_pipeline_custom(
            input_document="doc", purpose="purpose", node_configs=node_configs,
            input_id="input-03", label="exp-010-swap-critic",
        )

        assert captured["node_configs"] == node_configs
        assert captured["experiment_id"] == "exp-010-swap-critic"
