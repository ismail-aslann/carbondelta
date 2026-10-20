"""Şeffaflık: B ve S toplamlarının saat saat dökümü (core.simulate ile aynı terimler)."""
from __future__ import annotations

from engine.core import NO_LOAD, OK, SAME_WINDOW, Result


def breakdown(load_kwh: list[float], ci: list[float], result: Result, p: float) -> list[dict]:
    """Her i için standart ve seçilen saat satırları.

    Satırlar i = 0..L-1 sırasıyla; 'kg' sütunlarının aynı sırayla toplamı
    result.baseline_kg ve result.scenario_kg'ye birebir eşittir.
    Hesap yapılmayan durumlarda boş liste.
    """
    if result.status not in (OK, SAME_WINDOW, NO_LOAD):
        return []
    rows = []
    for src in result.source_hours:
        e = p * load_kwh[src]
        rows.append({"window": "standard", "hour": src, "from_hour": src,
                     "kwh": e, "ci": ci[src], "kg": e * ci[src]})
    for src, tgt in zip(result.source_hours, result.target_hours):
        e = p * load_kwh[src]
        rows.append({"window": "scenario", "hour": tgt, "from_hour": src,
                     "kwh": e, "ci": ci[tgt], "kg": e * ci[tgt]})
    return rows
