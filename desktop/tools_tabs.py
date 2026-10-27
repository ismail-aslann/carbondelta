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
from desktop.ratio import RatioControl  # noqa: E402
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

    def update_chart(self, items: list[tuple[int, float]], best_t: int | None, source_t: int,
                     best_pct: float | None = None, unit: str = "kg CO2") -> None:
        """items: (hedef başlangıç, emisyon değişimi kg). kg oranla değişir; yüzde en iyi çubukta yazılır."""
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
                if best_pct is not None:
                    v = vals[hours.index(best_t)]
                    ax.annotate(fmt.pct(best_pct), (best_t, v), xytext=(0, -12 if v < 0 else 4),
                                textcoords="offset points", ha="center", va="top" if v < 0 else "bottom",
                                fontsize=8, fontweight="bold", color="#0f5b46")
            ax.axhline(0, color="#9aa5b1", linewidth=0.8)
            lo, hi = min(min(vals), 0.0), max(max(vals), 0.0)
            pad = (hi - lo) * 0.12 or 0.1
            ax.set_ylim(lo - pad * 1.4, hi + pad)   # en iyi çubuğun yüzde etiketi eksene çarpmasın
            ax.axvline(source_t, color="#7f8a96", linewidth=1, linestyle="--")
            ax.text(source_t, ax.get_ylim()[1], " standart", fontsize=7.5, color="#5b6776", va="top")
        ax.set_xlim(-0.6, 23.6)
        ax.set_xticks(range(0, 24, 3))
        ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 3)], fontsize=8, color="#5b6776")
        ax.tick_params(axis="y", labelsize=8, colors="#5b6776", length=0)
        ax.tick_params(axis="x", length=0)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: fmt.num(v, 1)))
        ax.set_xlabel("Hedef başlangıç saati", fontsize=8.5, color="#5b6776")
        ax.set_ylabel(f"Emisyon değişimi ({unit})", fontsize=8.5, color="#5b6776")
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
        self.p = RatioControl(slider_width=100)
        self.p_label = QLabel()   # eski çağrılar için (gösterilmez)
        self._kind = "tCO2"
        self._param: float | None = None
        for label, w in (("Makine", self.machine), ("Gün", self.date), ("Standart", self.s),
                         ("Uzunluk", self.L)):
            row.addWidget(theme.muted(label))
            row.addWidget(w)
        row.addWidget(theme.muted("Oran"))
        row.addWidget(self.p)
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
        cl.addWidget(theme.muted("Her çubuk, o hedef saate taşınınca emisyonun kaç kg değiştiğini gösterir (oranla "
                                 "değişir). Yeşil düşüren, kırmızı artıran; çerçeveli çubuk en temiz penceredir.", wrap=True))
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
    def load_inputs(self, asset_id: str, date: str, s: int, L: int, p: float, restricted: list[int],
                    kind: str = "tCO2", param_kwh: float | None = None) -> None:
        self._kind, self._param = kind, param_kwh
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
        load, ci = data.scenario_series(i["asset_id"], i["date"], self._kind, self._param)
        cands = scan_windows(load, ci, i["s"], i["L"], i["p"], self._restricted, True)
        ranked = sorted(cands, key=lambda tr: (tr[1].scenario_kg, tr[0]))
        self._rows = ranked
        notes = ["Kısıtlı saatler (Senaryo sekmesinden): " + ", ".join(fmt.hour(h) for h in sorted(self._restricted))
                 if self._restricted else "Kısıtlı saat yok. Kısıtlı saatleri Senaryo sekmesinden işaretleyebilirsiniz."]
        if self._kind != "tCO2":
            notes.append("Emisyon tipi: tCO2-eşd.")
        if self._param is not None:
            notes.append(f"Parametrik mod: her saat sabit {fmt.num(self._param, 1)} kWh.")
        s_end = i["s"] + i["L"]
        if s_end <= 24:
            window = sum(load[i["s"]:s_end])
            notes.append(f"Taşınan: {fmt.num(i['p'] * window)} kWh (standart pencere {fmt.num(window)} kWh × "
                         f"%{fmt.num(i['p'] * 100, 0)}); yüzde orandan bağımsızdır, kg değerleri oranla değişir.")
        self.restricted_note.setText(" · ".join(notes))
        unit = "kg CO2" if self._kind == "tCO2" else "kg CO2-eşd"

        self.table.setRowCount(len(ranked))
        for n, (t, r) in enumerate(ranked):
            label = fmt.window(t, i["L"]) + ("  (standart)" if t == i["s"] else "")
            vals = [str(n + 1), label, f"{fmt.num(r.scenario_kg)} {unit.replace(' ', '')}", fmt.pct(r.delta_pct),
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
            self.chart.update_chart([], None, i["s"], None, unit)
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
        by_t = sorted(((t, r.scenario_kg - r.baseline_kg) for t, r in ranked), key=lambda x: x[0])
        self.chart.update_chart(by_t, best_t, i["s"], best.delta_pct, unit)

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
