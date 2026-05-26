"""
Unit tesztek az evaluator modul SRS logikájához.
Nem hív AA API-t — minden teszt mock adatokat használ.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from evaluator import _compute_srs, _compute_performance, _avg, evaluate_model, MODEL_SLUG_MAP


# ---------------------------------------------------------------------------
# _avg helper
# ---------------------------------------------------------------------------

class TestAvg:
    def test_all_values(self):
        assert _avg(0.5, 0.7, 0.9) == round((0.5 + 0.7 + 0.9) / 3, 4)

    def test_skip_none(self):
        assert _avg(0.5, None, 0.9) == round((0.5 + 0.9) / 2, 4)

    def test_all_none(self):
        assert _avg(None, None) is None

    def test_single_value(self):
        assert _avg(0.8) == 0.8


# ---------------------------------------------------------------------------
# Knowledge / Reasoning / Usability scores
# ---------------------------------------------------------------------------

class TestComputeSRS:
    def _evals(self, **kwargs):
        return kwargs

    def test_knowledge_score_both_available(self):
        result = _compute_srs(self._evals(mmlu_pro=0.8, gpqa=0.6))
        assert result["knowledge_score"] == round((0.8 + 0.6) / 2 * 100, 1)

    def test_knowledge_score_one_missing(self):
        result = _compute_srs(self._evals(mmlu_pro=0.8))
        assert result["knowledge_score"] == 80.0

    def test_knowledge_score_both_missing(self):
        result = _compute_srs(self._evals())
        assert result["knowledge_score"] is None

    def test_reasoning_score_all_available(self):
        result = _compute_srs(self._evals(math_500=0.9, aime=0.7, livecodebench=0.8))
        assert result["reasoning_score"] == round((0.9 + 0.7 + 0.8) / 3 * 100, 1)

    def test_reasoning_score_partial(self):
        result = _compute_srs(self._evals(math_500=0.9, aime=0.7))
        assert result["reasoning_score"] == round((0.9 + 0.7) / 2 * 100, 1)

    def test_usability_score_normalizes_from_100(self):
        # AA Intelligence Index 0–100 → normalized to 0–1 → displayed as 0–100
        result = _compute_srs(self._evals(artificial_analysis_intelligence_index=75.0))
        assert result["usability_score"] == 75.0

    def test_usability_score_missing(self):
        result = _compute_srs(self._evals())
        assert result["usability_score"] is None

    def test_srs_all_categories_available(self):
        evals = self._evals(
            mmlu_pro=0.8, gpqa=0.6,
            math_500=0.9, aime=0.7, livecodebench=0.8,
            artificial_analysis_intelligence_index=75.0
        )
        result = _compute_srs(evals)
        # Manual calculation
        k = (0.8 + 0.6) / 2       # 0.7
        r = (0.9 + 0.7 + 0.8) / 3 # 0.8
        u = 75.0 / 100             # 0.75
        weights = {"knowledge": 0.25, "reasoning": 0.35, "usability": 0.40}
        expected_srs = round((weights["knowledge"] * k + weights["reasoning"] * r + weights["usability"] * u) * 100, 1)
        assert result["service_readiness_score"] == expected_srs

    def test_srs_partial_categories_rescales_weights(self):
        # Only usability available → SRS = usability score
        result = _compute_srs(self._evals(artificial_analysis_intelligence_index=80.0))
        assert result["service_readiness_score"] == 80.0

    def test_srs_no_data_is_none(self):
        result = _compute_srs(self._evals())
        assert result["service_readiness_score"] is None

    def test_srs_within_0_100_range(self):
        evals = self._evals(
            mmlu_pro=1.0, gpqa=1.0,
            math_500=1.0, aime=1.0, livecodebench=1.0,
            artificial_analysis_intelligence_index=100.0
        )
        result = _compute_srs(evals)
        assert 0 <= result["service_readiness_score"] <= 100

    def test_benchmarks_used_field_present(self):
        result = _compute_srs(self._evals())
        assert "benchmarks_used" in result
        assert "knowledge" in result["benchmarks_used"]
        assert "reasoning" in result["benchmarks_used"]
        assert "usability" in result["benchmarks_used"]

    def test_srs_weights_field_present(self):
        result = _compute_srs(self._evals())
        assert result["srs_weights"]["knowledge"] == 0.25
        assert result["srs_weights"]["reasoning"] == 0.35
        assert result["srs_weights"]["usability"] == 0.40


# ---------------------------------------------------------------------------
# Performance metrics
# ---------------------------------------------------------------------------

class TestComputePerformance:
    def _aa_model(self, speed=None, ttft=None, price=None, intel=None):
        return (
            {
                "median_output_tokens_per_second": speed,
                "median_time_to_first_token_seconds": ttft,
                "pricing": {"price_1m_blended_3_to_1": price} if price else {},
            },
            {"artificial_analysis_intelligence_index": intel} if intel else {}
        )

    def test_speed_and_ttft(self):
        model, evals = self._aa_model(speed=120.5, ttft=0.54)
        result = _compute_performance(model, evals)
        assert result["speed_tokens_per_sec"] == 120.5
        assert result["time_to_first_token_sec"] == 0.54

    def test_quality_price_ratio(self):
        model, evals = self._aa_model(price=2.0, intel=80.0)
        result = _compute_performance(model, evals)
        assert result["quality_price_ratio"] == round(80.0 / 2.0, 2)

    def test_quality_price_ratio_missing_price(self):
        model, evals = self._aa_model(intel=80.0)
        result = _compute_performance(model, evals)
        assert result["quality_price_ratio"] is None

    def test_missing_speed(self):
        model, evals = self._aa_model()
        result = _compute_performance(model, evals)
        assert result["speed_tokens_per_sec"] is None


# ---------------------------------------------------------------------------
# evaluate_model — no API key → graceful unavailable response
# ---------------------------------------------------------------------------

class TestEvaluateModel:
    def test_no_api_key_returns_unavailable(self, monkeypatch):
        monkeypatch.delenv("ARTIFICIAL_ANALYSIS_API_KEY", raising=False)
        # Clear cache
        import evaluator
        evaluator._cache["data"] = None
        evaluator._cache["fetched_at"] = 0

        result = evaluate_model("gpt-4o")
        assert result["available"] is False

    def test_model_slug_map_covers_configured_models(self):
        configured_models = ["gemini-2.5-flash-lite", "gpt-4o-mini", "gpt-4o", "claude-sonnet-4-6"]
        for model in configured_models:
            assert model in MODEL_SLUG_MAP, f"{model} hiányzik a MODEL_SLUG_MAP-ból"
