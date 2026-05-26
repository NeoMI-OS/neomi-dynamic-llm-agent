"""
Pipeline node-ok az AI oktatási use case-hez.
Minden node egy-egy szerepet tölt be a curriculum tervezési folyamatban.

Use case: AI oktatási tanterv készítése menedzserek számára egy IT hardver vállalatnál.
"""
import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_core.messages import HumanMessage, SystemMessage
from pipeline_config import get_node_llm
from evaluator import evaluate_model

# Rendszer promptok magyarul
SYSTEM_PROMPTS = {
    "context_analyst": (
        "Te egy üzleti elemző vagy. Elemezd a megadott vállalati kontextust és készíts egy "
        "strukturált összefoglalót: iparág sajátosságai, célközönség profil, jelenlegi AI érettségi "
        "szint, főbb kihívások."
    ),
    "needs_analyzer": (
        "Te egy AI oktatási szakértő vagy. A vállalati kontextus alapján azonosítsd a menedzserek "
        "konkrét AI tudáshiányait és tanulási szükségleteit. Kategorizáld: stratégiai, operatív, "
        "technikai szintek szerint."
    ),
    "curriculum_designer": (
        "Te egy tanterv tervező vagy. Az azonosított szükségletek alapján tervezz strukturált AI "
        "oktatási tantervet. Adj meg modulokat, időkereteket, tanulási célokat."
    ),
    "content_writer": (
        "Te egy oktatási tartalomíró vagy. A tantervterv alapján írj részletes, engaging oktatási "
        "tartalmat az első modulhoz. Legyen gyakorlatias, példákkal teli."
    ),
    "critic": (
        "Te egy oktatási minőségbiztosítási szakértő vagy. Értékeld az elkészített AI oktatási "
        "anyagot és adj strukturált visszajelzést."
    ),
}


def _call_node(node_name: str, node_config: dict, human_message: str) -> dict:
    """
    Meghív egy pipeline node-ot és visszaadja az eredményt trace adatokkal.

    Args:
        node_name: A node neve (pl. "context_analyst")
        node_config: A node konfigurációja (model, provider, temperature)
        human_message: A felhasználói üzenet

    Returns:
        Dict az eredménnyel és trace metaadatokkal
    """
    system_prompt = SYSTEM_PROMPTS.get(node_name, "Te egy segítőkész AI asszisztens vagy.")
    model_name = node_config.get("model", "")
    provider = node_config.get("provider", "")

    start_time = time.time()
    error = None
    output = ""
    tokens = None

    try:
        llm = get_node_llm(node_config)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_message),
        ]
        response = llm.invoke(messages)
        output = response.content

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens = response.usage_metadata.get("total_tokens")

    except Exception as e:
        error = str(e)

    duration_ms = int((time.time() - start_time) * 1000)

    # Model evaluáció a meglévő evaluator modullal
    model_evaluation = evaluate_model(model_name)

    trace = {
        "node": node_name,
        "model_used": f"{provider}/{model_name}",
        "tokens": tokens,
        "duration_ms": duration_ms,
        "model_evaluation": model_evaluation,
    }
    if error:
        trace["error"] = error

    return {"output": output, "trace": trace, "error": error}


def run_context_analyst(state: dict, node_config: dict) -> dict:
    """
    Üzleti elemző: a vállalati kontextus strukturált elemzése.

    Args:
        state: A pipeline jelenlegi állapota
        node_config: A node LLM konfigurációja

    Returns:
        Frissített state dict
    """
    inp = state.get("input", {})
    company_name = inp.get("company_name", "")
    company_type = inp.get("company_type", "")
    target_audience = inp.get("target_audience", "")
    context = inp.get("context", "")
    goal = inp.get("goal", "")

    human_message = (
        f"Vállalat neve: {company_name}\n"
        f"Vállalat típusa: {company_type}\n"
        f"Célközönség: {target_audience}\n"
        f"Cél: {goal}\n"
        f"Kontextus: {context}\n\n"
        "Kérlek, készíts strukturált üzleti elemzést a fenti vállalati kontextusról!"
    )

    result = _call_node("context_analyst", node_config, human_message)
    state["context_analysis"] = result["output"]
    state["node_traces"].append(result["trace"])

    tokens = result["trace"].get("tokens") or 0
    state["total_tokens"] = state.get("total_tokens", 0) + tokens
    state["total_duration_ms"] = state.get("total_duration_ms", 0) + result["trace"]["duration_ms"]

    return state


def run_needs_analyzer(state: dict, node_config: dict) -> dict:
    """
    AI oktatási szakértő: a menedzserek tanulási szükségleteinek azonosítása.

    Args:
        state: A pipeline jelenlegi állapota
        node_config: A node LLM konfigurációja

    Returns:
        Frissített state dict
    """
    context_analysis = state.get("context_analysis", "")
    inp = state.get("input", {})

    human_message = (
        f"Vállalati kontextus elemzése:\n{context_analysis}\n\n"
        f"Célközönség: {inp.get('target_audience', '')}\n"
        f"Képzési cél: {inp.get('goal', '')}\n\n"
        "Kérlek, azonosítsd a menedzserek AI tudáshiányait és tanulási szükségleteit "
        "stratégiai, operatív és technikai szintek szerint!"
    )

    result = _call_node("needs_analyzer", node_config, human_message)
    state["needs_analysis"] = result["output"]
    state["node_traces"].append(result["trace"])

    tokens = result["trace"].get("tokens") or 0
    state["total_tokens"] = state.get("total_tokens", 0) + tokens
    state["total_duration_ms"] = state.get("total_duration_ms", 0) + result["trace"]["duration_ms"]

    return state


