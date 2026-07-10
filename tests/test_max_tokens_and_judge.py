"""
Unit tesztek a max_tokens node-cap és a Judge truncation-eltávolítás mögötti
plumbing-hoz. Nem hívnak élő API-t — a nagy modelleket mock-oljuk.

Kontextus: a Judge korábban 500-1000 karakterre vágta a node-kimeneteket,
miközben a content_writer kimenete akár 100 000+ karakter is lehetett
(max_tokens korlát nélkül) — ez a mérés érvényességét súlyosan sértette
(<5%, sokszor <1% a Judge által ténylegesen látott tartalom). A 2026-07-10-i
javítás: (1) node-onkénti max_tokens korlát a pipeline-ban, (2) a Judge
prompt truncation eltávolítása.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pipeline
import experiment_evaluator
from experiment_runner import _extract_node_configs


# ---------------------------------------------------------------------------
# pipeline._get_llm / _call_node — max_tokens plumbing
# ---------------------------------------------------------------------------

class TestMaxTokensPlumbing:
    def test_default_max_tokens_used_when_not_in_cfg(self, monkeypatch):
        captured = {}

        class FakeLLM:
            def invoke(self, messages):
                class R:
                    content = "ok"
                    usage_metadata = {"input_tokens": 1, "output_tokens": 1}
                return R()

        def fake_get_llm(provider, model, temperature, max_tokens=4000):
            captured["max_tokens"] = max_tokens
            return FakeLLM()

        monkeypatch.setattr(pipeline, "_get_llm", fake_get_llm)

        state = {"node_configs": {"content_writer": {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.5}}}
        pipeline._call_node(state, "content_writer", "sys", "user")

        assert captured["max_tokens"] == pipeline._DEFAULT_MAX_TOKENS["content_writer"]

    def test_yaml_override_takes_precedence(self, monkeypatch):
        captured = {}

        class FakeLLM:
            def invoke(self, messages):
                class R:
                    content = "ok"
                    usage_metadata = {"input_tokens": 1, "output_tokens": 1}
                return R()

        def fake_get_llm(provider, model, temperature, max_tokens=4000):
            captured["max_tokens"] = max_tokens
            return FakeLLM()

        monkeypatch.setattr(pipeline, "_get_llm", fake_get_llm)

        state = {"node_configs": {"critic": {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.5, "max_tokens": 999}}}
        pipeline._call_node(state, "critic", "sys", "user")

        assert captured["max_tokens"] == 999

    def test_get_llm_passes_max_tokens_to_openai(self, monkeypatch):
        captured = {}

        class FakeChatOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        import langchain_openai
        monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatOpenAI)

        pipeline._get_llm("openai", "gpt-4o-mini", 0.5, max_tokens=1234)
        assert captured["max_tokens"] == 1234

    def test_get_llm_passes_max_output_tokens_to_google(self, monkeypatch):
        captured = {}

        class FakeChatGoogle:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        import langchain_google_genai
        monkeypatch.setattr(langchain_google_genai, "ChatGoogleGenerativeAI", FakeChatGoogle)

        pipeline._get_llm("google", "gemini-2.5-flash", 0.5, max_tokens=4321)
        assert captured["max_output_tokens"] == 4321


class TestExtractNodeConfigsMaxTokens:
    def test_no_max_tokens_key_when_yaml_silent(self):
        cfg = {"pipeline": {"nodes": {"critic": {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3}}}}
        result = _extract_node_configs(cfg)
        assert "max_tokens" not in result["critic"]

    def test_max_tokens_extracted_when_present(self):
        cfg = {"pipeline": {"nodes": {"critic": {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3, "max_tokens": 500}}}}
        result = _extract_node_configs(cfg)
        assert result["critic"]["max_tokens"] == 500

    def test_hybrid_primary_max_tokens_extracted(self):
        cfg = {"pipeline": {"nodes": {"content_writer": {
            "primary": {"provider": "anthropic", "model": "claude-opus-4-8", "temperature": 0.4, "max_tokens": 8000}
        }}}}
        result = _extract_node_configs(cfg)
        assert result["content_writer"]["max_tokens"] == 8000


# ---------------------------------------------------------------------------
# experiment_evaluator.run_llm_judge — no truncation
# ---------------------------------------------------------------------------

class TestJudgeNoTruncation:
    def test_long_content_passed_untruncated_to_judge(self, monkeypatch):
        captured = {}
        long_content = "X" * 5000  # jóval a régi 1000-karakteres limit fölött

        class FakeLLM:
            def invoke(self, messages):
                captured["prompt"] = messages[0].content

                class R:
                    content = '{"overall_quality": 90, "node_scores": {}}'
                return R()

        monkeypatch.setattr(experiment_evaluator, "_get_judge_llm", lambda *a, **k: FakeLLM())

        outputs = {
            "context": "c", "needs": "n", "curriculum": "cu",
            "content": long_content, "critic": "cr",
        }
        experiment_evaluator.run_llm_judge(outputs, context="ctx", purpose="purpose")

        assert long_content in captured["prompt"]
