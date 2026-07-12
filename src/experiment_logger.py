"""
Structured JSONL logger kísérlet futásokhoz.
Minden run egy sor a JSONL fájlban.
Külön összefoglaló CSV is generálódik az összehasonlításhoz.

Cloud Run-on a helyi lemez felejtő (ephemeral) — egy instance-váltás
(skálázás, idle-timeout, nagyon hosszú kérés) törli a helyi fájlokat.
Ha a NEOMI_LOGS_GCS_BUCKET env-változó be van állítva, a logger minden
írás után feltölti a fájlokat egy GCS bucketbe, és minden __init__-nél
letölti onnan a legfrissebb állapotot — így a naplók túlélik az
instance-váltásokat, bármelyik instance szolgálja is ki a kérést.
Ha nincs beállítva (helyi fejlesztés), a viselkedés változatlan, tisztán
helyi fájlalapú.
"""
import json
import csv
import os
from pathlib import Path
from datetime import datetime, timezone

GCS_BUCKET = os.getenv("NEOMI_LOGS_GCS_BUCKET")
GCS_PREFIX = os.getenv("NEOMI_LOGS_GCS_PREFIX", "experiment_logs")


class ExperimentLogger:
    def __init__(self, logs_dir: Path):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.logs_dir / "experiment_runs.jsonl"
        self.csv_path   = self.logs_dir / "experiment_summary.csv"
        self.aggregate_csv_path = self.logs_dir / "experiment_robustness_aggregate.csv"
        if GCS_BUCKET:
            for p in (self.jsonl_path, self.csv_path, self.aggregate_csv_path):
                self._gcs_sync_down(p)

    def _gcs_blob_name(self, local_path: Path) -> str:
        return f"{GCS_PREFIX}/{local_path.name}"

    def _gcs_sync_down(self, local_path: Path) -> None:
        """Letölti a legfrissebb állapotot GCS-ből, mielőtt bármit olvasnánk/írnánk —
        így egy másik instance-on történt korábbi írás is látszik."""
        if not GCS_BUCKET:
            return
        try:
            from google.cloud import storage
            bucket = storage.Client().bucket(GCS_BUCKET)
            blob = bucket.blob(self._gcs_blob_name(local_path))
            if blob.exists():
                blob.download_to_filename(str(local_path))
        except Exception as e:
            print(f"[ExperimentLogger] GCS sync-down figyelmeztetés ({local_path.name}): {e}")

    def _gcs_sync_up(self, local_path: Path) -> None:
        """Feltölti a helyi fájlt GCS-be írás után, hogy más instance-ok is lássák."""
        if not GCS_BUCKET or not local_path.exists():
            return
        try:
            from google.cloud import storage
            bucket = storage.Client().bucket(GCS_BUCKET)
            blob = bucket.blob(self._gcs_blob_name(local_path))
            blob.upload_from_filename(str(local_path))
        except Exception as e:
            print(f"[ExperimentLogger] GCS sync-up figyelmeztetés ({local_path.name}): {e}")

    def log(self, run_record: dict) -> None:
        """Hozzáfűz egy run-rekordot a JSONL loghoz és frissíti a CSV-t."""
        self._gcs_sync_down(self.jsonl_path)
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(run_record, ensure_ascii=False) + "\n")
        self._gcs_sync_up(self.jsonl_path)
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
            "input_id":         record.get("input_id", ""),
        }

        write_header = not self.csv_path.exists()
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        self._gcs_sync_up(self.csv_path)

    def log_diversity_patch(self, run_id: str, diversity_score: float) -> None:
        """Appendál egy diverzitás-patch rekordot a JSONL-be. A diverzitás csak
        egy teljes batch lefutása után, több kombináció kimenetének
        összevetéséből számolható, ezért ez mindig egy utólagos patch, nem a
        run eredeti log()-jának a része. Append-only — nem írja felül helyben
        a már meglévő JSONL sort."""
        self._gcs_sync_down(self.jsonl_path)
        patch = {"patch_type": "diversity", "run_id": run_id, "diversity_score": diversity_score}
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(patch, ensure_ascii=False) + "\n")
        self._gcs_sync_up(self.jsonl_path)

    def log_novelty_patch(self, run_id: str, novelty_score: float) -> None:
        """Appendál egy novelty-patch rekordot (Phase 2): mennyire tér el a
        futás kimenete a kitüntetett baseline stratégiától (embedding-alapú
        cosinus-távolság). Kiegészítő, feltáró metrika -- NEM része a
        composite_score-nak/dimension_scores-nak, külön mezőként (evaluation.
        novelty_score) jelenik meg."""
        self._gcs_sync_down(self.jsonl_path)
        patch = {"patch_type": "novelty", "run_id": run_id, "novelty_score": novelty_score}
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(patch, ensure_ascii=False) + "\n")
        self._gcs_sync_up(self.jsonl_path)

    def log_rejudge_patch(self, run_id: str, evaluation: dict) -> None:
        """Appendál egy 'rejudge' patch-et: a Judge-ot újrafuttattuk egy MÁR
        LOGOLT futás meglévő kimenetein (nem futtattuk újra a pipeline-t), pl.
        mert bővült az értékelési séma (node_quality_scores). A patch a teljes
        evaluation dict-et cseréli, DE a diverzitás-pontszámot load_all_runs()
        megtartja a korábbi diverzitás-patch-ből, mert a diverzitás a kimenet
        szövegétől függ, ami nem változott."""
        self._gcs_sync_down(self.jsonl_path)
        patch = {"patch_type": "rejudge", "run_id": run_id, "evaluation": evaluation}
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(patch, ensure_ascii=False) + "\n")
        self._gcs_sync_up(self.jsonl_path)

    def log_aggregate(self, aggregate_record: dict) -> None:
        """Egy robustness-aggregátum sort ír a külön experiment_robustness_aggregate.csv-be
        (egy sor / experiment_id / batch — nem kell az alap run-CSV sémáját bővíteni vele)."""
        self._gcs_sync_down(self.aggregate_csv_path)
        write_header = not self.aggregate_csv_path.exists()
        with open(self.aggregate_csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(aggregate_record.keys()))
            if write_header:
                writer.writeheader()
            writer.writerow(aggregate_record)
        self._gcs_sync_up(self.aggregate_csv_path)

    def load_all_runs(self) -> list[dict]:
        """Visszaadja az összes eddigi run-rekordot, a diverzitás-patch-eket
        ráillesztve a megfelelő run_id-jú rekordokra. Minden futásnál (nem csak
        a patch-elteknél!) újraszámolja a composite_score-t a jelenleg érvényes
        súlyozási képlettel (recompute_composite_score) — így ha a formula
        változik (pl. a cost kikerül a súlyozásból), az a már régen logolt
        futásokra is automatikusan érvényesül a legközelebbi betöltéskor,
        új LLM-hívás nélkül, mert minden dimenzió-pontszám már el van mentve."""
        self._gcs_sync_down(self.jsonl_path)
        if not self.jsonl_path.exists():
            return []

        raw_lines = []
        with open(self.jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        raw_lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        runs_by_id: dict[str, dict] = {}
        diversity_patches: list[dict] = []
        novelty_patches: list[dict] = []
        rejudge_patches: list[dict] = []
        ordered_run_ids: list[str] = []
        for entry in raw_lines:
            patch_type = entry.get("patch_type")
            if patch_type == "diversity":
                diversity_patches.append(entry)
            elif patch_type == "novelty":
                novelty_patches.append(entry)
            elif patch_type == "rejudge":
                rejudge_patches.append(entry)
            else:
                run_id = entry.get("run_id")
                runs_by_id[run_id] = entry
                ordered_run_ids.append(run_id)

        patched_diversity_by_run: dict[str, float] = {}
        for patch in diversity_patches:
            run = runs_by_id.get(patch["run_id"])
            if run is None or not run.get("evaluation"):
                continue
            score = round(patch["diversity_score"] * 100, 1)
            run["evaluation"].setdefault("dimension_scores", {})["diversity"] = score
            patched_diversity_by_run[patch["run_id"]] = score

        patched_novelty_by_run: dict[str, float] = {}
        for patch in novelty_patches:
            run = runs_by_id.get(patch["run_id"])
            if run is None or not run.get("evaluation"):
                continue
            score = round(patch["novelty_score"] * 100, 1)
            run["evaluation"]["novelty_score"] = score
            patched_novelty_by_run[patch["run_id"]] = score

        # A rejudge-patch a teljes evaluation dict-et cseréli (új node_quality_scores,
        # llm_judge_raw, stb.), DE a diverzitást és a novelty_score-t megtartjuk abból,
        # amit fentebb egy VALÓS patch már beállított (nem a run eredeti log()-jából
        # származó placeholder-t!) — mindkettő a kimenet szövegétől függ, ami
        # újraítéléskor nem változik, csak a Judge nézi újra ugyanazt a szöveget.
        for patch in rejudge_patches:
            run = runs_by_id.get(patch["run_id"])
            if run is None:
                continue
            new_evaluation = patch["evaluation"]
            if patch["run_id"] in patched_diversity_by_run:
                new_evaluation.setdefault("dimension_scores", {})["diversity"] = patched_diversity_by_run[patch["run_id"]]
            if patch["run_id"] in patched_novelty_by_run:
                new_evaluation["novelty_score"] = patched_novelty_by_run[patch["run_id"]]
            run["evaluation"] = new_evaluation

        from experiment_evaluator import recompute_composite_score
        for run_id in ordered_run_ids:
            evaluation = runs_by_id[run_id].get("evaluation")
            if evaluation and evaluation.get("dimension_scores"):
                evaluation["composite_score"] = recompute_composite_score(evaluation["dimension_scores"])

        return [runs_by_id[rid] for rid in ordered_run_ids]

    def write_diversity_and_recompute_csv(self) -> None:
        """A teljes experiment_summary.csv-t újragenerálja a (patch-elt,
        újraszámolt) load_all_runs() adatból. Egyszeri, idempotens teljes
        újraírás — csak a batch végén hívandó, nem minden egyes run után."""
        runs = self.load_all_runs()
        if self.csv_path.exists():
            self.csv_path.unlink()
        for run in runs:
            self._update_csv(run)

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
