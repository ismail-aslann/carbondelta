"""Ekran biçimlendirme — yuvarlama yalnızca burada (2 ondalık, Türkçe virgül)."""
from __future__ import annotations

MINUS = "−"


def num(v: float, digits: int = 2) -> str:
    s = f"{abs(v):,.{digits}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    if round(v, digits) < 0:
        return MINUS + s
    return s


def signed(v: float, digits: int = 2) -> str:
    if round(v, digits) > 0:
        return "+" + num(v, digits)
    return num(v, digits)


def pct(v: float | None, digits: int = 2) -> str:
    return "—" if v is None else f"{signed(v, digits)} %"


def hour(h: int) -> str:
    return f"{h:02d}:00"


def window(start: int, length: int) -> str:
    return f"{hour(start)}–{hour(start + length)}"


def date(iso: str) -> str:
    """2025-07-15 → 15.07.2025"""
    y, m, d = iso[:10].split("-")
    return f"{d}.{m}.{y}"


def datetime(iso: str) -> str:
    """2026-10-20T11:03:03 → 20.10.2026 11:03"""
    return f"{date(iso)} {iso[11:16]}" if len(iso) >= 16 else date(iso)
