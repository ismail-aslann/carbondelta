"""Delti'ye Sor: sohbet ekranı (mesaj geçmişi, öneri düğmeleri, ön izlemelerde ‘Senaryoya uygula’)."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from desktop import delti, theme
from desktop.delti_chat import SUGGESTIONS

SOURCE_TAGS = {"ai": "AI", "local": "", "preview": "Ön izleme · motor hesabı",
               "fallback_offline": "Hazır cevap (Delti çevrimdışı)", "fallback_invalid": "Hazır cevap (doğrulanamadı)",
               "pending": "Düşünüyor…"}


def _to_html(text: str) -> str:
    return html.escape(text).replace("\n", "<br>")


class _Bubble(QFrame):
    def __init__(self, mine: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("bubbleMine" if mine else "bubbleDelti")
        self.setAttribute(Qt.WA_StyledBackground, True)
        bg, border = (theme.PRIMARY_SOFT, "#cfe5dc") if mine else ("#ffffff", theme.BORDER)
        self.setStyleSheet(f"QFrame#{self.objectName()} {{ background: {bg}; border: 1px solid {border};"
                           " border-radius: 12px; }")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(12, 9, 12, 9)
        self.lay.setSpacing(6)
        self.text = QLabel("")
        self.text.setWordWrap(True)
        self.text.setTextFormat(Qt.RichText)
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.text.setStyleSheet("background: transparent; font-size: 10.5pt; line-height: 140%;")
        self.lay.addWidget(self.text)
        self.tag = QLabel("")
        self.tag.setStyleSheet(f"background: transparent; color: {theme.MUTED}; font-size: 8pt;")
        self.tag.hide()
        self.lay.addWidget(self.tag)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(6)
        self.lay.addLayout(self.actions)


class ChatTab(QWidget):
    submit = Signal(str)               # kullanıcı mesajı (ana pencere niyete göre yanıtlar)
    apply_requested = Signal(dict)     # ön izlemedeki senaryoyu uygula
    settings_requested = Signal()      # Delti ayarları

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dpr = self.devicePixelRatioF() or 1.0
        self._bubbles: dict[int, _Bubble] = {}
        self._next_id = 0
        self._merged: dict | None = None   # son ön izleme (testler ve kısayol için)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 12, 0, 0)
        root.setSpacing(10)
        root.setAlignment(Qt.AlignHCenter)

        card, lay = theme.card(margins=(20, 14, 20, 14), spacing=10)
        card.setMaximumWidth(900)
        card.setMinimumWidth(640)
        top = QHBoxLayout()
        top.setSpacing(12)
        self.avatar = QLabel()
        self.avatar.setFixedSize(48, 48)
        self.avatar.setPixmap(delti.pixmap("ready", 48, self._dpr))
        top.addWidget(self.avatar)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        t = QLabel("Delti'ye sor")
        t.setStyleSheet("font-size: 15pt; font-weight: 700;")
        titles.addWidget(t)
        titles.addWidget(theme.muted("Uygulama hakkında sorun ya da “şöyle yaparsak ne olur?” diye deneyin."))
        top.addLayout(titles, 1)
        clear = QPushButton("Yeni sohbet")
        clear.setToolTip("Sohbet geçmişini temizler")
        clear.clicked.connect(self.clear)
        top.addWidget(clear, 0, Qt.AlignTop)
        gear = QPushButton("⚙ Ayarlar")
        gear.setToolTip("Delti ayarları: yapay zekâ sağlayıcısı ve API anahtarı (Ctrl+,)")
        gear.clicked.connect(self.settings_requested)
        top.addWidget(gear, 0, Qt.AlignTop)
        lay.addLayout(top)

        # Anahtar yoksa: Delti uyuyor uyarısı
        self.sleep_bar = QWidget()
        sl = QHBoxLayout(self.sleep_bar)
        sl.setContentsMargins(12, 7, 8, 7)
        msg = QLabel("<b>Delti uyuyor.</b> AI anahtarı girilmemiş; hazır cevaplar ve ön izleme çalışır. "
                     "Daha ayrıntılı sohbet için anahtarınızı girin.")
        msg.setWordWrap(True)
        msg.setStyleSheet(f"color: {theme.WARN}; background: transparent;")
        sl.addWidget(msg, 1)
        wake = QPushButton("Delti'yi uyandır")
        wake.setObjectName("primary")
        wake.clicked.connect(self.settings_requested)
        sl.addWidget(wake, 0, Qt.AlignVCenter)
        self.sleep_bar.setObjectName("sleepBar")
        self.sleep_bar.setStyleSheet(f"QWidget#sleepBar {{ background: {theme.WARN_SOFT}; border: 1px solid #f0d9a8;"
                                     " border-radius: 10px; }")
        self.sleep_bar.setAttribute(Qt.WA_StyledBackground, True)
        lay.addWidget(self.sleep_bar)

        # Mesajlar
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setMinimumHeight(220)
        inner = QWidget()
        self.msgs = QVBoxLayout(inner)
        self.msgs.setContentsMargins(0, 4, 6, 4)
        self.msgs.setSpacing(10)
        self.msgs.addStretch(1)
        self.scroll.setWidget(inner)
        # Yeni mesaj eklenip içerik büyüdükçe en alta kay (yerleşim sonradan tamamlansa da).
        self._stick = True
        bar = self.scroll.verticalScrollBar()
        bar.rangeChanged.connect(lambda _lo, hi: bar.setValue(hi) if self._stick else None)
        bar.valueChanged.connect(lambda v: setattr(self, "_stick", v >= bar.maximum() - 4))
        lay.addWidget(self.scroll, 1)

        # Öneriler
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_buttons = []
        for ex in SUGGESTIONS:
            b = QPushButton(ex)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ border-radius: 12px; padding: 3px 10px; font-size: 8.5pt;"
                            f" background: {theme.PRIMARY_SOFT}; border: 1px solid #cfe5dc; color: {theme.PRIMARY_DARK}; }}"
                            f"QPushButton:hover {{ border-color: {theme.PRIMARY}; }}")
            b.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            b.clicked.connect(lambda _c=False, e=ex: self.send(e))
            chips.addWidget(b)
            self.chip_buttons.append(b)
        chips.addStretch(1)
        lay.addLayout(chips)

        row = QHBoxLayout()
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Bir soru yazın… örn. “Presi %50 ile 21'e kaydırsak nasıl olur?”")
        self.edit.setStyleSheet("font-size: 11pt; padding: 8px 12px;")
        self.edit.returnPressed.connect(self._submit)
        row.addWidget(self.edit, 1)
        self.go = QPushButton("Gönder")
        self.go.setObjectName("primary")
        self.go.clicked.connect(self._submit)
        row.addWidget(self.go)
        lay.addLayout(row)
        root.addWidget(card, 1, Qt.AlignHCenter)
        self._welcome()

    # ---------------------------------------------------------- mesajlar
    def _welcome(self) -> None:
        self.add_delti("Merhaba! Ben Delti. Uygulamayla ilgili sorularınızı yanıtlarım; “Kompresörü 3'ten 18'e "
                       "alırsak ne olur?” gibi sorularda senaryoyu değiştirmeden ön izleme yapar, daha temiz bir saat "
                       "ve yıllık etkiyi de söylerim. Aşağıdaki önerilerden birini seçebilirsiniz.", "local")

    def _row(self, bubble: _Bubble, mine: bool) -> None:
        wrap = QWidget()
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        if mine:
            h.addStretch(1)
            h.addWidget(bubble, 0)
            bubble.setMaximumWidth(620)
        else:
            av = QLabel()
            av.setFixedSize(30, 30)
            av.setPixmap(delti.pixmap("ready", 30, self._dpr))
            h.addWidget(av, 0, Qt.AlignTop)
            h.addWidget(bubble, 1)
            h.addSpacing(60)
            bubble.avatar = av
        self.msgs.insertWidget(self.msgs.count() - 1, wrap)
        QTimer.singleShot(0, self._scroll_bottom)

    def _scroll_bottom(self) -> None:
        self._stick = True
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def add_user(self, text: str) -> None:
        b = _Bubble(True)
        b.text.setText(_to_html(text))
        # Kısa mesajlar tek satırda kalsın; uzunlar en fazla 560 px genişlikte satır kırsın.
        b.text.setMinimumWidth(min(b.text.fontMetrics().horizontalAdvance(text) + 12, 560))
        self._row(b, True)

    def add_delti(self, text: str, source: str = "local", actions: list[tuple[str, object]] | None = None) -> int:
        b = _Bubble(False)
        self._next_id += 1
        self._bubbles[self._next_id] = b
        self._row(b, False)
        self._fill(b, text, source, actions)
        return self._next_id

    def update_delti(self, bid: int, text: str, source: str, actions: list[tuple[str, object]] | None = None) -> None:
        b = self._bubbles.get(bid)
        if b is not None:
            self._fill(b, text, source, actions)
            QTimer.singleShot(0, self._scroll_bottom)

    def _fill(self, b: _Bubble, text: str, source: str, actions) -> None:
        color = theme.MUTED if source in ("pending",) else theme.TEXT
        b.text.setText(f"<span style='color:{color}'>{_to_html(text)}</span>")
        tag = SOURCE_TAGS.get(source, "")
        b.tag.setText(tag)
        b.tag.setVisible(bool(tag))
        state = {"pending": "think", "fallback_offline": "sleep"}.get(source, "ready")
        if hasattr(b, "avatar"):
            b.avatar.setPixmap(delti.pixmap(state, 30, self._dpr))
        while b.actions.count():
            item = b.actions.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for label, cb in actions or []:
            btn = QPushButton(label)
            btn.setObjectName("primary")
            btn.clicked.connect(cb)
            b.actions.addWidget(btn)
        if actions:
            b.actions.addStretch(1)

    # ------------------------------------------------------------ eylemler
    def send(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.edit.clear()
        self.add_user(text)
        self.avatar.setPixmap(delti.pixmap("think", 48, self._dpr))
        self.submit.emit(text)
        self.avatar.setPixmap(delti.pixmap("ready", 48, self._dpr))

    def _submit(self) -> None:
        self.send(self.edit.text())

    def offer_apply(self, merged: dict) -> list[tuple[str, object]]:
        self._merged = dict(merged)
        return [("Senaryoya uygula", lambda _c=False, m=dict(merged): self.apply_requested.emit(m))]

    def clear(self) -> None:
        for i in reversed(range(self.msgs.count() - 1)):
            item = self.msgs.takeAt(i)
            if item.widget():
                item.widget().deleteLater()
        self._bubbles.clear()
        self._merged = None
        self._welcome()
        self.focus_input()

    def set_online(self, online: bool) -> None:
        self.sleep_bar.setVisible(not online)
        self.avatar.setPixmap(delti.pixmap("ready" if online else "sleep", 48, self._dpr))

    def focus_input(self) -> None:
        self.edit.setFocus()
        self.edit.selectAll()
