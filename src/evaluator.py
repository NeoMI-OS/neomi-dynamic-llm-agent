"""
Artificial Analysis alapú modell értékelő modul.

Service Readiness Score (SRS) számítás három kategória alapján:
  Knowledge Score  = (MMLU-Pro + GPQA) / 2
  Reasoning Score  = (MATH-500 + AIME + LiveCodeBench) / 3
  Usability Score  = AA Intelligence Index / 100  (IFEval helyettesítő)
  SRS = w_knowledge * K + w_reasoning * R + w_usability * U
"""
import os
import time
import threading
import requests

# Model name → Artificial Analysis slug mapping
MODEL_SLUG_MAP = {
    "gemini-2.5-flash-lite": "gemini-2-5-flash-lite",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o": "gpt-4o",
    "claude-sonnet-4-6": "claude-sonnet-4-5",
}

AA_API_URL = "https://api.artificialanalysis.ai/data/llms/models"
CACHE_TTL_SECONDS = 3600  # 1 óra

# SRS súlyok – chat/agent szolgáltatásnál a Usability a legfontosabb
SRS_WEIGHTS = {
    "knowledge": 0.25,
    "reasoning": 0.35,
    "usability": 0.40,
}

_cache_lock = threading.Lock()
_cache = {"data": None, "fetched_at": 0}


def _fetch_aa_models() -> list:
    """Lekéri az AA API-ból a modellek listáját, cache-eléssel."""
    with _cache_lock:
        now = time.time()
        if _cache["data"] and (now - _cache["fetched_at"]) < CACHE_TTL_SECONDS:
            return _cache["data"]

        api_key = os.getenv("ARTIFICIAL_ANALYSIS_API_KEY")
        if not api_key:
            return []

        try:
            resp = requests.get(
                AA_API_URL,
                headers={"x-api-key": api_key},
                timeout=10
            )
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                _cache["data"] = models
                _cache["fetched_at"] = now
                return models
        except Exception:
            pass

        return []


def _find_model(models: list, model_name: str) -> dict | None:
    """Megkeresi a modellt az AA listában slug mapping alapján."""
    target_slug = MODEL_SLUG_MAP.get(model_name, model_name)
    for m in models:
        if m.get("slug") == target_slug:
            return m
        if model_name.lower() in (m.get("name") or "").lower():
            return m
    return None


def _avg(*values) -> float | None:
    """Átlagot számít, None értékeket kihagyva. Ha nincs adat, None-t ad vissza."""
    valid = [v for v in values if v is not None]
    return round(sum(valid) / len(valid), 4) if valid else None


def _compute_srs(evaluations: dict) -> dict:
    """
    Service Readiness Score (SRS) számítás.

    Benchmark mezők (0–1 skála az AA API-ban):
      Knowledge : mmlu_pro, gpqa
      Reasoning : math_500, aime, livecodebench
      Usability : artificial_analysis_intelligence_index / 100 (0–100 → 0–1)

    Minden kategória 0–100 skálán jelenik meg a végeredményben.
    """
    mmlu_pro    = evaluations.get("mmlu_pro")
    gpqa        = evaluations.get("gpqa")
    math_500    = evaluations.get("math_500")
    aime        = evaluations.get("aime")
    livecodebench = evaluations.get("livecodebench")
    intel_index = evaluations.get("artificial_analysis_intelligence_index")

    # Usability: az AA Intelligence Index 0–100 skálán jön → normalizálás 0–1-re
    usability_norm = (intel_index / 100) if intel_index is not None else None

    knowledge_score = _avg(mmlu_pro, gpqa)
    reasoning_score = _avg(math_500, aime, livecodebench)
    usability_score = usability_norm

    # SRS számítás — csak a rendelkezésre álló kategóriákkal, újrasúlyozva
    available = {
        k: v for k, v in {
            "knowledge": knowledge_score,
            "reasoning": reasoning_score,
            "usability": usability_score,
        }.items() if v is not None
    }

    srs = None
    if available:
        total_weight = sum(SRS_WEIGHTS[k] for k in available)
        srs = sum(SRS_WEIGHTS[k] * v for k, v in available.items()) / total_weight
        srs = round(srs * 100, 1)  # 0–100 skálára

    return {
        "knowledge_score": round(knowledge_score * 100, 1) if knowledge_score is not None else None,
        "reasoning_score": round(reasoning_score * 100, 1) if reasoning_score is not None else None,
        "usability_score": round(usability_score * 100, 1) if usability_score is not None else None,
        "service_readiness_score": srs,
        "srs_weights": SRS_WEIGHTS,
        "benchmarks_used": {
            "knowledge": ["mmlu_pro", "gpqa"],
            "reasoning": ["math_500", "aime", "livecodebench"],
            "usability": ["aa_intelligence_index"],
        },
    }


def _compute_performance(aa_model: dict, evaluations: dict) -> dict:
    """Sebesség és ár metrikák."""
    pricing = aa_model.get("pricing") or {}
    speed = aa_model.get("median_output_tokens_per_second")
    ttft = aa_model.get("median_time_to_first_token_seconds")
    price = pricing.get("price_1m_blended_3_to_1")
    intel_index = evaluations.get("artificial_analysis_intelligence_index")

    value = None
    if intel_index is not None and price and price > 0:
        value = round(intel_index / price, 2)

    return {
        "speed_tokens_per_sec": round(speed, 1) if speed is not None else None,
        "time_to_first_token_sec": round(ttft, 2) if ttft is not None else None,
        "price_per_1m_tokens_usd": round(price, 4) if price is not None else None,
        "quality_price_ratio": value,
    }


def evaluate_model(model_name: str) -> dict:
    """
    Fő belépési pont: visszaad egy teljes értékelési dict-et az adott modellről.
    Ha a modell nem található vagy az API nem elérhető, available=False-t ad vissza.
    """
    models = _fetch_aa_models()
    if not models:
        return {"available": False, "reason": "AA API not reachable or API key missing"}

    aa_model = _find_model(models, model_name)
    if not aa_model:
        return {"available": False, "reason": f"Model '{model_name}' not found in Artificial Analysis"}

    evaluations = aa_model.get("evaluations") or {}
    srs = _compute_srs(evaluations)
    performance = _compute_performance(aa_model, evaluations)

    return {
        "available": True,
        "aa_model_name": aa_model.get("name"),
        "aa_model_slug": aa_model.get("slug"),
        "source": "artificialanalysis.ai",
        **srs,
        **performance,
    }
