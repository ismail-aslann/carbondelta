"""Başlangıç ekranı: logo, son senaryo kartı ve bölüm listesi (koyu tema)."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from desktop import delti, fmt
from desktop.resources import resource_path
from engine.appinfo import APP_NAME, DEFAULT_APP_NAME

BG_CENTER = "#0d4a3d"
BG_EDGE = "#062720"
MINT = "#5fe0b0"
TEXT = "#f2fbf7"
MUTED = "#9fc4b7"
PEAK = "#ff8a7a"
PANEL_WIDTH = 390

_SVG = {
    "chart": '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    "chat": '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "doc": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 11h8M8 15h5"/>',
    "book": '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5V5.5"/>'
            '<path d="M9 8h7M9 12h5"/>',
    "dbplus": '<ellipse cx="11" cy="6" rx="7" ry="3"/><path d="M4 6v6c0 1.7 3.1 3 7 3"/>'
              '<path d="M4 12v6c0 1.7 3.1 3 7 3"/><path d="M18 6v4"/><path d="M19 15v6M16 18h6"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "db": '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/>'
          '<path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "year": '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/>'
            '<path d="M7 17v-3M11 17v-5M15 17v-2"/>',
    "play": None,
}

# (anahtar, başlık, alt yazı, ikon)
ITEMS = [
    ("new", "Yeni senaryo", "Yük kaydırmayı hesapla", "chart"),
    ("best", "En temiz saat", "Otomatik öneri", "search"),
    ("annual", "Yıllık etki", "Bir yılda kaç ton CO₂", "year"),
    ("nl", "Delti'ye sor", "Yazarak senaryo kur", "delti"),
    ("history", "Geçmiş", "Kayıtlı senaryolar", "clock"),
    ("calc", "Hesap dökümü", "Formül ve tablolar", "doc"),
    ("data", "Veri yönetimi", "Makine · yıl · katsayı ekle", "dbplus"),
    ("guide", "Kullanma kılavuzu", "Her şey adım adım · F1", "book"),
    ("sources", "Kaynaklar", "EPİAŞ · ETKB · Zenodo", "db"),
    ("contact", "İletişim", "Geliştiriciler ve danışman", "mail"),
]

STYLE = f"""
QWidget#start {{ background: transparent; }}
QWidget#start QLabel {{ background: transparent; color: {TEXT}; }}
QWidget#start QLabel#startTitle {{ font-size: 28pt; font-weight: 700; }}
QWidget#start QLabel#startTagline {{ color: {MUTED}; font-size: 11pt; }}
QWidget#start QLabel#small {{ color: {MUTED}; font-size: 8pt; letter-spacing: 1px; }}
QWidget#start QLabel#sub {{ color: {MUTED}; font-size: 9pt; }}
QWidget#start QLabel#rowTitle {{ font-size: 10.5pt; font-weight: 600; }}
QWidget#start QLabel#resumeText {{ font-size: 10.5pt; font-weight: 600; }}
QWidget#start QLabel#hint, QWidget#start QLabel#foot {{ color: {MUTED}; font-size: 8.5pt; }}
QFrame#resume {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(95,224,176,0.22), stop:1 rgba(95,224,176,0.07));
    border: 1px solid rgba(95,224,176,0.40); border-radius: 12px;
}}
QFrame#resume:hover {{ border-color: {MINT}; }}
QFrame#resume[sel="true"] {{ border: 2px solid {MINT}; }}
QFrame#list {{ background: rgba(4,30,24,0.62); border: 1px solid rgba(255,255,255,0.10); border-radius: 12px; }}
QFrame#row {{ background: transparent; border: none; border-left: 3px solid transparent; }}
QFrame#row[sep="true"] {{ border-top: 1px solid rgba(255,255,255,0.09); }}
QFrame#row[sel="true"] {{ background: rgba(255,255,255,0.08); border-left: 3px solid {MINT}; }}
QWidget#start QLabel#rowIcon {{ background: rgba(95,224,176,0.14); border-radius: 8px; }}
"""


def svg_pixmap(name: str, size: int, color: str, dpr: float) -> QPixmap:
    body = _SVG[name]
    if body is None:  # oynat üçgeni (dolu)
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" fill="{color}"/></svg>'
    else:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
               f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.fill(Qt.transparent)
    p = QPainter(px)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    px.setDevicePixelRatio(dpr)
    return px


class _Clickable(QFrame):
    clicked = Signal()
    hovered = Signal()

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setObjectName(name)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, e):
        self.hovered.emit()
        super().enterEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class StartScreen(QWidget):
    """Koyu zemin üzerinde logo, son senaryo kartı ve 6 bölümlük liste."""

    action = Signal(str)  # ITEMS anahtarı veya "resume"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("start")
        self.setStyleSheet(STYLE)
        self.setFocusPolicy(Qt.StrongFocus)
        self._curve: list[float] = []
        self._sel = 0
        dpr = self.devicePixelRatioF() or 1.0

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 0, 20, 10)
        root.addStretch(1)

        col = QVBoxLayout()
        col.setSpacing(0)
        col.setAlignment(Qt.AlignHCenter)

        logo = QLabel()
        icon = resource_path("desktop/icon.png")
        if icon.exists():
            logo.setPixmap(QIcon(str(icon)).pixmap(64, 64))
        logo.setAlignment(Qt.AlignCenter)
        glow = QGraphicsDropShadowEffect(logo)
        glow.setBlurRadius(46)
        glow.setOffset(0, 8)
        glow.setColor(QColor(95, 224, 176, 110))
        logo.setGraphicsEffect(glow)
        col.addWidget(logo, 0, Qt.AlignHCenter)
        col.addSpacing(8)

        title = QLabel(f"Carbon<span style='color:{MINT}'>Delta</span>")
        title.setObjectName("startTitle")
        title.setAlignment(Qt.AlignCenter)
        col.addWidget(title, 0, Qt.AlignHCenter)
        tagline = QLabel("Aynı iş, daha temiz saat.")
        tagline.setObjectName("startTagline")
        tagline.setAlignment(Qt.AlignCenter)
        col.addWidget(tagline, 0, Qt.AlignHCenter)
        if APP_NAME != DEFAULT_APP_NAME:
            # Deneme/geliştirme kopyası ana uygulamayla karışmasın.
            badge = QLabel(APP_NAME.replace(DEFAULT_APP_NAME, "").strip().upper() + " SÜRÜMÜ")
            badge.setStyleSheet(f"color: #1b1b1b; background: #ffd166; border-radius: 9px; padding: 2px 12px;"
                                " font-size: 8.5pt; font-weight: 700; letter-spacing: 1px;")
            col.addWidget(badge, 0, Qt.AlignHCenter)
        col.addSpacing(12)

        # Son senaryo kartı
        self.resume = _Clickable("resume")
        self.resume.setFixedWidth(PANEL_WIDTH)
        rl = QHBoxLayout(self.resume)
        rl.setContentsMargins(14, 10, 14, 10)
        rl.setSpacing(12)
        play = QLabel()
        play.setFixedSize(32, 32)
        play.setAlignment(Qt.AlignCenter)
        play.setStyleSheet(f"background: {MINT}; border-radius: 16px;")
        play.setPixmap(svg_pixmap("play", 14, "#063a2e", dpr))
        rl.addWidget(play)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        self.resume_small = QLabel("SON SENARYO")
        self.resume_small.setObjectName("small")
        self.resume_text = QLabel("")
        self.resume_text.setObjectName("resumeText")
        texts.addWidget(self.resume_small)
        texts.addWidget(self.resume_text)
        rl.addLayout(texts, 1)
        self.resume_delta = QLabel("")
        self.resume_delta.setStyleSheet(f"color: {MINT}; font-size: 14pt; font-weight: 700;")
        rl.addWidget(self.resume_delta)
        self.resume.clicked.connect(lambda: self.action.emit("resume"))
        self.resume.hovered.connect(lambda: self._select(-1))
        col.addWidget(self.resume, 0, Qt.AlignHCenter)
        col.addSpacing(8)

        # Bölüm listesi
        lst = QFrame()
        lst.setObjectName("list")
        lst.setAttribute(Qt.WA_StyledBackground, True)
        lst.setFixedWidth(PANEL_WIDTH)
        ll = QVBoxLayout(lst)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        self.rows: list[_Clickable] = []
        for n, (key, title_text, sub_text, icon_name) in enumerate(ITEMS):
            row = _Clickable("row")
            row.setProperty("sep", n > 0)
            hl = QHBoxLayout(row)
            hl.setContentsMargins(12, 6, 14, 6)
            hl.setSpacing(12)
            ico = QLabel()
            ico.setObjectName("rowIcon")
            ico.setFixedSize(32, 32)
            ico.setAlignment(Qt.AlignCenter)
            if icon_name == "delti":
                ico.setStyleSheet("background: transparent;")
                ico.setPixmap(delti.pixmap("ready", 32, dpr))
            else:
                ico.setPixmap(svg_pixmap(icon_name, 18, MINT, dpr))
            hl.addWidget(ico)
            tv = QVBoxLayout()
            tv.setSpacing(0)
            t = QLabel(title_text)
            t.setObjectName("rowTitle")
            s = QLabel(sub_text)
            s.setObjectName("sub")
            tv.addWidget(t)
            tv.addWidget(s)
            hl.addLayout(tv, 1)
            row.clicked.connect(lambda k=key: self.action.emit(k))
            row.hovered.connect(lambda i=n: self._select(i))
            ll.addWidget(row)
            self.rows.append(row)
        col.addWidget(lst, 0, Qt.AlignHCenter)
        col.addSpacing(10)

        hint = QLabel("↑ ↓ seç  ·  Enter aç  ·  F1 kılavuz  ·  Esc ana sayfa")
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        col.addWidget(hint, 0, Qt.AlignHCenter)

        root.addLayout(col)
        root.addStretch(1)

        foot = QHBoxLayout()
        left = QLabel("Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo")
        left.setObjectName("foot")
        foot.addWidget(left, 1)
        self.status = QLabel("")
        self.status.setObjectName("foot")
        self.status.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        self.status.linkActivated.connect(lambda _l: self.action.emit("delti_settings"))
        foot.addWidget(self.status)
        root.addLayout(foot)

        self._select(0)

    # --------------------------------------------------------------- veri
    def set_curve(self, ci: list[float]) -> None:
        self._curve = list(ci)
        self.update()

    def set_resume(self, small: str, text: str, delta: str, good: bool) -> None:
        self.resume_small.setText(small.upper())
        self.resume_text.setText(text)
        self.resume_delta.setText(delta)
        color = MINT if good else "#ff9a8a"
        self.resume_delta.setStyleSheet(f"color: {color}; font-size: 14pt; font-weight: 700;")

    def set_status(self, ai_online: bool, machine_count: int) -> None:
        dot = MINT if ai_online else "#8aa39a"
        ai = "Delti (AI) çevrimiçi" if ai_online else "Delti (AI) uyuyor"
        link = "ayarlar" if ai_online else "uyandır"
        self.status.setText(f"<span style='color:{dot}'>●</span> {ai} "
                            f"(<a href='delti' style='color:{MINT};'>{link}</a> · Ctrl+,)   ·   "
                            f"{machine_count} makine   ·   İnternetsiz hesap")

    # ---------------------------------------------------------- seçim/klavye
    def _select(self, i: int) -> None:
        """-1 = son senaryo kartı, 0.. = liste satırları (döngüsel)."""
        n = len(self.rows)
        self._sel = (i + 1) % (n + 1) - 1
        for k, row in enumerate([self.resume] + self.rows, start=-1):
            row.setProperty("sel", k == self._sel)
            row.style().unpolish(row)
            row.style().polish(row)

    def _activate(self) -> None:
        self.action.emit("resume" if self._sel < 0 else ITEMS[self._sel][0])

    def keyPressEvent(self, e) -> None:
        key = e.key()
        if key == Qt.Key_Down:
            self._select(self._sel + 1)
        elif key == Qt.Key_Up:
            self._select(self._sel - 1)
        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self._activate()
        elif Qt.Key_1 <= key < Qt.Key_1 + min(len(ITEMS), 9):
            self._select(key - Qt.Key_1)
            self._activate()
        else:
            super().keyPressEvent(e)

    def focusNextPrevChild(self, _next: bool) -> bool:
        """Tab da ↑ ↓ gibi davranır; odak başlangıç ekranından kaçmaz."""
        self._select(self._sel + (1 if _next else -1))
        return True

    # -------------------------------------------------------------- çizim
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Zemin: üst ortada açık, kenarlara doğru koyu
        bg = QRadialGradient(QPointF(w / 2, 0), max(w, h) * 0.85)
        bg.setColorAt(0.0, QColor(BG_CENTER))
        bg.setColorAt(0.75, QColor(BG_EDGE))
        bg.setColorAt(1.0, QColor(BG_EDGE))
        p.fillRect(self.rect(), bg)

        # Izgara: ortada belirgin, kenarlarda kaybolur
        fade = QRadialGradient(QPointF(w / 2, h * 0.4), max(w, h) * 0.62)
        fade.setColorAt(0.0, QColor(255, 255, 255, 26))
        fade.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(QPen(QBrush(fade), 1))
        step = 60
        for x in range(0, w + 1, step):
            p.drawLine(x, 0, x, h)
        for y in range(0, h + 1, step):
            p.drawLine(0, y, w, y)

        # 24 saatlik karbon yoğunluğu eğrisi
        if len(self._curve) == 24:
            ci = self._curve
            lo, hi = min(ci), max(ci)
            span = (hi - lo) or 1.0
            top, bottom = h * 0.52, h * 0.88
            pts = [QPointF(40 + i * (w - 80) / 23, bottom - (v - lo) / span * (bottom - top))
                   for i, v in enumerate(ci)]
            area = QPainterPath(QPointF(pts[0].x(), h))
            for pt in pts:
                area.lineTo(pt)
            area.lineTo(QPointF(pts[-1].x(), h))
            area.closeSubpath()
            fill = QLinearGradient(0, top, 0, h)
            fill.setColorAt(0, QColor(95, 224, 176, 30))
            fill.setColorAt(1, QColor(95, 224, 176, 0))
            p.fillPath(area, fill)
            line = QPainterPath(pts[0])
            for pt in pts[1:]:
                line.lineTo(pt)
            p.setPen(QPen(QColor(95, 224, 176, 125), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(line)

            f = QFont(self.font())
            f.setPointSizeF(8.5)
            p.setFont(f)
            hmax = max(range(24), key=lambda i: ci[i])
            hmin = min(range(24), key=lambda i: ci[i])
            for hour, color, label, above in ((hmax, PEAK, "en kirli", True), (hmin, MINT, "en temiz", False)):
                pt = pts[hour]
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(color))
                p.drawEllipse(pt, 4.5, 4.5)
                p.setPen(QColor(color).lighter(115))
                text = f"{fmt.hour(hour)} · {label}"
                if above:
                    r = QRectF(pt.x() - 170, pt.y() - 22, 160, 16)
                    p.drawText(r, Qt.AlignRight | Qt.AlignVCenter, text)
                else:
                    r = QRectF(pt.x() - 80, pt.y() + 8, 160, 16)
                    p.drawText(r, Qt.AlignHCenter | Qt.AlignVCenter, text)
        p.end()
