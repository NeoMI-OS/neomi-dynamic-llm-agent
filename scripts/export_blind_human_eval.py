#!/usr/bin/env python3
"""
Vak (blind) human-eval export (Phase 2): a 3 független emberi értékelőnek
szánt exportot generálja, amelyben az azonosító mezők (experiment_name,
optimization_strategy, node_configs/modellek) EL VANNAK REJTVE, hogy az
értékelés valóban vak maradjon (evaluation_framework.yaml: human_eval,
blind: true, evaluators: 3, criteria: completeness/coherence/usability/
maturity_alignment/risk_coverage, scale 1-10).

Csak --logs-dir módot támogat (helyi ExperimentLogger-en keresztül), mert a
teljes node-kimenetek (outputs.content stb.) NEM szerepelnek a /pipeline/logs
API válaszban (csak metrikák és pontszámok) -- az emberi értékelőknek viszont
pont a teljes szöveges tartalomra van szükségük.

A "kulcs" fájlt (blind_id -> valódi experiment_id/run_id) NE oszd meg az
értékelőkkel -- csak az eredmények kiértékelése után használd a visszafejtéshez.

Használat:
  python scripts/export_blind_human_eval.py --logs-dir <path> --run-ids-file <run_ids.json> --out exports/blind_human_eval.tsv
"""
import argparse
import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from experiment_logger import ExperimentLogger

BLIND_COLUMNS = [
    "blind_id", "input_id", "context", "needs", "curriculum", "content", "critic",
    "rating_completeness", "rating_coherence", "rating_usability",
    "rating_maturity_alignment", "rating_risk_coverage", "evaluator_notes",
]

KEY_COLUMNS = ["blind_id", "run_id", "experiment_id", "experiment_name", "optimization_strategy", "input_id"]


def build_blind_rows(runs: list[dict], seed: int = 42) -> tuple[list[dict], list[dict]]:
    """Determinisztikusan (de nem kronologikus/kísérlet szerinti sorrendben)
    megkeveri a futásokat, majd vak azonosítót ad mindegyiknek. Visszaadja a
    (blind_rows, key_rows) párost -- a key_rows tartalmazza a visszafejtéshez
    szükséges valódi azonosítókat, ezt NEM szabad az értékelőkkel megosztani."""
    shuffled = list(runs)
    random.Random(seed).shuffle(shuffled)

    blind_rows, key_rows = [], []
    for i, r in enumerate(shuffled, 1):
        blind_id = f"B{i:03d}"
        outputs = r.get("outputs", {})
        blind_rows.append({
            "blind_id": blind_id,
            "input_id": r.get("input_id", ""),
            "context": outputs.get("context", ""),
            "needs": outputs.get("needs", ""),
            "curriculum": outputs.get("curriculum", ""),
            "content": outputs.get("content", ""),
            "critic": outputs.get("critic", ""),
            "rating_completeness": "",
            "rating_coherence": "",
            "rating_usability": "",
            "rating_maturity_alignment": "",
            "rating_risk_coverage": "",
            "evaluator_notes": "",
        })
        key_rows.append({
            "blind_id": blind_id,
            "run_id": r.get("run_id", ""),
            "experiment_id": r.get("experiment_id", ""),
            "experiment_name": r.get("experiment_name", ""),
            "optimization_strategy": r.get("optimization_strategy", ""),
            "input_id": r.get("input_id", ""),
        })
    return blind_rows, key_rows


def main():
    parser = argparse.ArgumentParser(description="Vak human-eval export a 3 független értékelőnek")
    parser.add_argument("--logs-dir", required=True, help="Helyi experiment_logs/ mappa")
    parser.add_argument("--run-ids-file", default="", help="JSON run_id lista szűréshez (üres = mind)")
    parser.add_argument("--out", default="exports/blind_human_eval.tsv")
    parser.add_argument("--seed", type=int, default=42, help="Determinisztikus keverés seed-je")
    args = parser.parse_args()

    logger = ExperimentLogger(Path(args.logs_dir))
    runs = logger.load_all_runs()
    if args.run_ids_file:
        with open(args.run_ids_file) as f:
            wanted = set(json.load(f))
        runs = [r for r in runs if r.get("run_id") in wanted]

    blind_rows, key_rows = build_blind_rows(runs, args.seed)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BLIND_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(blind_rows)

    key_path = out_path.with_name(out_path.stem + "_key.tsv")
    with open(key_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=KEY_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(key_rows)

    print(f"{len(blind_rows)} sor -> {out_path} (vak export)")
    print(f"Kulcs (NE oszd meg az értékelőkkel!) -> {key_path}")


if __name__ == "__main__":
    main()
