import json
from pathlib import Path

import pytest

from engine.core import simulate

GOLDEN_FILE = Path(__file__).resolve().parents[2] / "shared" / "golden" / "vectors.json"
TOL = 1e-9

with open(GOLDEN_FILE, encoding="utf-8") as f:
    SCENARIOS = json.load(f)["scenarios"]


def test_golden_composition():
    assert len(SCENARIOS) == 30
    statuses = [sc["expected"]["status"] for sc in SCENARIOS]
    assert statuses.count("non_shiftable") >= 3
    assert statuses.count("restricted_conflict") >= 3
    assert statuses.count("no_load") >= 2
    assert statuses.count("same_window") >= 2
    assert sum(sc["mode"] == "parametric" for sc in SCENARIOS) >= 2


@pytest.mark.parametrize("sc", SCENARIOS, ids=[sc["id"] for sc in SCENARIOS])
def test_golden_vector(sc):
    inp, exp = sc["inputs"], sc["expected"]
    r = simulate(inp["load_kwh"], inp["ci"], inp["s"], inp["L"], inp["t"], inp["p"],
                 set(inp["restricted"]), inp["shiftable"])
    assert r.status == exp["status"]
    assert r.source_hours == exp["source_hours"]
    assert r.target_hours == exp["target_hours"]
    for key in ("shifted_kwh", "baseline_kg", "scenario_kg", "daily_kg",
                "delta_pct", "daily_delta_pct"):
        got, want = getattr(r, key), exp[key]
        if want is None:
            assert got is None, key
        else:
            assert got == pytest.approx(want, abs=TOL, rel=0), key
