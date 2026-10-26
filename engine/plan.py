"""Tesis günlük planı: bir günde her kaydırılabilir makine için en temiz hedef pencere.

Formül değişmez: her makine için simulate()/scan_windows() kullanılır. Planlayıcı yalnızca hangi hedef
pencerenin seçileceğine karar verir:
  1. Makineler, kendi başlarına elde edebilecekleri en büyük azaltıma göre büyükten küçüğe sıralanır.
  2. Her makine için hedefler S'ye göre (eşitlikte küçük t) denenir; isteğe bağlı saatlik tepe yük sınırı
     aşılıyorsa sonraki hedefe geçilir. Uygun hedef yoksa makine standart penceresinde kalır.
Tesis yük profili kaydırılamayan makineleri de içerir (tepe yük hesabı için); kaydırılan enerji korunur.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from engine import data
from engine.best_window import scan_windows
from engine.core import HOURS, Result, simulate
from engine.insights import fossil_sensitivity

# Satır durumları
PLANNED = "planned"          # daha temiz bir hedefe kaydırıldı
KEEP = "keep"                # daha temiz saat yok / sınır nedeniyle standartta kaldı
NON_SHIFTABLE = "non_shiftable"
NO_DATA = "no_data"          # bu gün makine verisi yok
EXCLUDED = "excluded"        # kullanıcı plana dahil etmedi
NO_LOAD = "no_load"          # standart pencerede yük yok


@dataclass
class MachineSetting:
    s: int | None          # None: otomatik (makinenin o gün en çok emisyon ürettiği pencere)
    L: int
    p: float = 1.0
    include: bool = True


def heaviest_window(load: list[float], ci: list[float], L: int, p: float = 1.0) -> int | None:
    """O gün en yüksek emisyonlu L saatlik pencerenin başlangıcı (eşitlikte küçük s); yük yoksa None."""
    best, best_b = None, 0.0
    for s in range(0, HOURS - L + 1):
        b = sum(p * load[s + i] * ci[s + i] for i in range(L))
        if b > best_b + 1e-12:
            best, best_b = s, b
    return best


@dataclass
class PlanRow:
    asset_id: str
    name: str
    status: str
    s: int = 0
    L: int = 0
    p: float = 1.0
    t: int | None = None
    result: Result | None = None
    renewable: tuple[float, float] | None = None     # kaydırılan enerjinin yenilenebilir payı (standart, hedef)
    fossil: tuple[float, float] | None = None        # (B_fosil, S_fosil)
    note: str = ""
    daily_kg: float = 0.0

    @property
    def delta_kg(self) -> float:
        r = self.result
        return r.scenario_kg - r.baseline_kg if r is not None else 0.0


@dataclass
class FacilityPlan:
    date: str
    kind: str
    rows: list[PlanRow] = field(default_factory=list)
    before: list[float] = field(default_factory=lambda: [0.0] * HOURS)   # tesis saatlik yükü (kWh)
    after: list[float] = field(default_factory=lambda: [0.0] * HOURS)
    ci: list[float] = field(default_factory=list)
    peak_limit: float | None = None

    def _sum(self, attr: str) -> float:
        return sum(getattr(r.result, attr) for r in self.rows if r.result is not None and r.status in (PLANNED, KEEP))

    @property
    def baseline_kg(self) -> float:
        return self._sum("baseline_kg")

    @property
    def scenario_kg(self) -> float:
        return self._sum("scenario_kg")

    @property
    def shifted_kwh(self) -> float:
        return self._sum("shifted_kwh")

    @property
    def delta_kg(self) -> float:
        return self.scenario_kg - self.baseline_kg

    @property
    def delta_pct(self) -> float | None:
        b = self.baseline_kg
        return self.delta_kg / b * 100 if b > 0 else None

    @property
    def daily_kg(self) -> float:
        """Plandaki günün tesis toplam emisyonu (verisi olan tüm makineler, kaydırma öncesi)."""
        return sum(r.daily_kg for r in self.rows if r.status != NO_DATA)

    @property
    def daily_delta_pct(self) -> float | None:
        d = self.daily_kg
        return self.delta_kg / d * 100 if d > 0 else None

    @property
    def fossil_delta_pct(self) -> float | None:
        b = sum(r.fossil[0] for r in self.rows if r.fossil and r.status in (PLANNED, KEEP))
        sc = sum(r.fossil[1] for r in self.rows if r.fossil and r.status in (PLANNED, KEEP))
        return (sc - b) / b * 100 if b > 0 else None

    @property
    def peak_before(self) -> float:
        return max(self.before) if self.before else 0.0

    @property
    def peak_after(self) -> float:
        return max(self.after) if self.after else 0.0

    @property
    def planned_count(self) -> int:
        return sum(1 for r in self.rows if r.status == PLANNED)


def _renewable(date: str, load: list[float], s: int, L: int, t: int, p: float) -> tuple[float, float] | None:
    ren = [data.mix_at(date, h)["renewable_pct"] for h in range(HOURS)]
    e = [p * load[s + i] for i in range(L)]
    tot = sum(e)
    if tot <= 0:
        return None
    return (sum(e[i] * ren[s + i] for i in range(L)) / tot, sum(e[i] * ren[t + i] for i in range(L)) / tot)


def _shift(profile: list[float], load: list[float], s: int, L: int, t: int, p: float) -> list[float]:
    out = list(profile)
    for i in range(L):
        e = p * load[s + i]
        out[s + i] -= e
        out[t + i] += e
    return out


def facility_plan(date: str, settings: dict[str, MachineSetting], restricted: set[int] = frozenset(),
                  kind: str = "tCO2", peak_limit: float | None = None) -> FacilityPlan:
    """settings: kaydırılabilir makine id → ayar. Ayarı olmayan kaydırılabilir makine dahil edilmez."""
    plan = FacilityPlan(date, kind, ci=data.ci_24(date, kind), peak_limit=peak_limit or None)
    ci, cif = plan.ci, data.ci_fossil_24(date, kind)
    candidates = []   # (azaltım potansiyeli, satır, yük, tarama sonucu)
    for m in data.machines():
        row = PlanRow(m["id"], m["name"], NO_DATA)
        plan.rows.append(row)
        if date not in m["days"]:
            row.note = "Bu gün için makine verisi yok"
            continue
        load = data.load_24(m["id"], date)
        row.daily_kg = sum(load[h] * ci[h] for h in range(HOURS))
        for h in range(HOURS):
            plan.before[h] += load[h]
        if not m["shiftable"]:
            row.status, row.note = NON_SHIFTABLE, "Sürekli/kısıtlı süreç; kaydırılamaz"
            continue
        st = settings.get(m["id"])
        if st is None or not st.include:
            row.status, row.note = EXCLUDED, "Plana dahil edilmedi"
            continue
        row.s, row.L, row.p = st.s, st.L, st.p
        if st.s is None:
            row.s = heaviest_window(load, ci, st.L, st.p)
            if row.s is None:
                row.s, row.status, row.note = 0, NO_LOAD, "Bu gün makinede yük yok"
                continue
        if row.s + row.L > HOURS:
            row.status, row.note = KEEP, "Pencere gün dışına taşıyor"
            continue
        cands = sorted(scan_windows(load, ci, row.s, row.L, row.p, set(restricted), True),
                       key=lambda tr: (tr[1].scenario_kg, tr[0]))
        if not cands:
            row.status, row.note = NO_LOAD, "Standart pencerede yük yok veya tüm hedefler kısıtlı"
            continue
        base = simulate(load, ci, row.s, row.L, row.s, row.p, set(), True)
        potential = base.baseline_kg - cands[0][1].scenario_kg
        candidates.append((potential, row, load, cands, base))

    plan.after = list(plan.before)
    limit = plan.peak_limit
    for _pot, row, load, cands, base in sorted(candidates, key=lambda c: (-c[0], c[1].asset_id)):
        chosen = None
        for t, r in cands:
            if r.scenario_kg >= r.baseline_kg:
                break                                    # bundan sonrası standarttan temiz değil
            trial = _shift(plan.after, load, row.s, row.L, t, row.p)
            if limit is None or max(trial) <= limit + 1e-9 or max(trial) <= max(plan.after) + 1e-9:
                chosen = (t, r, trial)
                break
        if chosen is None:
            row.status, row.t, row.result = KEEP, row.s, base
            better = cands[0][1].scenario_kg < cands[0][1].baseline_kg
            row.note = ("Tepe yük sınırı nedeniyle standart pencerede kaldı" if better and limit
                        else "Standart pencereden daha temiz saat yok")
        else:
            t, r, plan.after = chosen
            row.status, row.t, row.result = PLANNED, t, r
            if t != cands[0][0]:
                row.note = "Tepe yük sınırı nedeniyle sınırı aşmayan en temiz pencere seçildi"
        row.renewable = _renewable(date, load, row.s, row.L, row.t, row.p)
        bf, sf, _ = fossil_sensitivity(load, cif, row.s, row.L, row.t, row.p)
        row.fossil = (bf, sf)
    return plan


def default_settings(s: int | None, L: int, p: float) -> dict[str, MachineSetting]:
    return {m["id"]: MachineSetting(s, L, p) for m in data.machines() if m["shiftable"]}


def reason_counts(p: FacilityPlan) -> dict[str, int]:
    """Kaydırılmayan makinelerin nedenlerine göre sayısı (ekrandaki açıklama için)."""
    out: dict[str, int] = {}
    for r in p.rows:
        if r.status in (KEEP, NO_LOAD):
            out[r.note] = out.get(r.note, 0) + 1
    return out
