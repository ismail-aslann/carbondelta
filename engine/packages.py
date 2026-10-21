"""Kullanıcı veri paketleri: yeni makine, yeni yıl (EPİAŞ) ve yeni emisyon katsayıları.

Varsayılan 2025 verisi EXE içinde kalır (shared/assets). Eklenen veriler
%APPDATA%\\CarbonDelta\\veri\\<paket>\\ altında tutulur; her pakette manifest.json bulunur.
Hesap formülü değişmez: yalnızca veri eklenir. Karbon yoğunluğu, kaynak üretim payları ×
emisyon faktörleri ile hesaplanır (varsayılan veriyle aynı yöntem; 6. ondalığa kadar birebir).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

# Kaynaklar (varsayılan veriyle aynı sıra) + 2025'te sıfır olan Nafta/LNG
SOURCES = [
    "Dogal_Gaz", "Barajli", "Linyit", "Akarsu", "Ithal_Komur", "Ruzgar", "Gunes",
    "Fuel_Oil", "Jeotermal", "Asfaltit_Komur", "Tas_Komur", "Biyokutle", "Atik_Isi",
]
EXTRA_SOURCES = ["Nafta", "LNG"]
ALL_SOURCES = SOURCES + EXTRA_SOURCES
RENEWABLE = {"Barajli", "Akarsu", "Ruzgar", "Gunes", "Jeotermal", "Biyokutle", "Atik_Isi"}
SOURCE_NAMES = {
    "Dogal_Gaz": "Doğal gaz", "Barajli": "Barajlı hidro", "Linyit": "Linyit", "Akarsu": "Akarsu hidro",
    "Ithal_Komur": "İthal kömür", "Ruzgar": "Rüzgâr", "Gunes": "Güneş", "Fuel_Oil": "Fuel oil",
    "Jeotermal": "Jeotermal", "Asfaltit_Komur": "Asfaltit", "Tas_Komur": "Taş kömürü",
    "Biyokutle": "Biyokütle", "Atik_Isi": "Atık ısı", "Nafta": "Nafta", "LNG": "LNG",
}
REQUIRED_FOSSIL = ["Dogal_Gaz", "Linyit", "Ithal_Komur", "Fuel_Oil", "Asfaltit_Komur", "Tas_Komur"]

KIND_MACHINE, KIND_GRID, KIND_FACTORS = "machine", "grid", "factors"
KIND_BROKEN = "broken"  # manifest okunamayan klasör: yalnızca listede gösterilir ve silinebilir


# ------------------------------------------------------------------ yardımcılar
def data_dir() -> Path:
    env = os.environ.get("CARBONDELTA_DATA_DIR")
    if env:
        return Path(env)
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "CarbonDelta" / "veri"


def norm(text: str) -> str:
    """Sütun/kaynak adını karşılaştırma için sadeleştirir: 'Doğal Gaz (MWh)' → 'dogalgaz'."""
    t = str(text).replace("ı", "i").replace("İ", "i")
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"[^a-z0-9]", "", t)
    for suffix in ("mwh", "yuzde", "pay"):
        if t.endswith(suffix) and len(t) > len(suffix):
            t = t[: -len(suffix)]
    return t


SOURCE_KEYS = {
    "dogalgaz": "Dogal_Gaz", "barajli": "Barajli", "hidrolikbarajli": "Barajli", "linyit": "Linyit",
    "akarsu": "Akarsu", "hidrolikakarsu": "Akarsu", "ithalkomur": "Ithal_Komur", "ruzgar": "Ruzgar",
    "gunes": "Gunes", "fueloil": "Fuel_Oil", "jeotermal": "Jeotermal", "asfaltitkomur": "Asfaltit_Komur",
    "asfaltit": "Asfaltit_Komur", "taskomur": "Tas_Komur", "taskomuru": "Tas_Komur", "biyokutle": "Biyokutle",
    "atikisi": "Atik_Isi", "nafta": "Nafta", "lng": "LNG", "dogalgazlng": "LNG",
}


def source_key(name: str) -> str | None:
    n = norm(name)
    if n in SOURCE_KEYS:
        return SOURCE_KEYS[n]
    for k, v in SOURCE_KEYS.items():  # "Motorin / Fuel Oil Türevi" gibi açıklamalı adlar
        if n.startswith(k) and len(k) >= 5:
            return v
    return None


def parse_num(value) -> float:
    """'1.234,56', '12,40', ',01', '-,05', '12.4', 12.4 → float; boş → NaN."""
    if value is None:
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(" ", "").replace(" ", "")
    if s in ("", "-", "nan", "NaN", "None"):
        return float("nan")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def parse_date(value) -> str | None:
    """'2026-01-01', '01.01.2026', '01/01/2026', '2026-01-01 00:00:00' → '2026-01-01'."""
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
    else:
        m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
        if not m:
            return None
        d, mo, y = m.groups()
    try:
        return datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_hour(value) -> int | None:
    s = str(value).strip()
    m = re.search(r"(\d{1,2})(?::\d{2})?", s.split(" ")[-1] if " " in s else s)
    if not m:
        return None
    h = int(m.group(1))
    return h if 0 <= h <= 23 else None


def parse_minute(time_text) -> int:
    """'03:15' / '3.30' / '03:15:00' → dakika; saat bilgisi yoksa 0. Yalnızca saat metni verilmeli."""
    m = re.match(r"^\s*\d{1,2}[:.](\d{2})", str(time_text))
    return int(m.group(1)) if m else 0


def _minutes(df: pd.DataFrame) -> pd.Series:
    """Saat sütunundaki ya da birleşik tarih-saat sütununun saat kısmındaki dakika; yoksa 0."""
    dcol = find_col(df, "tarih", "date", "gun")
    # Saat_No (tam sayı) ile "Saat" (03:15) birlikte olabilir: dakika taşıyan ilk saat sütunu kullanılır.
    for c in df.columns:
        if c != dcol and norm(c).startswith(("saat", "hour", "time", "zaman")):
            mins = df[c].map(parse_minute)
            if mins.any():
                return mins
    hcol = find_col(df, "saatno", "saat", "hour")
    if hcol is not None and hcol != dcol:
        return df[hcol].map(parse_minute)
    tcol = find_col(df, "tarihsaat", "tarihsaatanahtari", "datetime", "zaman", "tarih", "date")
    if tcol is None:
        return pd.Series(0, index=df.index)
    return df[tcol].map(lambda v: parse_minute(str(v).strip().split(" ", 1)[1]) if " " in str(v).strip() else 0)


def read_table(path: str | Path) -> pd.DataFrame:
    """CSV (; veya ,) ya da Excel dosyasını metin sütunlarıyla okur."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(path, dtype=str)
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "cp1254", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    first = text.splitlines()[0] if text else ""
    sep = ";" if first.count(";") >= first.count(",") and ";" in first else ("\t" if "\t" in first else ",")
    from io import StringIO
    return pd.read_csv(StringIO(text), sep=sep, dtype=str, keep_default_na=False)


