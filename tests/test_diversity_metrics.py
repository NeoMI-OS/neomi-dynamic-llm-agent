"""
Unit tesztek a diversity_metrics modulhoz.
Az embed_text mockolva van fix vektorokkal — nincs élő OpenAI API-hívás.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import diversity_metrics as dm


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert dm.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0

    def test_orthogonal_vectors(self):
        assert abs(dm.cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-9

    def test_opposite_vectors(self):
        assert dm.cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0

    def test_zero_vector_does_not_crash(self):
        assert dm.cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestComputeDiversityForInput:
    def test_fewer_than_two_runs_returns_empty(self):
        result = dm.compute_diversity_for_input([{"input_id": "in-1", "experiment_id": "exp-A"}])
        assert result["per_experiment_diversity"] == {}
        assert result["pairwise_avg_similarity"] is None

    def test_near_identical_vs_orthogonal(self, monkeypatch):
        fake_vectors = {
            "exp-A": [1.0, 0.0, 0.0],
            "exp-B": [0.99, 0.01, 0.0],   # near-identical to exp-A
            "exp-C": [0.0, 1.0, 0.0],     # orthogonal to both
        }

        def fake_embed(text, model="text-embedding-3-small"):
            return fake_vectors[text]

        monkeypatch.setattr(dm, "embed_text", fake_embed)

        runs = [
            {"input_id": "in-1", "experiment_id": "exp-A", "outputs": {"content": "exp-A"}},
            {"input_id": "in-1", "experiment_id": "exp-B", "outputs": {"content": "exp-B"}},
            {"input_id": "in-1", "experiment_id": "exp-C", "outputs": {"content": "exp-C"}},
        ]
        result = dm.compute_diversity_for_input(runs)

        div = result["per_experiment_diversity"]
        assert div["exp-C"] > div["exp-A"]
        assert div["exp-C"] > div["exp-B"]
        assert all(0.0 <= v <= 1.0 for v in div.values())
        assert result["input_id"] == "in-1"

    def test_missing_content_treated_as_empty_string(self, monkeypatch):
        monkeypatch.setattr(dm, "embed_text", lambda text, model="text-embedding-3-small": [0.5, 0.5])
        runs = [
            {"input_id": "in-1", "experiment_id": "exp-A", "outputs": {}},
            {"input_id": "in-1", "experiment_id": "exp-B", "outputs": {"content": "something"}},
        ]
        result = dm.compute_diversity_for_input(runs)
        assert set(result["per_experiment_diversity"].keys()) == {"exp-A", "exp-B"}


class TestComputeNoveltyVsBaseline:
    def test_baseline_excluded_from_result(self, monkeypatch):
        monkeypatch.setattr(dm, "embed_text", lambda text, model="text-embedding-3-small": [1.0, 0.0])
        runs = [
            {"experiment_id": "exp-001", "outputs": {"content": "baseline"}},
            {"experiment_id": "exp-006", "outputs": {"content": "other"}},
        ]
        result = dm.compute_novelty_vs_baseline(runs, "exp-001")
        assert "exp-001" not in result
        assert "exp-006" in result

    def test_identical_to_baseline_has_zero_novelty(self, monkeypatch):
        monkeypatch.setattr(dm, "embed_text", lambda text, model="text-embedding-3-small": [1.0, 0.0])
        runs = [
            {"experiment_id": "exp-001", "outputs": {"content": "same"}},
            {"experiment_id": "exp-002", "outputs": {"content": "same"}},
        ]
        result = dm.compute_novelty_vs_baseline(runs, "exp-001")
        assert abs(result["exp-002"] - 0.0) < 1e-9

    def test_orthogonal_to_baseline_has_high_novelty(self, monkeypatch):
        vectors = {"base": [1.0, 0.0], "diff": [0.0, 1.0]}
        monkeypatch.setattr(dm, "embed_text", lambda text, model="text-embedding-3-small": vectors[text])
        runs = [
            {"experiment_id": "exp-001", "outputs": {"content": "base"}},
            {"experiment_id": "exp-006", "outputs": {"content": "diff"}},
        ]
        result = dm.compute_novelty_vs_baseline(runs, "exp-001")
        assert abs(result["exp-006"] - 1.0) < 1e-9

    def test_missing_baseline_returns_empty_dict(self, monkeypatch):
        monkeypatch.setattr(dm, "embed_text", lambda text, model="text-embedding-3-small": [1.0, 0.0])
        runs = [{"experiment_id": "exp-006", "outputs": {"content": "x"}}]
        result = dm.compute_novelty_vs_baseline(runs, "exp-001")
        assert result == {}
