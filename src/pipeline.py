"""
NeoMI Core 5-node pipeline: Context Analyst → Needs Analyzer →
Curriculum Designer → Content Writer → Critic
Minden node modellje futás közben konfigurálható.
"""
import os
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import TypedDict, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END


class PipelineState(TypedDict):
    input_document: str
    purpose: str
    experiment_id: str
    node_configs: dict          # {"context_analyst": {"provider": ..., "model": ...}, ...}

    context_output: str
    needs_output: str
    curriculum_output: str
    content_output: str
    critic_output: str

    node_timings: dict          # {"context_analyst": 1.23, ...}
    node_tokens: dict           # {"context_analyst": 450, ...}
    node_costs_usd: dict        # {"context_analyst": 0.0012, ...}
    errors: list


# Token árak USD / 1M token (input + output átlag, 2026-06-28)
_PRICING = {
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash":      {"input": 0.30, "output": 1.00},
    "gemini-2.5-pro":        {"input": 1.25, "output": 10.00},
    "gpt-4o-mini":           {"input": 0.15, "output": 0.60},
    "gpt-4o":                {"input": 2.50, "output": 10.00},
    "claude-haiku-4-5":      {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6":     {"input": 3.00, "output": 15.00},
    "claude-opus-4-8":       {"input": 15.00, "output": 75.00},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = _PRICING.get(model, {"input": 5.0, "output": 15.0})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


# Ezek a modellek elutasítják az explicit `temperature` paramétert (400-as hibát adnak)
_NO_TEMPERATURE_MODELS = {"claude-opus-4-8"}

# Node-onkénti alapértelmezett kimeneti token-limit — enélkül egyes modellek
# (jellemzően a content_writer node-on) 60-160 ezer karakteres, kontrollálatlan
# kimenetet is generáltak, amit sem a Judge (szűk truncation miatt), sem
# gyakorlatilag senki nem tudott érdemben átolvasni/kiértékelni.
_DEFAULT_MAX_TOKENS = {
    "context_analyst":     1500,
    "needs_analyzer":      2000,
    "curriculum_designer": 3000,
    "content_writer":      6000,
    "critic":              2500,
}


def _get_llm(provider: str, model: str, temperature: float, max_tokens: int = 4000):
    temp_kwargs = {} if model in _NO_TEMPERATURE_MODELS else {"temperature": temperature}
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model, **temp_kwargs, max_output_tokens=max_tokens,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model, **temp_kwargs, max_tokens=max_tokens,
            api_key=os.getenv("OPENAI_API_KEY")
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model, **temp_kwargs, max_tokens=max_tokens,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    raise ValueError(f"Ismeretlen provider: {provider}")


def _call_node(state: PipelineState, node_name: str, system_prompt: str, user_prompt: str) -> tuple[str, float, int, float]:
    """Meghív egy LLM-et, visszaadja: (kimenet, latencia_s, token_szám, cost_usd)."""
    cfg = state["node_configs"].get(node_name, {
        "provider": "openai", "model": "gpt-4o-mini", "temperature": 0.5
    })
    max_tokens = cfg.get("max_tokens", _DEFAULT_MAX_TOKENS.get(node_name, 4000))
    llm = _get_llm(cfg["provider"], cfg["model"], cfg.get("temperature", 0.5), max_tokens)

    t0 = time.time()
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    latency = time.time() - t0

    usage = getattr(response, "usage_metadata", None) or {}
    in_tok = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0) or 0
    out_tok = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0) or 0
    total_tok = in_tok + out_tok or len(response.content.split()) * 2

    cost = _estimate_cost(cfg["model"], in_tok, out_tok)
    return response.content, latency, total_tok, cost


def _update_metrics(state: PipelineState, node: str, latency: float, tokens: int, cost: float) -> PipelineState:
    state["node_timings"] = {**state.get("node_timings", {}), node: round(latency, 3)}
    state["node_tokens"]  = {**state.get("node_tokens", {}),  node: tokens}
    state["node_costs_usd"] = {**state.get("node_costs_usd", {}), node: round(cost, 6)}
    return state


# ── Node függvények ─────────────────────────────────────────────────────────

def node_context_analyst(state: PipelineState) -> PipelineState:
    system = (
        "Te egy AI oktatási rendszer Kontextus Elemzője vagy. "
        "A feladatod: a kapott dokumentumból és célból kinyerni a következő négy mezőt, "
        "JSON formátumban:\n"
        '{"goal": "...", "audience": "...", "maturity_level": "kezdő|haladó|szakértő", '
        '"constraints": ["..."]}'
    )
    user = f"Dokumentum:\n{state['input_document']}\n\nCél:\n{state['purpose']}"
    try:
        output, lat, tok, cost = _call_node(state, "context_analyst", system, user)
        state["context_output"] = output
        state = _update_metrics(state, "context_analyst", lat, tok, cost)
    except Exception as e:
        state["context_output"] = "{}"
        state.setdefault("errors", []).append(f"context_analyst: {e}")
    return state


def node_needs_analyzer(state: PipelineState) -> PipelineState:
    system = (
        "Te egy AI oktatási rendszer Szükséglet Elemzője vagy. "
        "A kontextus elemzés alapján azonosítsd a tudáshézagokat és tanulási célokat. "
        "Adj vissza JSON listát: "
        '[{"gap": "...", "learning_objective": "...", "priority": "magas|közepes|alacsony"}]'
    )
    user = f"Kontextus:\n{state['context_output']}\n\nEredeti dokumentum:\n{state['input_document']}"
    try:
        output, lat, tok, cost = _call_node(state, "needs_analyzer", system, user)
        state["needs_output"] = output
        state = _update_metrics(state, "needs_analyzer", lat, tok, cost)
    except Exception as e:
        state["needs_output"] = "[]"
        state.setdefault("errors", []).append(f"needs_analyzer: {e}")
    return state


