#!/usr/bin/env python3
"""
TSV export a NeoMI kísérlet-eredményekhez, Google Sheets-be másoláshoz.

Két forrásból olvashat:
  --api-base <url>   a deployolt szolgáltatásból, /pipeline/logs és
                      /pipeline/robustness-aggregate végpontokon keresztül
                      (a szerveren tárolt logok nem érhetők el helyi fájlként)
  --logs-dir <path>  helyi experiment_logs/ mappából (dev/teszt célra) —
                      ehhez a src/ modulokat importáljuk, hogy a patch-elt,
                      újraszámolt adatokat kapjuk (nem a nyers JSONL-t)

Három TSV-t ír:
  experiment_summary_runs.tsv       — egy sor / futás (a régi, "wide" séma)
  experiment_summary_aggregate.tsv  — egy sor / kísérlet (robustness-variancia)
  experiment_summary_nodes.tsv      — egy sor / (futás × node) — "long" formátum,
                                       node-onkénti nyers metrika (token/cost/latency)
                                       és a Judge node-onkénti minőség-pontszáma

Használat:
  python scripts/export_for_sheet.py --api-base https://dynamic-llm-agent-643234238822.europe-west1.run.app
  python scripts/export_for_sheet.py --logs-dir ../experiment_logs
"""
import argparse
import csv
import json
import sys
import urllib.request
from pathlib import Path

NODE_NAMES = ["context_analyst", "needs_analyzer", "curriculum_designer", "content_writer", "critic"]

RUN_COLUMNS = [
    "run_id", "experiment_id", "experiment_name", "strategy", "started_at",
    "total_cost_usd", "total_latency_s", "total_tokens", "composite_score",
    "quality_score", "cost_score", "latency_score", "robustness_score",
    "diversity_score", "critic_issues", "errors", "pareto_dominated", "input_id",
]
HUMAN_RATING_COLUMNS = ["human_rating_1", "human_rating_2", "human_rating_3"]

AGGREGATE_COLUMNS = [
    "experiment_id", "n_inputs", "mean_quality", "stdev_quality",
    "mean_composite", "stdev_composite", "failure_rate", "mean_cost_usd", "mean_latency_s",
]

NODE_COLUMNS = [
    "run_id", "experiment_id", "input_id", "node_name",
    "tokens", "cost_usd", "latency_s", "node_quality_score", "node_comment",
]


def fetch_remote_raw(api_base: str) -> list[dict]:
    """A /pipeline/logs végpont már a normalizált alakot adja vissza:
    run_id, experiment_id, input_id, experiment_name, strategy, started_at,
    metrics (node_timings/node_tokens/node_costs_usd is benne), composite_score,
    dimension_scores, node_quality_scores, critic_issues, errors."""
    with urllib.request.urlopen(f"{api_base}/pipeline/logs?limit=1000") as resp:
        return json.load(resp)


