"""
Unit tesztek a single_call_baseline modulhoz (Phase 2 fusion_gain
referenciapontja). A pipeline._get_llm mockolva van -- nincs élő API-hívás.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import single_call_baseline as scb


class _FakeResponse:
    def __init__(self, content, usage_metadata=None):
        self.content = content
        self.usage_metadata = usage_metadata or {}


class TestExtractJson:
    def test_plain_json(self):
        assert scb._extract_json('{"context": "x"}') == {"context": "x"}

    def test_fenced_json_block(self):
        text = '```json\n{"context": "x"}\n```'
        assert scb._extract_json(text) == {"context": "x"}

    def test_unparseable_returns_empty_dict(self):
        assert scb._extract_json("not json at all") == {}


class TestRunSingleCallBaseline:
    def test_returns_pipeline_compatible_shape(self, monkeypatch):
        fake_json = '{"context": "c", "needs": "n", "curriculum": "cu", "content": "co", "critic": "cr"}'

        class FakeLLM:
            def invoke(self, messages):
                return _FakeResponse(fake_json, {"input_tokens": 100, "output_tokens": 200})

        # pipeline._get_llm/_estimate_cost are imported inside the function body,
        # so patch the pipeline module directly.
        import pipeline
        monkeypatch.setattr(pipeline, "_get_llm", lambda *a, **k: FakeLLM())
        monkeypatch.setattr(pipeline, "_estimate_cost", lambda model, i, o: 0.01)

        result = scb.run_single_call_baseline("doc", "purpose", provider="anthropic", model="claude-opus-4-8")

        assert result["outputs"] == {"context": "c", "needs": "n", "curriculum": "cu", "content": "co", "critic": "cr"}
        assert result["node_tokens"]["single_call"] == 300
        assert result["total_tokens"] == 300
        assert result["total_cost_usd"] == 0.01
        assert result["errors"] == []

    def test_unparseable_response_flags_error(self, monkeypatch):
        class FakeLLM:
            def invoke(self, messages):
                return _FakeResponse("garbage, not json", {"input_tokens": 10, "output_tokens": 5})

        import pipeline
        monkeypatch.setattr(pipeline, "_get_llm", lambda *a, **k: FakeLLM())
        monkeypatch.setattr(pipeline, "_estimate_cost", lambda model, i, o: 0.001)

        result = scb.run_single_call_baseline("doc", "purpose")

        assert result["outputs"] == {"context": "", "needs": "", "curriculum": "", "content": "", "critic": ""}
        assert result["errors"] != []

    def test_uses_full_pipeline_equivalent_max_tokens_by_default(self, monkeypatch):
        captured = {}

        class FakeLLM:
            def invoke(self, messages):
                return _FakeResponse('{"context":"a","needs":"b","curriculum":"c","content":"d","critic":"e"}', {})

        import pipeline

        def fake_get_llm(provider, model, temperature, max_tokens=4000):
            captured["max_tokens"] = max_tokens
            return FakeLLM()

        monkeypatch.setattr(pipeline, "_get_llm", fake_get_llm)
        monkeypatch.setattr(pipeline, "_estimate_cost", lambda model, i, o: 0.0)

        scb.run_single_call_baseline("doc", "purpose")
        assert captured["max_tokens"] == scb.SINGLE_CALL_MAX_TOKENS
        assert scb.SINGLE_CALL_MAX_TOKENS == 15000
