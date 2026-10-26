"""shared/assets (varsayılan 2025 verisi) + etkin kullanıcı veri paketlerini okur.

Hesap için düz listeler sunar; formül burada değil, engine/core.py'dedir.
Katsayı paketi etkinse karbon yoğunluğu kaynak payları × yeni katsayılarla yeniden hesaplanır.
"""
from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from desktop.resources import resource_path
from engine import packages as pk

ASSETS = "shared/assets"
BASE_GRID_LABEL = "EPİAŞ 2025"
BASE_FACTORS_LABEL = "ETKB 2023"
SAMPLE_SOURCE = "Zenodo"

SOURCES = pk.SOURCES
CI_COLUMNS = {
    "tCO2": "Karbon_Yogunlugu_tCO2_MWh",
    "tCO2esd": "Karbon_Yogunlugu_tCO2esd_MWh",
}


def _asset(name: str):
    return resource_path(f"{ASSETS}/{name}")


def _enabled(kind: str) -> list[pk.Package]:
    return [p for p in pk.list_packages() if p.kind == kind and p.enabled]


# Okunamayan paketler: {paket id: hata}. Bozuk paket atlanır, uygulama açılmaya devam eder.
_ERRORS: dict[str, str] = {}


def _safe(p: pk.Package, fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        _ERRORS[p.id] = f"{type(e).__name__}: {e}"
        return None


def package_errors() -> dict[str, str]:
    errs = dict(_ERRORS)
    for p in pk.list_packages():
        if p.kind == pk.KIND_BROKEN:
            errs[p.id] = p.meta.get("error", "okunamadı")
    return errs


# ------------------------------------------------------------- emisyon katsayıları
@lru_cache(maxsize=1)
def _base_etkb_rows() -> tuple[dict, ...]:
    df = pd.read_csv(_asset("etkb_2023.csv"), dtype=str, keep_default_na=False)
    return tuple(df.to_dict("records"))


def _base_factors() -> dict[str, tuple[float, float]]:
    out = {}
    for row in _base_etkb_rows():
        k = pk.source_key(row["Yakit_Turu_EPIAS_Sutunu"])
        if k:
            out[k] = (float(row["Emisyon_Faktoru_tCO2_MWh"]), float(row["Emisyon_Faktoru_tCO2esd_MWh"]))
    return out


@lru_cache(maxsize=1)
def _active_factors() -> tuple[dict, str, tuple[dict, ...], bool]:
    """(katsayılar, etiket, tablo satırları, paket mi?)"""
    pkgs = sorted(_enabled(pk.KIND_FACTORS), key=lambda p: p.created_at)
    if not pkgs:
        return _base_factors(), BASE_FACTORS_LABEL, _base_etkb_rows(), False
    p = pkgs[-1]
    f = _safe(p, lambda: pk.read_factors_csv(p.path / "factors.csv"))
    if not f or any(s not in f for s in pk.REQUIRED_FOSSIL):
        _ERRORS.setdefault(p.id, "katsayı dosyası eksik ya da okunamadı")
        return _base_factors(), BASE_FACTORS_LABEL, _base_etkb_rows(), False
    for s in pk.ALL_SOURCES:
        f.setdefault(s, (0.0, 0.0))
    rows = tuple({"Yakit_Turu_EPIAS_Sutunu": pk.SOURCE_NAMES[s],
                  "Emisyon_Faktoru_tCO2_MWh": repr(f[s][0]), "Emisyon_Faktoru_tCO2esd_MWh": repr(f[s][1]),
                  "Kategori": "Yenilenebilir" if s in pk.RENEWABLE else "Fosil"} for s in pk.ALL_SOURCES if s in f)
    return f, p.name, rows, True


def factors() -> dict[str, tuple[float, float]]:
    return dict(_active_factors()[0])


def factors_label() -> str:
    return _active_factors()[1]


def etkb_factors() -> list[dict]:
    return [dict(r) for r in _active_factors()[2]]


# ------------------------------------------------------------------- şebeke
@lru_cache(maxsize=1)
def _epias() -> dict[str, list[dict]]:
    frames = []
    df = pd.read_csv(_asset("epias_2025.csv"), dtype={"Tarih": str}, float_precision="round_trip")
    df["_src"] = BASE_GRID_LABEL
    frames.append(df)
    for p in sorted(_enabled(pk.KIND_GRID), key=lambda p: p.created_at):
        g = _safe(p, lambda: _read_grid(p))
        if g is not None:
            g["_src"] = p.name
            frames.append(g)
    out: dict[str, list[dict]] = {}
    for frame in frames:  # sonraki paket aynı günü geçersiz kılar
        frame = frame.sort_values(["Tarih", "Saat_No"])
        for date, g in frame.groupby("Tarih", sort=False):
            out[date] = g.to_dict("records")

    f, _label, _rows, is_pkg = _active_factors()
    if is_pkg:  # yeni katsayılarla yeniden hesap: CI = Σ pay/100 × katsayı
        for recs in out.values():
            for r in recs:
                t = e = 0.0
                for s in pk.ALL_SOURCES:
                    share = r.get(f"{s}_Pay_Yuzde")
                    if share is None or share != share:
                        continue
                    t += float(share) / 100 * f[s][0]
                    e += float(share) / 100 * f[s][1]
                r["Karbon_Yogunlugu_tCO2_MWh"] = t
                r["Karbon_Yogunlugu_tCO2esd_MWh"] = e
    return out


def all_dates() -> list[str]:
    return sorted(_epias())


def grid_label(date: str) -> str:
    recs = _epias().get(date)
    return recs[0]["_src"] if recs else BASE_GRID_LABEL


def ci_24(date: str, kind: str = "tCO2") -> list[float]:
    col = CI_COLUMNS[kind]
    return [float(row[col]) for row in _epias()[date]]


def ci_fossil_24(date: str, kind: str = "tCO2") -> list[float]:
    """Duyarlılık için fosil marjinal yoğunluk: o saatte yalnızca fosil santrallerin ortalama yoğunluğu.

    Yenilenebilir kaynakların emisyon faktörü sıfır olduğundan CI_fosil = CI / fosil payı.
    Kaydırılan yükü fosil santrallerin karşıladığı varsayımına karşılık gelir (fosil üretim yoksa 0).
    """
    ci = ci_24(date, kind)
    out = []
    for h, recs in enumerate(_epias()[date]):
        frac = float(recs["Fosil_Payi_Yuzde"]) / 100
        out.append(ci[h] / frac if frac > 0 else 0.0)
    return out


def mix_at(date: str, hour: int) -> dict:
    row = _epias()[date][hour]
    return {
        "dominant": row["Baskin_Kaynak"],
        "renewable_pct": float(row["Yenilenebilir_Payi_Yuzde"]),
        "fossil_pct": float(row["Fosil_Payi_Yuzde"]),
        "shares": {src: float(row.get(f"{src}_Pay_Yuzde", 0.0)) for src in SOURCES},
    }


# ------------------------------------------------------------------ makineler
@lru_cache(maxsize=1)
def _loads() -> dict[tuple[str, str], list[float]]:
    frames = [pd.read_csv(_asset("loads_hourly.csv"), dtype={"AssetId": str, "Tarih": str},
                          float_precision="round_trip")]
    for p in _enabled(pk.KIND_MACHINE):
        f = _safe(p, lambda: pd.read_csv(p.path / "loads.csv", dtype={"AssetId": str, "Tarih": str},
                                         float_precision="round_trip")[["AssetId", "Tarih", "Saat_No",
                                                                        "Saatlik_Tuketim_kWh"]])
        if f is not None:
            frames.append(f)
    out: dict[tuple[str, str], list[float]] = {}
    for df in frames:
        df = df.sort_values(["AssetId", "Tarih", "Saat_No"])
        for (asset_id, date), g in df.groupby(["AssetId", "Tarih"], sort=False):
            out[(asset_id, date)] = [float(v) for v in g["Saatlik_Tuketim_kWh"]]
    return out


@lru_cache(maxsize=1)
def _machines() -> tuple[dict, ...]:
    with open(_asset("machines.json"), encoding="utf-8") as f:
        base = json.load(f)
    for m in base:
        m.setdefault("source", "sample")
        m["package"] = None
    extra = []
    for p in _enabled(pk.KIND_MACHINE):
        ms = _safe(p, lambda: _read_machines(p))
        for m in ms or []:
            m["package"] = p.id
            extra.append(m)
    grid = _epias()
    out = []
    for m in base + extra:
        days = [d for d in m["days"] if d in grid]  # şebeke verisi olmayan günler düşer
        if not days:
            continue
        m["days"], m["first_day"], m["last_day"] = days, days[0], days[-1]
        out.append(m)
    return tuple(out)


def machines() -> list[dict]:
    return [dict(m) for m in _machines()]


def machine(asset_id: str) -> dict:
    for m in _machines():
        if m["id"] == asset_id:
            return dict(m)
    raise KeyError(asset_id)


def has_machine(asset_id: str) -> bool:
    return any(m["id"] == asset_id for m in _machines())


def days_for(asset_id: str) -> list[str]:
    return list(machine(asset_id)["days"])


def load_24(asset_id: str, date: str) -> list[float]:
    return list(_loads()[(asset_id, date)])


def scenario_series(asset_id: str, date: str, kind: str = "tCO2",
                    parametric_kwh: float | None = None) -> tuple[list[float], list[float]]:
    """simulate() için (load_kwh, ci). Parametrik modda yük sabit kWh/saat."""
    if parametric_kwh is None:
        load = load_24(asset_id, date)
    else:
        load = [float(parametric_kwh)] * 24
    return load, ci_24(date, kind)


# ------------------------------------------------------------------ etiketler
def is_real(asset_id: str) -> bool:
    try:
        return machine(asset_id).get("source") == "real"
    except KeyError:
        return False


def source_label(asset_id: str, date: str) -> str:
    """Ekrandaki zorunlu kaynak etiketi; makinenin veri türüne göre değişir."""
    grid = grid_label(date)
    if is_real(asset_id):
        return f"Tesis ölçümü (Balıkesir) · Kaynak: {grid}, {factors_label()}"
    return f"Örnek yük, Balıkesir tesisi değil · Kaynak: {grid}, {factors_label()}, {SAMPLE_SOURCE}"


# ------------------------------------------------------------------ önbellek
def preload() -> None:
    """Uygulama açılışında tüm veriyi bir kez belleğe al."""
    _machines()
    _loads()
    _epias()
    _active_factors()


def reload() -> None:
    """Paket eklenince / açılıp kapatılınca veriyi yeniden okur."""
    _ERRORS.clear()
    for fn in (_active_factors, _epias, _loads, _machines):
        fn.cache_clear()
    preload()


def _read_grid(p: pk.Package) -> pd.DataFrame:
    g = pd.read_csv(p.path / "epias.csv", dtype={"Tarih": str}, float_precision="round_trip")
    need = ["Tarih", "Saat_No", "Karbon_Yogunlugu_tCO2_MWh", "Karbon_Yogunlugu_tCO2esd_MWh",
            "Yenilenebilir_Payi_Yuzde", "Fosil_Payi_Yuzde", "Baskin_Kaynak"]
    missing = [c for c in need if c not in g.columns]
    if missing:
        raise ValueError("eksik sütun: " + ", ".join(missing))
    return g


def _read_machines(p: pk.Package) -> list[dict]:
    ms = json.loads((p.path / "machines.json").read_text(encoding="utf-8"))
    for m in ms:
        for k in ("id", "name", "shiftable", "days"):
            if k not in m:
                raise ValueError(f"makine kaydında '{k}' yok")
    return ms
