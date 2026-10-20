"""AI açıklamalarına giden yardımcı istatistikler (deterministik, emisyon formülü değil).

Buradaki sayılar LLM'e girdi olarak gönderilir; LLM yalnızca bunları kullanabilir.
"""
from __future__ import annotations

from collections import Counter

from engine import data

TOP_SOURCES = 3


def window_mix(date: str, hours: list[int], kind: str = "tCO2") -> dict:
    """Bir pencerenin ortalama karbon yoğunluğu ve üretim karışımı."""
    if not hours:
        return {}
    ci = data.ci_24(date, kind)
    mixes = [data.mix_at(date, h) for h in hours]
    n = len(hours)
    shares: dict[str, float] = {}
    for m in mixes:
        for src, v in m["shares"].items():
            shares[src] = shares.get(src, 0.0) + v / n
    top = sorted(shares.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_SOURCES]
    dominant = Counter(m["dominant"] for m in mixes).most_common(1)[0][0]
    return {
        "ci_avg": sum(ci[h] for h in hours) / n,
        "renewable_pct_avg": sum(m["renewable_pct"] for m in mixes) / n,
        "dominant": dominant,
        "top_sources": [{"source": s, "share_pct": v} for s, v in top],
    }


def compare(delta_a: float | None, delta_b: float | None) -> dict:
    """İki senaryonun ana yüzdelerini kıyaslar. Eksi yönde olan daha iyidir."""
    if delta_a is None or delta_b is None:
        return {"better": None, "diff_points": None}
    if delta_a == delta_b:
        return {"better": "equal", "diff_points": 0.0}
    better = "a" if delta_a < delta_b else "b"
    return {"better": better, "diff_points": abs(delta_a - delta_b)}


def season_profile(source_hours: list[int], target_hours: list[int],
                   kind: str = "tCO2") -> dict:
    """Aynı saatlerin 2025 aylık ortalama karbon yoğunluğu (yükten bağımsız).

    Her ay için standart ve seçilen pencerenin ortalama CI'si ve yüzde farkı.
    """
    by_month: dict[str, list[tuple[float, float]]] = {}
    for date in data.all_dates():
        ci = data.ci_24(date, kind)
        src = sum(ci[h] for h in source_hours) / len(source_hours)
        tgt = sum(ci[h] for h in target_hours) / len(target_hours)
        by_month.setdefault(date[:7], []).append((src, tgt))
    months = []
    for month in sorted(by_month):
        vals = by_month[month]
        src = sum(v[0] for v in vals) / len(vals)
        tgt = sum(v[1] for v in vals) / len(vals)
        months.append({"month": month, "source_ci_avg": src, "target_ci_avg": tgt,
                       "diff_pct": (tgt - src) / src * 100})
    better = [m for m in months if m["diff_pct"] < 0]
    best = min(months, key=lambda m: m["diff_pct"])
    worst = max(months, key=lambda m: m["diff_pct"])
    return {
        "months": months,
        "better_month_count": len(better),
        "worse_month_count": len(months) - len(better),
        "best_month": best["month"],
        "best_month_diff_pct": best["diff_pct"],
        "worst_month": worst["month"],
        "worst_month_diff_pct": worst["diff_pct"],
    }
