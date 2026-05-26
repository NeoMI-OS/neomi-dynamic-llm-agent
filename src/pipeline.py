"""
LangGraph-alapú multi-agent pipeline az AI oktatási use case-hez.
Öt node dolgozik sorban: context_analyst → needs_analyzer → curriculum_designer
→ content_writer → critic.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from pipeline_config import load_experiment
from pipeline_nodes import (
    run_context_analyst,
    run_needs_analyzer,
    run_curriculum_designer,
    run_content_writer,
    run_critic,
)


class PipelineState(TypedDict):
    # Bemenet
    experiment_id: str
    input: dict  # company_name, company_type, target_audience, goal, context

    # Node kimenetek
    context_analysis: str
    needs_analysis: str
    curriculum_design: str
    content: str
    critique: dict  # structured: maturity_score, categories, overall_feedback

    # Metaadatok
    node_traces: list  # [{node, model_used, tokens, duration_ms, model_evaluation}]
    total_tokens: int
    total_duration_ms: int

    # Kísérletkonfiguráció (belső használatra)
    _experiment_config: dict


def _make_node(node_fn, node_name: str):
    """
    Létrehoz egy LangGraph-kompatibilis node függvényt, amely a kísérlet
    konfigurációjából kiolvassa a saját node konfigurációját, majd meghívja
    a megfelelő pipeline_nodes függvényt.
    """
    def node(state: PipelineState) -> PipelineState:
        exp_config = state.get("_experiment_config", {})
        node_config = exp_config.get("nodes", {}).get(node_name, {})
        return node_fn(state, node_config)

    node.__name__ = f"pipeline_{node_name}"
    return node


def build_pipeline_graph() -> StateGraph:
    """Felépíti a LangGraph pipeline workflow-t."""
    workflow = StateGraph(PipelineState)

    workflow.add_node("context_analyst", _make_node(run_context_analyst, "context_analyst"))
    workflow.add_node("needs_analyzer", _make_node(run_needs_analyzer, "needs_analyzer"))
    workflow.add_node("curriculum_designer", _make_node(run_curriculum_designer, "curriculum_designer"))
    workflow.add_node("content_writer", _make_node(run_content_writer, "content_writer"))
    workflow.add_node("critic", _make_node(run_critic, "critic"))

    workflow.set_entry_point("context_analyst")
    workflow.add_edge("context_analyst", "needs_analyzer")
    workflow.add_edge("needs_analyzer", "curriculum_designer")
    workflow.add_edge("curriculum_designer", "content_writer")
    workflow.add_edge("content_writer", "critic")
    workflow.add_edge("critic", END)

    return workflow


def run_pipeline(experiment_id: str, input_data: dict) -> dict:
    """
    Futtatja a teljes multi-agent pipeline-t a megadott kísérlet konfigurációval.

    Args:
        experiment_id: A kísérlet azonosítója (pl. "exp-001")
        input_data: A bemenet dict-je (company_name, company_type, target_audience, goal, context)

    Returns:
        A pipeline teljes eredménye: node_traces, critique és közbülső kimenetek
    """
    exp_config = load_experiment(experiment_id)

    graph = build_pipeline_graph()
    app = graph.compile()

    initial_state: PipelineState = {
        "experiment_id": experiment_id,
        "input": input_data,
        "context_analysis": "",
        "needs_analysis": "",
        "curriculum_design": "",
        "content": "",
        "critique": {},
        "node_traces": [],
        "total_tokens": 0,
        "total_duration_ms": 0,
        "_experiment_config": exp_config,
    }

    result = app.invoke(initial_state)

    # Belső konfig eltávolítása a kimenetből
    result.pop("_experiment_config", None)

    return result
