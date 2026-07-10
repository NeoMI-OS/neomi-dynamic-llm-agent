"""
Unit tesztek a scripts/export_for_sheet.py sor-építő függvényeihez.
Nincs hálózati/API-hívás — csak szintetikus "nyers" run-rekordokkal dolgozik.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from export_for_sheet import build_run_rows, build_node_rows, NODE_NAMES


def _raw_run(run_id="run-1", experiment_id="exp-001", input_id="in-1",
             node_quality_scores=None, node_timings=None,
             started_at_override="2026-07-10T00:00:00Z"):
    return {
        "run_id": run_id,
        "experiment_id": experiment_id,
        "input_id": input_id,
        "experiment_name": "Test",
        "strategy": "trivial_strongest",
        "started_at": started_at_override,
        "metrics": {
            "total_cost_usd": 0.15,
            "total_latency_seconds": 60,
            "total_tokens": 1000,
            "node_timings": node_timings if node_timings is not None else {n: 10.0 for n in NODE_NAMES},
            "node_tokens": {n: 100 for n in NODE_NAMES},
            "node_costs_usd": {n: 0.03 for n in NODE_NAMES},
        },
        "composite_score": 70.0,
        "dimension_scores": {"quality": 85.0, "cost": 69.8, "latency": 44.9, "robustness": 90.0, "diversity": 50.0},
        "node_quality_scores": node_quality_scores or {},
        "critic_issues": 1,
        "errors": 0,
    }


class TestBuildRunRows:
    def test_flat_row_has_all_columns(self):
        rows = build_run_rows([_raw_run()])
        assert len(rows) == 1
        assert rows[0]["run_id"] == "run-1"
        assert rows[0]["quality_score"] == 85.0
        assert rows[0]["cost_score"] == 69.8

    def test_multiple_runs(self):
        rows = build_run_rows([_raw_run("run-1"), _raw_run("run-2")])
        assert len(rows) == 2


class TestBuildNodeRows:
    def test_one_row_per_node(self):
        node_scores = {n: {"score": 80, "comment": f"{n} ok"} for n in NODE_NAMES}
        rows = build_node_rows([_raw_run(node_quality_scores=node_scores)])
        assert len(rows) == len(NODE_NAMES)
        assert {r["node_name"] for r in rows} == set(NODE_NAMES)

    def test_node_quality_score_and_raw_metrics_both_present(self):
        node_scores = {"content_writer": {"score": 82, "comment": "reszletes"}}
        rows = build_node_rows([_raw_run(node_quality_scores=node_scores)])
        cw_row = next(r for r in rows if r["node_name"] == "content_writer")
        assert cw_row["node_quality_score"] == 82
        assert cw_row["node_comment"] == "reszletes"
        assert cw_row["tokens"] == 100
        assert cw_row["cost_usd"] == 0.03

    def test_missing_node_quality_scores_still_exports_raw_metrics(self):
        # Judge esetleg nem adott node_scores-t (régi futás, formula-váltás előtti) —
        # a nyers metrikák (node_timings alapján) akkor is exportálódjanak.
        rows = build_node_rows([_raw_run(node_quality_scores={})])
        assert len(rows) == len(NODE_NAMES)
        assert all(r["node_quality_score"] == "" for r in rows)
        assert all(r["tokens"] == 100 for r in rows)

    def test_node_missing_from_both_sources_is_skipped(self):
        # Egy node kimaradt a node_timings-ből is (pl. hibázott és sosem futott le) —
        # ne szerepeljen üres sorként.
        timings = {n: 10.0 for n in NODE_NAMES if n != "critic"}
        rows = build_node_rows([_raw_run(node_timings=timings, node_quality_scores={})])
        assert len(rows) == 4
        assert "critic" not in {r["node_name"] for r in rows}

    def test_multiple_runs_produce_independent_node_rows(self):
        rows = build_node_rows([_raw_run("run-1"), _raw_run("run-2")])
        assert len(rows) == 2 * len(NODE_NAMES)


class TestAfterTimestampFilter:
    """A main()-ben lévő --after-timestamp szűrő ugyanazt a mintát követi mint a
    meglévő --exclude-input-ids: sima lexikografikus ISO8601 összehasonlítás,
    hogy egy metodológiai javítás (pl. max_tokens sapka) utáni friss futásokat
    el lehessen különíteni a régi, elavult futásoktól a logban anélkül, hogy
    törölnénk azokat."""

    def _filter(self, raw_runs, after_timestamp):
        return [r for r in raw_runs if (r.get("started_at") or "") > after_timestamp]

    def test_excludes_runs_at_or_before_cutoff(self):
        runs = [
            _raw_run("run-old", started_at_override="2026-07-09T00:00:00Z"),
            _raw_run("run-new", started_at_override="2026-07-10T12:00:00Z"),
        ]
        result = self._filter(runs, "2026-07-10T00:00:00Z")
        assert [r["run_id"] for r in result] == ["run-new"]

    def test_missing_started_at_is_excluded(self):
        runs = [_raw_run("run-no-ts", started_at_override=None)]
        result = self._filter(runs, "2026-07-10T00:00:00Z")
        assert result == []
