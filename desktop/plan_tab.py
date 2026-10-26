"""Tesis Planı sekmesi: seçilen günde her kaydırılabilir makine için en temiz hedef pencere, tesis yük profili
ve isteğe bağlı saatlik tepe yük sınırı."""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from PySide6.QtCore import QDate, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from desktop import fmt, theme  # noqa: E402
from desktop.keyboard import DateEdit  # noqa: E402
from desktop.tabs import _item, _raw, _stat, _table  # noqa: E402
from engine import data, plan  # noqa: E402

COLS = ["Dahil", "Makine", "Standart", "Uzunluk", "Önerilen pencere", "Kaydırılan (kWh)", "Değişim (kg)",
        "Değişim", "Yenilenebilir payı", "Not"]
STATUS_COLOR = {plan.PLANNED: theme.GOOD, plan.KEEP: theme.MUTED, plan.NON_SHIFTABLE: theme.MUTED,
                plan.NO_DATA: theme.MUTED, plan.EXCLUDED: theme.MUTED, plan.NO_LOAD: theme.WARN}


def plan_source(p: plan.FacilityPlan) -> tuple[str, bool]:
    ids = [r.asset_id for r in p.rows if r.status != plan.NO_DATA]
    if not ids:
        return data.grid_label(p.date), False
    reals = [data.is_real(a) for a in ids]
    if all(reals) or not any(reals):
        return data.source_label(ids[0], p.date), all(reals)
    return (f"Tesis planı: tesis ölçümü ve örnek yük birlikte · Kaynak: {data.grid_label(p.date)}, "
            f"{data.factors_label()}"), False


class _LoadChart(FigureCanvasQTAgg):
    """Tesis saatlik yükü (önce/sonra) ve şebeke karbon yoğunluğu."""

    def __init__(self):
        self.figure = Figure(figsize=(4, 2.6), dpi=100, layout="constrained", facecolor="white")
        super().__init__(self.figure)
        self.setMinimumHeight(160)
        self.ax = self.figure.add_subplot(111)
        self.ax2 = self.ax.twinx()

    def update_chart(self, p: plan.FacilityPlan | None, ci_label: str = "tCO2") -> None:
        ax, ax2 = self.ax, self.ax2
        ax.clear()
        ax2.clear()
        if p is not None:
            hours = list(range(24))
            ax.bar([h - 0.2 for h in hours], p.before, width=0.4, color="#c9d3dd", label="Plan öncesi")
            ax.bar([h + 0.2 for h in hours], p.after, width=0.4, color="#1f9254", alpha=0.85, label="Plan sonrası")
            top = max(max(p.before), max(p.after), 1.0) * 1.18
            if p.peak_limit and p.peak_limit <= top:
                ax.axhline(p.peak_limit, color="#d03c3c", linewidth=1, linestyle="--")
                ax.text(23.6, p.peak_limit, " sınır", fontsize=7.5, color="#d03c3c", va="bottom", ha="right")
            elif p.peak_limit:
                ax.text(0.99, 0.97, f"sınır {fmt.num(p.peak_limit, 0)} kWh (grafik dışında)", transform=ax.transAxes,
                        fontsize=7.5, color="#d03c3c", va="top", ha="right")
            ax.set_ylim(0, top)
            moved = p.shifted_kwh if p.planned_count else 0.0   # özetteki taşınan enerjiyle aynı
            msg = (f"Taşınan enerji: {fmt.num(moved, 1)} kWh" if moved > 1e-9
                   else "Plan değişiklik önermedi")
            ax.text(0.01, 0.97, msg, transform=ax.transAxes, fontsize=8, va="top",
                    color="#16785c" if moved > 1e-9 else "#9a6412",
                    bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "#e1e6ec"})
            ax2.plot(hours, p.ci, color="#1f4e79", linewidth=1.6, marker="o", markersize=2.5, label="Karbon yoğunluğu")
            ax2.yaxis.set_label_position("right")
            ax2.yaxis.tick_right()
            ax2.set_ylabel(f"{ci_label}/MWh", fontsize=8, color="#1f4e79")
            ax2.tick_params(axis="y", labelsize=7.5, colors="#1f4e79", length=0)
            h1, l1 = ax.get_legend_handles_labels()
            h2, l2 = ax2.get_legend_handles_labels()
            ax.legend(h1 + h2, l1 + l2, loc="lower center", bbox_to_anchor=(0.5, 1.0), fontsize=7.5, frameon=False,
                      ncol=3)
        ax.set_xlim(-0.7, 23.7)
        ax.set_xticks(range(0, 24, 3))
        ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 3)], fontsize=8, color="#5b6776")
        ax.tick_params(axis="y", labelsize=8, colors="#5b6776", length=0)
        ax.tick_params(axis="x", length=0)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: fmt.num(v, 0)))
        ax.set_ylabel("Tesis yükü (kWh)", fontsize=8.5, color="#5b6776")
        ax.grid(axis="y", color="#e9edf1", linewidth=0.8)
        ax.set_axisbelow(True)
        for a in (ax, ax2):
            for side in ("top",):
                a.spines[side].set_visible(False)
        self.draw_idle()


