"""En Temiz Saat ve Doğal Dil sekmeleri."""
from __future__ import annotations

import bisect
from datetime import date as Date

import matplotlib

matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from PySide6.QtCore import QDate, QEvent, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from desktop import delti, fmt, theme  # noqa: E402
from desktop.keyboard import DateEdit  # noqa: E402
from desktop.tabs import _item, _table  # noqa: E402
from engine import data  # noqa: E402
from engine.best_window import scan_windows  # noqa: E402
from engine.core import simulate  # noqa: E402


def nearest_day(days: list[str], iso: str) -> str:
    ords = [Date.fromisoformat(d).toordinal() for d in days]
    try:
        target = Date.fromisoformat(iso).toordinal()
    except ValueError:
        return days[0]
    i = bisect.bisect_left(ords, target)
    cand = [j for j in (i - 1, i) if 0 <= j < len(ords)]
    return days[min(cand, key=lambda j: (abs(ords[j] - target), j))]


class _DeltaChart(FigureCanvasQTAgg):
    """Hedef başlangıç saatine göre emisyon değişimi (%) çubuk grafiği."""

    def __init__(self):
        self.figure = Figure(figsize=(4, 2.4), dpi=100, layout="constrained", facecolor="white")
        super().__init__(self.figure)
        self.setMinimumHeight(200)
        self.ax = self.figure.add_subplot(111)

    def update_chart(self, items: list[tuple[int, float]], best_t: int | None, source_t: int) -> None:
        ax = self.ax
        ax.clear()
        if items:
            hours = [t for t, _ in items]
            vals = [d for _, d in items]
            colors = ["#1f9254" if d <= 0 else "#d03c3c" for d in vals]
            bars = ax.bar(hours, vals, width=0.75, color=colors, alpha=0.75)
            if best_t is not None and best_t in hours:
                b = bars[hours.index(best_t)]
                b.set_alpha(1.0)
                b.set_edgecolor("#0f5b46")
                b.set_linewidth(1.6)
            ax.axhline(0, color="#9aa5b1", linewidth=0.8)
            ax.axvline(source_t, color="#7f8a96", linewidth=1, linestyle="--")
            ax.text(source_t, ax.get_ylim()[1], " standart", fontsize=7.5, color="#5b6776", va="top")
        ax.set_xlim(-0.6, 23.6)
        ax.set_xticks(range(0, 24, 3))
        ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 3)], fontsize=8, color="#5b6776")
        ax.tick_params(axis="y", labelsize=8, colors="#5b6776", length=0)
        ax.tick_params(axis="x", length=0)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: fmt.num(v, 1)))
        ax.set_xlabel("Hedef başlangıç saati", fontsize=8.5, color="#5b6776")
        ax.set_ylabel("Değişim (%)", fontsize=8.5, color="#5b6776")
        ax.grid(axis="y", color="#e9edf1", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#cfd6de")
        self.draw_idle()


class BestWindowTab(QWidget):
    """Bir gün için tüm geçerli hedef pencereleri emisyona göre sıralar."""

    apply_requested = Signal(dict)  # {"asset_id", "date", "s", "L", "t", "p"}

    def __init__(self, hour_spin_cls, parent=None):
        super().__init__(parent)
        self._rows: list[tuple[int, object]] = []
        self._restricted: set[int] = set()
        self._loading = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self.recompute)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(10)

        # Ayarlar
        card, lay = theme.card()
        row = QHBoxLayout()
        row.setSpacing(10)
        t = QLabel("En temiz saat")
        t.setObjectName("cardTitle")
        row.addWidget(t)
        row.addSpacing(8)
        self.machine = QComboBox()
        for m in data.machines():
            if m["shiftable"]:
                self.machine.addItem(m["name"], m["id"])
        self.date = DateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd.MM.yyyy")
        self.s = hour_spin_cls()
        self.s.setRange(0, 23)
        self.L = QSpinBox()
        self.L.setRange(1, 12)
        self.L.setSuffix(" saat")
        self.p = QSlider(Qt.Horizontal)
        self.p.setRange(0, 100)
        self.p.setFixedWidth(110)
        self.p_label = QLabel("%100")
        self.p_label.setMinimumWidth(38)
        for label, w in (("Makine", self.machine), ("Gün", self.date), ("Standart", self.s),
                         ("Uzunluk", self.L)):
            row.addWidget(theme.muted(label))
            row.addWidget(w)
        row.addWidget(theme.muted("Oran"))
        row.addWidget(self.p)
        row.addWidget(self.p_label)
        row.addStretch(1)
        lay.addLayout(row)
        self.restricted_note = theme.muted("", wrap=True)
        lay.addWidget(self.restricted_note)
        root.addWidget(card)

        self.machine.currentIndexChanged.connect(self._on_machine)
        self.date.dateChanged.connect(self._on_date)
        for sig in (self.s.valueChanged, self.L.valueChanged):
            sig.connect(self._schedule)
        self.p.valueChanged.connect(lambda v: (self.p_label.setText(f"%{v}"), self._schedule()))

        # Sonuç: tablo + grafik
        body = QHBoxLayout()
        body.setSpacing(10)
        tcard, tl = theme.card("Hedef pencere sıralaması")
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        tl.addWidget(self.summary)
        self.table = _table(["Sıra", "Hedef pencere", "Seçilen emisyon", "Değişim", "Günlük etki"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setFocusPolicy(Qt.StrongFocus)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Stretch)
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.cellDoubleClicked.connect(lambda r, _c: self._apply_row(r))
        self.table.installEventFilter(self)
        tl.addWidget(self.table, 1)
        btns = QHBoxLayout()
        btns.addWidget(theme.muted("↑ ↓ ile seçip Enter'a basın ya da satıra çift tıklayın."), 1)
        self.apply_button = QPushButton("Seçili saati senaryoya uygula")
        self.apply_button.setObjectName("primary")
        self.apply_button.clicked.connect(lambda: self._apply_row(self._selected_row()))
        btns.addWidget(self.apply_button)
        tl.addLayout(btns)
        body.addWidget(tcard, 3)

        ccard, cl = theme.card("Saate göre emisyon değişimi")
        self.chart = _DeltaChart()
        cl.addWidget(self.chart, 1)
        cl.addWidget(theme.muted("Yeşil çubuklar emisyonu düşüren, kırmızılar artıran hedef saatlerdir. "
                                 "Çerçeveli çubuk en temiz penceredir.", wrap=True))
        body.addWidget(ccard, 2)
        root.addLayout(body, 1)

    def reload_machines(self) -> None:
        current = self.machine.currentData()
        self._loading = True
        self.machine.clear()
        for m in data.machines():
            if m["shiftable"]:
                self.machine.addItem(m["name"], m["id"])
        idx = self.machine.findData(current)
        self.machine.setCurrentIndex(idx if idx >= 0 else 0)
        self._loading = False

    # ---------------------------------------------------------- girdiler
    def load_inputs(self, asset_id: str, date: str, s: int, L: int, p: float, restricted: list[int]) -> None:
        """Senaryo sekmesindeki değerlerle başlar (kaydırılamaz makinede ilk uygun makine)."""
        self._loading = True
        idx = self.machine.findData(asset_id)
        self.machine.setCurrentIndex(idx if idx >= 0 else 0)
        self._set_day_range()
        self.date.setDate(QDate.fromString(nearest_day(self._days, date), "yyyy-MM-dd"))
        self.s.setValue(s)
        self.L.setValue(L)
        self.p.setValue(round(p * 100))
        self.p_label.setText(f"%{round(p * 100)}")
        self._restricted = set(restricted)
        self._loading = False
        self.recompute()

    def _set_day_range(self) -> None:
        m = data.machine(self.machine.currentData())
        self._days = m["days"]
        self.date.setDateRange(QDate.fromString(m["first_day"], "yyyy-MM-dd"),
                               QDate.fromString(m["last_day"], "yyyy-MM-dd"))

    def _on_machine(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._set_day_range()
        iso = self.date.date().toString("yyyy-MM-dd")
        self.date.setDate(QDate.fromString(nearest_day(self._days, iso), "yyyy-MM-dd"))
        self._loading = False
        self._schedule()

    def _on_date(self, qd: QDate) -> None:
        if self._loading:
            return
        iso = qd.toString("yyyy-MM-dd")
        near = nearest_day(self._days, iso)
        if near != iso:
            self._loading = True
            self.date.setDate(QDate.fromString(near, "yyyy-MM-dd"))
            self._loading = False
        self._schedule()

    def _schedule(self, *_a) -> None:
        if not self._loading:
            self._timer.start()

    def _inputs(self) -> dict:
        return {"asset_id": self.machine.currentData(), "date": self.date.date().toString("yyyy-MM-dd"),
                "s": self.s.value(), "L": self.L.value(), "p": self.p.value() / 100}

    # ------------------------------------------------------------- hesap
    def recompute(self) -> None:
        i = self._inputs()
        load, ci = data.scenario_series(i["asset_id"], i["date"])
        cands = scan_windows(load, ci, i["s"], i["L"], i["p"], self._restricted, True)
        ranked = sorted(cands, key=lambda tr: (tr[1].scenario_kg, tr[0]))
        self._rows = ranked
        self.restricted_note.setText(
            "Kısıtlı saatler (Senaryo sekmesinden): " + ", ".join(fmt.hour(h) for h in sorted(self._restricted))
            if self._restricted else "Kısıtlı saat yok. Kısıtlı saatleri Senaryo sekmesinden işaretleyebilirsiniz.")

        self.table.setRowCount(len(ranked))
        for n, (t, r) in enumerate(ranked):
            label = fmt.window(t, i["L"]) + ("  (standart)" if t == i["s"] else "")
            vals = [str(n + 1), label, f"{fmt.num(r.scenario_kg)} kgCO2", fmt.pct(r.delta_pct),
                    fmt.pct(r.daily_delta_pct)]
            for col, v in enumerate(vals):
                it = _item(v, Qt.AlignCenter)
                if col == 3 and r.delta_pct:
                    it.setForeground(QColor(theme.GOOD if r.delta_pct < 0 else theme.BAD))
                if n == 0:
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.table.setItem(n, col, it)
        if ranked:
            self.table.selectRow(0)
        self.apply_button.setEnabled(bool(ranked))

        name = data.machine(i["asset_id"])["name"]
        if not ranked:
            self.summary.setText("Bu girdilerle geçerli hedef pencere yok (standart pencerede yük yok "
                                 "veya tüm saatler kısıtlı).")
            self.chart.update_chart([], None, i["s"])
            return
        best_t, best = ranked[0]
        if best_t == i["s"]:
            text = (f"{name} için {fmt.date(i['date'])} gününde standart pencereden ({fmt.window(i['s'], i['L'])}) "
                    "daha temiz bir saat yok.")
        else:
            text = (f"<b>En temiz pencere: {fmt.window(best_t, i['L'])}</b> — {name}, {fmt.date(i['date'])}. "
                    f"Standart {fmt.window(i['s'], i['L'])} yerine bu saatte emisyon "
                    f"<b style='color:{theme.GOOD}'>{fmt.pct(best.delta_pct)}</b> değişir "
                    f"({len(ranked)} geçerli pencere tarandı).")
        self.summary.setText(text)
        by_t = sorted(((t, r.delta_pct or 0.0) for t, r in ranked), key=lambda x: x[0])
        self.chart.update_chart(by_t, best_t, i["s"])

    def eventFilter(self, obj, event) -> bool:
        if obj is self.table and event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._apply_row(self._selected_row())
            return True
        return super().eventFilter(obj, event)

    def _selected_row(self) -> int:
        items = self.table.selectedItems()
        return items[0].row() if items else 0

    def _apply_row(self, row: int) -> None:
        if not 0 <= row < len(self._rows):
            return
        t, _ = self._rows[row]
        i = self._inputs()
        i["t"] = t
        self.apply_requested.emit(i)


EXAMPLES = [
    "Kompresörü 3'ten 18'e al",
    "Presi %50 ile 21'e kaydır",
    "Karıştırıcıyı 10'dan 19'a al",
]


class NLTab(QWidget):
    """Delti'ye sor: cümle → anlaşılan senaryo (Senaryo sekmesine uygulanır) → önizleme."""

    submit = Signal(str)          # cümle (ana pencere AI/kural çözümleyiciye gönderir)
    open_requested = Signal(dict)  # doğrulanmış girdiler
    settings_requested = Signal()  # Delti ayarları penceresi

    def __init__(self, parent=None):
        super().__init__(parent)
        self._merged: dict | None = None
        self._dpr = self.devicePixelRatioF() or 1.0
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 24, 0, 0)
        root.setSpacing(14)
        root.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        card, lay = theme.card(margins=(22, 18, 22, 18), spacing=10)
        card.setFixedWidth(720)
        top = QHBoxLayout()
        top.setSpacing(12)
        self.avatar = QLabel()
        self.avatar.setFixedSize(56, 56)
        self.avatar.setPixmap(delti.pixmap("ready", 56, self._dpr))
        top.addWidget(self.avatar)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        t = QLabel("Delti'ye sor")
        t.setStyleSheet("font-size: 15pt; font-weight: 700;")
        titles.addWidget(t)
        titles.addWidget(theme.muted("Ne yapmak istediğinizi günlük dille yazın."))
        top.addLayout(titles, 1)
        ai = QLabel("AI")
        ai.setStyleSheet(f"color: {theme.PRIMARY}; background: {theme.PRIMARY_SOFT}; border-radius: 9px;"
                         " padding: 2px 10px; font-size: 8.5pt; font-weight: 600;")
        ai.setToolTip("Delti bir yapay zekâ yardımcısıdır; hesap yapmaz, karar sizindir.")
        top.addWidget(ai, 0, Qt.AlignTop)
        gear = QPushButton("⚙ Ayarlar")
        gear.setToolTip("Delti ayarları: API anahtarı (Ctrl+,)")
        gear.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        gear.clicked.connect(self.settings_requested)
        top.addWidget(gear, 0, Qt.AlignTop)
        lay.addLayout(top)

        # Anahtar yoksa: Delti uyuyor uyarısı + ayarlara giden düğme
        self.sleep_bar = QWidget()
        sl = QHBoxLayout(self.sleep_bar)
        sl.setContentsMargins(12, 8, 8, 8)
        msg = QLabel("<b>Delti uyuyor.</b> AI anahtarı girilmemiş; cümleler yine de basit kurallarla "
                     "çözülür. Delti'yi uyandırmak için anahtarınızı girin.")
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

        self.bubble = QLabel("Hangi makineyi hangi saatten hangi saate almak istersiniz? "
                             "İsterseniz kaydırma oranını da söyleyin.")
        self.bubble.setWordWrap(True)
        self.bubble.setStyleSheet(f"background: {theme.PRIMARY_SOFT}; border: 1px solid #cfe5dc; border-radius: 12px;"
                                  f" padding: 9px 12px; color: {theme.PRIMARY_DARK}; margin-left: 66px;")
        lay.addWidget(self.bubble)

        row = QHBoxLayout()
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Örn. Kompresörü 3'ten 18'e al")
        self.edit.setStyleSheet("font-size: 11pt; padding: 8px 12px;")
        self.edit.returnPressed.connect(self._submit)
        row.addWidget(self.edit, 1)
        self.go = QPushButton("Sor")
        self.go.setObjectName("primary")
        self.go.clicked.connect(self._submit)
        row.addWidget(self.go)
        lay.addLayout(row)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(theme.muted("Örnekler:"))
        for ex in EXAMPLES:
            b = QPushButton(ex)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ border-radius: 12px; padding: 3px 10px; font-size: 8.5pt;"
                            f" background: {theme.PRIMARY_SOFT}; border: 1px solid #cfe5dc; color: {theme.PRIMARY_DARK}; }}"
                            f"QPushButton:hover {{ border-color: {theme.PRIMARY}; }}")
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            b.clicked.connect(lambda _c=False, e=ex: (self.edit.setText(e), self._submit()))
            chips.addWidget(b)
        chips.addStretch(1)
        lay.addLayout(chips)

        # Delti'nin cevabı
        self.answer = QWidget()
        al = QVBoxLayout(self.answer)
        al.setContentsMargins(0, 10, 0, 0)
        al.setSpacing(8)
        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {theme.BORDER};")
        al.addWidget(line)
        head = QHBoxLayout()
        head.setSpacing(12)
        self.answer_avatar = QLabel()
        self.answer_avatar.setFixedSize(32, 32)
        head.addWidget(self.answer_avatar, 0, Qt.AlignTop)
        self.answer_text = QLabel("")
        self.answer_text.setWordWrap(True)
        self.answer_text.setTextFormat(Qt.RichText)
        self.answer_text.setStyleSheet("font-size: 10.5pt;")
        head.addWidget(self.answer_text, 1)
        al.addLayout(head)
        self.explain = theme.muted("", wrap=True)
        self.explain.setContentsMargins(44, 0, 0, 0)
        al.addWidget(self.explain)
        btns = QHBoxLayout()
        self.via = theme.muted("")
        btns.addWidget(self.via, 1)
        self.clear_button = QPushButton("Temizle")
        self.clear_button.clicked.connect(self.clear)
        btns.addWidget(self.clear_button)
        self.open_button = QPushButton("Senaryoya git")
        self.open_button.setObjectName("primary")
        self.open_button.clicked.connect(lambda: self._merged and self.open_requested.emit(self._merged))
        btns.addWidget(self.open_button)
        al.addLayout(btns)
        self.answer.hide()
        lay.addWidget(self.answer)
        root.addWidget(card, 0, Qt.AlignHCenter)

    @property
    def status(self) -> QLabel:
        """Delti'nin son cevap metni."""
        return self.answer_text

    def focus_input(self) -> None:
        self.edit.setFocus()
        self.edit.selectAll()

    def set_online(self, online: bool) -> None:
        self.sleep_bar.setVisible(not online)
        if not self._merged:
            self.avatar.setPixmap(delti.pixmap("ready" if online else "sleep", 56, self._dpr))

    def clear(self) -> None:
        self.edit.clear()
        self.answer.hide()
        self._merged = None
        self.avatar.setPixmap(delti.pixmap("ready", 56, self._dpr))
        self.focus_input()

    def _show_answer(self, html: str, state: str, explain: str = "", via: str = "",
                     can_open: bool = False) -> None:
        self.answer_avatar.setPixmap(delti.pixmap(state, 32, self._dpr))
        self.answer_text.setText(html)
        self.explain.setText(explain)
        self.explain.setVisible(bool(explain))
        self.via.setText(via)
        self.open_button.setVisible(can_open)
        self.answer.show()

    def _submit(self) -> None:
        text = self.edit.text().strip()
        if text:
            self._merged = None
            self.avatar.setPixmap(delti.pixmap("think", 56, self._dpr))
            self._show_answer("Düşünüyorum…", "think")
            self.submit.emit(text)

    def show_error(self, msg: str) -> None:
        self._merged = None
        self.avatar.setPixmap(delti.pixmap("ready", 56, self._dpr))
        self._show_answer(f"<b>Bunu tam anlayamadım.</b> {msg} Örneklerden birini deneyebilir misiniz?", "ready")

    def show_result(self, merged: dict, via: str, explanation_fn) -> None:
        """merged: asset_id, date, s, L, t, p. Önizleme motorla hesaplanır."""
        self._merged = merged
        m = data.machine(merged["asset_id"])
        load, ci = data.scenario_series(merged["asset_id"], merged["date"])
        r = simulate(load, ci, merged["s"], merged["L"], merged["t"], merged["p"], set(), m["shiftable"])
        what = (f"{m['name']} · {fmt.date(merged['date'])} · {fmt.window(merged['s'], merged['L'])} → "
                f"{fmt.window(merged['t'], merged['L'])} · %{fmt.num(merged['p'] * 100, 0)}")
        if r.status == "ok":
            color = theme.GOOD if r.delta_pct <= 0 else theme.BAD
            effect = (f"Senaryo sekmesine uyguladım; emisyon "
                      f"<b style='color:{color}'>{fmt.pct(r.delta_pct)}</b> değişiyor.")
        else:
            effect = "Senaryo sekmesine uyguladım; bu girdilerle yüzde hesaplanamıyor."
        self.avatar.setPixmap(delti.pixmap("ready", 56, self._dpr))
        self._show_answer(f"<b>Anladım:</b> {what}<br>{effect}", "ready",
                          explanation_fn(m, merged, r), f"Çözümleyen: {via}", True)
        if self.edit.hasFocus():
            self.open_button.setFocus(Qt.TabFocusReason)  # Enter → Senaryoya git
