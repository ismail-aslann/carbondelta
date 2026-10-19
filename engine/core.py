"""Saf hesap çekirdeği — shared/FORMUL.md ile birebir.

pandas yok; düz liste ve float. Mobil (Dart) sürümü bu dosyadan satır satır kopyalanır.
Toplama sırası her zaman i = 0'dan L-1'e (h = 0'dan 23'e). Yuvarlama yok.
"""
from __future__ import annotations

from dataclasses import dataclass, field

HOURS = 24

OK = "ok"
NON_SHIFTABLE = "non_shiftable"
OUT_OF_RANGE = "out_of_range"
RESTRICTED_CONFLICT = "restricted_conflict"
SAME_WINDOW = "same_window"
NO_LOAD = "no_load"


@dataclass(frozen=True)
class Result:
    status: str               # ok | non_shiftable | out_of_range | restricted_conflict | same_window | no_load
    shifted_kwh: float
    baseline_kg: float        # B
    scenario_kg: float        # S
    delta_pct: float | None
    daily_kg: float
    daily_delta_pct: float | None
    source_hours: list[int] = field(default_factory=list)
    target_hours: list[int] = field(default_factory=list)


def _empty(status: str, source_hours: list[int] | None = None,
           target_hours: list[int] | None = None) -> Result:
    return Result(status, 0.0, 0.0, 0.0, None, 0.0, None,
                  source_hours or [], target_hours or [])


def simulate(load_kwh: list[float], ci: list[float], s: int, L: int, t: int, p: float,
             restricted: set[int] = frozenset(), shiftable: bool = True) -> Result:
    if len(load_kwh) != HOURS or len(ci) != HOURS:
        raise ValueError("load_kwh ve ci 24 elemanlı olmalı")

    # 1) Kaydırılamaz yük
    if not shiftable:
        return _empty(NON_SHIFTABLE)

    # 2) Aralık dışı (gece yarısı sarması yok)
    if L < 1 or s < 0 or t < 0 or s + L > HOURS or t + L > HOURS or p < 0.0 or p > 1.0:
        return _empty(OUT_OF_RANGE)

    source_hours = [s + i for i in range(L)]
    target_hours = [t + i for i in range(L)]

    # 3) Kısıtlı saat çakışması
    for h in target_hours:
        if h in restricted:
            return _empty(RESTRICTED_CONFLICT, source_hours, target_hours)

    shifted_kwh = 0.0
    baseline_kg = 0.0
    scenario_kg = 0.0
    for i in range(L):
        e_i = p * load_kwh[s + i]
        shifted_kwh += e_i
        baseline_kg += e_i * ci[s + i]
        scenario_kg += e_i * ci[t + i]

    daily_kg = 0.0
    for h in range(HOURS):
        daily_kg += load_kwh[h] * ci[h]

    # 4) Aynı pencere
    if s == t:
        return Result(SAME_WINDOW, shifted_kwh, baseline_kg, scenario_kg, 0.0,
                      daily_kg, 0.0, source_hours, target_hours)

    # 5) Kaydırılacak yük yok
    if baseline_kg == 0.0:
        return Result(NO_LOAD, shifted_kwh, baseline_kg, scenario_kg, None,
                      daily_kg, None, source_hours, target_hours)

    # 6) Tam sonuç
    delta_pct = (scenario_kg - baseline_kg) / baseline_kg * 100
    daily_delta_pct = (scenario_kg - baseline_kg) / daily_kg * 100
    return Result(OK, shifted_kwh, baseline_kg, scenario_kg, delta_pct,
                  daily_kg, daily_delta_pct, source_hours, target_hours)
