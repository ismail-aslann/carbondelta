"""shared/assets dosyalarını bir kez okur ve hesap için düz listeler sunar."""
from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from desktop.resources import resource_path

ASSETS = "shared/assets"

SOURCES = [
    "Dogal_Gaz", "Barajli", "Linyit", "Akarsu", "Ithal_Komur", "Ruzgar", "Gunes",
    "Fuel_Oil", "Jeotermal", "Asfaltit_Komur", "Tas_Komur", "Biyokutle", "Atik_Isi",
]
CI_COLUMNS = {
    "tCO2": "Karbon_Yogunlugu_tCO2_MWh",
    "tCO2esd": "Karbon_Yogunlugu_tCO2esd_MWh",
}


def _asset(name: str):
    return resource_path(f"{ASSETS}/{name}")


@lru_cache(maxsize=1)
def _machines() -> tuple[dict, ...]:
    with open(_asset("machines.json"), encoding="utf-8") as f:
        return tuple(json.load(f))


@lru_cache(maxsize=1)
def _loads() -> dict[tuple[str, str], list[float]]:
    df = pd.read_csv(_asset("loads_hourly.csv"), dtype={"AssetId": str, "Tarih": str},
                     float_precision="round_trip")
    df = df.sort_values(["AssetId", "Tarih", "Saat_No"])
    out: dict[tuple[str, str], list[float]] = {}
    for (asset_id, date), g in df.groupby(["AssetId", "Tarih"], sort=False):
        out[(asset_id, date)] = [float(v) for v in g["Saatlik_Tuketim_kWh"]]
    return out


@lru_cache(maxsize=1)
def _epias() -> dict[str, list[dict]]:
    df = pd.read_csv(_asset("epias_2025.csv"), dtype={"Tarih": str},
                     float_precision="round_trip")
    df = df.sort_values(["Tarih", "Saat_No"])
    out: dict[str, list[dict]] = {}
    for date, g in df.groupby("Tarih", sort=False):
        out[date] = g.to_dict("records")
    return out


@lru_cache(maxsize=1)
def etkb_factors() -> list[dict]:
    df = pd.read_csv(_asset("etkb_2023.csv"), dtype=str, keep_default_na=False)
    return df.to_dict("records")


def preload() -> None:
    """Uygulama açılışında tüm asset'leri bir kez belleğe al."""
    _machines()
    _loads()
    _epias()
    etkb_factors()


def machines() -> list[dict]:
    return [dict(m) for m in _machines()]


def machine(asset_id: str) -> dict:
    for m in _machines():
        if m["id"] == asset_id:
            return dict(m)
    raise KeyError(asset_id)


def days_for(asset_id: str) -> list[str]:
    return list(machine(asset_id)["days"])


def load_24(asset_id: str, date: str) -> list[float]:
    return list(_loads()[(asset_id, date)])


def ci_24(date: str, kind: str = "tCO2") -> list[float]:
    col = CI_COLUMNS[kind]
    return [float(row[col]) for row in _epias()[date]]


def mix_at(date: str, hour: int) -> dict:
    row = _epias()[date][hour]
    return {
        "dominant": row["Baskin_Kaynak"],
        "renewable_pct": float(row["Yenilenebilir_Payi_Yuzde"]),
        "fossil_pct": float(row["Fosil_Payi_Yuzde"]),
        "shares": {src: float(row[f"{src}_Pay_Yuzde"]) for src in SOURCES},
    }
