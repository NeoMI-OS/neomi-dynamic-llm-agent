"""
Egylépéses ("single-call") baseline (Phase 2): egyetlen LLM-hívással próbálja
megoldani a TELJES feladatot, amit az 5-node pipeline egymás utáni lépésekben
végez el (kontextus-elemzés → szükséglet-elemzés → tananyag-tervezés →
tartalomírás → kritikai értékelés).

Ez a fusion_gain metrika referenciapontja: mennyivel jobb (vagy rosszabb) a
multi-agent pipeline egy ugyanolyan képességű modell egylépéses megoldásánál,
azonos teljes token-kerettel (a pipeline 5 node-jának max_tokens összegével,
hogy a kettő ne csak a modell erejében, hanem a "gondolkodási térben" is
összemérhető legyen).
"""
import os
import re
import json
import time

from langchain_core.messages import HumanMessage, SystemMessage

# Ugyanaz az össz-token-keret, mint az 5 node pipeline.max_tokens összege --
# hogy a fusion_gain az ARCHITEKTÚRA (több lépés, specializált promptok)
# hatását mérje, ne azt, hogy az egyik oldal egyszerűen kevesebb helyet kapott.
SINGLE_CALL_MAX_TOKENS = 1500 + 2000 + 3000 + 6000 + 2500  # 15000

_SYSTEM_PROMPT = (
    "Te egy AI oktatási rendszer vagy, amely EGYETLEN válaszban végzi el mind "
    "az öt lépést, amit egy specializált 5-ügynökös rendszer külön-külön "
    "végezne el: (1) kontextus-elemzés — cél, közönség, érettségi szint, "
    "korlátok; (2) szükséglet-elemzés — tudáshézagok és tanulási célok; "
    "(3) tananyag-tervezés — modulok, célkitűzések, szekciók; (4) tartalomírás "
    "— részletes, teljes oktatási anyag; (5) kritikai értékelés — strukturált "
    "rubrika szerinti önértékelés.\n\n"
    "Add vissza JSON formátumban, PONTOSAN ezekkel a kulcsokkal:\n"
    '{"context": "...", "needs": "...", "curriculum": "...", "content": "...", "critic": "..."}\n'
    "Minden mező tartalma ugyanolyan részletes és teljes legyen, mintha egy "
    "külön, specializált ügynök készítette volna."
)


def _extract_json(text: str) -> dict:
    match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
    try:
        return json.loads(text)
    except Exception:
        return {}


def run_single_call_baseline(input_document: str, purpose: str,
                              provider: str = "anthropic", model: str = "claude-opus-4-8",
                              temperature: float = 0.5,
                              max_tokens: int = SINGLE_CALL_MAX_TOKENS) -> dict:
    """
    Visszaad egy, a normál pipeline run_pipeline()-jével AZONOS alakú dict-et
    (outputs.context/needs/curriculum/content/critic, node_timings, node_tokens,
    node_costs_usd, total_*), hogy ugyanazzal az evaluate_run()-nal kiértékelhető
    legyen, mint egy rendes 5-node futás. A node_timings/node_tokens/node_costs_usd
    egyetlen "single_call" kulcs alatt szerepel (nincs 5 külön node).
    """
    from pipeline import _get_llm, _estimate_cost

    llm = _get_llm(provider, model, temperature, max_tokens)

    user_prompt = f"Dokumentum:\n{input_document}\n\nCél:\n{purpose}"

    t0 = time.time()
    response = llm.invoke([SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_prompt)])
    latency = time.time() - t0

    parsed = _extract_json(response.content)

    usage = getattr(response, "usage_metadata", None) or {}
    in_tok = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0) or 0
    out_tok = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0) or 0
    total_tok = in_tok + out_tok or len(response.content.split()) * 2
    cost = _estimate_cost(model, in_tok, out_tok)

    outputs = {
        "context": parsed.get("context", "") or "",
        "needs": parsed.get("needs", "") or "",
        "curriculum": parsed.get("curriculum", "") or "",
        "content": parsed.get("content", "") or "",
        "critic": parsed.get("critic", "") or "",
    }

    return {
        "outputs": outputs,
        "node_timings": {"single_call": round(latency, 3)},
        "node_tokens": {"single_call": total_tok},
        "node_costs_usd": {"single_call": round(cost, 6)},
        "errors": [] if parsed else ["single_call_baseline: JSON parse failed, empty outputs"],
        "total_tokens": total_tok,
        "total_cost_usd": round(cost, 6),
        "total_latency_seconds": round(latency, 2),
    }