def find_col(df: pd.DataFrame, *aliases: str) -> str | None:
    cols = {norm(c): c for c in df.columns}
    for a in aliases:
        if a in cols:
            return cols[a]
    for a in aliases:
        for n, c in cols.items():
            if n.startswith(a):
                return c
    return None


def _date_hour(df: pd.DataFrame) -> tuple[pd.Series, pd.Series] | None:
    dcol = find_col(df, "tarih", "date", "gun")
    hcol = find_col(df, "saatno", "saat", "hour")
    if dcol is not None and hcol is not None and dcol != hcol:
        return df[dcol].map(parse_date), df[hcol].map(parse_hour)
    tcol = find_col(df, "tarihsaat", "tarihsaatanahtari", "datetime", "zaman", "tarih", "date")
    if tcol is None:
        return None
    return df[tcol].map(parse_date), df[tcol].map(parse_hour)


@dataclass
class Report:
    """İçe aktarma kontrol raporu: (düzey, metin) satırları; düzey ok | warn | err."""
    lines: list[tuple[str, str]] = field(default_factory=list)

    def ok(self, t): self.lines.append(("ok", t))
    def warn(self, t): self.lines.append(("warn", t))
    def err(self, t): self.lines.append(("err", t))

    @property
    def has_errors(self) -> bool:
        return any(level == "err" for level, _ in self.lines)


