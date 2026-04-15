"""
Dinamikus LLM Router Agent - LangGraph implementáció
"""
from typing import Literal
from langgraph.graph import StateGraph, END

import os
import sys

# Fix: hozzáadjuk a src mappát a path-hoz
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import AgentState, ModelTier
from nodes import (
    detect_intent,
    calculate_complexity,
    select_model_tier,
    call_fast_model,
    call_balanced_model,
    call_powerful_model,
    call_creative_model
)


def route_to_model(state: AgentState) -> Literal["fast", "balanced", "powerful", "creative"]:
    """Router függvény a conditional edge-hez."""
    return state["selected_tier"]


def build_agent_graph() -> StateGraph:
    """Felépíti a LangGraph workflow-t."""
    workflow = StateGraph(AgentState)

    workflow.add_node("detect_intent", detect_intent)
    workflow.add_node("calculate_complexity", calculate_complexity)
    workflow.add_node("select_model_tier", select_model_tier)
    workflow.add_node("fast", call_fast_model)
    workflow.add_node("balanced", call_balanced_model)
    workflow.add_node("powerful", call_powerful_model)
    workflow.add_node("creative", call_creative_model)

    workflow.set_entry_point("detect_intent")
    workflow.add_edge("detect_intent", "calculate_complexity")
    workflow.add_edge("calculate_complexity", "select_model_tier")

    workflow.add_conditional_edges(
        "select_model_tier",
        route_to_model,
        {
            "fast": "fast",
            "balanced": "balanced",
            "powerful": "powerful",
            "creative": "creative"
        }
    )

    workflow.add_edge("fast", END)
    workflow.add_edge("balanced", END)
    workflow.add_edge("powerful", END)
    workflow.add_edge("creative", END)

    return workflow


def create_agent():
    """Létrehozza és compile-olja az agent-et."""
    workflow = build_agent_graph()
    return workflow.compile()


def run_agent(query: str, conversation_history: list = None) -> dict:
    """Futtatja az agent-et egy query-vel."""
    agent = create_agent()

    initial_state: AgentState = {
        "query": query,
        "conversation_history": conversation_history or [],
        "detected_intent": "",
        "complexity_score": 0.0,
        "selected_tier": "",
        "routing_reason": "",
        "response": "",
        "model_used": "",
        "tokens_used": None
    }

    result = agent.invoke(initial_state)
    return result


# CLI teszt - közvetlenül futtatható
if __name__ == "__main__":
    import os
    import sys
    
    # Add parent directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

    test_queries = [
        "Mi a főváros Magyarországon?",
        "Írj egy rövid verset a tavaszról",
        "Elemezd a Python és Rust közötti különbségeket",
        "Fordítsd le angolra: Szia, hogy vagy?",
    ]

    print("=" * 60)
    print("DINAMIKUS LLM ROUTER AGENT - TESZT")
    print("=" * 60)

    for query in test_queries:
        print(f"\n📝 Query: {query[:50]}...")
        print("-" * 40)

        try:
            result = run_agent(query)
            print(f"🎯 Intent: {result['detected_intent']}")
            print(f"📊 Komplexitás: {result['complexity_score']:.2f}")
            print(f"🤖 Modell: {result['model_used']}")
            print(f"💡 Routing: {result['routing_reason']}")
            print(f"💬 Válasz: {result['response'][:100]}...")
        except Exception as e:
            print(f"❌ Hiba: {e}")

        print()
