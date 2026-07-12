"""
Unit tesztek a compute_fusion_gain függvényhez (Phase 2): mennyivel jobb a
multi-agent pipeline egy ugyanazon input dokumentumon futtatott egylépéses
baseline-nál, composite_score pontban.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from experiment_evaluator import compute_fusion_gain


def _pipeline_run(run_id, input_id, composite):
    return {"run_id": run_id, "input_id": input_id, "evaluation": {"composite_score": composite}}


def _baseline_run(input_id, composite):
    return {"input_id": input_id, "evaluation": {"composite_score": composite}}


class TestComputeFusionGain:
    def test_positive_gain_when_pipeline_beats_baseline(self):
        pipeline_runs = [_pipeline_run("run-a", "input-01", 80.0)]
        baseline_runs = [_baseline_run("input-01", 50.0)]
        result = compute_fusion_gain(pipeline_runs, baseline_runs)
        assert result["run-a"] == 30.0

    def test_negative_gain_when_baseline_beats_pipeline(self):
        pipeline_runs = [_pipeline_run("run-a", "input-01", 40.0)]
        baseline_runs = [_baseline_run("input-01", 60.0)]
        result = compute_fusion_gain(pipeline_runs, baseline_runs)
        assert result["run-a"] == -20.0

    def test_matches_baseline_by_input_id(self):
        pipeline_runs = [
            _pipeline_run("run-a", "input-01", 80.0),
            _pipeline_run("run-b", "input-02", 70.0),
        ]
        baseline_runs = [
            _baseline_run("input-01", 50.0),
            _baseline_run("input-02", 65.0),
        ]
        result = compute_fusion_gain(pipeline_runs, baseline_runs)
        assert result["run-a"] == 30.0
        assert result["run-b"] == 5.0

    def test_missing_baseline_for_input_is_skipped(self):
        pipeline_runs = [_pipeline_run("run-a", "input-99", 80.0)]
        baseline_runs = [_baseline_run("input-01", 50.0)]
        result = compute_fusion_gain(pipeline_runs, baseline_runs)
        assert "run-a" not in result

    def test_missing_composite_score_is_skipped(self):
        pipeline_runs = [{"run_id": "run-a", "input_id": "input-01", "evaluation": {}}]
        baseline_runs = [_baseline_run("input-01", 50.0)]
        result = compute_fusion_gain(pipeline_runs, baseline_runs)
        assert "run-a" not in result
