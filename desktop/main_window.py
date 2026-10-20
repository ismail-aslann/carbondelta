"""Ana pencere: girdiler, grafik, sonuç kartı, AI açıklama kutusu."""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import date as Date

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QTextCharFormat, QValidator
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QPushButton, QRadioButton,
    QScrollArea, QSlider, QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from desktop import fmt
from desktop.chart_widget import ChartWidget
from engine import data
from engine.best_window import best_window
from engine.core import Result, simulate

APP_TITLE = "CarbonDelta — Emisyon Potansiyeli Karar Destek"
FOOTER_TEXT = "Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo"
NON_SHIFTABLE_TEXT = "Bu yük kaydırılamaz (sürekli/kısıtlı süreç). Öneri üretilmez."
CI_LABELS = {"tCO2": "tCO2", "tCO2esd": "tCO2-eşd"}

GOOD = "#2e9d4f"
BAD = "#d03c3c"
MUTED = "#6b7785"


class HourSpinBox(QSpinBox):
    """Saati 03:00 biçiminde gösterir; 3 veya 03:00 yazılabilir."""

    def textFromValue(self, value: int) -> str:
        return fmt.hour(value)

    def valueFromText(self, text: str) -> int:
        return int(text.split(":")[0] or 0)

    def validate(self, text: str, pos: int):
        head = text.split(":")[0]
        if head == "":
            return QValidator.Intermediate, text, pos
        if head.isdigit() and self.minimum() <= int(head) <= self.maximum():
            return QValidator.Acceptable, text, pos
        return QValidator.Invalid, text, pos


@dataclass
class ScenarioInputs:
    asset_id: str
    date: str
    s: int
    L: int
    t: int
    p: float
    restricted: list[int] = field(default_factory=list)
    ci_kind: str = "tCO2"
    parametric: bool = False
    param_kwh: float = 50.0

    @property
    def mode(self) -> str:
        return "parametric" if self.parametric else "data"


@dataclass
class Computation:
    inputs: ScenarioInputs
    machine: dict
    load: list[float]
    ci: list[float]
    result: Result


def status_message(r: Result, restricted: set[int]) -> str:
    """ok dışındaki durumlar için kullanıcıya gösterilen Türkçe açıklama."""
    if r.status == "non_shiftable":
        return NON_SHIFTABLE_TEXT
    if r.status == "out_of_range":
        return ("Aralık dışı: pencere aynı gün içinde kalmalı "
                "(başlangıç saati + uzunluk en fazla 24 olabilir).")
    if r.status == "restricted_conflict":
        hours = ", ".join(fmt.hour(h) for h in r.target_hours if h in restricted)
        return f"Seçilen pencere kısıtlı saatlerle çakışıyor ({hours}). Hesap yapılmadı."
    if r.status == "same_window":
        return "Standart ve seçilen pencere aynı; emisyon değişmez."
    if r.status == "no_load":
        return "Standart pencerede yük yok (0 kWh); yüzde hesaplanamaz."
    return ""


