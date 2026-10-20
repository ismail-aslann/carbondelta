"""Delti: CarbonDelta'nın AI yardımcısı maskotu (SVG'den çizilir).

Halleri: "ready" (hazır), "think" (AI metni hazırlanıyor), "sleep" (çevrimdışı).
Delti hesap yapmaz; motorun sonuçlarını açıklar ve cümleleri senaryoya çevirir.
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

NAME = "Delti"

_DEFS = """
<defs>
  <linearGradient id="body" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#7cf0c4"/><stop offset="1" stop-color="#2fb487"/>
  </linearGradient>
</defs>
"""
_BODY = """
<path d="M53 6 C60 2 70 3 74 9 C66 9 60 12 56 18 Z" fill="#2fb487"/>
<path d="M53 18 C53 12 53 8 53 6" stroke="#1e8f69" stroke-width="2.4" stroke-linecap="round" fill="none"/>
<path d="M50 16 C53 16 55 17.5 56.8 20.6 L91 81 C93.6 85.6 90.6 91 85.4 91 H14.6 C9.4 91 6.4 85.6 9 81 L43.2 20.6 C45 17.5 47 16 50 16 Z" fill="url(#body)"/>
<path d="M50 16 C53 16 55 17.5 56.8 20.6 L91 81 C93.6 85.6 90.6 91 85.4 91 H14.6 C9.4 91 6.4 85.6 9 81 L43.2 20.6 C45 17.5 47 16 50 16 Z" fill="none" stroke="#0f5b46" stroke-opacity=".25" stroke-width="2"/>
<ellipse cx="31" cy="72" rx="4.5" ry="2.6" fill="#ff9a8a" opacity=".55"/>
<ellipse cx="69" cy="72" rx="4.5" ry="2.6" fill="#ff9a8a" opacity=".55"/>
"""
_EYES_OPEN = """
<ellipse cx="40" cy="60" rx="5.2" ry="6.4" fill="#0b3d33"/>
<ellipse cx="60" cy="60" rx="5.2" ry="6.4" fill="#0b3d33"/>
<circle cx="41.6" cy="57.8" r="1.7" fill="#fff"/><circle cx="61.6" cy="57.8" r="1.7" fill="#fff"/>
"""
_FACES = {
    "ready": _EYES_OPEN + '<path d="M42 72 Q50 79 58 72" stroke="#0b3d33" stroke-width="3.4" stroke-linecap="round" fill="none"/>',
    "think": _EYES_OPEN + '<path d="M44 74 H56" stroke="#0b3d33" stroke-width="3.4" stroke-linecap="round"/>'
             '<circle cx="80" cy="32" r="3" fill="#9fc4b7"/><circle cx="88" cy="22" r="4" fill="#9fc4b7"/>',
    "sleep": '<path d="M35 61 Q40 64 45 61 M55 61 Q60 64 65 61" stroke="#0b3d33" stroke-width="3" stroke-linecap="round" fill="none"/>'
             '<path d="M44 74 Q50 77 56 74" stroke="#0b3d33" stroke-width="3" stroke-linecap="round" fill="none"/>'
             '<text x="72" y="40" font-size="14" font-weight="700" fill="#8aa39a" font-family="Segoe UI">z</text>'
             '<text x="81" y="29" font-size="10" font-weight="700" fill="#8aa39a" font-family="Segoe UI">z</text>',
}


def svg(state: str = "ready") -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            f'{_DEFS}{_BODY}{_FACES[state]}</svg>')


@lru_cache(maxsize=32)
def _render(state: str, px: int) -> QPixmap:
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(svg(state).encode())).render(p)
    p.end()
    return pm


def pixmap(state: str = "ready", size: int = 32, dpr: float = 1.0) -> QPixmap:
    pm = QPixmap(_render(state, int(round(size * dpr))))
    pm.setDevicePixelRatio(dpr)
    return pm


# Kaynak türüne göre Delti hali
STATE_FOR_SOURCE = {
    "ai": "ready",
    "local": "ready",
    "pending": "think",
    "fallback_offline": "sleep",
    "fallback_invalid": "ready",
}
