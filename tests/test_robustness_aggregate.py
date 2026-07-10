"""
Unit tesztek a experiment_evaluator.py új függvényeihez:
recompute_composite_score és compute_robustness_aggregate.
Nincs LLM-hívás — csak szintetikus dimension_scores/run_record adatokkal dolgozik.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from experiment_evaluator import recompute_composite_score, compute_robustness_aggregate


class TestRecomputeCompositeScore:
    def test_matches_known_formula_without_cost(self):
        # quality*0.50 + latency*0.1875 + robustness*0.1875 + diversity*0.125, cost NEM számít bele
        ds = {"quality": 85.0, "cost": 69.8, "latency": 44.9, "robustness": 90.0, "diversity": 50.0}
        expected = round((0.50 * 85.0 + 0.1875 * 44.9 + 0.1875 * 90.0 + 0.125 * 50.0), 1)
        assert recompute_composite_score(ds) == expected

    def test_cost_does_not_affect_composite(self):
        ds_low_cost = {"quality": 85.0, "cost": 10.0, "latency": 44.9, "robustness": 90.0, "diversity": 50.0}
        ds_high_cost = dict(ds_low_cost, cost=95.0)
        assert recompute_composite_score(ds_low_cost) == recompute_composite_score(ds_high_cost)

    def test_higher_diversity_increases_composite(self):
        ds_low = {"quality": 85.0, "cost": 69.8, "latency": 44.9, "robustness": 90.0, "diversity": 50.0}
        ds_high = dict(ds_low, diversity=90.0)
        assert recompute_composite_score(ds_high) > recompute_composite_score(ds_low)

    def test_missing_dimension_defaults_to_zero(self):
        ds = {"quality": 100.0}
        # csak a quality súlya (0.50) számít bele, a többi (cost kizárva, a többi hiányzik) 0
        assert recompute_composite_score(ds) == 50.0

    def test_custom_weights(self):
        ds = {"quality": 100.0, "cost": 0.0, "latency": 0.0, "robustness": 0.0, "diversity": 0.0}
        weights = {"quality": 1.0, "cost": 0.0, "latency": 0.0, "robustness": 0.0, "diversity": 0.0}
        assert recompute_composite_score(ds, weights) == 100.0


class TestComputeRobustnessAggregate:
    def _run(self, quality, composite, has_error, cost=0.05, latency=60):
        return {
            "experiment_id": "exp-001",
            "evaluation": {"dimension_scores": {"quality": quality}, "composite_score": composite},
            "errors": ["boom"] if has_error else [],
            "metrics": {"total_cost_usd": cost, "total_latency_seconds": latency},
        }

    def test_empty_input_returns_empty_dict(self):
        assert compute_robustness_aggregate([]) == {}

    def test_n_inputs_matches_run_count(self):
        runs = [self._run(80, 70, False), self._run(90, 75, False), self._run(60, 55, True)]
        agg = compute_robustness_aggregate(runs)
        assert agg["n_inputs"] == 3
        assert agg["experiment_id"] == "exp-001"

    def test_failure_rate(self):
        runs = [self._run(80, 70, False), self._run(90, 75, False), self._run(60, 55, True)]
        agg = compute_robustness_aggregate(runs)
        assert agg["failure_rate"] == round(1 / 3, 4)

    def test_mean_and_stdev_quality(self):
        runs = [self._run(80, 70, False), self._run(90, 75, False), self._run(70, 65, False)]
        agg = compute_robustness_aggregate(runs)
        assert agg["mean_quality"] == 80.0
        assert agg["stdev_quality"] > 0

    def test_single_run_stdev_is_zero_not_crash(self):
        runs = [self._run(80, 70, False)]
        agg = compute_robustness_aggregate(runs)
        assert agg["stdev_quality"] == 0.0
        assert agg["stdev_composite"] == 0.0

    def test_zero_variance_when_all_identical(self):
        runs = [self._run(80, 70, False), self._run(80, 70, False)]
        agg = compute_robustness_aggregate(runs)
        assert agg["stdev_quality"] == 0.0