def template_text(c: Computation) -> str:
    """AI katmanı gelene kadar gösterilen şablon açıklama."""
    r, i = c.result, c.inputs
    if r.status != "ok":
        return status_message(r, set(i.restricted))
    direction = "düşürür" if r.delta_pct <= 0 else "artırır"
    return (
        f"{i.asset_id} yükünün %{fmt.num(i.p * 100, 0)}'ü {fmt.window(i.s, i.L)} yerine "
        f"{fmt.window(i.t, i.L)} aralığına alınırsa pencere emisyonu "
        f"{fmt.num(r.baseline_kg)} → {fmt.num(r.scenario_kg)} kg olur ({fmt.pct(r.delta_pct)}); "
        f"bu kaydırma emisyonu {direction}. "
        f"Günlük toplam emisyona etkisi {fmt.pct(r.daily_delta_pct)}."
    )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 820)
        self.current: Computation | None = None
        self._loading = False

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(50)
        self._debounce.timeout.connect(self.recompute)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 6)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_scenario_tab(), "Senaryo")
        root.addWidget(self.tabs, 1)

        self.footer = QLabel(FOOTER_TEXT)
        self.footer.setAlignment(Qt.AlignCenter)
        self.footer.setStyleSheet(f"color: {MUTED}; padding: 4px; border-top: 1px solid #d8dde3;")
        root.addWidget(self.footer)
        self.setCentralWidget(central)

        self._on_machine_changed()

    # ------------------------------------------------------------------ UI
    def _build_scenario_tab(self) -> QWidget:
        tab = QWidget()
        lay = QHBoxLayout(tab)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(360)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self._build_inputs())
        lay.addWidget(scroll)

        right = QVBoxLayout()
        self.chart = ChartWidget()
        right.addWidget(self.chart, 3)
        right.addWidget(self._build_result_card(), 0)
        right.addWidget(self._build_ai_box(), 1)
        lay.addLayout(right, 1)
        return tab

    def _build_inputs(self) -> QWidget:
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 6, 0)

        # Makine ve gün
        box = QGroupBox("Makine ve gün")
        form = QFormLayout(box)
        self.machine_combo = QComboBox()
        for m in data.machines():
            label = f"{m['id']} — {m['type']}"
            if not m["shiftable"]:
                label += " (kaydırılamaz)"
            self.machine_combo.addItem(label, m["id"])
        self.machine_combo.currentIndexChanged.connect(self._on_machine_changed)
        form.addRow("Makine", self.machine_combo)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.dateChanged.connect(self._on_date_changed)
        form.addRow("Gün", self.date_edit)

        self.non_shiftable_label = QLabel(NON_SHIFTABLE_TEXT)
        self.non_shiftable_label.setWordWrap(True)
        self.non_shiftable_label.setStyleSheet(f"color: {BAD}; font-weight: 600;")
        self.non_shiftable_label.hide()
        form.addRow(self.non_shiftable_label)
        v.addWidget(box)

        # Pencere
        box = QGroupBox("Zaman penceresi")
        form = QFormLayout(box)
        self.s_spin = self._spin(0, 23, 3, cls=HourSpinBox)
        self.L_spin = self._spin(1, 12, 3, " saat")
        self.t_spin = self._spin(0, 23, 18, cls=HourSpinBox)
        form.addRow("Standart başlangıç", self.s_spin)
        form.addRow("Pencere uzunluğu", self.L_spin)
        form.addRow("Hedef başlangıç", self.t_spin)

        p_row = QHBoxLayout()
        self.p_slider = QSlider(Qt.Horizontal)
        self.p_slider.setRange(0, 100)
        self.p_slider.setValue(100)
        self.p_label = QLabel("%100")
        self.p_label.setMinimumWidth(40)
        self.p_slider.valueChanged.connect(self._on_p_changed)
        p_row.addWidget(self.p_slider)
        p_row.addWidget(self.p_label)
        form.addRow("Kaydırma oranı", p_row)

        self.best_button = QPushButton("En iyi saati bul")
        self.best_button.clicked.connect(self.apply_best_window)
        form.addRow(self.best_button)
        v.addWidget(box)

        # Kısıtlı saatler
        self.restricted_box = QGroupBox("Kısıtlı saatler (hedef olamaz)")
        grid = QGridLayout(self.restricted_box)
        grid.setSpacing(3)
        self.hour_chips: list[QPushButton] = []
        for h in range(24):
            chip = QPushButton(f"{h:02d}")
            chip.setCheckable(True)
            chip.setFixedSize(36, 26)
            chip.setStyleSheet(
                "QPushButton { border: 1px solid #c3cbd3; border-radius: 4px; background: #f6f8fa; }"
                f"QPushButton:checked {{ background: {BAD}; color: white; border-color: {BAD}; }}"
                "QPushButton:disabled { color: #b0b8c0; }"
            )
            chip.toggled.connect(self.schedule)
            grid.addWidget(chip, h // 8, h % 8)
            self.hour_chips.append(chip)
        v.addWidget(self.restricted_box)

        # Emisyon tipi ve parametrik mod
        box = QGroupBox("Hesap ayarları")
        form = QFormLayout(box)
        ci_row = QHBoxLayout()
        self.ci_group = QButtonGroup(self)
        self.ci_tco2 = QRadioButton("tCO2")
        self.ci_tco2esd = QRadioButton("tCO2-eşd")
        self.ci_tco2.setChecked(True)
        for b in (self.ci_tco2, self.ci_tco2esd):
            self.ci_group.addButton(b)
            ci_row.addWidget(b)
            b.toggled.connect(self.schedule)
        form.addRow("Emisyon tipi", ci_row)

        self.param_check = QCheckBox("Parametrik mod (sabit yük)")
        self.param_check.toggled.connect(self._on_param_toggled)
        form.addRow(self.param_check)
        self.param_spin = QDoubleSpinBox()
        self.param_spin.setRange(0.0, 100000.0)
        self.param_spin.setDecimals(2)
        self.param_spin.setValue(50.0)
        self.param_spin.setSuffix(" kWh/saat")
        self.param_spin.setEnabled(False)
        self.param_spin.valueChanged.connect(self.schedule)
        form.addRow("Sabit yük", self.param_spin)
        v.addWidget(box)

        v.addStretch(1)
        return panel

    def _spin(self, lo: int, hi: int, value: int, suffix: str = "",
              cls: type[QSpinBox] = QSpinBox) -> QSpinBox:
        sp = cls()
        sp.setRange(lo, hi)
        sp.setValue(value)
        sp.setSuffix(suffix)
        sp.valueChanged.connect(self.schedule)
        return sp

    def _build_result_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("resultCard")
        card.setStyleSheet("#resultCard { background: #f7f9fb; border: 1px solid #d8dde3; border-radius: 8px; }")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(16, 10, 16, 10)

        left = QVBoxLayout()
        self.delta_label = QLabel("—")
        f = QFont()
        f.setPointSize(30)
        f.setBold(True)
        self.delta_label.setFont(f)
        self.verdict_label = QLabel("")
        self.verdict_label.setWordWrap(True)
        self.verdict_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        left.addWidget(self.delta_label)
        left.addWidget(self.verdict_label)
        lay.addLayout(left, 1)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        self.detail_labels: dict[str, QLabel] = {}
        rows = [
            ("baseline", "Standart pencere emisyonu"),
            ("scenario", "Seçilen pencere emisyonu"),
            ("shifted", "Kaydırılan enerji"),
            ("daily", "Günlük etki"),
        ]
        for i, (key, title) in enumerate(rows):
            t = QLabel(title)
            t.setStyleSheet(f"color: {MUTED};")
            val = QLabel("—")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet("font-weight: 600;")
            grid.addWidget(t, i, 0)
            grid.addWidget(val, i, 1)
            self.detail_labels[key] = val
        lay.addLayout(grid)
        return card

    def _build_ai_box(self) -> QWidget:
        box = QGroupBox("Açıklama")
        lay = QVBoxLayout(box)
        self.ai_text = QTextEdit()
        self.ai_text.setReadOnly(True)
        self.ai_text.setMinimumHeight(70)
        lay.addWidget(self.ai_text)
        return box

    # ------------------------------------------------------------ handlers
    def _selected_machine(self) -> dict:
        return data.machine(self.machine_combo.currentData())

    def _on_machine_changed(self) -> None:
        m = self._selected_machine()
        self._valid_days = m["days"]
        self._valid_ordinals = [Date.fromisoformat(d).toordinal() for d in self._valid_days]
        first, last = QDate.fromString(m["first_day"], "yyyy-MM-dd"), QDate.fromString(m["last_day"], "yyyy-MM-dd")

        self._loading = True
        self.date_edit.setDateRange(first, last)
        self._mark_calendar(first, last)
        current = self.date_edit.date().toString("yyyy-MM-dd")
        self.date_edit.setDate(QDate.fromString(self._nearest_day(current), "yyyy-MM-dd"))
        self._loading = False

        shiftable = m["shiftable"]
        for w in (self.s_spin, self.L_spin, self.t_spin, self.p_slider, self.best_button,
                  self.restricted_box, self.param_check):
            w.setEnabled(shiftable)
        self.param_spin.setEnabled(shiftable and self.param_check.isChecked())
        self.non_shiftable_label.setVisible(not shiftable)
        self.schedule()

    def _mark_calendar(self, first: QDate, last: QDate) -> None:
        cal = self.date_edit.calendarWidget()
        cal.setDateTextFormat(QDate(), QTextCharFormat())  # sıfırla
        invalid = QTextCharFormat()
        invalid.setForeground(QBrush(QColor("#c0c6cc")))
        valid = set(self._valid_days)
        d = first
        while d <= last:
            if d.toString("yyyy-MM-dd") not in valid:
                cal.setDateTextFormat(d, invalid)
            d = d.addDays(1)

    def _nearest_day(self, iso: str) -> str:
        try:
            target = Date.fromisoformat(iso).toordinal()
        except ValueError:
            return self._valid_days[0]
        i = bisect.bisect_left(self._valid_ordinals, target)
        candidates = [j for j in (i - 1, i) if 0 <= j < len(self._valid_ordinals)]
        best = min(candidates, key=lambda j: (abs(self._valid_ordinals[j] - target), j))
        return self._valid_days[best]

    def _on_date_changed(self, qdate: QDate) -> None:
        if self._loading:
            return
        iso = qdate.toString("yyyy-MM-dd")
        nearest = self._nearest_day(iso)
        if nearest != iso:
            self._loading = True
            self.date_edit.setDate(QDate.fromString(nearest, "yyyy-MM-dd"))
            self._loading = False
        self.schedule()

    def _on_p_changed(self, value: int) -> None:
        self.p_label.setText(f"%{value}")
        self.schedule()

    def _on_param_toggled(self, on: bool) -> None:
        self.param_spin.setEnabled(on)
        self.schedule()

    def schedule(self, *_args) -> None:
        if not self._loading:
            self._debounce.start()

    # --------------------------------------------------------------- state
    def inputs(self) -> ScenarioInputs:
        return ScenarioInputs(
            asset_id=self.machine_combo.currentData(),
            date=self.date_edit.date().toString("yyyy-MM-dd"),
            s=self.s_spin.value(),
            L=self.L_spin.value(),
            t=self.t_spin.value(),
            p=self.p_slider.value() / 100,
            restricted=[h for h, c in enumerate(self.hour_chips) if c.isChecked()],
            ci_kind="tCO2esd" if self.ci_tco2esd.isChecked() else "tCO2",
            parametric=self.param_check.isChecked(),
            param_kwh=self.param_spin.value(),
        )

    def set_inputs(self, i: ScenarioInputs) -> None:
        """Kaydedilmiş bir senaryoyu girdilere geri yükler."""
        self._loading = True
        idx = self.machine_combo.findData(i.asset_id)
        if idx >= 0:
            self.machine_combo.setCurrentIndex(idx)
        self._loading = False
        self._on_machine_changed()
        self._loading = True
        self.date_edit.setDate(QDate.fromString(self._nearest_day(i.date), "yyyy-MM-dd"))
        self.s_spin.setValue(i.s)
        self.L_spin.setValue(i.L)
        self.t_spin.setValue(i.t)
        self.p_slider.setValue(round(i.p * 100))
        self.p_label.setText(f"%{round(i.p * 100)}")
        for h, chip in enumerate(self.hour_chips):
            chip.setChecked(h in i.restricted)
        (self.ci_tco2esd if i.ci_kind == "tCO2esd" else self.ci_tco2).setChecked(True)
        self.param_check.setChecked(i.parametric)
        self.param_spin.setValue(i.param_kwh)
        self.param_spin.setEnabled(i.parametric and self._selected_machine()["shiftable"])
        self._loading = False
        self.recompute()

    def _series(self, i: ScenarioInputs) -> tuple[list[float], list[float]]:
        return data.scenario_series(i.asset_id, i.date, i.ci_kind,
                                    i.param_kwh if i.parametric else None)

    # ------------------------------------------------------------- compute
    def recompute(self) -> None:
        i = self.inputs()
        m = data.machine(i.asset_id)
        load, ci = self._series(i)
        r = simulate(load, ci, i.s, i.L, i.t, i.p, set(i.restricted), m["shiftable"])
        self.current = Computation(i, m, load, ci, r)

        self.chart.update_chart(ci, load, i.s, i.L, i.t, set(i.restricted), r.status,
                                r.delta_pct, CI_LABELS[i.ci_kind])
        self._update_card(self.current)
        self.ai_text.setPlainText(template_text(self.current))

    def _update_card(self, c: Computation) -> None:
        r = c.result
        unit = "kgCO2" if c.inputs.ci_kind == "tCO2" else "kgCO2-eşd"
        if r.status == "ok":
            good = r.delta_pct <= 0
            color = verdict_color = GOOD if good else BAD
            self.delta_label.setText(fmt.pct(r.delta_pct))
            self.verdict_label.setText("Daha düşük emisyon potansiyeli" if good
                                       else "Bu kaydırma emisyonu ARTIRIR")
        else:
            color = MUTED
            verdict_color = MUTED if r.status == "same_window" else BAD
            self.delta_label.setText(fmt.pct(0.0) if r.status == "same_window" else "—")
            self.verdict_label.setText(status_message(r, set(c.inputs.restricted)))
        self.delta_label.setStyleSheet(f"color: {color};")
        self.verdict_label.setStyleSheet(f"color: {verdict_color}; font-size: 13px; font-weight: 600;")

        computed = r.status in ("ok", "same_window", "no_load")
        self.detail_labels["baseline"].setText(f"{fmt.num(r.baseline_kg)} {unit}" if computed else "—")
        self.detail_labels["scenario"].setText(f"{fmt.num(r.scenario_kg)} {unit}" if computed else "—")
        self.detail_labels["shifted"].setText(f"{fmt.num(r.shifted_kwh)} kWh" if computed else "—")
        self.detail_labels["daily"].setText(fmt.pct(r.daily_delta_pct))

    def apply_best_window(self) -> None:
        i = self.inputs()
        m = data.machine(i.asset_id)
        load, ci = self._series(i)
        found = best_window(load, ci, i.s, i.L, i.p, set(i.restricted), m["shiftable"])
        if found is None:
            self.ai_text.setPlainText("Bu girdilerle geçerli bir hedef pencere bulunamadı "
                                      "(yük yok, aralık dışı veya tüm saatler kısıtlı).")
            return
        t, _ = found
        self.t_spin.setValue(t)
        self.recompute()
