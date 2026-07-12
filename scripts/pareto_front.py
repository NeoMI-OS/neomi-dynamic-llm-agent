#!/usr/bin/env python3
"""
Pareto-front script (Phase 2): kiszámolja, mely kísérletek NEM dominált
megoldások Quality/Cost/Latency/Robustness dimenzióban (evaluation_framework.yaml
composite_score.pareto_front definíciója szerint), a /pipeline/logs végpontról
beolvasott, kísérletenkénti átlagos dimension_scores alapján.

Használat:
  python scripts/pareto_front.py --api-base https://dynamic-llm-agent-643234238822.europe-west1.run.app
  python scripts/pareto_front.py --api-base <url> --input-ids input-03-..-v2maxtok,input-06-..-v2maxtok
"""
import argparse
import json
import statistics
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from experiment_evaluator import compute_pareto_front_multi_dim


def fetch_runs(api_base: str) -> list[dict]:
    with urllib.request.urlopen(f"{api_base}/pipeline/logs?limit=1000") as resp:
        return json.load(resp)


def build_per_experiment_means(runs: list[dict], input_ids: set[str] | None = None,
                                run_ids: set[str] | None = None) -> list[dict]:
    by_exp: dict[str, list[dict]] = {}
    for r in runs:
        if input_ids is not None and r.get("input_id") not in input_ids:
            continue
        if run_ids is not None and r.get("run_id") not in run_ids:
            continue
        ds = r.get("dimension_scores")
        if not ds:
            continue
        by_exp.setdefault(r["experiment_id"], []).append(ds)

    result = []
    for exp_id, ds_list in by_exp.items():
        mean_scores = {
            dim: statistics.mean(ds.get(dim, 0) or 0 for ds in ds_list)
            for dim in ["quality", "cost", "latency", "robustness", "diversity"]
        }
        result.append({"experiment_id": exp_id, "dimension_scores": mean_scores, "n": len(ds_list)})
    return result


def main():
    parser = argparse.ArgumentParser(description="Pareto-front számítás kísérletenkénti átlagos dimenziópontszámokból")
    parser.add_argument("--api-base", required=True, help="Deployolt API base URL")
    parser.add_argument("--input-ids", default="", help="Vesszővel elválasztott input_id lista a szűréshez (üres = mind)")
    parser.add_argument("--run-ids-file", default="", help="JSON fájl elérési útja: run_id-k listája (pontos szűrés, felülírja az --input-ids-t)")
    args = parser.parse_args()

    runs = fetch_runs(args.api_base)
    input_ids = {x.strip() for x in args.input_ids.split(",") if x.strip()} or None
    run_ids = None
    if args.run_ids_file:
        with open(args.run_ids_file) as f:
            run_ids = set(json.load(f))
        input_ids = None
    experiments = build_per_experiment_means(runs, input_ids, run_ids)

    front = set(compute_pareto_front_multi_dim(experiments))

    print(f"{'experiment_id':12} {'n':3} {'quality':9} {'cost':7} {'latency':9} {'robustness':11} {'pareto':7}")
    for e in sorted(experiments, key=lambda x: x["experiment_id"]):
        ds = e["dimension_scores"]
        on_front = "IGEN" if e["experiment_id"] in front else ""
        print(f"{e['experiment_id']:12} {e['n']:3} {ds['quality']:9.1f} {ds['cost']:7.1f} "
              f"{ds['latency']:9.1f} {ds['robustness']:11.1f} {on_front:7}")

    print(f"\nPareto-front ({len(front)} kísérlet): {sorted(front)}")


if __name__ == "__main__":
    main()