def _fmt_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# ------------------------------------------------------------------ paketler
@dataclass
class Package:
    id: str
    kind: str
    name: str
    enabled: bool
    created_at: str
    meta: dict
    path: Path


def list_packages() -> list[Package]:
    root = data_dir()
    out = []
    if not root.exists():
        return out
    for d in sorted(root.iterdir()):
        mf = d / "manifest.json"
        if not mf.exists():
            continue
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
            out.append(Package(str(m["id"]), str(m["kind"]), str(m["name"]), bool(m.get("enabled", True)),
                               str(m.get("created_at", "")), dict(m.get("meta", {})), d))
        except Exception as e:  # noqa: BLE001 — bozuk paket uygulamayı durdurmaz, listede gösterilir
            out.append(Package(d.name, KIND_BROKEN, d.name, False, "", {"error": f"manifest okunamadı: {e}"}, d))
    return out


def _write_manifest(path: Path, manifest: dict) -> None:
    (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


def set_enabled(pkg_id: str, enabled: bool) -> None:
    for p in list_packages():
        if p.id == pkg_id:
            if p.kind == KIND_BROKEN:
                raise ValueError("Okunamayan paket açılamaz; silip yeniden ekleyin.")
            m = json.loads((p.path / "manifest.json").read_text(encoding="utf-8"))
            m["enabled"] = enabled
            _write_manifest(p.path, m)
            if enabled and p.kind == KIND_FACTORS:  # aynı anda tek katsayı paketi etkin
                for q in list_packages():
                    if q.kind == KIND_FACTORS and q.id != pkg_id and q.enabled:
                        set_enabled(q.id, False)
            return
    raise KeyError(pkg_id)


def delete_package(pkg_id: str) -> None:
    for p in list_packages():
        if p.id == pkg_id:
            shutil.rmtree(p.path)
            return
    raise KeyError(pkg_id)


def _slug(text: str) -> str:
    s = norm(text)[:24]
    return s or "paket"


def _new_package(kind: str, name: str, meta: dict) -> tuple[Path, dict]:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:17]
    pkg_id = f"{kind}-{stamp}-{_slug(name)}"
    path = data_dir() / pkg_id
    path.mkdir(parents=True, exist_ok=False)
    manifest = {"id": pkg_id, "kind": kind, "name": name, "enabled": True,
                "created_at": datetime.now().isoformat(timespec="seconds"), "meta": meta}
    return path, manifest


# ------------------------------------------------------------- makine ekleme
@dataclass
class MachineCheck:
    report: Report
    frame: pd.DataFrame | None = None   # Tarih, Saat_No, Saatlik_Tuketim_kWh (kullanılabilir günler)
    days: list[str] = field(default_factory=list)
    profile: list[float] = field(default_factory=list)  # 24 saatlik ortalama
    rows: int = 0


