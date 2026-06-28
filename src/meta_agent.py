"""
Meta-Agent: beolvassa az összes kísérlet-logot, kiértékeli a mintákat,
és új YAML konfigurációkat javasol a következő sprint-hez.
"""
import os
import sys
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from experiment_logger import ExperimentLogger
from experiment_evaluator import compute_pareto_front

LOGS_DIR       = Path(__file__).parent.parent / "experiment_logs"
EXPERIMENTS_DIR = Path(__file__).parent.parent / "experiments"


def _get_llm(provider: str = "anthropic", model: str = "claude-opus-4-8"):
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0.7,
                             api_key=os.getenv("ANTHROPIC_API_KEY"))
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0.7,
                          api_key=os.getenv("OPENAI_API_KEY"))
    raise ValueError(f"Ismeretlen provider: {provider}")


def _build_analysis_prompt(runs: list[dict], summary: list[dict]) -> str:
    """Felépíti a meta-agent elemzési promptját a logok alapján."""
    summary_json = json.dumps(summary, ensure_ascii=False, indent=2)

    # A legjobb 3 futás részletes adatai
    top_runs = sorted(
        [r for r in runs if r.get("evaluation")],
        key=lambda r: r["evaluation"].get("composite_score", 0) or 0,
        reverse=True
    )[:3]

    top_details = []
    for r in top_runs:
        top_details.append({
            "experiment_id": r.get("experiment_id"),
            "strategy": r.get("optimization_strategy"),
            "node_configs": r.get("node_configs"),
            "composite_score": r["evaluation"].get("composite_score"),
            "dimension_scores": r["evaluation"].get("dimension_scores"),
            "key_strengths": r["evaluation"].get("llm_judge_raw", {}).get("key_strengths", []),
            "key_weaknesses": r["evaluation"].get("llm_judge_raw", {}).get("key_weaknesses", []),
        })

    top_json = json.dumps(top_details, ensure_ascii=False, indent=2)

    return f"""Te egy AI kísérlet-tervező Meta-Agent vagy.

Az alábbi kísérlet-sorozat eredményei állnak rendelkezésre:

## ÖSSZEFOGLALÓ TÁBLÁZAT:
{summary_json}

## TOP 3 KÍSÉRLET RÉSZLETES ADATAI:
{top_json}

Feladatod:
1. Elemezd, melyik stratégia/modell-kombináció teljesített legjobban és miért.
2. Azonosítsd a mintákat: mely node-ok modelljei bizonyultak kritikusnak a minőség szempontjából?
3. Javasolj 3 új kísérlet-konfigurációt, amelyek az eredményekből tanulva jobb teljesítményt ígérnek.
   - Kísérletezz mutációkkal (a legjobb konfig 1-2 node-jának cseréje)
   - Javasolj egy ensemble/debate variánst (párhuzamos node-ok, majd szintézis)
   - Javasolj egy cost-vs-quality Pareto-optimális konfigurációt

Válaszolj JSON formátumban:
{{
  "analysis": {{
    "best_strategy": "...",
    "key_insights": ["...", "..."],
    "critical_nodes": ["...", "..."],
    "patterns": "...",
    "recommended_direction": "..."
  }},
  "proposed_experiments": [
    {{
      "id": "exp-011",
      "name": "...",
      "hypothesis": "...",
      "optimization_strategy": "...",
      "pipeline": {{
        "nodes": {{
          "context_analyst":    {{"provider": "...", "model": "...", "temperature": 0.2, "rationale": "..."}},
          "needs_analyzer":     {{"provider": "...", "model": "...", "temperature": 0.3, "rationale": "..."}},
          "curriculum_designer":{{"provider": "...", "model": "...", "temperature": 0.5, "rationale": "..."}},
          "content_writer":     {{"provider": "...", "model": "...", "temperature": 0.7, "rationale": "..."}},
          "critic":             {{"provider": "...", "model": "...", "temperature": 0.1, "rationale": "..."}}
        }}
      }},
      "expected_improvement": "...",
      "tags": ["..."]
    }}
  ],
  "meta_learning_summary": "...",
  "next_sprint_priority": "..."
}}

Elérhető modellek:
- google: gemini-2.5-flash-lite, gemini-2.5-flash, gemini-2.5-pro
- openai: gpt-4o-mini, gpt-4o
- anthropic: claude-haiku-4-5, claude-sonnet-4-6, claude-opus-4-8

Csak JSON-t adj vissza."""


