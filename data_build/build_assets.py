"""Ham veriden (data_raw/) uygulamanın okuyacağı küçük asset dosyalarını üretir.

Çalıştır: python data_build\\build_assets.py
Ham sayısal değerler metin olarak okunup olduğu gibi yazılır (ondalık kırpma yok).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data_raw" / "karbondeltaveri"
OUT = ROOT / "shared" / "assets"

EPIAS_FILE = RAW / "1_EPIAS_2025_Saatlik_Karbon_Yogunlugu_Temiz.csv"
LOADS_FILE = RAW / "3_CarbonDelta_Ana_Veri_Seti_Saatlik_Birlesik.csv"
INVENTORY_FILE = RAW / "0_Makine_Envanteri_ve_Temizlik_Ozeti.csv"
ETKB_FILE = RAW / "2_ETKB_2023_Resmi_Emisyon_Faktorleri_Tablosu.csv"

SOURCES = [
    "Dogal_Gaz", "Barajli", "Linyit", "Akarsu", "Ithal_Komur", "Ruzgar", "Gunes",
    "Fuel_Oil", "Jeotermal", "Asfaltit_Komur", "Tas_Komur", "Biyokutle", "Atik_Isi",
]
EPIAS_KEEP = [
    "Tarih", "Saat_No", "Karbon_Yogunlugu_tCO2_MWh", "Karbon_Yogunlugu_tCO2esd_MWh",
    "Yenilenebilir_Payi_Yuzde", "Fosil_Payi_Yuzde", "Baskin_Kaynak",
]
MAIN_PACKAGE = "Evet (Ana Paket)"
NON_SHIFTABLE_ROLE = "Kayamayan_Kisitli_Yuk"


def build_epias() -> pd.DataFrame:
    raw = pd.read_csv(EPIAS_FILE, dtype=str, keep_default_na=False)
    assert len(raw) == 8760, f"EPİAŞ satır sayısı {len(raw)} != 8760"
    assert not raw.duplicated(["Tarih", "Saat_No"]).any(), "EPİAŞ (Tarih, Saat_No) tekil değil"

    out = raw[EPIAS_KEEP].copy()
    total = raw["Yurtici_Toplam_Uretim_MWh"].astype(float)
    for src in SOURCES:
        share = raw[f"{src}_MWh"].astype(float) / total * 100
        out[f"{src}_Pay_Yuzde"] = [repr(float(v)) for v in share]
    return out


def build_loads() -> pd.DataFrame:
    raw = pd.read_csv(LOADS_FILE, dtype=str, keep_default_na=False)
    out = raw[["AssetId", "Tarih", "Saat_No", "Saatlik_Tuketim_kWh"]].copy()

    hours = out.assign(h=out["Saat_No"].astype(int)).groupby(["AssetId", "Tarih"])["h"]
    bad = hours.apply(lambda s: sorted(s.tolist()) != list(range(24)))
    assert not bad.any(), f"24 saati eksik/tekrarlı günler: {bad[bad].index.tolist()[:5]}"
    return out


def build_machines(loads: pd.DataFrame) -> list[dict]:
    inv = pd.read_csv(INVENTORY_FILE, dtype=str, encoding="utf-8-sig")
    inv = inv[inv["Paket_Durumu"] == MAIN_PACKAGE]
    machines = []
    for row in inv.itertuples(index=False):
        days = sorted(loads.loc[loads["AssetId"] == row.AssetId, "Tarih"].unique().tolist())
        assert days, f"{row.AssetId} için yük verisi yok"
        machines.append({
            "id": row.AssetId,
            "type": row.AssetType,
            "role": row.CarbonDelta_Role,
            "shiftable": row.CarbonDelta_Role != NON_SHIFTABLE_ROLE,
            "first_day": days[0],
            "last_day": days[-1],
            "days": days,
        })
    return machines


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    epias = build_epias()
    epias.to_csv(OUT / "epias_2025.csv", index=False, lineterminator="\n")

    loads = build_loads()
    machines = build_machines(loads)
    ids = {m["id"] for m in machines}
    assert set(loads["AssetId"]) == ids, "Yük dosyasındaki makineler ana paketle uyuşmuyor"
    loads.to_csv(OUT / "loads_hourly.csv", index=False, lineterminator="\n")

    with open(OUT / "machines.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(machines, f, ensure_ascii=False, indent=1)

    etkb = pd.read_csv(ETKB_FILE, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    etkb.to_csv(OUT / "etkb_2023.csv", index=False, lineterminator="\n")

    print(f"EPİAŞ: {len(epias)}")
    print(f"Yük: {len(loads)}")
    print(f"Makine: {len(machines)}")
    print(f"ETKB faktör: {len(etkb)}")


if __name__ == "__main__":
    main()
