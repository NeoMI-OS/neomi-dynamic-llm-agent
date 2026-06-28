"""
Structured JSONL logger kísérlet futásokhoz.
Minden run egy sor a JSONL fájlban.
Külön összefoglaló CSV is generálódik az összehasonlításhoz.
"""
import json
import csv
import os
from pathlib import Path
from datetime import datetime, timezone


class ExperimentLogger:
    def __init__(self, logs_dir: Path):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.logs_dir / "experiment_runs.jsonl"
        self.csv_path   = self.logs_dir / "experiment_summary.csv"

    def log(self, run_record: dict) -> None:
        """Hozzáfűz egy run-rekordot a JSONL loghoz és frissíti a CSV-t."""
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(run_record, ensure_ascii=False) + "\n")
        self._update_csv(run_record)

    def _update_csv(self, record: dict) -> None:
        """Hozzáad egy sort az összefoglaló CSV-hez."""
        metrics = record.get("metrics", {})
        evaluation = record.get("evaluation") or {}
        scores = evaluation.get("dimension_scores", {})

        row = {
            "run_id":           record.get("run_id", ""),
            "experiment_id":    record.get("experiment_id", ""),
            "experiment_name":  record.get("experiment_name", ""),
            "strategy":         record.get("optimization_strategy", ""),
            "started_at":       record.get("started_at", ""),
            "total_cost_usd":   metrics.get("total_cost_usd", ""),
            "total_latency_s":  metrics.get("total_latency_seconds", ""),
            "total_tokens":     metrics.get("total_tokens", ""),
            "composite_score":  evaluation.get("composite_score", ""),
            "quality_score":    scores.get("quality", ""),
            "cost_score":       scores.get("cost", ""),
            "latency_score":    scores.get("latency", ""),
            "robustness_score": scores.get("robustness", ""),
            "diversity_score":  scores.get("diversity", ""),
            "critic_issues":    evaluation.get("critic_issues_count", ""),
            "errors":           len(record.get("errors", [])),
            "pareto_dominated": evaluation.get("pareto_dominated", ""),
        }

        write_header = not self.csv_path.exists()
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def load_all_runs(self) -> list[dict]:
        """Visszaadja az összes eddigi run-rekordot."""
        if not self.jsonl_path.exists():
            return []
        runs = []
        with open(self.jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        runs.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return runs

    def load_runs_for_experiment(self, experiment_id: str) -> list[dict]:
        return [r for r in self.load_all_runs() if r.get("experiment_id") == experiment_id]

    def get_best_run(self, metric: str = "composite_score") -> dict | None:
        """Visszaadja a legjobb futást egy adott metrika szerint."""
        runs = [r for r in self.load_all_runs() if r.get("evaluation")]
        if not runs:
            return None
        return max(runs, key=lambda r: r["evaluation"].get(metric, 0) or 0)

    def get_summary_table(self) -> list[dict]:
        """Minden kísérletből a legjobb futás összefoglalója."""
        runs = self.load_all_runs()
        by_exp: dict[str, list] = {}
        for r in runs:
            by_exp.setdefault(r.get("experiment_id", "?"), []).append(r)

        summary = []
        for exp_id, exp_runs in sorted(by_exp.items()):
            best = max(
                exp_runs,
                key=lambda r: (r.get("evaluation") or {}).get("composite_score", 0) or 0
            )
            metrics = best.get("metrics", {})
            ev = best.get("evaluation") or {}
            summary.append({
                "experiment_id":   exp_id,
                "experiment_name": best.get("experiment_name", ""),
                "strategy":        best.get("optimization_strategy", ""),
                "runs_count":      len(exp_runs),
                "best_composite":  ev.get("composite_score"),
                "best_quality":    (ev.get("dimension_scores") or {}).get("quality"),
                "avg_cost_usd":    sum(r.get("metrics", {}).get("total_cost_usd", 0) for r in exp_runs) / len(exp_runs),
                "avg_latency_s":   sum(r.get("metrics", {}).get("total_latency_seconds", 0) for r in exp_runs) / len(exp_runs),
            })
        return summary

    def print_leaderboard(self) -> None:
        """Kiírja a kísérlet-ranglistát a konzolon."""
        summary = self.get_summary_table()
        if not summary:
            print("Még nincsenek logolt futások.")
            return
        summary_sorted = sorted(summary, key=lambda x: x.get("best_composite") or 0, reverse=True)
        print(f"\n{'='*75}")
        print(f"{'Kísérlet':<35} {'Score':>7} {'Quality':>8} {'Cost $':>8} {'Latency':>8}")
        print(f"{'-'*75}")
        for s in summary_sorted:
            print(
                f"{s['experiment_name'][:35]:<35} "
                f"{str(s.get('best_composite') or 'n/a'):>7} "
                f"{str(s.get('best_quality') or 'n/a'):>8} "
                f"{s['avg_cost_usd']:>8.4f} "
                f"{s['avg_latency_s']:>7.1f}s"
            )
        print(f"{'='*75}\n")
