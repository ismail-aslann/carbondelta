import json
from pathlib import Path

import pytest

from engine.core import simulate
from engine.explain import breakdown

GOLDEN_FILE = Path(__file__).resolve().parents[2] / "shared" / "golden" / "vectors.json"
with open(GOLDEN_FILE, encoding="utf-8") as f:
    SCENARIOS = json.load(f)["scenarios"]


@pytest.mark.parametrize("sc", SCENARIOS, ids=[sc["id"] for sc in SCENARIOS])
def test_breakdown_sums_match_result(sc):
    i = sc["inputs"]
    r = simulate(i["load_kwh"], i["ci"], i["s"], i["L"], i["t"], i["p"],
                 set(i["restricted"]), i["shiftable"])
    rows = breakdown(i["load_kwh"], i["ci"], r, i["p"])
    if r.status in ("non_shiftable", "out_of_range", "restricted_conflict"):
        assert rows == []
        return
    b = 0.0
    s = 0.0
    for row in rows:
        if row["window"] == "standard":
            b += row["kg"]
        else:
            s += row["kg"]
    assert b == r.baseline_kg
    assert s == r.scenario_kg
    assert [row["hour"] for row in rows if row["window"] == "scenario"] == r.target_hours
