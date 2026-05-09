"""
Tests for intent detection, complexity scoring, and tier selection logic.
No LLM calls are made — all tests are pure unit tests.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from nodes import detect_intent, calculate_complexity, select_model_tier
from config import ModelTier, AgentState


def make_state(query: str, history: list = None) -> AgentState:
    return {
        "query": query,
        "conversation_history": history or [],
        "detected_intent": "",
        "complexity_score": 0.0,
        "selected_tier": "",
        "routing_reason": "",
        "response": "",
        "model_used": "",
        "tokens_used": None,
    }


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

class TestDetectIntent:
    def test_simple_qa_english(self):
        state = detect_intent(make_state("What is Python?"))
        assert state["detected_intent"] == "simple_qa"

    def test_simple_qa_hungarian(self):
        state = detect_intent(make_state("Mi a különbség?"))
        assert state["detected_intent"] == "simple_qa"

    def test_creative_english(self):
        state = detect_intent(make_state("Write a poem about the ocean"))
        assert state["detected_intent"] == "creative"

    def test_creative_hungarian(self):
        state = detect_intent(make_state("Írj egy verset a tengerről"))
        assert state["detected_intent"] == "creative"

    def test_analysis_english(self):
        state = detect_intent(make_state("Analyze the pros and cons of microservices"))
        assert state["detected_intent"] == "analysis"

    def test_analysis_hungarian(self):
        state = detect_intent(make_state("Elemezd a Python és Rust közötti különbségeket"))
        assert state["detected_intent"] == "analysis"

    def test_coding(self):
        state = detect_intent(make_state("Fix this bug in my code"))
        assert state["detected_intent"] == "coding"

    def test_coding_hungarian(self):
        # "írj" triggers creative before "függvény" triggers coding due to keyword order;
        # use a query without a creative verb to test coding detection unambiguously
        state = detect_intent(make_state("Python függvényt kell debuggolni"))
        assert state["detected_intent"] == "coding"

    def test_translation(self):
        state = detect_intent(make_state("Translate this to Hungarian"))
        assert state["detected_intent"] == "translation"

    def test_translation_hungarian(self):
        state = detect_intent(make_state("Fordítsd le ezt angolul"))
        assert state["detected_intent"] == "translation"

    def test_general_fallback(self):
        state = detect_intent(make_state("Tell me something interesting"))
        assert state["detected_intent"] == "general"


# ---------------------------------------------------------------------------
# Complexity scoring
# ---------------------------------------------------------------------------

class TestCalculateComplexity:
    def test_short_query_low_complexity(self):
        state = calculate_complexity(make_state("Hi"))
        assert state["complexity_score"] == 0.0

    def test_medium_length_adds_score(self):
        query = "a" * 51
        state = calculate_complexity(make_state(query))
        assert state["complexity_score"] >= 0.1

    def test_long_query_higher_score(self):
        query = "a" * 201
        state = calculate_complexity(make_state(query))
        assert state["complexity_score"] >= 0.2

    def test_very_long_query(self):
        query = "a" * 501
        state = calculate_complexity(make_state(query))
        assert state["complexity_score"] >= 0.3

    def test_code_indicators_add_score(self):
        state = calculate_complexity(make_state("```python\ndef hello(): pass\n```"))
        assert state["complexity_score"] >= 0.2

    def test_many_sentences_add_score(self):
        query = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five. Sentence six."
        state = calculate_complexity(make_state(query))
        assert state["complexity_score"] >= 0.2

    def test_long_history_adds_score(self):
        history = ["msg"] * 6
        state = calculate_complexity(make_state("Short query", history=history))
        assert state["complexity_score"] >= 0.2

    def test_complex_vocabulary_adds_score(self):
        state = calculate_complexity(make_state("Please analyze and compare these options"))
        assert state["complexity_score"] >= 0.1

    def test_score_capped_at_one(self):
        long_query = "analyze compare " * 100 + "```def foo(): pass``` " * 10
        history = ["msg"] * 10
        state = calculate_complexity(make_state(long_query, history=history))
        assert state["complexity_score"] <= 1.0


# ---------------------------------------------------------------------------
# Tier selection
# ---------------------------------------------------------------------------

class TestSelectModelTier:
    def _run(self, query: str, history: list = None) -> AgentState:
        state = make_state(query, history)
        state = detect_intent(state)
        state = calculate_complexity(state)
        state = select_model_tier(state)
        return state

    # Complexity-driven overrides
    def test_high_complexity_forces_powerful(self):
        long_query = "a" * 501 + ". " * 6 + "analyze compare "
        state = self._run(long_query, history=["msg"] * 6)
        assert state["selected_tier"] == ModelTier.POWERFUL.value

    def test_low_complexity_forces_fast_for_general_intent(self):
        state = self._run("Hi")
        assert state["selected_tier"] == ModelTier.FAST.value

    def test_low_complexity_does_not_override_creative_intent(self):
        # Short creative query must not be downgraded to FAST
        state = self._run("Write a poem about the ocean")
        assert state["selected_tier"] == ModelTier.CREATIVE.value

    def test_low_complexity_does_not_override_analysis_intent(self):
        # Short analysis query must not be downgraded to FAST
        state = self._run("Analyze the differences between Python and Rust")
        assert state["selected_tier"] == ModelTier.POWERFUL.value

    def test_low_complexity_does_not_override_coding_intent(self):
        state = self._run("Fix this bug in my code")
        assert state["selected_tier"] == ModelTier.POWERFUL.value

    # Intent-driven selection (mid-range complexity)
    def test_creative_intent_selects_creative_tier(self):
        state = make_state("Write a short poem")
        state = detect_intent(state)
        state["complexity_score"] = 0.4  # mid-range, no override
        state = select_model_tier(state)
        assert state["selected_tier"] == ModelTier.CREATIVE.value

    def test_analysis_intent_selects_powerful_tier(self):
        state = make_state("Analyze this situation")
        state = detect_intent(state)
        state["complexity_score"] = 0.4
        state = select_model_tier(state)
        assert state["selected_tier"] == ModelTier.POWERFUL.value

    def test_coding_intent_selects_powerful_tier(self):
        state = make_state("Fix this bug in my code")
        state = detect_intent(state)
        state["complexity_score"] = 0.4
        state = select_model_tier(state)
        assert state["selected_tier"] == ModelTier.POWERFUL.value

    def test_translation_intent_selects_balanced_tier(self):
        state = make_state("Translate this text")
        state = detect_intent(state)
        state["complexity_score"] = 0.4
        state = select_model_tier(state)
        assert state["selected_tier"] == ModelTier.BALANCED.value

    def test_general_intent_selects_balanced_tier(self):
        state = make_state("Tell me something interesting")
        state = detect_intent(state)
        state["complexity_score"] = 0.4
        state = select_model_tier(state)
        assert state["selected_tier"] == ModelTier.BALANCED.value

    def test_simple_qa_intent_selects_fast_tier(self):
        state = make_state("What is the capital of France?")
        state = detect_intent(state)
        state["complexity_score"] = 0.4  # mid-range, intent wins
        state = select_model_tier(state)
        assert state["selected_tier"] == ModelTier.FAST.value

    # Boundary conditions
    def test_complexity_exactly_at_upgrade_threshold(self):
        state = make_state("general query")
        state = detect_intent(state)
        state["complexity_score"] = 0.7
        state = select_model_tier(state)
        assert state["selected_tier"] == ModelTier.POWERFUL.value

    def test_complexity_exactly_at_downgrade_threshold(self):
        state = make_state("general query")
        state = detect_intent(state)
        state["complexity_score"] = 0.2
        state = select_model_tier(state)
        assert state["selected_tier"] == ModelTier.FAST.value

    def test_routing_reason_is_set(self):
        state = self._run("Hi")
        assert state["routing_reason"] != ""
