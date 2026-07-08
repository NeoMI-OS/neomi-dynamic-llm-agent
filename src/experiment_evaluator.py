"""
LLM-as-a-Judge értékelő modul.
Az evaluation_framework.yaml composite score képletét implementálja:
  Final_Score = (0.4 × Quality) + (0.2 × (1/Cost_norm)) + (0.15 × (1/Latency_norm)) +
                (0.15 × Robustness) + (0.1 × Diversity)
"""
import os
import sys
import json
import re
import statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# evaluation_framework.yaml composite_score.formula súlyai
_DEFAULT_WEIGHTS = {"quality": 0.40, "cost": 0.20, "latency": 0.15, "robustness": 0.15, "diversity": 0.10}


def recompute_composite_score(dimension_scores: dict, weights: dict | None = None) -> float:
    """Újraszámolja a composite score-t a dimension_scores (0-100 skálán) alapján,
    ugyanazzal a képlettel mint evaluate_run(). Akkor kell, ha egy dimenzió
    (jellemzően diversity) utólag frissül a valós értékkel a placeholder helyett."""
    w = weights or _DEFAULT_WEIGHTS
    composite = sum(w[dim] * (dimension_scores.get(dim, 0) or 0) / 100.0 for dim in w)
    return round(composite * 100, 1)


# Referencia értékek a normalizáláshoz (az összes kísérlet átlagából frissítendő)
_COST_REFERENCE_USD    = 0.15   # tipikus run cost, frissül a logok alapján
_LATENCY_REFERENCE_SEC = 60.0   # tipikus latencia


# Ezek a modellek elutasítják az explicit `temperature` paramétert (400-as hibát adnak)
_NO_TEMPERATURE_MODELS = {"claude-opus-4-8"}


def _get_judge_llm(provider: str = "anthropic", model: str = "claude-opus-4-8"):
    temp_kwargs = {} if model in _NO_TEMPERATURE_MODELS else {"temperature": 0.1}
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model, **temp_kwargs,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model, **temp_kwargs,
            api_key=os.getenv("OPENAI_API_KEY")
        )
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model, **temp_kwargs,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
    raise ValueError(f"Ismeretlen provider: {provider}")


def _parse_json_safe(text: str) -> dict:
    """JSON kinyerése modell-válaszból – blokkos és sima formát is kezel."""
    # Próbáljuk kinyerni a ```json ... ``` blokkot
    match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        # Keressük az első { ... } blokkot
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
    try:
        return json.loads(text)
    except Exception:
        return {}


def run_llm_judge(outputs: dict, context: str, purpose: str,
                   judge_provider: str = "anthropic",
                   judge_model: str = "claude-opus-4-8") -> dict:
    """
    LLM-as-a-Judge: értékeli a pipeline kimenetét 1–100 skálán.
    Visszaad egy dict-et pontszámokkal és indokolással.
    """
    llm = _get_judge_llm(judge_provider, judge_model)

    prompt = f"""Te egy AI oktatási tartalom minőség-értékelője vagy.
Az alábbi pipeline-kimeneteket értékeld 1–100 skálán az alábbi dimenziókban.

KONTEXTUS (context_analyst kimenete):
{outputs.get('context', 'n/a')[:500]}

SZÜKSÉGLETEK (needs_analyzer kimenete):
{outputs.get('needs', 'n/a')[:500]}

TANANYAG STRUKTÚRA (curriculum_designer kimenete):
{outputs.get('curriculum', 'n/a')[:800]}

TARTALOM (content_writer kimenete – első 1000 karakter):
{outputs.get('content', 'n/a')[:1000]}

KRITIKA (critic kimenete):
{outputs.get('critic', 'n/a')[:600]}

EREDETI CÉL: {purpose}

Értékeld JSON formátumban:
{{
  "goal_alignment": <1-100>,
  "logical_consistency": <1-100>,
  "content_quality": <1-100>,
  "audience_fit": <1-100>,
  "readability": <1-100>,
  "overall_quality": <1-100>,
  "critic_issues_count": <integer>,
  "key_strengths": ["..."],
  "key_weaknesses": ["..."],
  "justification": "..."
}}

Csak JSON-t adj vissza, semmi mást."""

    try:
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        return _parse_json_safe(response.content)
    except Exception as e:
        return {"error": str(e), "overall_quality": 50}


def _normalize_cost(cost_usd: float) -> float:
    """Cost normalizálás 0–1 skálára (alacsonyabb cost = magasabb score)."""
    # Sigmoid-szerű: 0.01 USD → ~0.9, 0.15 USD → ~0.5, 0.5 USD → ~0.1
    ratio = cost_usd / _COST_REFERENCE_USD
    return max(0.0, min(1.0, 1.0 / (1.0 + ratio)))


def _normalize_latency(latency_sec: float) -> float:
    """Latency normalizálás 0–1 skálára (alacsonyabb latency = magasabb score)."""
    ratio = latency_sec / _LATENCY_REFERENCE_SEC
    return max(0.0, min(1.0, 1.0 / (1.0 + ratio)))