class PlanTab(QWidget):
    apply_requested = Signal(dict)        # {"asset_id", "date", "s", "L", "t", "p"}
    footer_changed = Signal(str, bool)

    def __init__(self, hour_spin_cls, parent=None):
        super().__init__(parent)
        self._hour_spin_cls = hour_spin_cls
        self._restricted: set[int] = set()
        self._kind = "tCO2"
        self._loading = False
        self.plan: plan.FacilityPlan | None = None
        self._row_widgets: dict[str, tuple[QCheckBox, QSpinBox, QSpinBox]] = {}
        self._ids: list[str] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self.recompute)

        root = theme.scroll_page(self, 600)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(10)

        card, lay = theme.card()
        row = QHBoxLayout()
        row.setSpacing(10)
        t = QLabel("Tesis günlük planı")
        t.setObjectName("cardTitle")
        row.addWidget(t)
        row.addSpacing(8)
        self.date = DateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd.MM.yyyy")
        days = data.all_dates()
        self.date.setDateRange(QDate.fromString(days[0], "yyyy-MM-dd"), QDate.fromString(days[-1], "yyyy-MM-dd"))
        self.s = hour_spin_cls()
        self.s.setRange(0, 23)
        self.L = QSpinBox()
        self.L.setRange(1, 12)
        self.L.setSuffix(" saat")
        self.p = QSlider(Qt.Horizontal)
        self.p.setRange(0, 100)
        self.p.setValue(100)
        self.p.setFixedWidth(100)
        self.p_label = QLabel("%100")
        self.p_label.setMinimumWidth(38)
        self.limit = QDoubleSpinBox()
        self.limit.setRange(0, 1_000_000)
        self.limit.setDecimals(0)
        self.limit.setSingleStep(10)
        self.limit.setSuffix(" kWh")
        self.limit.setSpecialValueText("sınır yok")
        self.limit.setToolTip("Tesisin herhangi bir saatteki toplam yükü bu değeri aşmasın (0 = sınır yok). "
                              "Sınır aşılıyorsa planlayıcı makineyi sınırı aşmayan en temiz pencereye alır.")
        self.mode = QComboBox()
        self.mode.addItem("Otomatik", "auto")
        self.mode.addItem("Elle", "manual")
        self.mode.setToolTip("Otomatik: her makine için o gün en çok emisyon ürettiği pencere standart kabul edilir. "
                             "Elle: aşağıdaki saat (satır başına değiştirilebilir) kullanılır.")
        self.mode.currentIndexChanged.connect(self._on_mode)
        for label, w in (("Gün", self.date), ("Standart", self.mode), ("", self.s), ("Uzunluk", self.L)):
            if label:
                row.addWidget(theme.muted(label))
            row.addWidget(w)
        row.addWidget(theme.muted("Oran"))
        row.addWidget(self.p)
        row.addWidget(self.p_label)
        row.addWidget(theme.muted("Tepe sınırı"))
        row.addWidget(self.limit)
        row.addStretch(1)
        self.export_button = QPushButton("CSV")
        self.export_button.setToolTip("Planı CSV olarak kaydeder")
        self.export_button.clicked.connect(self.export_csv)
        row.addWidget(self.export_button)
        lay.addLayout(row)
        self.note = theme.muted("", wrap=True)
        lay.addWidget(self.note)
        root.addWidget(card)

        self.date.dateChanged.connect(self._schedule)
        self.s.valueChanged.connect(self._on_global)
        self.L.valueChanged.connect(self._on_global)
        self.p.valueChanged.connect(lambda v: (self.p_label.setText(f"%{v}"), self._schedule()))
        self.limit.valueChanged.connect(self._schedule)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        f1, self.v_delta = _stat("Tesis emisyon değişimi")
        f2, self.v_pct = _stat("Kaydırılan yükte değişim")
        f3, self.v_daily = _stat("Tesisin günlük emisyonunda")
        f4, self.v_peak = _stat("Tepe yük (önce → sonra)")
        for f in (f1, f2, f3, f4):
            stats.addWidget(f, 1)
        root.addLayout(stats)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        root.addWidget(self.summary)

        body = QHBoxLayout()
        body.setSpacing(10)
        tcard, tl = theme.card("Makine bazlı plan")
        self.table = _table(COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setFocusPolicy(Qt.StrongFocus)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(len(COLS) - 1, QHeaderView.Stretch)
        self.table.cellDoubleClicked.connect(lambda r, _c: self._apply_row(r))
        tl.addWidget(self.table, 1)
        btns = QHBoxLayout()
        btns.addWidget(theme.muted("Elle modunda satır başına standart saat ve uzunluk değiştirilebilir; çift tıklama o makineyi "
                                   "Senaryo'da açar."), 1)
        self.apply_button = QPushButton("Seçili makineyi senaryoya aç")
        self.apply_button.setObjectName("primary")
        self.apply_button.clicked.connect(lambda: self._apply_row(self.table.currentRow()))
        btns.addWidget(self.apply_button)
        tl.addLayout(btns)
        body.addWidget(tcard, 3)
        ccard, cl = theme.card("Tesis saatlik yükü")
        self.chart = _LoadChart()
        cl.addWidget(self.chart, 1)
        cl.addWidget(theme.muted("Gri: plan öncesi, yeşil: plan sonrası tesis yükü. Mavi çizgi şebekenin saatlik karbon "
                                 "yoğunluğudur. Yüklerin aynı saate toplanması tepe yükü artırabilir.", wrap=True))
        body.addWidget(ccard, 2)
        root.addLayout(body, 1)

        self.reload_machines()
        self._on_mode()

    # ---------------------------------------------------------- girdiler
    @property
    def auto(self) -> bool:
        return self.mode.currentData() == "auto"

    def _on_mode(self, *_a) -> None:
        self.s.setEnabled(not self.auto)
        for a, (chk, ws, _wl) in self._row_widgets.items():
            ws.setEnabled(not self.auto and data.machine(a)["shiftable"])
        if not self.auto and not self._loading:
            self._on_global()
        self._schedule()
    def reload_machines(self) -> None:
        self._loading = True
        machines = data.machines()
        self._ids = [m["id"] for m in machines]
        self._row_widgets.clear()
        self.table.setRowCount(len(machines))
        for n, m in enumerate(machines):
            chk = QCheckBox()
            chk.setChecked(m["shiftable"])
            chk.setEnabled(m["shiftable"])
            chk.toggled.connect(self._schedule)
            box = QWidget()
            bl = QHBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setAlignment(Qt.AlignCenter)
            bl.addWidget(chk)
            self.table.setCellWidget(n, 0, box)
            self.table.setItem(n, 1, _item(m["name"], Qt.AlignLeft | Qt.AlignVCenter))
            s = self._hour_spin_cls()
            s.setRange(0, 23)
            s.setValue(self.s.value())
            s.setEnabled(m["shiftable"] and self.mode.currentData() == "manual")
            s.valueChanged.connect(self._schedule)
            L = QSpinBox()
            L.setRange(1, 12)
            L.setValue(self.L.value())
            L.setEnabled(m["shiftable"])
            L.valueChanged.connect(self._schedule)
            self.table.setCellWidget(n, 2, s)
            self.table.setCellWidget(n, 3, L)
            self._row_widgets[m["id"]] = (chk, s, L)
        self._loading = False

    def load_inputs(self, date: str, s: int, L: int, p: float, restricted: list[int], kind: str = "tCO2") -> None:
        """Senaryo sekmesindeki gün, saatler, oran ve kısıtlarla başlar."""
        self._loading = True
        self.date.setDate(QDate.fromString(date, "yyyy-MM-dd"))
        self.s.setValue(s)
        self.L.setValue(L)
        self.p.setValue(round(p * 100))
        self.p_label.setText(f"%{round(p * 100)}")
        self._restricted = set(restricted)
        self._kind = kind
        for _chk, ws, wl in self._row_widgets.values():
            ws.setValue(s)
            wl.setValue(L)
        self._loading = False
        self.recompute()

    def _on_global(self, *_a) -> None:
        """Üstteki standart saat/uzunluk değişince bütün satırlar ona eşitlenir."""
        if self._loading:
            return
        self._loading = True
        for _chk, ws, wl in self._row_widgets.values():
            ws.setValue(self.s.value())
            wl.setValue(self.L.value())
        self._loading = False
        self._schedule()

    def _schedule(self, *_a) -> None:
        if not self._loading:
            self._timer.start()

    def settings(self) -> dict[str, plan.MachineSetting]:
        p = self.p.value() / 100
        return {a: plan.MachineSetting(None if self.auto else ws.value(), wl.value(), p, chk.isChecked())
                for a, (chk, ws, wl) in self._row_widgets.items() if data.machine(a)["shiftable"]}

    # ------------------------------------------------------------- hesap
    def recompute(self) -> None:
        date = self.date.date().toString("yyyy-MM-dd")
        if date not in set(data.all_dates()):
            return
        limit = self.limit.value() or None
        p = plan.facility_plan(date, self.settings(), self._restricted, self._kind, limit)
        self.plan = p
        notes = ["Kısıtlı saatler (Senaryo sekmesinden): " + ", ".join(fmt.hour(h) for h in sorted(self._restricted))
                 if self._restricted else "Kısıtlı saat yok; Senaryo sekmesinden işaretlenebilir."]
        if self._kind != "tCO2":
            notes.append("Emisyon tipi: tCO2-eşd.")
        self.note.setText(" · ".join(notes))
        self._show(p)
        self.footer_changed.emit(*plan_source(p))

    def _show(self, p: plan.FacilityPlan) -> None:
        unit = "kg CO2" if self._kind == "tCO2" else "kg CO2-eşd"
        good = p.delta_kg <= 0
        color = theme.GOOD if good else theme.BAD
        self.v_delta.setText(f"{fmt.num(p.delta_kg, 1)} {unit}" if p.planned_count else "—")
        self.v_delta.setStyleSheet(f"color: {color};" if p.planned_count else "")
        self.v_pct.setText(fmt.pct(p.delta_pct) if p.planned_count else "—")
        self.v_pct.setStyleSheet(f"color: {color};" if p.planned_count else "")
        self.v_daily.setText(fmt.pct(p.daily_delta_pct) if p.planned_count else "—")
        self.v_peak.setText(f"{fmt.num(p.peak_before, 1)} → {fmt.num(p.peak_after, 1)} kWh")
        rise = p.peak_after > p.peak_before + 1e-9
        self.v_peak.setStyleSheet(f"color: {theme.WARN};" if rise else "")
        if p.planned_count:
            text = (f"<b>{fmt.date(p.date)}</b> için {p.planned_count} makine daha temiz saatlere alınabilir: kaydırılan "
                    f"{fmt.num(p.shifted_kwh, 1)} kWh enerjinin emisyonu {fmt.num(p.baseline_kg, 1)} yerine "
                    f"{fmt.num(p.scenario_kg, 1)} {unit} olur ({fmt.pct(p.delta_pct)}).")
            if p.fossil_delta_pct is not None:
                text += (f" <span style='color:{theme.MUTED}'>Fosil marjinal varsayımla: "
                         f"{fmt.pct(p.fossil_delta_pct)}.</span>")
            if rise:
                text += (f" <span style='color:{theme.WARN}'>Dikkat: yükler aynı saatlere toplandığı için tesis tepe "
                         f"yükü {fmt.num(p.peak_before, 1)}'den {fmt.num(p.peak_after, 1)} kWh'e çıkıyor; sözleşme "
                         "gücü veya trafo sınırı varsa <i>Tepe sınırı</i> girin.</span>")
        else:
            reasons = plan.reason_counts(p)
            why = "; ".join(f"{n} makinede: {k.lower()}" for k, n in reasons.items()) or "plana dahil makine yok"
            hint = ("Standart pencereyi makinelerin çalıştığı saatlere çekin ya da <i>Otomatik</i>'i seçin."
                    if not self.auto else "Bu gün için daha temiz bir saat bulunmuyor.")
            text = (f"<b>{fmt.date(p.date)}</b> için plan değişiklik önermedi, iki çubuk bu yüzden aynı ({why}). "
                    f"<span style='color:{theme.WARN}'>{hint}</span>")
        self.summary.setText(text)

        if self.auto:
            for a, (_chk, ws, _wl) in self._row_widgets.items():
                rr = next(x for x in p.rows if x.asset_id == a)
                if rr.status in (plan.PLANNED, plan.KEEP):
                    ws.blockSignals(True)
                    ws.setValue(rr.s)
                    ws.blockSignals(False)
        for n, a in enumerate(self._ids):
            r = next(x for x in p.rows if x.asset_id == a)
            res = r.result
            target = fmt.window(r.t, r.L) if r.t is not None and r.status in (plan.PLANNED, plan.KEEP) else "—"
            if r.status == plan.KEEP and r.t == r.s:
                target += " (standart)"
            vals = {4: target,
                    5: fmt.num(res.shifted_kwh, 1) if res else "—",
                    6: fmt.num(r.delta_kg, 2) if res else "—",
                    7: fmt.pct(res.delta_pct) if res and r.status == plan.PLANNED else ("%0,00" if res else "—"),
                    8: (f"%{fmt.num(r.renewable[0], 1)} → %{fmt.num(r.renewable[1], 1)}" if r.renewable else "—"),
                    9: r.note}
            for col, v in vals.items():
                it = _item(v, (Qt.AlignLeft if col == 9 else Qt.AlignCenter) | Qt.AlignVCenter)
                if col in (4, 6, 7):
                    it.setForeground(QColor(STATUS_COLOR.get(r.status, theme.TEXT)))
                    if col == 4 and r.status == plan.PLANNED:
                        f = it.font()
                        f.setBold(True)
                        it.setFont(f)
                if col == 9 and r.status == plan.NO_LOAD:
                    it.setForeground(QColor(theme.WARN))
                self.table.setItem(n, col, it)
        self.apply_button.setEnabled(any(r.result is not None for r in p.rows))
        self.export_button.setEnabled(True)
        self.chart.update_chart(p, "tCO2" if self._kind == "tCO2" else "tCO2-eşd")

    def emit_footer(self) -> None:
        if self.plan is not None:
            self.footer_changed.emit(*plan_source(self.plan))

    # ------------------------------------------------------------- işler
    def _apply_row(self, n: int) -> None:
        if self.plan is None or not 0 <= n < len(self._ids):
            return
        r = next(x for x in self.plan.rows if x.asset_id == self._ids[n])
        if r.result is None or r.t is None:
            return
        self.apply_requested.emit({"asset_id": r.asset_id, "date": self.plan.date, "s": r.s, "L": r.L, "t": r.t,
                                   "p": r.p})

    def export_csv(self) -> None:
        if self.plan is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Tesis planını kaydet", f"CarbonDelta_tesis_plani_{self.plan.date}.csv",
                                              "CSV (*.csv)")
        if not path:
            return
        try:
            export_plan_csv(path, self.plan, self._restricted)
        except OSError as e:
            QMessageBox.warning(self, "Kaydedilemedi", str(e))

    def focus_default(self) -> None:
        self.table.setFocus(Qt.TabFocusReason)
        if self.table.currentRow() < 0:
            self.table.selectRow(0)


