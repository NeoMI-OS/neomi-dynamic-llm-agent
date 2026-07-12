"""
Unit tesztek a compute_pareto_front_multi_dim függvényhez (Phase 2: kísérlet-
szintű Pareto-front Quality/Cost/Latency/Robustness dimenziókban, az
evaluation_framework.yaml saját definíciója szerint).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from experiment_evaluator import compute_pareto_front_multi_dim


def _exp(exp_id, quality, cost, latency, robustness):
    return {"experiment_id": exp_id, "dimension_scores": {
        "quality": quality, "cost": cost, "latency": latency, "robustness": robustness,
    }}


class TestComputePartoFrontMultiDim:
    def test_strictly_dominated_experiment_excluded(self):
        experiments = [
            _exp("A", 90, 90, 90, 90),
            _exp("B", 50, 50, 50, 50),  # A dominates B on every dim
        ]
        front = compute_pareto_front_multi_dim(experiments)
        assert front == ["A"]

    def test_tradeoff_experiments_both_on_front(self):
        experiments = [
            _exp("A", 90, 20, 50, 50),   # high quality, low cost score
            _exp("B", 50, 90, 50, 50),   # low quality, high cost score (cheap)
        ]
        front = compute_pareto_front_multi_dim(experiments)
        assert set(front) == {"A", "B"}

    def test_equal_scores_are_not_dominated(self):
        experiments = [_exp("A", 70, 70, 70, 70), _exp("B", 70, 70, 70, 70)]
        front = compute_pareto_front_multi_dim(experiments)
        assert set(front) == {"A", "B"}

    def test_custom_dims_subset(self):
        experiments = [
            _exp("A", 90, 10, 90, 10),
            _exp("B", 50, 90, 50, 90),
        ]
        # csak quality+latency alapján: A dominálja B-t
        front = compute_pareto_front_multi_dim(experiments, dims=["quality", "latency"])
        assert front == ["A"]

    def test_missing_dimension_defaults_to_zero(self):
        experiments = [
            _exp("A", 90, 90, 90, 90),
            {"experiment_id": "B", "dimension_scores": {}},
        ]
        front = compute_pareto_front_multi_dim(experiments)
        assert front == ["A"]