def node_curriculum_designer(state: PipelineState) -> PipelineState:
    system = (
        "Te egy AI oktatási rendszer Tananyag Tervezője vagy. "
        "A kontextus és szükségletek alapján tervezd meg a tananyag struktúráját. "
        "Adj vissza JSON-t: "
        '{"modules": [{"title": "...", "objectives": [...], "duration_min": 30, '
        '"sections": [{"title": "...", "content_type": "elmélet|gyakorlat|összefoglalás"}]}]}'
    )
    user = (
        f"Kontextus:\n{state['context_output']}\n\n"
        f"Szükségletek:\n{state['needs_output']}"
    )
    try:
        output, lat, tok, cost = _call_node(state, "curriculum_designer", system, user)
        state["curriculum_output"] = output
        state = _update_metrics(state, "curriculum_designer", lat, tok, cost)
    except Exception as e:
        state["curriculum_output"] = "{}"
        state.setdefault("errors", []).append(f"curriculum_designer: {e}")
    return state


def node_content_writer(state: PipelineState) -> PipelineState:
    system = (
        "Te egy AI oktatási rendszer Tartalom Írója vagy. "
        "A tananyag struktúra alapján írj részletes, lebilincselő oktatási anyagot. "
        "A tartalom legyen koherens, a célközönséghez igazított, és könnyen érthető. "
        "Minden modulhoz írj teljes tartalmat, példákkal és összefoglalókkal."
    )
    user = (
        f"Kontextus:\n{state['context_output']}\n\n"
        f"Tananyag struktúra:\n{state['curriculum_output']}\n\n"
        f"Szükségletek:\n{state['needs_output']}"
    )
    try:
        output, lat, tok, cost = _call_node(state, "content_writer", system, user)
        state["content_output"] = output
        state = _update_metrics(state, "content_writer", lat, tok, cost)
    except Exception as e:
        state["content_output"] = ""
        state.setdefault("errors", []).append(f"content_writer: {e}")
    return state


def node_critic(state: PipelineState) -> PipelineState:
    system = (
        "Te egy AI oktatási rendszer Kritikusa vagy. "
        "Értékeld az elkészült tananyagot egy strukturált rubrika alapján. "
        "Adj vissza JSON-t:\n"
        '{"scores": {"completeness": 1-10, "coherence": 1-10, "usability": 1-10, '
        '"maturity_alignment": 1-10, "risk_coverage": 1-10}, '
        '"issues": [{"severity": "kritikus|közepes|kisebb", "description": "...", '
        '"suggestion": "..."}], '
        '"overall_assessment": "...", "recommendation": "elfogad|revízió|elutasít"}'
    )
    user = (
        f"Kontextus:\n{state['context_output']}\n\n"
        f"Szükségletek:\n{state['needs_output']}\n\n"
        f"Tananyag struktúra:\n{state['curriculum_output']}\n\n"
        f"Elkészült tartalom:\n{state['content_output']}"
    )
    try:
        output, lat, tok, cost = _call_node(state, "critic", system, user)
        state["critic_output"] = output
        state = _update_metrics(state, "critic", lat, tok, cost)
    except Exception as e:
        state["critic_output"] = "{}"
        state.setdefault("errors", []).append(f"critic: {e}")
    return state


def build_pipeline() -> StateGraph:
    workflow = StateGraph(PipelineState)
    workflow.add_node("context_analyst",    node_context_analyst)
    workflow.add_node("needs_analyzer",     node_needs_analyzer)
    workflow.add_node("curriculum_designer", node_curriculum_designer)
    workflow.add_node("content_writer",     node_content_writer)
    workflow.add_node("critic",             node_critic)

    workflow.set_entry_point("context_analyst")
    workflow.add_edge("context_analyst",    "needs_analyzer")
    workflow.add_edge("needs_analyzer",     "curriculum_designer")
    workflow.add_edge("curriculum_designer", "content_writer")
    workflow.add_edge("content_writer",     "critic")
    workflow.add_edge("critic",             END)
    return workflow


def run_pipeline(input_document: str, purpose: str,
                 node_configs: dict, experiment_id: str = "manual") -> dict:
    """
    Futtatja a pipeline-t és visszaadja az összes node kimenetét és metrikáját.
    node_configs: {"context_analyst": {"provider": "openai", "model": "gpt-4o", "temperature": 0.2}, ...}
    """
    compiled = build_pipeline().compile()

    initial: PipelineState = {
        "input_document": input_document,
        "purpose": purpose,
        "experiment_id": experiment_id,
        "node_configs": node_configs,
        "context_output": "",
        "needs_output": "",
        "curriculum_output": "",
        "content_output": "",
        "critic_output": "",
        "node_timings": {},
        "node_tokens": {},
        "node_costs_usd": {},
        "errors": [],
    }

    result = compiled.invoke(initial)

    total_tokens = sum(result["node_tokens"].values())
    total_cost   = sum(result["node_costs_usd"].values())
    total_latency = sum(result["node_timings"].values())

    return {
        **result,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "total_latency_seconds": round(total_latency, 2),
    }