def export_plan_csv(path: Path | str, p: plan.FacilityPlan, restricted: set[int]) -> None:
    """Tesis planını CSV'ye yazar (UTF-8 BOM, ';' ayraç, tam hassasiyet)."""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["CarbonDelta tesis günlük planı"])
        w.writerow(["Gün", fmt.date(p.date), "Emisyon tipi", p.kind, "Tepe sınırı (kWh)", _raw(p.peak_limit),
                    "Kısıtlı saatler", ",".join(str(h) for h in sorted(restricted))])
        w.writerow([])
        w.writerow(["Makine", "Durum", "Standart başlangıç", "Uzunluk", "Hedef başlangıç", "Kaydırılan (kWh)",
                    "B (kg)", "S (kg)", "Değişim (kg)", "Değişim (%)", "Yenilenebilir payı standart (%)",
                    "Yenilenebilir payı hedef (%)", "Not"])
        for r in p.rows:
            res = r.result
            w.writerow([r.name, r.status, r.s if res else "", r.L if res else "", "" if r.t is None else r.t,
                        _raw(res.shifted_kwh) if res else "", _raw(res.baseline_kg) if res else "",
                        _raw(res.scenario_kg) if res else "", _raw(r.delta_kg) if res else "",
                        _raw(res.delta_pct) if res else "", _raw(r.renewable[0]) if r.renewable else "",
                        _raw(r.renewable[1]) if r.renewable else "", r.note])
        w.writerow([])
        w.writerow(["Toplam değişim (kg)", _raw(p.delta_kg)])
        w.writerow(["Kaydırılan yükte değişim (%)", _raw(p.delta_pct)])
        w.writerow(["Tesisin günlük emisyonunda (%)", _raw(p.daily_delta_pct)])
        w.writerow(["Fosil marjinal duyarlılık (%)", _raw(p.fossil_delta_pct)])
        w.writerow(["Tepe yük önce (kWh)", _raw(p.peak_before)])
        w.writerow(["Tepe yük sonra (kWh)", _raw(p.peak_after)])
        w.writerow([])
        w.writerow([plan_source(p)[0]])