def check_machine_file(path: str | Path, grid_dates: set[str]) -> MachineCheck:
    rep = Report()
    try:
        df = read_table(path)
    except Exception as e:  # noqa: BLE001 — kullanıcıya okunur mesaj
        rep.err(f"Dosya okunamadı: {e}")
        return MachineCheck(rep)
    rows = len(df)
    dh = _date_hour(df)
    kcol = find_col(df, "kwh", "saatliktuketimkwh", "saatliktuketim", "tuketim", "enerji", "consumption")
    power = False
    if kcol is None:  # enerji yoksa güç (kW): saatlik ortalama güç = o saatin enerjisi (kWh)
        kcol = find_col(df, "saatlikortalamaguckw", "ortalamaguc", "guckw", "guc", "kw", "power")
        power = kcol is not None
    if dh is None or kcol is None:
        rep.err("Sütunlar bulunamadı. Beklenen: Tarih, Saat, kWh (ör. 2026-01-01;0;12,40).")
        return MachineCheck(rep, rows=rows)
    dates, hours = dh
    minutes = _minutes(df)
    vals = df[kcol].map(parse_num)
    t = pd.DataFrame({"Tarih": dates, "Saat_No": hours, "Dakika": minutes, "kWh": vals})
    bad_rows = t["Tarih"].isna() | t["Saat_No"].isna()
    if bad_rows.any():
        sample = ", ".join(_fmt_int(i + 2) for i in t.index[bad_rows][:4])
        rep.warn(f"{int(bad_rows.sum())} satırda tarih/saat okunamadı (satır {sample}…) — atlanacak")
    t = t[~bad_rows].copy()
    t["Saat_No"] = t["Saat_No"].astype(int)
    if t.empty:
        rep.err("Okunabilir satır yok.")
        return MachineCheck(rep, rows=rows)

    # Saat altı veri (15 / 30 dk): saatlik toplama çevir
    mins = sorted(set(t["Dakika"]))
    if mins != [0]:
        n = len(mins)
        if 60 % n or mins != list(range(0, 60, 60 // n)):
            rep.err(f"Desteklenmeyen zaman aralığı (dakikalar: {', '.join(map(str, mins[:6]))}). "
                    "Saatlik, 30 veya 15 dakikalık veri kullanın.")
            return MachineCheck(rep, rows=rows)
        grp = t.groupby(["Tarih", "Saat_No"], sort=True)
        agg = grp["kWh"].agg(["count", "sum", "mean"]).reset_index()
        nan_in = grp["kWh"].apply(lambda s: s.isna().any()).reset_index(drop=True)
        complete = (agg["count"] == n) & ~nan_in
        agg["kWh"] = (agg["mean"] if power else agg["sum"]).where(complete)
        t = agg[["Tarih", "Saat_No", "kWh"]]
        how = "saatlik ortalama güç alındı (kWh)" if power else "her saatin enerjisi toplandı (kWh)"
        rep.ok(f"{60 // n} dakikalık veri algılandı; saatliğe çevrildi — {how}")
    elif power:
        rep.ok("Güç (kW) sütunu algılandı; saatlik ortalama güç, o saatin enerjisi (kWh) olarak alındı")

    all_days = sorted(t["Tarih"].unique())
    rep.ok(f"{_fmt_int(len(all_days))} gün okundu · {_fmt_date(all_days[0])} – {_fmt_date(all_days[-1])}")
    usable, skipped, no_grid = [], [], []
    for day, g in t.groupby("Tarih", sort=True):
        hrs = sorted(g["Saat_No"].tolist())
        if hrs != list(range(24)):
            skipped.append((day, f"{len(set(hrs))} saat" + (" (tekrarlı saat)" if len(hrs) != len(set(hrs)) else "")))
        elif g["kWh"].isna().any():
            skipped.append((day, f"{int(g['kWh'].isna().sum())} saat boş"))
        elif (g["kWh"] < 0).any():
            skipped.append((day, "negatif değer"))
        elif day not in grid_dates:
            no_grid.append(day)
        else:
            usable.append(day)
    if skipped:
        sample = "; ".join(f"{_fmt_date(d)} ({r})" for d, r in skipped[:3])
        rep.warn(f"{len(skipped)} gün eksik/hatalı — atlanacak: {sample}{' …' if len(skipped) > 3 else ''}")
    if no_grid:
        rep.warn(f"{len(no_grid)} gün için şebeke verisi yok — atlanacak "
                 f"({_fmt_date(no_grid[0])} – {_fmt_date(no_grid[-1])}). Gerekirse önce o yılı ekleyin.")
    if not usable:
        rep.err("Kullanılabilir gün yok (her gün 24 tekrarsız saat ve şebeke verisi gerekir).")
        return MachineCheck(rep, rows=rows)
    rep.ok(f"{_fmt_int(len(usable))} gün kullanılabilir (her gün 24 saat, tekrarsız, şebeke verisi var)")
    keep = t[t["Tarih"].isin(set(usable))].sort_values(["Tarih", "Saat_No"])
    rep.ok(f"Negatif değer yok · en büyük saatlik değer {keep['kWh'].max():,.2f} kWh"
           .replace(",", "X").replace(".", ",").replace("X", "."))
    profile = keep.groupby("Saat_No")["kWh"].mean().reindex(range(24)).tolist()
    frame = keep.rename(columns={"kWh": "Saatlik_Tuketim_kWh"})[["Tarih", "Saat_No", "Saatlik_Tuketim_kWh"]]
    return MachineCheck(rep, frame, usable, profile, rows)


def add_machine_package(check: MachineCheck, name: str, machine_type: str, shiftable: bool,
                        source: str) -> Package:
    """source: 'sample' (örnek yük) | 'real' (tesis ölçümü)."""
    assert check.frame is not None and not check.report.has_errors
    asset_id = f"u_{_slug(name)[:12]}_{datetime.now().strftime('%H%M%S')}"
    meta = {"machines": 1, "first_day": check.days[0], "last_day": check.days[-1],
            "days": len(check.days), "source": source}
    path, manifest = _new_package(KIND_MACHINE, name, meta)
    f = check.frame.copy()
    f.insert(0, "AssetId", asset_id)
    f["Saatlik_Tuketim_kWh"] = [repr(float(v)) for v in f["Saatlik_Tuketim_kWh"]]
    f.to_csv(path / "loads.csv", index=False, lineterminator="\n")
    machine = {"id": asset_id, "name": name, "type": machine_type or "Kullanıcı makinesi",
               "role": "Esnek_Yuk" if shiftable else "Kayamayan_Kisitli_Yuk", "shiftable": shiftable,
               "first_day": check.days[0], "last_day": check.days[-1], "days": check.days,
               "source": source}
    (path / "machines.json").write_text(json.dumps([machine], ensure_ascii=False, indent=1), encoding="utf-8")
    _write_manifest(path, manifest)
    return Package(manifest["id"], KIND_MACHINE, name, True, manifest["created_at"], meta, path)


def write_machine_template(path: str | Path) -> None:
    rows = ["Tarih;Saat;kWh"]
    for h in range(24):
        rows.append(f"2026-01-01;{h};{12.4 + (h % 6) * 0.5:.2f}".replace(".", ","))
    Path(path).write_text("\n".join(rows) + "\n", encoding="utf-8-sig")


# ---------------------------------------------------------------- şebeke (yıl)
def compute_grid(mwh: pd.DataFrame, factors: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """Kaynak üretimlerinden (MWh) varsayılan asset şemasını üretir.

    mwh: Tarih, Saat_No ve ALL_SOURCES sütunları. Yurtiçi toplam = kaynakların toplamı.
    """
    total = mwh[ALL_SOURCES].sum(axis=1)
    out = pd.DataFrame({"Tarih": mwh["Tarih"], "Saat_No": mwh["Saat_No"]})
    em_t = sum(mwh[s] * factors.get(s, (0.0, 0.0))[0] for s in ALL_SOURCES)
    em_e = sum(mwh[s] * factors.get(s, (0.0, 0.0))[1] for s in ALL_SOURCES)
    out["Karbon_Yogunlugu_tCO2_MWh"] = em_t / total
    out["Karbon_Yogunlugu_tCO2esd_MWh"] = em_e / total
    ren = sum(mwh[s] for s in RENEWABLE) / total * 100
    out["Yenilenebilir_Payi_Yuzde"] = ren
    out["Fosil_Payi_Yuzde"] = 100 - ren
    out["Baskin_Kaynak"] = mwh[ALL_SOURCES].idxmax(axis=1)
    for s in ALL_SOURCES:
        out[f"{s}_Pay_Yuzde"] = mwh[s] / total * 100
    return out


@dataclass
class GridCheck:
    report: Report
    frame: pd.DataFrame | None = None
    days: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)


def check_grid_file(path: str | Path, factors: dict[str, tuple[float, float]],
                    existing_dates: set[str]) -> GridCheck:
    rep = Report()
    try:
        df = read_table(path)
    except Exception as e:  # noqa: BLE001
        rep.err(f"Dosya okunamadı: {e}")
        return GridCheck(rep)
    dh = _date_hour(df)
    if dh is None:
        rep.err("Tarih/saat sütunu bulunamadı (ör. Tarih + Saat).")
        return GridCheck(rep)
    cols: dict[str, str] = {}
    for c in df.columns:
        k = source_key(c)
        if k and k not in cols:
            cols[k] = c
    missing = [SOURCE_NAMES[s] for s in SOURCES if s not in cols]
    if len(missing) > 3:
        rep.err("Kaynak bazında üretim sütunları bulunamadı (Doğal Gaz, Linyit, Rüzgar …). "
                "EPİAŞ Şeffaflık Platformu › Gerçek Zamanlı Üretim dışa aktarımını kullanın.")
        return GridCheck(rep)
    if missing:
        rep.warn("Bulunamayan kaynak sütunları 0 kabul edildi: " + ", ".join(missing))
    rep.ok(f"Biçim tanındı: {len(cols)} kaynak sütunu, {_fmt_int(len(df))} satır")

    dates, hours = dh
    t = pd.DataFrame({"Tarih": dates, "Saat_No": hours})
    neg = 0
    fixed = 0
    for s in ALL_SOURCES:
        if s in cols:
            raw = df[cols[s]].astype(str)
            fixed += int(raw.str.match(r"^\s*-?,\d").sum())  # ',01' / '-,05' yazımları
            v = raw.map(parse_num)
            neg += int((v < 0).sum())
            t[s] = v.clip(lower=0)
        else:
            t[s] = 0.0
    if fixed:
        rep.ok(f"{_fmt_int(fixed)} hücrede eksik sıfırlı ondalık (',01') düzeltildi")
    if neg:
        rep.warn(f"{_fmt_int(neg)} negatif üretim değeri (gece güneş iç tüketimi vb.) 0 yapıldı")
    bad = t["Tarih"].isna() | t["Saat_No"].isna() | t[ALL_SOURCES].isna().any(axis=1)
    if bad.any():
        rep.warn(f"{int(bad.sum())} satır okunamadı — atlanacak")
    t = t[~bad].copy()
    if t.empty:
        rep.err("Okunabilir satır yok.")
        return GridCheck(rep)
    t["Saat_No"] = t["Saat_No"].astype(int)
    usable, skipped = [], []
    for day, g in t.groupby("Tarih", sort=True):
        hrs = sorted(g["Saat_No"].tolist())
        (usable if hrs == list(range(24)) and g[ALL_SOURCES].sum(axis=1).gt(0).all() else skipped).append(day)
    if skipped:
        rep.warn(f"{len(skipped)} gün eksik/tekrarlı saatli — atlanacak (ör. {_fmt_date(skipped[0])})")
    if not usable:
        rep.err("Tam 24 saati olan gün yok.")
        return GridCheck(rep)
    t = t[t["Tarih"].isin(set(usable))].sort_values(["Tarih", "Saat_No"]).reset_index(drop=True)
    grid = compute_grid(t, factors)
    years = sorted({int(d[:4]) for d in usable})
    rep.ok(f"{_fmt_int(len(usable))} tam gün · {_fmt_int(len(t))} saat · "
           f"{_fmt_date(usable[0])} – {_fmt_date(usable[-1])}")
    ci = grid["Karbon_Yogunlugu_tCO2_MWh"]
    rep.ok(f"Karbon yoğunluğu (tCO2/MWh): en düşük {ci.min():.3f} · ortalama {ci.mean():.3f} · "
           f"en yüksek {ci.max():.3f}".replace(".", ","))
    overlap = sorted(set(usable) & existing_dates)
    if overlap:
        rep.warn(f"{len(overlap)} gün mevcut veriyle çakışıyor; bu paket etkinken yeni veri kullanılır.")
    return GridCheck(rep, grid, usable, years)


def add_grid_package(check: GridCheck, name: str) -> Package:
    assert check.frame is not None and not check.report.has_errors
    meta = {"years": check.years, "first_day": check.days[0], "last_day": check.days[-1],
            "days": len(check.days), "hours": len(check.frame)}
    path, manifest = _new_package(KIND_GRID, name, meta)
    f = check.frame.copy()
    for c in f.columns:
        if c not in ("Tarih", "Saat_No", "Baskin_Kaynak"):
            f[c] = [repr(float(v)) for v in f[c]]
    f.to_csv(path / "epias.csv", index=False, lineterminator="\n")
    _write_manifest(path, manifest)
    return Package(manifest["id"], KIND_GRID, name, True, manifest["created_at"], meta, path)


# ------------------------------------------------------------ emisyon katsayıları
@dataclass
class FactorsCheck:
    report: Report
    factors: dict[str, tuple[float, float]] = field(default_factory=dict)


def check_factors_file(path: str | Path, current: dict[str, tuple[float, float]]) -> FactorsCheck:
    rep = Report()
    try:
        df = read_table(path)
    except Exception as e:  # noqa: BLE001
        rep.err(f"Dosya okunamadı: {e}")
        return FactorsCheck(rep)
    tcol = find_col(df, "emisyonfaktorutco2", "tco2", "co2")
    ecol = find_col(df, "emisyonfaktorutco2esd", "tco2esd", "tco2eşd", "co2esd", "esdeger")
    if ecol == tcol:
        ecol = None
    if tcol is None:
        rep.err("tCO2/MWh sütunu bulunamadı (ör. Kaynak; tCO2/MWh; tCO2-eşd/MWh).")
        return FactorsCheck(rep)
    name_cols = [c for c in df.columns if c not in (tcol, ecol)]
    factors: dict[str, tuple[float, float]] = {}
    unknown = []
    for _, row in df.iterrows():
        key = None
        for c in name_cols:
            key = source_key(row[c])
            if key:
                break
        t = parse_num(row[tcol])
        e = parse_num(row[ecol]) if ecol else t
        if key is None:
            label = next((str(row[c]) for c in name_cols if str(row[c]).strip()), "?")
            unknown.append(label)
            continue
        if t != t or t < 0 or (e != e) or e < 0:
            rep.err(f"{SOURCE_NAMES[key]} için geçersiz katsayı.")
            continue
        factors[key] = (t, e)
    if unknown:
        rep.warn("Tanınmayan satırlar atlandı: " + ", ".join(unknown[:5]))
    missing = [SOURCE_NAMES[s] for s in REQUIRED_FOSSIL if s not in factors]
    if missing:
        rep.err("Eksik fosil kaynak katsayısı: " + ", ".join(missing))
    for s in ALL_SOURCES:
        factors.setdefault(s, current.get(s, (0.0, 0.0)) if s not in RENEWABLE else (0.0, 0.0))
    changed = [s for s in ALL_SOURCES if abs(factors[s][0] - current.get(s, (0, 0))[0]) > 1e-12]
    rep.ok(f"{len([s for s in ALL_SOURCES if s in factors])} kaynak katsayısı okundu")
    if changed:
        rep.ok("Değişen: " + ", ".join(
            f"{SOURCE_NAMES[s]} {current.get(s, (0, 0))[0]:g} → {factors[s][0]:g}".replace(".", ",") for s in changed))
    else:
        rep.warn("Katsayılar mevcut değerlerle aynı; sonuçlar değişmez.")
    return FactorsCheck(rep, factors)


def add_factors_package(check: FactorsCheck, name: str) -> Package:
    assert not check.report.has_errors
    meta = {"label": name}
    path, manifest = _new_package(KIND_FACTORS, name, meta)
    rows = ["Kaynak;Emisyon_Faktoru_tCO2_MWh;Emisyon_Faktoru_tCO2esd_MWh;Kategori"]
    for s in ALL_SOURCES:
        t, e = check.factors[s]
        cat = "Yenilenebilir / Sıfır Doğrudan Yakıt Emisyonu" if s in RENEWABLE else "Fosil"
        rows.append(f"{SOURCE_NAMES[s]};{t!r};{e!r};{cat}")
    (path / "factors.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    _write_manifest(path, manifest)
    for q in list_packages():  # yeni katsayı paketi tek etkin paket olur
        if q.kind == KIND_FACTORS and q.id != manifest["id"] and q.enabled:
            set_enabled(q.id, False)
    return Package(manifest["id"], KIND_FACTORS, name, True, manifest["created_at"], meta, path)


def read_factors_csv(path: Path) -> dict[str, tuple[float, float]]:
    df = read_table(path)
    out = {}
    for _, row in df.iterrows():
        k = source_key(row.iloc[0])
        if k:
            out[k] = (parse_num(row.iloc[1]), parse_num(row.iloc[2]))
    return out