def evaluate_run(run_record: dict, judge_cfg: dict | None = None) -> dict:
    """
    Teljes értékelési pipeline egy run-rekordra.
    Lefuttatja az LLM Judge-ot és kiszámolja a composite score-t.
    """
    judge_cfg = judge_cfg or {}
    judge_provider = judge_cfg.get("judge_provider", "anthropic")
    judge_model    = judge_cfg.get("judge_model", "claude-opus-4-8")

    outputs = run_record.get("outputs", {})
    purpose = run_record.get("purpose", "")
    metrics = run_record.get("metrics", {})

    # 1. LLM Judge értékelés
    judge_result = run_llm_judge(
        outputs=outputs,
        context=outputs.get("context", ""),
        purpose=purpose,
        judge_provider=judge_provider,
        judge_model=judge_model,
    )

    quality_raw = judge_result.get("overall_quality", 50)
    quality_norm = quality_raw / 100.0

    # 2. Cost score (invertált)
    cost_usd   = metrics.get("total_cost_usd", 0.1)
    cost_score = _normalize_cost(cost_usd)

    # 3. Latency score (invertált)
    latency_s   = metrics.get("total_latency_seconds", 60)
    latency_score = _normalize_latency(latency_s)

    # 4. Robustness (erre nincs valódi mérés egyetlen futásból → becsléssel)
    # Ha a critic kritikus hibát talált → alacsonyabb; ha az errors lista nem üres → alacsonyabb
    errors_count  = len(run_record.get("errors", []))
    critic_raw    = run_record.get("outputs", {}).get("critic", "")
    critic_issues = judge_result.get("critic_issues_count", 0)
    robustness = max(0.0, 1.0 - (errors_count * 0.2) - (critic_issues * 0.05))
    robustness = min(1.0, robustness)

    # 5. Diversity (egyetlen futásból nem mérhető; placeholder 0.5)
    diversity = 0.5

    # Composite Score (evaluation_framework.yaml képlete)
    dimension_scores = {
        "quality":    round(quality_norm * 100, 1),
        "cost":       round(cost_score * 100, 1),
        "latency":    round(latency_score * 100, 1),
        "robustness": round(robustness * 100, 1),
        "diversity":  round(diversity * 100, 1),
    }
    composite_pct = recompute_composite_score(dimension_scores)

    return {
        "judge_model":       f"{judge_provider}/{judge_model}",
        "composite_score":   composite_pct,
        "dimension_scores": dimension_scores,
        "llm_judge_raw":    judge_result,
        "critic_issues_count": critic_issues,
        "pareto_dominated":  None,  # utólag számítja ki a meta-agent
        "quality_raw_score": quality_raw,
        "cost_usd":          cost_usd,
        "latency_seconds":   latency_s,
    }


def compute_pareto_front(evaluations: list[dict]) -> list[dict]:
    """
    Meghatározza a Pareto-frontot Quality és (1/Cost) dimenzióban.
    Beállítja minden rekordban a pareto_dominated mezőt.
    """
    for ev in evaluations:
        q = ev.get("dimension_scores", {}).get("quality", 0) or 0
        c = ev.get("dimension_scores", {}).get("cost", 0) or 0
        dominated = False
        for other in evaluations:
            if other is ev:
                continue
            oq = other.get("dimension_scores", {}).get("quality", 0) or 0
            oc = other.get("dimension_scores", {}).get("cost", 0) or 0
            if oq >= q and oc >= c and (oq > q or oc > c):
                dominated = True
                break
        ev["pareto_dominated"] = dominated
    return evaluations


def compute_robustness_aggregate(runs_for_experiment: list[dict]) -> dict:
    """
    runs_for_experiment: egy experiment_id összes futása, különböző input_id-kkal
    (ugyanaz a modell-kombináció, több különböző dokumentumon).

    Ez adja a valódi robustness-mérést (evaluation_framework.yaml
    robustness.components.variance_across_inputs) — az evaluate_run()-beli
    egy-futásos robustness dimenzió csak egy közelítő helyettesítő addig,
    amíg ez az aggregátum el nem készül.
    """
    if not runs_for_experiment:
        return {}

    experiment_id = runs_for_experiment[0].get("experiment_id")
    n = len(runs_for_experiment)

    quality_scores, composite_scores, costs, latencies = [], [], [], []
    failures = 0
    for r in runs_for_experiment:
        ev = r.get("evaluation") or {}
        q = (ev.get("dimension_scores") or {}).get("quality")
        if q is not None:
            quality_scores.append(q)
        c = ev.get("composite_score")
        if c is not None:
            composite_scores.append(c)
        if r.get("errors"):
            failures += 1
        metrics = r.get("metrics", {})
        costs.append(metrics.get("total_cost_usd", 0) or 0)
        latencies.append(metrics.get("total_latency_seconds", 0) or 0)

    def _stdev(xs):
        return round(statistics.stdev(xs), 2) if len(xs) >= 2 else 0.0

    return {
        "experiment_id":   experiment_id,
        "n_inputs":        n,
        "mean_quality":    round(statistics.mean(quality_scores), 2) if quality_scores else None,
        "stdev_quality":   _stdev(quality_scores),
        "mean_composite":  round(statistics.mean(composite_scores), 2) if composite_scores else None,
        "stdev_composite": _stdev(composite_scores),
        "failure_rate":    round(failures / n, 4),
        "mean_cost_usd":   round(statistics.mean(costs), 6) if costs else None,
        "mean_latency_s":  round(statistics.mean(latencies), 2) if latencies else None,
    }
