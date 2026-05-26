"""
LangGraph Node-ok
"""
import os
import re
import sys

# Fix: hozzáadjuk a src mappát a path-hoz
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_core.messages import HumanMessage, SystemMessage
from config import (
    AgentState, ModelTier, MODEL_CONFIG,
    INTENT_KEYWORDS, INTENT_TO_TIER, COMPLEXITY_THRESHOLDS
)
from evaluator import evaluate_model


def detect_intent(state: AgentState) -> AgentState:
    """Felismeri a user szándékát kulcsszavak alapján."""
    query_lower = state["query"].lower()
    detected = "general"

    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query_lower:
                detected = intent
                break
        if detected != "general":
            break

    state["detected_intent"] = detected
    return state


def calculate_complexity(state: AgentState) -> AgentState:
    """Kiszámolja a kérés komplexitását 0-1 skálán."""
    query = state["query"]
    history = state.get("conversation_history", [])

    score = 0.0

    length = len(query)
    if length > 500:
        score += 0.3
    elif length > 200:
        score += 0.2
    elif length > 50:
        score += 0.1

    sentences = len(re.split(r'[.!?]', query))
    if sentences > 5:
        score += 0.2
    elif sentences > 2:
        score += 0.1

    code_indicators = ['```', 'def ', 'function', 'class ', 'import ', '{', '}']
    if any(ind in query for ind in code_indicators):
        score += 0.2

    if len(history) > 5:
        score += 0.2
    elif len(history) > 2:
        score += 0.1

    complex_words = ['összehasonlít', 'elemez', 'compare', 'analyze', 'evaluate']
    if any(word in query.lower() for word in complex_words):
        score += 0.1

    state["complexity_score"] = min(score, 1.0)
    return state


def select_model_tier(state: AgentState) -> AgentState:
    """Kiválasztja a megfelelő modell tier-t."""
    complexity = state["complexity_score"]
    intent = state["detected_intent"]

    downgradeable_intents = {"simple_qa", "general"}

    if complexity >= COMPLEXITY_THRESHOLDS["upgrade_to_powerful"]:
        tier = ModelTier.POWERFUL
        reason = f"Magas komplexitás ({complexity:.2f}) -> erős modell"
    elif complexity <= COMPLEXITY_THRESHOLDS["downgrade_to_fast"] and intent in downgradeable_intents:
        tier = ModelTier.FAST
        reason = f"Alacsony komplexitás ({complexity:.2f}) -> gyors modell"
    else:
        tier = INTENT_TO_TIER.get(intent, ModelTier.BALANCED)
        reason = f"Intent: {intent} -> {tier.value}"

    state["selected_tier"] = tier.value
    state["routing_reason"] = reason
    return state


def get_llm_for_tier(tier: ModelTier):
    """Visszaadja a megfelelő LLM példányt."""
    config = MODEL_CONFIG[tier]
    provider = config["provider"]
    model = config["model"]
    temperature = config["temperature"]

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY")
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    else:
        raise ValueError(f"Ismeretlen provider: {provider}")


def call_llm(state: AgentState) -> AgentState:
    """Meghívja a kiválasztott LLM-et."""
    tier = ModelTier(state["selected_tier"])
    config = MODEL_CONFIG[tier]

    llm = get_llm_for_tier(tier)

    system_prompt = f"""Te egy segítőkész AI asszisztens vagy.
Jelenlegi mód: {config['description']}
Válaszolj magyarul, ha a kérdés magyar, angolul, ha angol."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["query"])
    ]

    response = llm.invoke(messages)

    state["response"] = response.content
    state["model_used"] = f"{config['provider']}/{config['model']}"

    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        state["tokens_used"] = response.usage_metadata.get('total_tokens')

    return state


def create_tier_node(tier: ModelTier):
    """Létrehoz egy tier-specifikus node-ot."""
    def tier_node(state: AgentState) -> AgentState:
        state["selected_tier"] = tier.value
        return call_llm(state)

    tier_node.__name__ = f"call_{tier.value}_model"
    return tier_node


call_fast_model = create_tier_node(ModelTier.FAST)
call_balanced_model = create_tier_node(ModelTier.BALANCED)
call_powerful_model = create_tier_node(ModelTier.POWERFUL)
call_creative_model = create_tier_node(ModelTier.CREATIVE)


def run_model_evaluation(state: AgentState) -> AgentState:
    """Lekéri az Artificial Analysis értékelést a használt modellről."""
    model_name = state.get("model_used", "")
    # model_used formátuma: "provider/model-name" — csak a modell neve kell
    if "/" in model_name:
        model_name = model_name.split("/", 1)[1]

    state["model_evaluation"] = evaluate_model(model_name)
    return state
