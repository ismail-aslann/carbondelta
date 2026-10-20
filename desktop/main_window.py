"""Ana pencere: girdiler, grafik, sonuç kartı, AI açıklama kutusu."""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import date as Date

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QTextCharFormat, QValidator
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMenu, QPushButton, QRadioButton, QScrollArea, QSlider, QSpinBox, QTabWidget, QTextEdit,
    QToolButton, QVBoxLayout, QWidget,
)

from desktop import ai_context, fmt
from desktop.ai_client import AIReply, AIRequest, AIService, parse_json_reply, prompts
from desktop.chart_widget import ChartWidget
from desktop.history_db import HistoryDB
from desktop.tabs import CalcTab, HistoryTab, SourcesTab
from engine import data
from engine.best_window import best_window
from engine.core import Result, simulate

APP_TITLE = "CarbonDelta — Emisyon Potansiyeli Karar Destek"
FOOTER_TEXT = "Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo"
NON_SHIFTABLE_TEXT = "Bu yük kaydırılamaz (sürekli/kısıtlı süreç). Öneri üretilmez."
CI_LABELS = {"tCO2": "tCO2", "tCO2esd": "tCO2-eşd"}
DEMO_DATE = "2025-07-15"

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


SOURCE_LABELS = {
    "ai": "AI",
    "fallback_offline": "şablon · çevrimdışı",
    "fallback_invalid": "şablon · doğrulanamadı",
    "local": "uygulama",
    "pending": "AI metni hazırlanıyor…",
}


