"""Başvuru belgelerindeki tüm rakamları motordan üretir (basvuru/sonuclar.json).

Çalıştırma: .venv\Scripts\python basvuru\sonuclari_hesapla.py
"""
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import annual, data  # noqa: E402
from engine.core import simulate  # noqa: E402

dates = data.all_dates()
prof = [st.mean(data.ci_24(d)[h] for d in dates) for h in range(24)]
load, ci = data.scenario_series("comp_b", "2025-07-15")
r = simulate(load, ci, 3, 3, 18, 1.0)
machines, tot = [], {"B": 0.0, "S": 0.0, "D": 0.0}
for m in data.machines():
    row = {"id": m["id"], "name": m["name"], "shiftable": m["shiftable"], "days": len(m["days"])}
    if m["shiftable"]:
        a = annual.annual_impact(m["id"], 2025, 3, 3, 18, 1.0)
        b = annual.best_annual_target(m["id"], 2025, 3, 3, 1.0)[0]
        row.update(days_ok=a.days_ok, shifted_kwh=a.shifted_kwh, B=a.baseline_kg, S=a.scenario_kg,
                   delta_kg=a.delta_kg, delta_pct=a.delta_pct, daily_pct=a.daily_delta_pct, best_t=b.t,
                   better=a.better_days, worse=a.worse_days)
        tot["B"] += a.baseline_kg; tot["S"] += a.scenario_kg; tot["D"] += a.daily_kg
    machines.append(row)
out = {
    "grid_days": len(dates), "profile": prof,
    "dirtiest_h": max(range(24), key=lambda h: prof[h]), "cleanest_h": min(range(24), key=lambda h: prof[h]),
    "ref_day": {"B": r.baseline_kg, "S": r.scenario_kg, "kwh": r.shifted_kwh, "delta_pct": r.delta_pct,
                "daily_pct": r.daily_delta_pct},
    "machines": machines,
    "total": {"delta_kg": tot["S"] - tot["B"], "delta_pct": (tot["S"] - tot["B"]) / tot["B"] * 100,
              "daily_pct": (tot["S"] - tot["B"]) / tot["D"] * 100},
}
(Path(__file__).parent / "sonuclar.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", out["dirtiest_h"], out["cleanest_h"], round(out["total"]["delta_kg"], 1))
