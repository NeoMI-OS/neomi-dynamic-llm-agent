"""
Experiment Runner – YAML konfigurációból futtatja a pipeline-t,
loggolja az eredményeket, opcionálisan automatikus értékelést futtat.
"""
import os
import sys
import yaml
import json
import uuid
import time
import glob as glob_module
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import run_pipeline
from experiment_logger import ExperimentLogger
from experiment_evaluator import evaluate_run


EXPERIMENTS_DIR = Path(__file__).parent.parent / "experiments"
LOGS_DIR = Path(__file__).parent.parent / "experiment_logs"


def load_experiment(experiment_id: str) -> dict:
    """Betölt egy YAML kísérlet-konfigurációt ID alapján."""
    pattern = str(EXPERIMENTS_DIR / f"{experiment_id}_*.yaml")
    matches = glob_module.glob(pattern)
    if not matches:
        # Próbáljuk a pontos fájlnévvel is
        direct = EXPERIMENTS_DIR / f"{experiment_id}.yaml"
        if direct.exists():
            matches = [str(direct)]
    if not matches:
        raise FileNotFoundError(
            f"Nem található kísérlet-konfig: {experiment_id} "
            f"(keresett minta: {pattern})"
        )
    with open(matches[0], encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_all_experiments() -> list[dict]:
    """Betölti az összes YAML kísérlet-konfigurációt."""
    configs = []
    for path in sorted(EXPERIMENTS_DIR.glob("exp_*.yaml")):
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            cfg["_yaml_path"] = str(path)
            configs.append(cfg)
    return configs


def _extract_node_configs(experiment_cfg: dict) -> dict:
    """Kigyűjti a node konfigurációkat a YAML pipeline.nodes szekciójából."""
    nodes = experiment_cfg.get("pipeline", {}).get("nodes", {})
    result = {}
    for node_name, node_cfg in nodes.items():
        # Hibrid eszkaláció esetén csak a primary szekciót vesszük
        if "primary" in node_cfg:
            src = node_cfg["primary"]
        else:
            src = node_cfg
        result[node_name] = {
            "provider":    src.get("provider", "openai"),
            "model":       src.get("model", "gpt-4o-mini"),
            "temperature": src.get("temperature", 0.5),
        }
    return result


def run_experiment(
    experiment_id: str,
    input_document: str,
    purpose: str,
    auto_evaluate: bool = True,
    tags: list[str] | None = None,
) -> dict:
    """
    Egyetlen kísérlet futtatása:
    1. Betölti a YAML konfigurációt
    2. Futtatja a pipeline-t
    3. Loggolja az eredményt
    4. (Opcionálisan) LLM-Judge értékelést futtat
    Visszaadja a teljes run-rekordot.
    """
    cfg = load_experiment(experiment_id)
    node_configs = _extract_node_configs(cfg)

    run_id = f"run-{uuid.uuid4().hex[:8]}"
    started_at = datetime.now(timezone.utc).isoformat()

    print(f"\n[{experiment_id}] Futtatás: {run_id}")
    print(f"  Modell konfiguráció:")
    for node, nc in node_configs.items():
        print(f"    {node}: {nc['provider']}/{nc['model']} (t={nc['temperature']})")

    pipeline_result = run_pipeline(
        input_document=input_document,
        purpose=purpose,
        node_configs=node_configs,
        experiment_id=experiment_id,
    )

    finished_at = datetime.now(timezone.utc).isoformat()

    run_record = {
        "run_id":        run_id,
        "experiment_id": experiment_id,
        "experiment_name": cfg.get("name", experiment_id),
        "optimization_strategy": cfg.get("optimization_strategy", ""),
        "started_at":    started_at,
        "finished_at":   finished_at,
        "input_document_length": len(input_document),
        "purpose":       purpose,
        "node_configs":  node_configs,
        "outputs": {
            "context":    pipeline_result["context_output"],
            "needs":      pipeline_result["needs_output"],
            "curriculum": pipeline_result["curriculum_output"],
            "content":    pipeline_result["content_output"],
            "critic":     pipeline_result["critic_output"],
        },
        "metrics": {
            "node_timings":   pipeline_result["node_timings"],
            "node_tokens":    pipeline_result["node_tokens"],
            "node_costs_usd": pipeline_result["node_costs_usd"],
            "total_tokens":   pipeline_result["total_tokens"],
            "total_cost_usd": pipeline_result["total_cost_usd"],
            "total_latency_seconds": pipeline_result["total_latency_seconds"],
        },
        "errors": pipeline_result.get("errors", []),
        "tags": (tags or []) + cfg.get("tags", []),
        "evaluation": None,
    }

    print(f"  Kész: {pipeline_result['total_latency_seconds']}s | "
          f"${pipeline_result['total_cost_usd']:.4f} | "
          f"{pipeline_result['total_tokens']} token")

    if auto_evaluate:
        print(f"  LLM-Judge értékelés futtatása...")
        judge_cfg = cfg.get("evaluation", {})
        eval_result = evaluate_run(run_record, judge_cfg)
        run_record["evaluation"] = eval_result
        score = eval_result.get("composite_score")
        print(f"  Composite Score: {score}")

    logger = ExperimentLogger(LOGS_DIR)
    logger.log(run_record)

    return run_record


def run_experiment_series(
    input_document: str,
    purpose: str,
    experiment_ids: list[str] | None = None,
    auto_evaluate: bool = True,
    delay_between_runs: float = 2.0,
) -> list[dict]:
    """
    Futtatja az összes (vagy megadott) kísérlet teljes sorozatát ugyanazon az inputon.
    Visszaadja az összes run-rekordot.
    """
    if experiment_ids is None:
        configs = load_all_experiments()
        experiment_ids = [c["id"] for c in configs if c.get("status", "planned") == "planned"]

    print(f"\n{'='*60}")
    print(f"KÍSÉRLET SOROZAT INDÍTÁSA")
    print(f"  {len(experiment_ids)} kísérlet: {experiment_ids}")
    print(f"  Dokumentum hossz: {len(input_document)} karakter")
    print(f"{'='*60}")

    results = []
    for i, exp_id in enumerate(experiment_ids, 1):
        print(f"\n[{i}/{len(experiment_ids)}] {exp_id}")
        try:
            record = run_experiment(
                experiment_id=exp_id,
                input_document=input_document,
                purpose=purpose,
                auto_evaluate=auto_evaluate,
            )
            results.append(record)
        except Exception as e:
            print(f"  HIBA: {e}")
            results.append({"experiment_id": exp_id, "error": str(e)})

        if i < len(experiment_ids):
            time.sleep(delay_between_runs)

    print(f"\n{'='*60}")
    print(f"SOROZAT KÉSZ: {len(results)} futtatás befejezve")

    # Összefoglaló kiírása
    valid = [r for r in results if "metrics" in r]
    if valid:
        print(f"\n{'Kísérlet':<40} {'Score':>8} {'Cost $':>9} {'Latency':>9}")
        print("-" * 70)
        for r in sorted(valid, key=lambda x: x.get("evaluation", {}) and
                         x["evaluation"].get("composite_score", 0) or 0, reverse=True):
            score = (r.get("evaluation") or {}).get("composite_score", "n/a")
            cost  = r["metrics"]["total_cost_usd"]
            lat   = r["metrics"]["total_latency_seconds"]
            print(f"{r['experiment_name'][:40]:<40} {str(score):>8} {cost:>9.4f} {lat:>8.1f}s")

    print(f"{'='*60}\n")
    return results


# ── CLI belépési pont ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NeoMI Experiment Runner")
    parser.add_argument("--exp", help="Kísérlet ID (pl. exp-003), vagy 'all' az összes futtatáshoz")
    parser.add_argument("--doc", help="Input dokumentum fájl elérési útja")
    parser.add_argument("--purpose", default="Oktatási anyag generálása", help="A dokumentum feldolgozásának célja")
    parser.add_argument("--no-eval", action="store_true", help="LLM-Judge értékelés kihagyása")
    args = parser.parse_args()

    if not args.doc:
        # Demo input ha nincs megadva fájl
        demo_doc = """
        A mesterséges intelligencia és a gépi tanulás alapjai.
        Ez a dokumentum bemutatja a neurális hálózatok működését,
        a backpropagation algoritmus elvét, és a modern deep learning
        architektúrák (CNN, RNN, Transformer) főbb jellemzőit.
        """
        print("Nincs --doc megadva, demo dokumentumot használok.")
    else:
        with open(args.doc, encoding="utf-8") as f:
            demo_doc = f.read()

    if args.exp == "all" or args.exp is None:
        run_experiment_series(
            input_document=demo_doc,
            purpose=args.purpose,
            auto_evaluate=not args.no_eval,
        )
    else:
        run_experiment(
            experiment_id=args.exp,
            input_document=demo_doc,
            purpose=args.purpose,
            auto_evaluate=not args.no_eval,
        )
