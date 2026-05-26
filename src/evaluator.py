"""
Artificial Analysis alapú modell értékelő modul.
Lekéri a modell minőségi, sebességi és ár adatait, majd értékelést készít.
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


def _compute_scores(aa_model: dict) -> dict:
    """
    Értékelési pontszámokat számít az AA adatok alapján.

    Minőség:  Intelligence Index (0–100)
    Sebesség: output tokens/s (nyers érték)
    Ár:       blended $/M token (nyers érték, alacsonyabb = jobb)
    Értékesség: minőség / ár (price-performance arány)
    """
    evaluations = aa_model.get("evaluations") or {}
    pricing = aa_model.get("pricing") or {}

    quality = evaluations.get("artificial_analysis_intelligence_index")
    speed = aa_model.get("median_output_tokens_per_second")
    price = pricing.get("price_1m_blended_3_to_1")
    ttft = aa_model.get("median_time_to_first_token_seconds")

    value = None
    if quality is not None and price and price > 0:
        value = round(quality / price, 2)

    return {
        "quality_index": round(quality, 1) if quality is not None else None,
        "speed_tokens_per_sec": round(speed, 1) if speed is not None else None,
        "time_to_first_token_sec": round(ttft, 2) if ttft is not None else None,
        "price_per_1m_tokens_usd": round(price, 4) if price is not None else None,
        "value_score": value,
    }


def evaluate_model(model_name: str) -> dict:
    """
    Fő belépési pont: visszaad egy értékelési dict-et az adott modellről.
    Ha a modell nem található vagy az API nem elérhető, None értékeket ad vissza.
    """
    models = _fetch_aa_models()
    if not models:
        return {"available": False, "reason": "AA API not reachable or API key missing"}

    aa_model = _find_model(models, model_name)
    if not aa_model:
        return {"available": False, "reason": f"Model '{model_name}' not found in Artificial Analysis"}

    scores = _compute_scores(aa_model)
    return {
        "available": True,
        "aa_model_name": aa_model.get("name"),
        "aa_model_slug": aa_model.get("slug"),
        "source": "artificialanalysis.ai",
        **scores,
    }
