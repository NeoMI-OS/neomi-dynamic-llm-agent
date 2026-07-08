#!/usr/bin/env python3
"""
TSV export a NeoMI kísérlet-eredményekhez, Google Sheets-be másoláshoz.

Két forrásból olvashat:
  --api-base <url>   a deployolt szolgáltatásból, /pipeline/logs és
                      /pipeline/robustness-aggregate végpontokon keresztül
                      (a szerveren tárolt logok nem érhetők el helyi fájlként)
  --logs-dir <path>  helyi experiment_logs/ mappából (dev/teszt célra)

Használat:
  python scripts/export_for_sheet.py --api-base https://dynamic-llm-agent-643234238822.europe-west1.run.app
  python scripts/export_for_sheet.py --logs-dir ../experiment_logs
"""
import argparse
import csv
import json
import urllib.request
from pathlib import Path

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


def fetch_remote_runs(api_base: str) -> list[dict]:
    with urllib.request.urlopen(f"{api_base}/pipeline/logs?limit=1000") as resp:
        data = json.load(resp)
    rows = []
    for r in data:
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


def fetch_remote_aggregate(api_base: str) -> list[dict]:
    with urllib.request.urlopen(f"{api_base}/pipeline/robustness-aggregate") as resp:
        return json.load(resp)


def read_local_csv(path: Path) -> list[dict]:
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
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    exclude_ids = {x.strip() for x in args.exclude_input_ids.split(",") if x.strip()}

    if args.api_base:
        api_base = args.api_base.rstrip("/")
        run_rows = fetch_remote_runs(api_base)
        agg_rows = fetch_remote_aggregate(api_base)
    else:
        logs_dir = Path(args.logs_dir)
        run_rows = read_local_csv(logs_dir / "experiment_summary.csv")
        agg_rows = read_local_csv(logs_dir / "experiment_robustness_aggregate.csv")

    if exclude_ids:
        run_rows = [r for r in run_rows if r.get("input_id") not in exclude_ids]

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
    write_tsv(run_rows, RUN_COLUMNS + HUMAN_RATING_COLUMNS, runs_path)
    write_tsv(agg_rows, AGGREGATE_COLUMNS, agg_path)

    print(f"{len(run_rows)} run sor -> {runs_path}")
    print(f"{len(agg_rows)} aggregátum sor -> {agg_path}")


if __name__ == "__main__":
    main()
