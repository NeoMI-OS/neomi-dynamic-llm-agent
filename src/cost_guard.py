"""
Cost-cap védelem kísérlet-sorozatokhoz.
Megakadályozza, hogy egy elszabadult batch korlátlanul költsön.
"""
import csv
import os
from pathlib import Path

DEFAULT_SERIES_COST_CAP_USD = float(os.getenv("NEOMI_SERIES_COST_CAP_USD", "25.0"))
DEFAULT_GLOBAL_DAILY_COST_CAP_USD = float(os.getenv("NEOMI_GLOBAL_COST_CAP_USD", "100.0"))

_WARNED_AT = set()


class CostCapExceeded(Exception):
    """Akkor dobódik, ha egy kísérlet-sorozat elérte a megengedett költség-limitet."""

    def __init__(self, current_cost: float, cap: float, label: str):
        self.current_cost = current_cost
        self.cap = cap
        self.label = label
        super().__init__(
            f"Cost cap túllépve ({label}): ${current_cost:.4f} >= ${cap:.4f}"
        )


def check_cost_cap(current_cost: float, cap: float, label: str = "series") -> None:
    """Ellenőrzi a futó összköltséget a limithez képest.

    - cap elérésekor/túllépésekor CostCapExceeded-et dob.
    - 80%-os küszöbnél egyszer figyelmeztet (label-enként csak egyszer).
    """
    if cap is None:
        return

    if current_cost >= cap:
        raise CostCapExceeded(current_cost, cap, label)

    warn_threshold = 0.8 * cap
    if current_cost >= warn_threshold and label not in _WARNED_AT:
        _WARNED_AT.add(label)
        print(
            f"  ⚠️  Cost cap figyelmeztetés ({label}): ${current_cost:.4f} / ${cap:.4f} "
            f"(80%-os küszöb elérve)"
        )


def sum_global_cost_from_csv(csv_path: Path) -> float:
    """Összegzi a total_cost_usd oszlopot egy meglévő experiment_summary.csv-ből.
    Ha a fájl nem létezik, 0.0-t ad vissza.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return 0.0

    total = 0.0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get("total_cost_usd", "")
            if raw:
                try:
                    total += float(raw)
                except ValueError:
                    pass
    return total