def run_meta_analysis(
    provider: str = "anthropic",
    model: str = "claude-opus-4-8",
    save_proposals: bool = True,
) -> dict:
    """
    Beolvassa az összes logot, elemzi a mintákat,
    és generál új YAML kísérleteket.
    """
    logger = ExperimentLogger(LOGS_DIR)
    runs = logger.load_all_runs()

    if not runs:
        print("Még nincs logolt kísérlet. Futtass legalább néhány kísérletet előbb.")
        return {}

    summary = logger.get_summary_table()

    # Pareto-front számítás
    evals = [r["evaluation"] for r in runs if r.get("evaluation")]
    if evals:
        compute_pareto_front(evals)

    print(f"\n[Meta-Agent] {len(runs)} run elemzése {len(set(r.get('experiment_id') for r in runs))} kísérletből...")

    prompt = _build_analysis_prompt(runs, summary)
    llm = _get_llm(provider, model)

    from langchain_core.messages import HumanMessage
    response = llm.invoke([HumanMessage(content=prompt)])

    # JSON kinyerése
    import re
    text = response.content
    match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        m2 = re.search(r"\{.*\}", text, re.DOTALL)
        if m2:
            text = m2.group(0)

    try:
        result = json.loads(text)
    except Exception:
        result = {"raw_response": response.content, "error": "JSON parse hiba"}
        print(f"[Meta-Agent] Figyelmeztetés: JSON parse hiba a modell válaszában")

    # Elemzés kiírása
    analysis = result.get("analysis", {})
    if analysis:
        print(f"\n{'='*60}")
        print("META-AGENT ELEMZÉS")
        print(f"{'='*60}")
        print(f"Legjobb stratégia: {analysis.get('best_strategy', 'n/a')}")
        print(f"Kritikus node-ok: {analysis.get('critical_nodes', [])}")
        print(f"\nFő megállapítások:")
        for insight in analysis.get("key_insights", []):
            print(f"  • {insight}")
        print(f"\nKövetkező sprint fókusza: {result.get('next_sprint_priority', 'n/a')}")

    # Javasolt kísérletek mentése YAML-ként
    proposals = result.get("proposed_experiments", [])
    if save_proposals and proposals:
        print(f"\n[Meta-Agent] {len(proposals)} új kísérlet-konfig generálva:")
        for proposal in proposals:
            exp_id = proposal.get("id", f"exp-meta-{len(list(EXPERIMENTS_DIR.glob('exp_*.yaml')))+1:03d}")
            # YAML struktúra kiegészítése
            yaml_content = {
                "id":                    exp_id,
                "name":                  proposal.get("name", ""),
                "version":               "1.0",
                "date":                  datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "status":                "planned",
                "source":                "meta_agent_generated",
                "hypothesis":            proposal.get("hypothesis", ""),
                "optimization_strategy": proposal.get("optimization_strategy", "meta_generated"),
                "pipeline":              proposal.get("pipeline", {}),
                "evaluation": {
                    "scoring_weights": {
                        "quality": 0.40, "cost": 0.20, "latency": 0.15,
                        "robustness": 0.15, "diversity": 0.10,
                    },
                    "judge_model":    "claude-opus-4-8",
                    "judge_provider": "anthropic",
                },
                "expected_improvement": proposal.get("expected_improvement", ""),
                "tags": proposal.get("tags", []) + ["meta_agent_generated"],
            }

            # Fájlnév: exp_NNN_<slug>.yaml
            slug = proposal.get("name", exp_id).lower()
            slug = re.sub(r"[^a-z0-9]+", "_", slug)[:40].strip("_")
            filename = f"{exp_id.replace('-', '_')}_{slug}.yaml"
            filepath = EXPERIMENTS_DIR / filename

            with open(filepath, "w", encoding="utf-8") as f:
                yaml.dump(yaml_content, f, allow_unicode=True, default_flow_style=False,
                          sort_keys=False, indent=2)

            print(f"  ✓ {filepath.name}")

    # Meta-log mentése
    meta_log_path = LOGS_DIR / "meta_analysis.jsonl"
    with open(meta_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runs_analyzed": len(runs),
            "result": result,
        }, ensure_ascii=False) + "\n")

    return result


def show_leaderboard():
    """Kiírja a kísérlet-ranglistát."""
    ExperimentLogger(LOGS_DIR).print_leaderboard()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NeoMI Meta-Agent")
    parser.add_argument("--leaderboard", action="store_true", help="Ranglista megjelenítése")
    parser.add_argument("--analyze", action="store_true", help="Meta-elemzés futtatása és új kísérletek generálása")
    parser.add_argument("--provider", default="anthropic", help="Meta-agent LLM provider")
    parser.add_argument("--model", default="claude-opus-4-8", help="Meta-agent LLM modell")
    args = parser.parse_args()

    if args.leaderboard:
        show_leaderboard()
    elif args.analyze:
        run_meta_analysis(provider=args.provider, model=args.model)
    else:
        print("Használat: python meta_agent.py --leaderboard | --analyze")
