"""Otomatik pencere önerisi — deterministik tarama, AI yok."""
from __future__ import annotations

from engine.core import HOURS, OK, SAME_WINDOW, Result, simulate


def scan_windows(load_kwh: list[float], ci: list[float], s: int, L: int, p: float,
                 restricted: set[int] = frozenset(),
                 shiftable: bool = True) -> list[tuple[int, Result]]:
    """t = 0..24-L içindeki geçerli hedef pencereler, t sırasıyla."""
    out: list[tuple[int, Result]] = []
    for t in range(0, HOURS - L + 1):
        r = simulate(load_kwh, ci, s, L, t, p, restricted, shiftable)
        # same_window, B == 0 iken de dönebilir; yük yoksa öneri yok.
        if r.status not in (OK, SAME_WINDOW) or r.baseline_kg == 0.0:
            continue
        out.append((t, r))
    return out


def best_window(load_kwh: list[float], ci: list[float], s: int, L: int, p: float,
                restricted: set[int] = frozenset(),
                shiftable: bool = True) -> tuple[int, Result] | None:
    """Geçerli pencerelerden en düşük S'yi döndürür.

    Eşitlikte en küçük t kazanır. Geçerli pencere yoksa (kaydırılamaz, aralık dışı,
    yük yok veya tüm hedefler kısıtlı) None.
    """
    best: tuple[int, Result] | None = None
    for t, r in scan_windows(load_kwh, ci, s, L, p, restricted, shiftable):
        if best is None or r.scenario_kg < best[1].scenario_kg:
            best = (t, r)
    return best