def run_curriculum_designer(state: dict, node_config: dict) -> dict:
    """
    Tanterv tervező: strukturált AI oktatási tanterv elkészítése.

    Args:
        state: A pipeline jelenlegi állapota
        node_config: A node LLM konfigurációja

    Returns:
        Frissített state dict
    """
    needs_analysis = state.get("needs_analysis", "")
    inp = state.get("input", {})

    human_message = (
        f"Azonosított tanulási szükségletek:\n{needs_analysis}\n\n"
        f"Vállalat: {inp.get('company_name', '')} ({inp.get('company_type', '')})\n"
        f"Célközönség: {inp.get('target_audience', '')}\n\n"
        "Kérlek, tervezz részletes AI oktatási tantervet modulokkal, időkeretekkel és tanulási célokkal!"
    )

    result = _call_node("curriculum_designer", node_config, human_message)
    state["curriculum_design"] = result["output"]
    state["node_traces"].append(result["trace"])

    tokens = result["trace"].get("tokens") or 0
    state["total_tokens"] = state.get("total_tokens", 0) + tokens
    state["total_duration_ms"] = state.get("total_duration_ms", 0) + result["trace"]["duration_ms"]

    return state


def run_content_writer(state: dict, node_config: dict) -> dict:
    """
    Oktatási tartalomíró: részletes tartalom az első modulhoz.

    Args:
        state: A pipeline jelenlegi állapota
        node_config: A node LLM konfigurációja

    Returns:
        Frissített state dict
    """
    curriculum_design = state.get("curriculum_design", "")
    inp = state.get("input", {})

    human_message = (
        f"Tantervterv:\n{curriculum_design}\n\n"
        f"Vállalat: {inp.get('company_name', '')} ({inp.get('company_type', '')})\n"
        f"Célközönség: {inp.get('target_audience', '')}\n\n"
        "Kérlek, írj részletes, engaging oktatási tartalmat a tanterv ELSŐ moduljához. "
        "Legyen gyakorlatias, valódi példákkal és feladatokkal!"
    )

    result = _call_node("content_writer", node_config, human_message)
    state["content"] = result["output"]
    state["node_traces"].append(result["trace"])

    tokens = result["trace"].get("tokens") or 0
    state["total_tokens"] = state.get("total_tokens", 0) + tokens
    state["total_duration_ms"] = state.get("total_duration_ms", 0) + result["trace"]["duration_ms"]

    return state


def run_critic(state: dict, node_config: dict) -> dict:
    """
    Oktatási minőségbiztosítási szakértő: az elkészített anyag értékelése.
    Strukturált JSON outputot ad vissza maturity_score-ral és kategóriákkal.

    Args:
        state: A pipeline jelenlegi állapota
        node_config: A node LLM konfigurációja

    Returns:
        Frissített state dict strukturált critique dict-tel
    """
    content = state.get("content", "")
    curriculum_design = state.get("curriculum_design", "")
    needs_analysis = state.get("needs_analysis", "")

    human_message = (
        f"Tantervterv összefoglalója:\n{curriculum_design[:500]}...\n\n"
        f"Azonosított szükségletek:\n{needs_analysis[:300]}...\n\n"
        f"Elkészített oktatási tartalom:\n{content}\n\n"
        "Kérlek, értékeld az oktatási anyagot és adj strukturált visszajelzést "
        "PONTOSAN az alábbi JSON formátumban (más szöveg nélkül):\n\n"
        "{\n"
        '  "maturity_score": <0-100 közötti egész szám>,\n'
        '  "categories": {\n'
        '    "relevance": {"score": <0-100>, "comment": "<magyar szöveg>"},\n'
        '    "depth": {"score": <0-100>, "comment": "<magyar szöveg>"},\n'
        '    "applicability": {"score": <0-100>, "comment": "<magyar szöveg>"}\n'
        "  },\n"
        '  "overall_feedback": "<részletes magyar visszajelzés>"\n'
        "}"
    )

    result = _call_node("critic", node_config, human_message)
    raw_output = result["output"]

    # JSON parse kísérlet
    critique = _parse_critique(raw_output)
    state["critique"] = critique
    state["node_traces"].append(result["trace"])

    tokens = result["trace"].get("tokens") or 0
    state["total_tokens"] = state.get("total_tokens", 0) + tokens
    state["total_duration_ms"] = state.get("total_duration_ms", 0) + result["trace"]["duration_ms"]

    return state


def _parse_critique(raw_output: str) -> dict:
    """
    Megpróbálja parse-olni a kritikus JSON outputját.
    Ha nem sikerül, visszaad egy alapértelmezett struktúrát.

    Args:
        raw_output: A LLM nyers szöveges válasza

    Returns:
        Strukturált critique dict
    """
    # JSON blokk keresése a válaszban
    text = raw_output.strip()

    # Markdown code block eltávolítása, ha van
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()

    # JSON keresése { } blokk alapján
    if not text.startswith("{"):
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            text = text[brace_start:brace_end + 1]

    try:
        parsed = json.loads(text)
        # Alapvető struktúra ellenőrzése
        if "maturity_score" not in parsed:
            parsed["maturity_score"] = 0
        if "categories" not in parsed:
            parsed["categories"] = {}
        if "overall_feedback" not in parsed:
            parsed["overall_feedback"] = raw_output
        return parsed
    except (json.JSONDecodeError, ValueError):
        # Fallback: nyers szöveg visszaadása strukturált formában
        return {
            "maturity_score": 0,
            "categories": {
                "relevance": {"score": 0, "comment": "JSON parse hiba"},
                "depth": {"score": 0, "comment": "JSON parse hiba"},
                "applicability": {"score": 0, "comment": "JSON parse hiba"},
            },
            "overall_feedback": raw_output,
            "parse_error": True,
        }
