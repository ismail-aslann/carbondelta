"""Yıllık etki: aynı senaryo bir yılın tüm günlerinde uygulanırsa toplam emisyon değişimi.

Formül değişmez: her gün simulate() ile hesaplanır, yalnızca B, S ve günlük emisyon toplanır.
Yıllık değişim = (ΣS − ΣB) / ΣB × 100; yıllık günlük etki = (ΣS − ΣB) / Σ günlük emisyon × 100.
Durumu "ok" olmayan günler (yük yok, kısıtlı vb.) toplama girmez ve ayrıca sayılır.

Yenilenebilir pay: kaydırılan enerjinin, tüketildiği saatteki şebeke yenilenebilir payıyla ağırlıklı
ortalaması (konum bazlı gösterge; standart ve hedef pencere için ayrı).
Tesis geneli (ALL): aynı kaydırma tüm kaydırılabilir makinelere uygulanır, sonuçlar toplanır.
Fosil marjinal duyarlılık: aynı günler ve pencereler, saatlik yoğunluk yerine yalnızca fosil santrallerin
yoğunluğu (data.ci_fossil_24) ile; ana sonuca alternatif bir alt sınır göstergesidir.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from engine import data
from engine.core import HOURS, OK, simulate


ALL = "__tesis__"   # tesis geneli: tüm kaydırılabilir makineler


@dataclass
class MonthTotal:
    month: int                 # 1..12
    days: int = 0
    baseline_kg: float = 0.0
    scenario_kg: float = 0.0

    @property
    def delta_kg(self) -> float:
        return self.scenario_kg - self.baseline_kg

    @property
    def delta_pct(self) -> float | None:
        return self.delta_kg / self.baseline_kg * 100 if self.baseline_kg > 0 else None


@dataclass
class AnnualResult:
    asset_id: str
    year: int
    s: int
    L: int
    t: int
    p: float
    days_total: int = 0                 # makinenin o yıldaki gün sayısı
    days_ok: int = 0                    # toplama giren günler
    status_counts: dict[str, int] = field(default_factory=dict)
    shifted_kwh: float = 0.0
    baseline_kg: float = 0.0            # ΣB
    scenario_kg: float = 0.0            # ΣS
    daily_kg: float = 0.0               # toplama giren günlerin toplam emisyonu
    better_days: int = 0                # S < B
    worse_days: int = 0                 # S > B
    best_day: tuple[str, float] | None = None    # (tarih, değişim %) en çok düşüren gün
    worst_day: tuple[str, float] | None = None
    months: list[MonthTotal] = field(default_factory=lambda: [MonthTotal(m) for m in range(1, 13)])
    ren_source_kwh: float = 0.0         # kaydırılan enerjinin standart pencerede yenilenebilir karşılığı
    ren_target_kwh: float = 0.0         # aynı enerjinin hedef pencerede yenilenebilir karşılığı
    parts: list[AnnualResult] = field(default_factory=list)   # tesis genelinde makine sonuçları
    fossil_baseline_kg: float = 0.0     # fosil marjinal duyarlılık: ΣB_fosil
    fossil_scenario_kg: float = 0.0     # ΣS_fosil

    @property
    def fossil_delta_kg(self) -> float:
        return self.fossil_scenario_kg - self.fossil_baseline_kg

    @property
    def fossil_delta_pct(self) -> float | None:
        return self.fossil_delta_kg / self.fossil_baseline_kg * 100 if self.fossil_baseline_kg > 0 else None

    @property
    def is_facility(self) -> bool:
        return self.asset_id == ALL

    @property
    def ren_source_pct(self) -> float | None:
        return self.ren_source_kwh / self.shifted_kwh * 100 if self.shifted_kwh > 0 else None

    @property
    def ren_target_pct(self) -> float | None:
        return self.ren_target_kwh / self.shifted_kwh * 100 if self.shifted_kwh > 0 else None

    @property
    def delta_kg(self) -> float:
        return self.scenario_kg - self.baseline_kg

    @property
    def delta_pct(self) -> float | None:
        return self.delta_kg / self.baseline_kg * 100 if self.baseline_kg > 0 else None

    @property
    def daily_delta_pct(self) -> float | None:
        return self.delta_kg / self.daily_kg * 100 if self.daily_kg > 0 else None


def facility_machines() -> list[str]:
    return [m["id"] for m in data.machines() if m["shiftable"]]


def years_for(asset_id: str) -> list[int]:
    ids = facility_machines() if asset_id == ALL else [asset_id]
    return sorted({int(d[:4]) for a in ids for d in data.days_for(a)})


def year_series(asset_id: str, year: int, kind: str, parametric_kwh: float | None = None) -> list[tuple]:
    """(tarih, yük, CI, yenilenebilir %, fosil marjinal CI) — parametrik modda yük her saat sabit kWh."""
    prefix = f"{year:04d}-"
    out = []
    for d in data.days_for(asset_id):
        if d.startswith(prefix):
            load, ci = data.scenario_series(asset_id, d, kind, parametric_kwh)
            out.append((d, load, ci, [data.mix_at(d, h)["renewable_pct"] for h in range(HOURS)],
                        data.ci_fossil_24(d, kind)))
    return out


def annual_impact(asset_id: str, year: int, s: int, L: int, t: int, p: float,
                  restricted: set[int] = frozenset(), kind: str = "tCO2",
                  series: list | None = None) -> AnnualResult:
    shiftable = data.machine(asset_id)["shiftable"]
    days = series if series is not None else year_series(asset_id, year, kind)
    out = AnnualResult(asset_id, year, s, L, t, p, days_total=len(days))
    for date, load, ci, ren, cif in days:
        r = simulate(load, ci, s, L, t, p, set(restricted), shiftable)
        out.status_counts[r.status] = out.status_counts.get(r.status, 0) + 1
        if r.status != OK:
            continue
        out.days_ok += 1
        out.shifted_kwh += r.shifted_kwh
        out.baseline_kg += r.baseline_kg
        out.scenario_kg += r.scenario_kg
        out.daily_kg += r.daily_kg
        for i in range(L):
            e = p * load[s + i]
            out.ren_source_kwh += e * ren[s + i] / 100
            out.ren_target_kwh += e * ren[t + i] / 100
            out.fossil_baseline_kg += e * cif[s + i]
            out.fossil_scenario_kg += e * cif[t + i]
        m = out.months[int(date[5:7]) - 1]
        m.days += 1
        m.baseline_kg += r.baseline_kg
        m.scenario_kg += r.scenario_kg
        if r.scenario_kg < r.baseline_kg:
            out.better_days += 1
        elif r.scenario_kg > r.baseline_kg:
            out.worse_days += 1
        if out.best_day is None or r.delta_pct < out.best_day[1]:
            out.best_day = (date, r.delta_pct)
        if out.worst_day is None or r.delta_pct > out.worst_day[1]:
            out.worst_day = (date, r.delta_pct)
    return out


def best_annual_target(asset_id: str, year: int, s: int, L: int, p: float,
                       restricted: set[int] = frozenset(), kind: str = "tCO2") -> list[AnnualResult]:
    """Yıl boyunca sabit tutulacak her hedef saat için yıllık sonuç; en düşük ΣS (eşitlikte küçük t) önce.

    Toplama hiç gün girmeyen hedefler (kısıtlı saat, aralık dışı) listelenmez.
    """
    series = year_series(asset_id, year, kind)
    results = [annual_impact(asset_id, year, s, L, t, p, restricted, kind, series)
               for t in range(0, HOURS - L + 1)]
    valid = [r for r in results if r.days_ok > 0]
    return sorted(valid, key=lambda r: (r.scenario_kg, r.t))


def facility_impact(year: int, s: int, L: int, t: int, p: float, restricted: set[int] = frozenset(),
                    kind: str = "tCO2", series_by_asset: dict | None = None,
                    parametric_kwh: float | None = None) -> AnnualResult:
    """Tesis geneli: aynı kaydırma her kaydırılabilir makineye; gün sayıları makine-gün olarak toplanır."""
    out = AnnualResult(ALL, year, s, L, t, p)
    for a in facility_machines():
        series = (series_by_asset or {}).get(a)
        if series is None:
            series = year_series(a, year, kind, parametric_kwh)
        if not series:
            continue
        r = annual_impact(a, year, s, L, t, p, restricted, kind, series)
        out.parts.append(r)
        out.days_total += r.days_total
        out.days_ok += r.days_ok
        for k, v in r.status_counts.items():
            out.status_counts[k] = out.status_counts.get(k, 0) + v
        for name in ("shifted_kwh", "baseline_kg", "scenario_kg", "daily_kg", "ren_source_kwh", "ren_target_kwh",
                     "better_days", "worse_days", "fossil_baseline_kg", "fossil_scenario_kg"):
            setattr(out, name, getattr(out, name) + getattr(r, name))
        for mo, mr in zip(out.months, r.months):
            mo.days += mr.days
            mo.baseline_kg += mr.baseline_kg
            mo.scenario_kg += mr.scenario_kg
    return out
