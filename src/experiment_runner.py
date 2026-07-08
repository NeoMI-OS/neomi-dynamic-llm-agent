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
from experiment_evaluator import evaluate_run, compute_robustness_aggregate
from diversity_metrics import compute_diversity_for_input
from cost_guard import (
    check_cost_cap, CostCapExceeded, sum_global_cost_from_csv,
    DEFAULT_SERIES_COST_CAP_USD, DEFAULT_GLOBAL_DAILY_COST_CAP_USD,
)


EXPERIMENTS_DIR = Path(__file__).parent.parent / "experiments"
INPUTS_DIR = EXPERIMENTS_DIR / "inputs"
LOGS_DIR = Path(__file__).parent.parent / "experiment_logs"


def load_experiment(experiment_id: str) -> dict:
    """Betölt egy YAML kísérlet-konfigurációt ID alapján.
    Illeszkedik: exp-003 → exp_003_*.yaml és exp-003_*.yaml alakokra is.
    """
    # Próbáljuk kötőjellel és aláhúzással is (exp-003 → exp_003)
    normalized = experiment_id.replace("-", "_")
    candidates = [
        str(EXPERIMENTS_DIR / f"{experiment_id}_*.yaml"),   # exp-003_*.yaml
        str(EXPERIMENTS_DIR / f"{normalized}_*.yaml"),       # exp_003_*.yaml
        str(EXPERIMENTS_DIR / f"{experiment_id}.yaml"),      # exp-003.yaml
        str(EXPERIMENTS_DIR / f"{normalized}.yaml"),         # exp_003.yaml
    ]
    matches = []
    for pattern in candidates:
        matches = glob_module.glob(pattern)
        if matches:
            break
    if not matches:
        raise FileNotFoundError(
            f"Nem található kísérlet-konfig: {experiment_id} "
            f"(keresett minták: {candidates})"
        )
    with open(sorted(matches)[0], encoding="utf-8") as f:
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


