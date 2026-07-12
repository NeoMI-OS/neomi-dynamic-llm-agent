"""
Unit tesztek a coverage_metrics modulhoz (Phase 2: ROUGE-L + szemantikai
fedettség a content_writer kimenete és a curriculum_designer terve között).
Az embed_text mockolva van -- nincs élő OpenAI API-hívás.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import coverage_metrics as cm


class TestRougeLF1:
    def test_identical_text_scores_one(self):
        text = "a b c d e"
        assert cm.rouge_l_f1(text, text) == 1.0

    def test_completely_disjoint_tokens_scores_zero(self):
        assert cm.rouge_l_f1("alpha beta gamma", "delta epsilon zeta") == 0.0

    def test_partial_overlap_between_zero_and_one(self):
        score = cm.rouge_l_f1("module one two three", "intro module one summary")
        assert 0.0 < score < 1.0

    def test_empty_reference_or_hypothesis_returns_zero(self):
        assert cm.rouge_l_f1("", "something") == 0.0
        assert cm.rouge_l_f1("something", "") == 0.0

    def test_case_insensitive(self):
        assert cm.rouge_l_f1("Module One", "module one") == 1.0


class TestSemanticSimilarityScore:
    def test_uses_embed_text_and_cosine_similarity(self, monkeypatch):
        calls = []

        def fake_embed(text, model="text-embedding-3-small"):
            calls.append(text)
            return [1.0, 0.0] if text == "ref" else [0.0, 1.0]

        monkeypatch.setattr(cm, "embed_text", fake_embed)
        score = cm.semantic_similarity_score("ref", "hyp")
        assert calls == ["ref", "hyp"]
        assert abs(score - 0.0) < 1e-9

    def test_empty_inputs_return_zero_without_calling_embed(self, monkeypatch):
        def fail_embed(text, model="text-embedding-3-small"):
            raise AssertionError("should not be called")

        monkeypatch.setattr(cm, "embed_text", fail_embed)
        assert cm.semantic_similarity_score("", "hyp") == 0.0
        assert cm.semantic_similarity_score("ref", "") == 0.0


class TestComputeCoverageForRun:
    def test_returns_both_metrics(self, monkeypatch):
        monkeypatch.setattr(cm, "embed_text", lambda text, model="text-embedding-3-small": [1.0, 0.0])
        result = cm.compute_coverage_for_run("module one two", "module one two")
        assert result["rouge_l"] == 1.0
        assert result["semantic_similarity"] == 1.0