def read_local_raw(logs_dir: Path) -> list[dict]:
    """Helyi módban a src/experiment_logger.ExperimentLogger-t importáljuk,
    hogy a patch-elt/újraszámolt adatokat kapjuk (nem a nyers JSONL sorokat
    közvetlenül) — ugyanazt a normalizált alakot adja, mint fetch_remote_raw."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from experiment_logger import ExperimentLogger

    logger = ExperimentLogger(logs_dir)
    raw = []
    for r in logger.load_all_runs():
        evaluation = r.get("evaluation") or {}
        raw.append({
            "run_id":              r.get("run_id"),
            "experiment_id":       r.get("experiment_id"),
            "input_id":            r.get("input_id"),
            "experiment_name":     r.get("experiment_name"),
            "strategy":            r.get("optimization_strategy"),
            "started_at":          r.get("started_at"),
            "metrics":             r.get("metrics", {}),
            "composite_score":     evaluation.get("composite_score"),
            "dimension_scores":    evaluation.get("dimension_scores"),
            "node_quality_scores": evaluation.get("node_quality_scores"),
            "critic_issues":       evaluation.get("critic_issues_count"),
            "errors":              len(r.get("errors", [])),
        })
    return raw


def build_run_rows(raw_runs: list[dict]) -> list[dict]:
    rows = []
    for r in raw_runs:
        ds = r.get("dimension_scores") or {}
        metrics = r.get("metrics") or {}
        rows.append({
            "run_id":           r.get("run_id", ""),
            "experiment_id":    r.get("experiment_id", ""),
            "experiment_name":  r.get("experiment_name", ""),
            "strategy":         r.get("strategy", ""),
            "started_at":       r.get("started_at", ""),
            "total_cost_usd":   metrics.get("total_cost_usd", ""),
            "total_latency_s":  metrics.get("total_latency_seconds", ""),
            "total_tokens":     metrics.get("total_tokens", ""),
            "composite_score":  r.get("composite_score", ""),
            "quality_score":    ds.get("quality", ""),
            "cost_score":       ds.get("cost", ""),
            "latency_score":    ds.get("latency", ""),
            "robustness_score": ds.get("robustness", ""),
            "diversity_score":  ds.get("diversity", ""),
            "critic_issues":    r.get("critic_issues", ""),
            "errors":           r.get("errors", ""),
            "pareto_dominated": "",
            "input_id":         r.get("input_id", ""),
        })
    return rows


def build_node_rows(raw_runs: list[dict]) -> list[dict]:
    """Long-format: egy sor / (futás × node). Node-onkénti nyers metrika
    (node_timings/node_tokens/node_costs_usd) + a Judge node-onkénti
    minőség-pontszáma (node_quality_scores), ha van."""
    rows = []
    for r in raw_runs:
        metrics = r.get("metrics") or {}
        node_timings = metrics.get("node_timings") or {}
        node_tokens = metrics.get("node_tokens") or {}
        node_costs = metrics.get("node_costs_usd") or {}
        node_quality = r.get("node_quality_scores") or {}

        for node_name in NODE_NAMES:
            # Csak akkor veszünk fel sort, ha legalább egy adatforrásban szerepel a node
            # (egy node hibázhatott/kimaradhatott egy adott futásnál).
            if node_name not in node_timings and node_name not in node_quality:
                continue
            nq = node_quality.get(node_name) or {}
            rows.append({
                "run_id":             r.get("run_id", ""),
                "experiment_id":      r.get("experiment_id", ""),
                "input_id":           r.get("input_id", ""),
                "node_name":          node_name,
                "tokens":             node_tokens.get(node_name, ""),
                "cost_usd":           node_costs.get(node_name, ""),
                "latency_s":          node_timings.get(node_name, ""),
                "node_quality_score": nq.get("score", ""),
                "node_comment":       nq.get("comment", ""),
            })
    return rows


def fetch_remote_aggregate(api_base: str) -> list[dict]:
    with urllib.request.urlopen(f"{api_base}/pipeline/robustness-aggregate") as resp:
        return json.load(resp)


def read_local_aggregate(logs_dir: Path) -> list[dict]:
    path = Path(logs_dir) / "experiment_robustness_aggregate.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_tsv(rows: list[dict], columns: list[str], out_path: Path) -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="NeoMI kísérlet-eredmények exportja TSV-be Google Sheets-hez")
    parser.add_argument("--api-base", help="Deployolt API base URL — ha megadva, onnan olvas (nem helyi fájlból)")
    parser.add_argument("--logs-dir", default="experiment_logs", help="Helyi experiment_logs/ mappa (ha nincs --api-base)")
    parser.add_argument("--out-dir", default="exports", help="Kimeneti mappa a TSV fájloknak")
    parser.add_argument("--exclude-input-ids", default="", help="Vesszővel elválasztott input_id lista, amit ki kell zárni (pl. teszt-futások)")
    parser.add_argument("--after-timestamp", default="", help="ISO8601 időbélyeg (pl. 2026-07-10T12:00:00Z) — csak az ennél KÉSŐBB started_at-tal rendelkező futásokat exportálja. Arra kell, ha egy metodológiai javítás (pl. max_tokens sapka) után a régi, elavult futásokat ki kell zárni anélkül, hogy törölnénk a logból.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    exclude_ids = {x.strip() for x in args.exclude_input_ids.split(",") if x.strip()}

    if args.api_base:
        api_base = args.api_base.rstrip("/")
        raw_runs = fetch_remote_raw(api_base)
        agg_rows = fetch_remote_aggregate(api_base)
    else:
        logs_dir = Path(args.logs_dir)
        raw_runs = read_local_raw(logs_dir)
        agg_rows = read_local_aggregate(logs_dir)

    if exclude_ids:
        raw_runs = [r for r in raw_runs if r.get("input_id") not in exclude_ids]

    if args.after_timestamp:
        raw_runs = [r for r in raw_runs if (r.get("started_at") or "") > args.after_timestamp]

    run_rows = build_run_rows(raw_runs)
    node_rows = build_node_rows(raw_runs)

    # A robustness-aggregátum CSV append-only (minden postprocess-hívás új sort ír) —
    # ha ugyanazt a batch-et véletlenül kétszer postprocesszáljuk (pl. egy kliens-oldali
    # timeout miatti retry), duplikált sorok keletkeznek. Csak az utolsó (legfrissebb)
    # sort tartjuk meg experiment_id-nként.
    dedup_agg = {}
    for row in agg_rows:
        dedup_agg[row.get("experiment_id")] = row
    agg_rows = list(dedup_agg.values())

    for row in run_rows:
        for col in HUMAN_RATING_COLUMNS:
            row.setdefault(col, "")

    runs_path = out_dir / "experiment_summary_runs.tsv"
    agg_path = out_dir / "experiment_summary_aggregate.tsv"
    nodes_path = out_dir / "experiment_summary_nodes.tsv"
    write_tsv(run_rows, RUN_COLUMNS + HUMAN_RATING_COLUMNS, runs_path)
    write_tsv(agg_rows, AGGREGATE_COLUMNS, agg_path)
    write_tsv(node_rows, NODE_COLUMNS, nodes_path)

    print(f"{len(run_rows)} run sor -> {runs_path}")
    print(f"{len(agg_rows)} aggregátum sor -> {agg_path}")
    print(f"{len(node_rows)} node sor -> {nodes_path}")


if __name__ == "__main__":
    main()