class MainWindow(QMainWindow):
    def __init__(self, db: HistoryDB | None = None, ai: AIService | None = None):
        super().__init__()
        self.db = db or HistoryDB()
        self.ai = ai or AIService(parent=self)
        self.ai.reply.connect(self._on_ai_reply)
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 860)
        self.current: Computation | None = None
        self._loading = False
        self._ai_gen = 0
        self._ai_slots: list[tuple[str, str, str]] = []  # (başlık, metin, kaynak)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(50)
        self._debounce.timeout.connect(self.recompute)

        # Kaydırıcı sürüklenirken her adımda API çağrısı yapmamak için ayrı bekleme.
        self._ai_debounce = QTimer(self)
        self._ai_debounce.setSingleShot(True)
        self._ai_debounce.setInterval(700)
        self._ai_debounce.timeout.connect(self._request_auto_ai)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 6)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_scenario_tab(), "Senaryo")
        self.calc_tab = CalcTab()
        self.tabs.addTab(self.calc_tab, "Hesabı Göster")
        self.history_tab = HistoryTab(self.db)
        self.history_tab.restore_requested.connect(self.restore_history)
        self.history_tab.summarize_requested.connect(self.summarize_history)
        self.tabs.addTab(self.history_tab, "Geçmiş")
        self.tabs.addTab(SourcesTab(), "Kaynaklar")
        root.addWidget(self.tabs, 1)

        self.footer = QLabel(FOOTER_TEXT)
        self.footer.setAlignment(Qt.AlignCenter)
        self.footer.setStyleSheet(f"color: {MUTED}; padding: 4px; border-top: 1px solid #d8dde3;")
        root.addWidget(self.footer)
        self.setCentralWidget(central)

        # Açılış: rapordaki demo senaryosu (comp_b, 15.07.2025, 03:00 → 18:00).
        self._loading = True
        self.date_edit.setDate(QDate.fromString(DEMO_DATE, "yyyy-MM-dd"))
        self._loading = False
        self._on_machine_changed()

    # ------------------------------------------------------------------ UI
    def _build_scenario_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)

        nl_row = QHBoxLayout()
        nl_row.addWidget(QLabel("Doğal dil:"))
        self.nl_edit = QLineEdit()
        self.nl_edit.setPlaceholderText("Örn. Kompresörü 3'ten 18'e al · Presi %50 oranla 2 saat 21'e kaydır")
        self.nl_edit.returnPressed.connect(self.submit_nl)
        nl_row.addWidget(self.nl_edit, 1)
        self.nl_button = QPushButton("Uygula")
        self.nl_button.clicked.connect(self.submit_nl)
        nl_row.addWidget(self.nl_button)
        self.nl_status = QLabel("")
        self.nl_status.setStyleSheet(f"color: {MUTED};")
        nl_row.addWidget(self.nl_status)
        outer.addLayout(nl_row)

        lay = QHBoxLayout()
        outer.addLayout(lay, 1)

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
        self.save_button = QPushButton("Kaydet")
        self.save_button.clicked.connect(self.save_current)
        grid.addWidget(self.save_button, len(rows), 1)
        lay.addLayout(grid)
        return card

    def _build_ai_box(self) -> QWidget:
        box = QGroupBox("Açıklama")
        lay = QVBoxLayout(box)

        bar = QHBoxLayout()
        self.ai_source_label = QLabel("")
        self.ai_source_label.setStyleSheet(f"color: {MUTED};")
        bar.addWidget(self.ai_source_label, 1)
        self.why_button = QPushButton("Neden bu saat?")
        self.why_button.clicked.connect(lambda: self.request_manual(ai_context.hour_reason))
        bar.addWidget(self.why_button)
        self.compare_button = QPushButton("Senaryoyu karşılaştır")
        self.compare_button.clicked.connect(self.compare_with_saved)
        bar.addWidget(self.compare_button)

        more = QToolButton()
        more.setText("Diğer")
        more.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(more)
        menu.addAction("Günlük etki yorumu", lambda: self.request_manual(ai_context.daily_impact))
        menu.addAction("Mevsim notu", lambda: self.request_manual(ai_context.season_note))
        menu.addAction("Rapor cümlesi", lambda: self.request_manual(ai_context.report_sentence))
        menu.addSeparator()
        menu.addAction("Terim açıkla…", self.explain_term)
        menu.addAction("Veri kaynakları", lambda: self.request_manual(lambda c: ai_context.data_source_explain()))
        menu.addSeparator()
        menu.addAction("Metni kopyala", lambda: QApplication.clipboard().setText(self.ai_text.toPlainText()))
        more.setMenu(menu)
        bar.addWidget(more)
        lay.addLayout(bar)

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
    def recompute(self, auto_ai: bool = True) -> None:
        i = self.inputs()
        m = data.machine(i.asset_id)
        load, ci = self._series(i)
        r = simulate(load, ci, i.s, i.L, i.t, i.p, set(i.restricted), m["shiftable"])
        self.current = Computation(i, m, load, ci, r)

        self.chart.update_chart(ci, load, i.s, i.L, i.t, set(i.restricted), r.status,
                                r.delta_pct, CI_LABELS[i.ci_kind])
        self._update_card(self.current)
        self.calc_tab.update_computation(self.current)
        if auto_ai:
            self._schedule_auto_ai()

    def save_current(self) -> int | None:
        if self.current is None:
            return None
        i, r = self.current.inputs, self.current.result
        row_id = self.db.add(
            asset_id=i.asset_id, date=i.date, s=i.s, L=i.L, t=i.t, p=i.p,
            restricted=i.restricted, mode=i.mode, ci_kind=i.ci_kind, status=r.status,
            delta_pct=r.delta_pct, daily_delta_pct=r.daily_delta_pct,
            baseline_kg=r.baseline_kg, scenario_kg=r.scenario_kg,
            param_kwh=i.param_kwh if i.parametric else None,
        )
        self.history_tab.refresh()
        self.statusBar().showMessage("Senaryo geçmişe kaydedildi.", 3000)
        return row_id

    def restore_history(self, h: dict) -> None:
        self.set_inputs(ScenarioInputs(
            asset_id=h["asset_id"], date=h["date"], s=h["s"], L=h["L"], t=h["t"], p=h["p"],
            restricted=h["restricted"], ci_kind=h["ci_kind"],
            parametric=h["mode"] == "parametric",
            param_kwh=h["param_kwh"] if h["param_kwh"] is not None else 50.0,
        ))
        self.tabs.setCurrentIndex(0)

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
            self._show_local("En iyi saat", "Bu girdilerle geçerli bir hedef pencere bulunamadı "
                             "(yük yok, aralık dışı veya tüm saatler kısıtlı).")
            return
        t, _ = found
        self.t_spin.setValue(t)
        self._debounce.stop()
        self.recompute(auto_ai=False)
        self.request_manual(ai_context.best_window_explain)

    # ------------------------------------------------------------------ AI
    def _start_batch(self, items: list[tuple[str, str, str]]) -> int:
        """Açıklama kutusunda yeni bir metin grubu başlatır; eski yanıtlar yok sayılır."""
        self._ai_gen += 1
        self._ai_slots = list(items)
        self._render_ai()
        return self._ai_gen

    def _show_local(self, title: str, text: str) -> None:
        self._ai_debounce.stop()
        self._start_batch([(title, text, "local")])

    def _render_ai(self) -> None:
        texts, sources = [], []
        offline = invalid = False
        for title, text, source in self._ai_slots:
            texts.append(text)
            sources.append(f"{title} · {SOURCE_LABELS[source]}")
            offline |= source == "fallback_offline"
            invalid |= source == "fallback_invalid"
        notes = []
        if offline:
            notes.append(prompts()["offline_message"])
        if invalid:
            notes.append(prompts()["invalid_message"])
        body = "\n\n".join(texts)
        self.ai_text.setPlainText("\n".join(notes) + ("\n\n" if notes else "") + body)
        self.ai_source_label.setText("  |  ".join(sources))

    def _submit_batch(self, reqs: list[AIRequest]) -> None:
        pending = "pending" if self.ai.online else "fallback_offline"
        gen = self._start_batch([(self._title(r), r.fallback(), pending) for r in reqs])
        for idx, req in enumerate(reqs):
            self.ai.submit(req, ("main", gen, idx))

    @staticmethod
    def _title(req: AIRequest) -> str:
        return prompts()["by_id"][req.func_id]["title"]

    def _schedule_auto_ai(self) -> None:
        c = self.current
        reqs = ai_context.auto_requests(c)
        if not reqs:
            self._show_local("Durum", status_message(c.result, set(c.inputs.restricted)))
            return
        if not self.ai.online:
            self._ai_debounce.stop()
            self._submit_batch(reqs)
            return
        # Şablon metni hemen göster, AI metni kısa bir beklemeden sonra iste.
        self._start_batch([(self._title(r), r.fallback(), "pending") for r in reqs])
        self._ai_debounce.start()

    def _request_auto_ai(self) -> None:
        if self.current is not None:
            reqs = ai_context.auto_requests(self.current)
            if reqs:
                self._submit_batch(reqs)

    def request_manual(self, builder) -> None:
        if self.current is None:
            return
        self._ai_debounce.stop()
        req = builder(self.current)
        if req is None:
            self._show_local("Açıklama", "Bu işlev mevcut senaryo durumunda kullanılamaz "
                             f"({status_message(self.current.result, set(self.current.inputs.restricted)) or 'hesap yok'}).")
            return
        self._submit_batch([req])

    def compare_with_saved(self) -> None:
        saved = self.db.latest()
        if saved is None:
            self._show_local("Senaryo kıyası", "Kıyas için önce bir senaryoyu \"Kaydet\" ile geçmişe ekleyin.")
            return
        self.request_manual(lambda c: ai_context.scenario_compare(saved, c))

    def explain_term(self) -> None:
        terms = list(prompts()["glossary"])
        term, ok = QInputDialog.getItem(self, "Terim açıkla", "Terim:", terms, 0, True)
        if ok and term.strip():
            self.request_manual(lambda c: ai_context.term_explain(term.strip()))

    def summarize_history(self) -> None:
        req = ai_context.history_summary(self.db.list(limit=10))
        if req is None:
            self.history_tab.show_summary("Özetlenecek kayıt yok.", "")
            return
        self.history_tab.show_summary(req.fallback(), SOURCE_LABELS["pending" if self.ai.online
                                                                    else "fallback_offline"])
        self.ai.submit(req, ("history",))

    def submit_nl(self) -> None:
        sentence = self.nl_edit.text().strip()
        if not sentence:
            return
        self.nl_status.setText("Çözümleniyor…" if self.ai.online else "")
        self.ai.submit(ai_context.nl_input(sentence, self.inputs()), ("nl", sentence))

    def _apply_nl(self, sentence: str, reply: AIReply) -> None:
        obj, via = None, "AI"
        if reply.source == "ai":
            try:
                obj = parse_json_reply(reply.text)
            except Exception:
                obj = None
        if obj is None:
            obj, via = ai_context.parse_nl_rule(sentence), "kural çözümleyici (AI çevrimdışı)"
        merged, err = ai_context.validate_nl(obj, self.inputs())
        if merged is None:
            self.nl_status.setText(f"Uygulanamadı: {err}")
            self.nl_status.setStyleSheet(f"color: {BAD};")
            self._show_local("Doğal dil girişi", prompts()["by_id"]["nl_input"]["fallback_template"])
            return
        cur = self.inputs()
        self.set_inputs(ScenarioInputs(
            asset_id=merged["asset_id"], date=cur.date, s=merged["s"], L=merged["L"],
            t=merged["t"], p=merged["p"], restricted=cur.restricted, ci_kind=cur.ci_kind,
            parametric=cur.parametric, param_kwh=cur.param_kwh,
        ))
        self.nl_status.setText(f"Uygulandı · {via}")
        self.nl_status.setStyleSheet(f"color: {GOOD};")

    def _on_ai_reply(self, tag, reply: AIReply) -> None:
        kind = tag[0]
        if kind == "main":
            _, gen, idx = tag
            if gen != self._ai_gen or idx >= len(self._ai_slots):
                return  # eski senaryoya ait yanıt
            title = self._ai_slots[idx][0]
            self._ai_slots[idx] = (title, reply.text, reply.source)
            self._render_ai()
        elif kind == "history":
            note = ""
            if reply.source == "fallback_offline":
                note = prompts()["offline_message"] + "\n\n"
            elif reply.source == "fallback_invalid":
                note = prompts()["invalid_message"] + "\n\n"
            self.history_tab.show_summary(note + reply.text, SOURCE_LABELS[reply.source])
        elif kind == "nl":
            self._apply_nl(tag[1], reply)

    def closeEvent(self, event) -> None:
        self.ai.shutdown()
        super().closeEvent(event)