def load_test_inputs(input_ids: list[str] | None = None) -> list[dict]:
    """Betölti a experiments/inputs/*.yaml teszt-dokumentumokat.
    input_ids megadása esetén csak a megfelelő input_id-jű fájlokat adja vissza,
    a megadott sorrendben.
    """
    by_id = {}
    for path in sorted(INPUTS_DIR.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            by_id[cfg["input_id"]] = cfg

    if input_ids is None:
        return list(by_id.values())

    missing = [i for i in input_ids if i not in by_id]
    if missing:
        raise FileNotFoundError(f"Nem található input: {missing} (elérhető: {list(by_id.keys())})")
    return [by_id[i] for i in input_ids]


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
    input_id: str | None = None,
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
        "input_id":      input_id,
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


def run_experiment_series_multi_input(
    inputs: list[dict],
    experiment_ids: list[str] | None = None,
    auto_evaluate: bool = True,
    delay_between_runs: float = 2.0,
    cost_cap_usd: float | None = None,
    global_cost_cap_usd: float | None = None,
) -> dict:
    """
    Futtatja a megadott (vagy összes) kísérletet TÖBB input dokumentumon.
    inputs: [{"input_id": str, "input_document": str, "purpose": str}, ...]
    (pl. load_test_inputs() kimenete).

    Külső ciklus inputonként, belső ciklus experiment_id-nként — ha a cost-cap
    közben leáll, teljes lefedettség marad annyi inputra, amennyi belefért
    (nem féloldalas, ami tönkretenné a robustness-varianciát).

    A batch végén két post-processing lépés fut:
    - diverzitás számítás inputonként (a 10 kombináció kimenetének
      összevetése ugyanazon a dokumentumon), patch-elve a logba
    - robustness-aggregátum experiment_id-nkénti (szórás a minőségben/
      composite score-ban a különböző inputok között, hibaarány)

    Visszaad: {"runs", "runs_completed", "series_cost_usd", "aborted", "abort_reason"}
    """
    if experiment_ids is None:
        configs = load_all_experiments()
        experiment_ids = [c["id"] for c in configs if c.get("status", "planned") == "planned"]

    cost_cap_usd = DEFAULT_SERIES_COST_CAP_USD if cost_cap_usd is None else cost_cap_usd
    global_cost_cap_usd = DEFAULT_GLOBAL_DAILY_COST_CAP_USD if global_cost_cap_usd is None else global_cost_cap_usd

    logger = ExperimentLogger(LOGS_DIR)

    global_cost_so_far = sum_global_cost_from_csv(logger.csv_path)
    if global_cost_so_far >= global_cost_cap_usd:
        msg = f"Globális napi cost cap már túllépve: ${global_cost_so_far:.2f} >= ${global_cost_cap_usd:.2f}"
        print(f"ABORT (batch el sem indul): {msg}")
        return {"runs": [], "runs_completed": 0, "series_cost_usd": 0.0, "aborted": True, "abort_reason": msg}

    total_runs_planned = len(experiment_ids) * len(inputs)
    print(f"\n{'='*60}")
    print(f"MULTI-INPUT KÍSÉRLET SOROZAT INDÍTÁSA")
    print(f"  {len(experiment_ids)} kísérlet x {len(inputs)} input = {total_runs_planned} futás")
    print(f"  Series cost cap: ${cost_cap_usd:.2f} | Globális eddig: ${global_cost_so_far:.2f}")
    print(f"{'='*60}")

    series_cost = 0.0
    all_runs = []
    aborted = False
    abort_reason = None

    for i, inp in enumerate(inputs, 1):
        if aborted:
            break
        print(f"\n--- Input {i}/{len(inputs)}: {inp['input_id']} ---")
        for j, exp_id in enumerate(experiment_ids, 1):
            try:
                check_cost_cap(series_cost, cost_cap_usd, label="series")
            except CostCapExceeded as e:
                print(f"  ABORT: {e}")
                aborted = True
                abort_reason = str(e)
                break

            print(f"  [{j}/{len(experiment_ids)}] {exp_id} (input: {inp['input_id']})")
            try:
                record = run_experiment(
                    experiment_id=exp_id,
                    input_document=inp["input_document"],
                    purpose=inp["purpose"],
                    auto_evaluate=auto_evaluate,
                    input_id=inp["input_id"],
                )
                all_runs.append(record)
                series_cost += record.get("metrics", {}).get("total_cost_usd", 0) or 0
            except Exception as e:
                print(f"    HIBA: {e}")
                all_runs.append({"experiment_id": exp_id, "input_id": inp["input_id"], "error": str(e)})

            if not (i == len(inputs) and j == len(experiment_ids)):
                time.sleep(delay_between_runs)

    print(f"\n{'='*60}")
    print(f"BATCH KÉSZ: {len(all_runs)} futtatás, ${series_cost:.4f} költség"
          + (" (LEÁLLÍTVA cost cap miatt)" if aborted else ""))

    valid_runs = [r for r in all_runs if "metrics" in r and r.get("evaluation")]
    postprocess_diversity_and_robustness(valid_runs, logger)
    print(f"{'='*60}\n")

    return {
        "runs": all_runs,
        "runs_completed": len(valid_runs),
        "series_cost_usd": round(series_cost, 6),
        "aborted": aborted,
        "abort_reason": abort_reason,
    }


def postprocess_diversity_and_robustness(valid_runs: list[dict], logger: ExperimentLogger) -> None:
    """
    Batch utáni post-processing: valós diverzitás-metrika (inputonként, a
    kombinációk kimeneteinek összevetésével) + robustness-aggregátum
    (experiment_id-nkénti, a különböző inputok közötti varianciából).

    valid_runs: run_record-ok, amikhez van "metrics" és "evaluation" (a
    hibás/hiányos futásokat a hívó már kiszűrte).
    """
    by_input: dict[str, list] = {}
    for r in valid_runs:
        by_input.setdefault(r.get("input_id"), []).append(r)

    diversity_errors = []
    for input_id, runs_same_input in by_input.items():
        try:
            div_result = compute_diversity_for_input(runs_same_input)
            for exp_id, div_score in div_result.get("per_experiment_diversity", {}).items():
                run = next((r for r in runs_same_input if r["experiment_id"] == exp_id), None)
                if run:
                    logger.log_diversity_patch(run["run_id"], div_score)
        except Exception as e:
            diversity_errors.append(f"{input_id}: {e}")
    if diversity_errors:
        print(f"  Figyelem: diverzitás-számítás hibázott néhány inputnál: {diversity_errors}")

    valid_run_ids = {r["run_id"] for r in valid_runs}
    patched_runs = logger.load_all_runs()
    patched_by_experiment: dict[str, list] = {}
    for r in patched_runs:
        if r.get("run_id") in valid_run_ids:
            patched_by_experiment.setdefault(r["experiment_id"], []).append(r)

    for exp_id, exp_runs in patched_by_experiment.items():
        aggregate = compute_robustness_aggregate(exp_runs)
        if aggregate:
            logger.log_aggregate(aggregate)

    logger.write_diversity_and_recompute_csv()


def postprocess_logged_runs(input_ids: list[str], experiment_ids: list[str] | None = None) -> dict:
    """
    Lefuttatja a diverzitás + robustness post-processing-et MÁR LOGOLT futásokra,
    anélkül hogy bármit újrafuttatna. Akkor hasznos, ha a kísérletek futtatása
    külön (pl. egyenkénti /pipeline/run hívásokkal) történt, és utólag kell a
    batch-szintű elemzést elvégezni ugyanazon a szerver-instance-on tárolt
    logokra.
    """
    logger = ExperimentLogger(LOGS_DIR)
    all_runs = logger.load_all_runs()
    input_id_set = set(input_ids)
    valid_runs = [
        r for r in all_runs
        if r.get("input_id") in input_id_set
        and r.get("evaluation")
        and (experiment_ids is None or r.get("experiment_id") in experiment_ids)
    ]
    postprocess_diversity_and_robustness(valid_runs, logger)
    return {"runs_postprocessed": len(valid_runs)}


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
