"""
Unit tesztek a cost_guard modulhoz.
Nem hív API-t — csak szintetikus költség-adatokkal dolgozik.
"""
import sys
import os
import csv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cost_guard import check_cost_cap, CostCapExceeded, sum_global_cost_from_csv


class TestCheckCostCap:
    def test_below_threshold_no_warning_no_exception(self, capsys):
        check_cost_cap(3.0, 10.0, label="below")
        assert "figyelmeztetés" not in capsys.readouterr().out

    def test_warns_at_80_percent(self, capsys):
        check_cost_cap(8.0, 10.0, label="warn-test")
        assert "figyelmeztetés" in capsys.readouterr().out

    def test_warns_only_once_per_label(self, capsys):
        check_cost_cap(8.0, 10.0, label="warn-once")
        capsys.readouterr()
        check_cost_cap(8.5, 10.0, label="warn-once")
        assert "figyelmeztetés" not in capsys.readouterr().out

    def test_raises_when_cap_reached(self):
        try:
            check_cost_cap(10.0, 10.0, label="exact")
            assert False, "should have raised"
        except CostCapExceeded as e:
            assert e.current_cost == 10.0
            assert e.cap == 10.0

    def test_raises_when_cap_exceeded(self):
        try:
            check_cost_cap(15.0, 10.0, label="over")
            assert False, "should have raised"
        except CostCapExceeded:
            pass

    def test_none_cap_never_raises(self):
        check_cost_cap(1_000_000.0, None, label="no-cap")


class TestSumGlobalCostFromCsv:
    def test_missing_file_returns_zero(self, tmp_path):
        assert sum_global_cost_from_csv(tmp_path / "does_not_exist.csv") == 0.0

    def test_sums_total_cost_column(self, tmp_path):
        csv_path = tmp_path / "experiment_summary.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["run_id", "total_cost_usd"])
            writer.writeheader()
            writer.writerow({"run_id": "r1", "total_cost_usd": "0.05"})
            writer.writerow({"run_id": "r2", "total_cost_usd": "1.2345"})
            writer.writerow({"run_id": "r3", "total_cost_usd": ""})
        assert sum_global_cost_from_csv(csv_path) == 0.05 + 1.2345
