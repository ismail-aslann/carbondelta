"""Ana pencere: başlık bandı, girdiler, grafik, sonuç kartı, AI açıklama kartı."""
from __future__ import annotations

import bisect
import html
from dataclasses import dataclass, field
from datetime import date as Date

from PySide6.QtCore import QDate, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QIcon, QKeySequence, QShortcut, QTextCharFormat, QValidator
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QStackedWidget,
    QTabWidget,
    QTextBrowser,
    QToolButton, QVBoxLayout, QWidget,
)

from desktop import ai_context, delti, fmt, theme
from desktop.ai_client import AIReply, AIRequest, AIService, load_config, parse_json_reply, prompts
from desktop.chart_widget import ChartWidget
from desktop.history_db import HistoryDB
from desktop.resources import resource_path
from desktop.start_screen import StartScreen
from desktop.tools_tabs import BestWindowTab, NLTab
from desktop.annual_tab import AnnualTab
from desktop.plan_tab import PlanTab
from desktop.guide_tab import GuideTab
from desktop.data_tab import DataTab
from desktop.contact_tab import ContactTab
from desktop.delti_settings import DeltiSettingsDialog
from desktop.keyboard import DateEdit, KeyboardHelper
from desktop.tabs import CalcTab, HistoryTab, SourcesTab
from engine import data
from engine.best_window import best_window
from engine.core import Result, simulate
from engine.insights import fossil_sensitivity, shifted_renewable
from engine.appinfo import APP_NAME

APP_TITLE = f"{APP_NAME} — Emisyon Potansiyeli Karar Destek"
FOOTER_TEXT = "Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo"
NON_SHIFTABLE_TEXT = "Bu yük kaydırılamaz (sürekli/kısıtlı süreç). Öneri üretilmez."
CI_LABELS = {"tCO2": "tCO2", "tCO2esd": "tCO2-eşd"}
DEMO_DATE = "2025-07-15"
LEFT_PANEL_WIDTH = 330

GOOD = theme.GOOD
BAD = theme.BAD
MUTED = theme.MUTED


def machine_label(m: dict) -> str:
    return m["name"] if m["shiftable"] else f"{m['name']} — kaydırılamaz"


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


def status_message(r: Result, restricted: set[int], p: float | None = None) -> str:
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
        if p == 0:
            return "Kaydırma oranı %0: taşınacak enerji yok; yüzde hesaplanamaz. Oranı artırın."
        return "Standart pencerede yük yok (0 kWh); yüzde hesaplanamaz."
    return ""


def result_explanation(c: "Computation") -> str:
    """Sonuç kartında büyük yüzdenin ne anlama geldiğini anlatan cümle (hesaptan, AI'sız)."""
    i, r = c.inputs, c.result
    unit = "kgCO2" if i.ci_kind == "tCO2" else "kgCO2-eşd"
    src, tgt = fmt.window(i.s, i.L), fmt.window(i.t, i.L)
    moved = f"{fmt.num(r.shifted_kwh)} kWh enerji (yükün %{fmt.num(i.p * 100, 0)} kadarı)"
    if r.status == "ok":
        if r.delta_pct <= 0:
            what = (f"Bu yüzde, {src} aralığındaki {moved} {tgt} aralığında kullanılırsa "
                    f"bu enerjinin emisyonunun {fmt.num(r.baseline_kg)} {unit} yerine "
                    f"{fmt.num(r.scenario_kg)} {unit} olacağını gösterir.")
        else:
            what = (f"Bu yüzde, {src} aralığındaki {moved} {tgt} aralığına alınırsa "
                    f"emisyonun {fmt.num(r.baseline_kg)} {unit} yerine {fmt.num(r.scenario_kg)} {unit} "
                    f"olacağını, yani seçilen saatlerde şebekenin daha kirli olduğunu gösterir.")
        return (f"{what} Makinenin o günkü toplam emisyonu açısından etkisi "
                f"{fmt.pct(r.daily_delta_pct)}.")
    if r.status == "same_window":
        return "Yük aynı saatlerde kaldığı için emisyon değişmez."
    return ""


# Açıklama kartındaki kaynak etiketi: (metin, yazı rengi, zemin)
SOURCE_CHIPS = {
    "ai": ("AI", theme.PRIMARY, theme.PRIMARY_SOFT),
    "pending": ("Düşünüyor…", theme.MUTED, "#eef1f4"),
    "fallback_offline": ("Çevrimdışı · şablon", theme.MUTED, "#eef1f4"),
    "fallback_invalid": ("Şablon · doğrulanamadı", theme.WARN, theme.WARN_SOFT),
    "local": ("Uygulama", theme.MUTED, "#eef1f4"),
}


def chip_style(source: str) -> str:
    _, fg, bg = SOURCE_CHIPS[source]
    return (f"color: {fg}; background: {bg}; border-radius: 9px; padding: 2px 10px;"
            " font-size: 8.5pt; font-weight: 600;")


class MainWindow(QMainWindow):
    def __init__(self, db: HistoryDB | None = None, ai: AIService | None = None):
        super().__init__()
        self.db = db or HistoryDB()
        self.ai = ai or AIService(parent=self)
        self.ai.reply.connect(self._on_ai_reply)
        self.setWindowTitle(APP_TITLE)
        self.resize(1360, 820)
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

        self._saved_timer = QTimer(self)
        self._saved_timer.setSingleShot(True)
        self._saved_timer.setInterval(2500)
        self._saved_timer.timeout.connect(lambda: self.saved_label.setText(""))

        central = QWidget()
        central.setObjectName("root")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QVBoxLayout()
        body.setContentsMargins(14, 6, 14, 4)
        body.setSpacing(4)
        self.tabs = QTabWidget()
        self.scenario_tab = self._build_scenario_tab()
        self.tabs.addTab(self.scenario_tab, "Senaryo")
        self.best_tab = BestWindowTab(HourSpinBox)
        self.best_tab.apply_requested.connect(self.apply_best_choice)
        self.tabs.addTab(self.best_tab, "En Temiz Saat")
        self.annual_tab = AnnualTab(HourSpinBox)
        self.annual_tab.apply_requested.connect(self.apply_best_choice)
        self.annual_tab.explain_requested.connect(lambda req: self.ai.submit(req, ("annual", req.cache_key())))
        self.annual_tab.footer_changed.connect(lambda t, r: self._tab_footer(self.annual_tab, t, r))
        self.tabs.addTab(self.annual_tab, "Yıllık Etki")
        self.plan_tab = PlanTab(HourSpinBox)
        self.plan_tab.apply_requested.connect(self.apply_best_choice)
        self.plan_tab.footer_changed.connect(lambda t, r: self._tab_footer(self.plan_tab, t, r))
        self.tabs.addTab(self.plan_tab, "Tesis Planı")
        self.nl_tab = NLTab()
        self.nl_tab.submit.connect(self.submit_nl_page)
        self.nl_tab.open_requested.connect(self.open_nl_result)
        self.nl_tab.settings_requested.connect(self.open_delti_settings)
        self.nl_tab.set_online(self.ai.online)
        self.tabs.addTab(self.nl_tab, "Delti'ye Sor")
        self.calc_tab = CalcTab()
        self.tabs.addTab(self.calc_tab, "Hesabı Göster")
        self.history_tab = HistoryTab(self.db)
        self.history_tab.restore_requested.connect(self.restore_history)
        self.history_tab.summarize_requested.connect(self.summarize_history)
        self.tabs.addTab(self.history_tab, "Geçmiş")
        self.data_tab = DataTab()
        self.data_tab.data_changed.connect(lambda msg: QTimer.singleShot(0, lambda: self._apply_data_change(msg)))
        self.tabs.addTab(self.data_tab, "Veri")
        self.guide_tab = GuideTab()
        self.tabs.addTab(self.guide_tab, "Kılavuz")
        self.sources_tab = SourcesTab()
        self.tabs.addTab(self.sources_tab, "Kaynaklar")
        self.contact_tab = ContactTab()
        self.tabs.addTab(self.contact_tab, "İletişim")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        body.addWidget(self.tabs, 1)

        self.footer = QLabel(FOOTER_TEXT)
        self.footer.setAlignment(Qt.AlignCenter)
        self.footer.setStyleSheet(f"color: {MUTED}; padding: 3px; font-size: 8.5pt;")
        body.addWidget(self.footer)
        root.addLayout(body, 1)

        # Başlangıç ekranı (0) ve uygulama (1)
        self.start = StartScreen()
        self.start.action.connect(self._on_start_action)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.start)
        self.pages.addWidget(central)
        self.setCentralWidget(self.pages)

        # Açılış: rapordaki demo senaryosu (Kompresör, 15.07.2025, 03:00 → 18:00).
        self._loading = True
        self.date_edit.setDate(QDate.fromString(DEMO_DATE, "yyyy-MM-dd"))
        self._loading = False
        self._on_machine_changed()
        self._install_keyboard()
        self.go_home()

    # ------------------------------------------------------------------ UI
    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("header")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(16, 8, 16, 6)
        lay.setSpacing(12)

        icon = QLabel()
        icon_path = resource_path("desktop/icon.png")
        if icon_path.exists():
            icon.setPixmap(QIcon(str(icon_path)).pixmap(QSize(36, 36)))
        lay.addWidget(icon)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        t = QLabel(APP_NAME)
        t.setObjectName("appTitle")
        st = QLabel("Emisyon Potansiyeli Karar Destek")
        st.setObjectName("appSubtitle")
        titles.addWidget(t)
        titles.addWidget(st)
        lay.addLayout(titles)
        lay.addSpacing(18)
        self.home_button = QPushButton("⌂  Ana sayfa")
        self.home_button.setObjectName("nlButton")
        self.home_button.setToolTip("Başlangıç ekranına dön (Esc)")
        self.home_button.clicked.connect(self.go_home)
        lay.addWidget(self.home_button)
        lay.addStretch(1)

        nl_box = QVBoxLayout()
        nl_box.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.nl_edit = QLineEdit()
        self.nl_edit.setObjectName("nlEdit")
        self.nl_edit.setMinimumWidth(420)
        self.nl_edit.setPlaceholderText("Delti'ye yazın: Kompresörü 3'ten 18'e al · Presi %50 ile 21'e kaydır")
        self.nl_edit.returnPressed.connect(self.submit_nl)
        row.addWidget(self.nl_edit, 1)
        self.nl_button = QPushButton("Sor")
        self.nl_button.setObjectName("nlButton")
        self.nl_button.clicked.connect(self.submit_nl)
        row.addWidget(self.nl_button)
        nl_box.addLayout(row)
        self.nl_status = QLabel("")
        self.nl_status.setStyleSheet("color: #cfe9df; font-size: 8.5pt; padding-left: 14px;")
        nl_box.addWidget(self.nl_status)
        lay.addLayout(nl_box, 2)
        return header

    def _build_scenario_tab(self) -> QWidget:
        tab = QWidget()
        lay = QHBoxLayout(tab)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(LEFT_PANEL_WIDTH + 14)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self._build_inputs())
        lay.addWidget(scroll)

        right = QVBoxLayout()
        right.setSpacing(10)
        chart_card, chart_lay = theme.card(margins=(6, 6, 6, 4))
        self.chart = ChartWidget()
        chart_lay.addWidget(self.chart)
        right.addWidget(chart_card, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        bottom.addWidget(self._build_result_card(), 4)
        bottom.addWidget(self._build_ai_box(), 6)
        right.addLayout(bottom, 0)
        lay.addLayout(right, 1)
        return tab

    def _form(self, parent_lay: QVBoxLayout) -> QFormLayout:
        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        parent_lay.addLayout(form)
        return form

    def _build_inputs(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(LEFT_PANEL_WIDTH)
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        # Makine ve gün
        box, box_lay = theme.card("Makine ve gün")
        form = self._form(box_lay)
        self.machine_combo = QComboBox()
        for m in data.machines():
            self.machine_combo.addItem(machine_label(m), m["id"])
        self.machine_combo.currentIndexChanged.connect(self._on_machine_changed)
        form.addRow("Makine", self.machine_combo)

        self.date_edit = DateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.dateChanged.connect(self._on_date_changed)
        form.addRow("Gün", self.date_edit)

        self.non_shiftable_box, ns_lay = theme.card(name="alert", margins=(10, 8, 10, 8))
        self.non_shiftable_label = QLabel(NON_SHIFTABLE_TEXT)
        self.non_shiftable_label.setWordWrap(True)
        ns_lay.addWidget(self.non_shiftable_label)
        self.non_shiftable_box.hide()
        box_lay.addWidget(self.non_shiftable_box)
        # Emisyon tipi ve parametrik mod (aynı kartta)
        ci_row = QHBoxLayout()
        ci_row.setSpacing(16)
        ci_row.addWidget(QLabel("Emisyon tipi"))
        self.ci_group = QButtonGroup(self)
        self.ci_tco2 = QRadioButton("tCO2")
        self.ci_tco2esd = QRadioButton("tCO2-eşd")
        self.ci_tco2.setChecked(True)
        for b in (self.ci_tco2, self.ci_tco2esd):
            self.ci_group.addButton(b)
            ci_row.addWidget(b)
            b.toggled.connect(self.schedule)
        ci_row.addStretch(1)
        box_lay.addLayout(ci_row)

        self.param_check = QCheckBox("Parametrik mod (sabit yük)")
        self.param_check.setToolTip("Ölçülen yük yerine her saat için aynı kWh değerini kullanır.")
        self.param_check.toggled.connect(self._on_param_toggled)
        box_lay.addWidget(self.param_check)
        self.param_row = QWidget()
        pr = QHBoxLayout(self.param_row)
        pr.setContentsMargins(22, 0, 0, 0)
        pr.addWidget(QLabel("Sabit yük"))
        self.param_spin = QDoubleSpinBox()
        self.param_spin.setRange(0.0, 100000.0)
        self.param_spin.setDecimals(2)
        self.param_spin.setValue(50.0)
        self.param_spin.setSuffix(" kWh/saat")
        self.param_spin.valueChanged.connect(self.schedule)
        pr.addWidget(self.param_spin, 1)
        self.param_row.hide()
        box_lay.addWidget(self.param_row)

        v.addWidget(box)

        # Pencere
        box, box_lay = theme.card("Zaman penceresi")
        form = self._form(box_lay)
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
        self.p_label.setMinimumWidth(38)
        self.p_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.p_slider.valueChanged.connect(self._on_p_changed)
        p_row.addWidget(self.p_slider)
        p_row.addWidget(self.p_label)
        form.addRow("Kaydırma oranı", p_row)

        self.best_button = QPushButton("En iyi saati bul")
        self.best_button.setObjectName("primary")
        self.best_button.setToolTip("Aynı yük için en düşük emisyonlu hedef pencereyi seçer (kısıtlı saatler atlanır).")
        self.best_button.clicked.connect(self.apply_best_window)
        box_lay.addWidget(self.best_button)
        v.addWidget(box)

        # Kısıtlı saatler
        self.restricted_box, rb_lay = theme.card("Kısıtlı saatler")
        self.restricted_box.setToolTip("İşaretli saatler hedef pencereye giremez.")
        rb_lay.itemAt(0).widget().setText(
            f"Kısıtlı saatler <span style='color:{MUTED}; font-weight:400; font-size:9pt;'>· hedef olamaz</span>")
        grid = QGridLayout()
        grid.setSpacing(4)
        self.hour_chips: list[QPushButton] = []
        for h in range(24):
            chip = QPushButton(f"{h:02d}")
            chip.setObjectName("chip")
            chip.setCheckable(True)
            chip.setFixedHeight(24)
            chip.toggled.connect(self.schedule)
            grid.addWidget(chip, h // 8, h % 8)
            # Sekme zincirine yalnızca ilk çip girer; diğerlerine oklarla geçilir.
            chip.setFocusPolicy(Qt.StrongFocus if h == 0 else Qt.ClickFocus)
            self.hour_chips.append(chip)
        rb_lay.addLayout(grid)
        v.addWidget(self.restricted_box)

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
        card, lay = theme.card("Sonuç", spacing=4)

        self.delta_label = QLabel("—")
        self.delta_label.setObjectName("bigDelta")
        self.verdict_label = QLabel("")
        self.verdict_label.setWordWrap(True)
        self.explain_label = QLabel("")
        self.explain_label.setWordWrap(True)
        self.explain_label.setStyleSheet(f"color: {theme.TEXT}; font-size: 9pt; line-height: 135%;")
        lay.addWidget(self.delta_label)
        lay.addWidget(self.verdict_label)
        lay.addWidget(self.explain_label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {theme.BORDER};")
        lay.addWidget(line)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(3)
        self.detail_labels: dict[str, QLabel] = {}
        rows = [
            ("baseline", "Standart pencere emisyonu"),
            ("scenario", "Seçilen pencere emisyonu"),
            ("shifted", "Kaydırılan enerji"),
            ("daily", "Günlük etki"),
            ("renewable", "Yenilenebilir payı (kaydırılan enerji)"),
            ("fossil", "Fosil marjinal varsayımla"),
        ]
        for i, (key, title) in enumerate(rows):
            t = theme.muted(title)
            val = QLabel("—")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet("font-weight: 600;")
            grid.addWidget(t, i, 0)
            grid.addWidget(val, i, 1)
            self.detail_labels[key] = val
        lay.addLayout(grid)
        lay.addStretch(1)

        save_row = QHBoxLayout()
        self.saved_label = QLabel("")
        self.saved_label.setStyleSheet(f"color: {GOOD}; font-weight: 600;")
        save_row.addWidget(self.saved_label, 1)
        self.save_button = QPushButton("Senaryoyu kaydet")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save_current)
        save_row.addWidget(self.save_button)
        lay.addLayout(save_row)
        return card

    def _build_ai_box(self) -> QWidget:
        card, lay = theme.card(spacing=6)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.delti_avatar = QLabel()
        self.delti_avatar.setFixedSize(34, 34)
        self.delti_avatar.setPixmap(delti.pixmap("ready", 34, self.devicePixelRatioF() or 1.0))
        self.delti_avatar.setToolTip("Delti, CarbonDelta'nın AI yardımcısı. Hesap yapmaz; sonuçları açıklar.")
        head.addWidget(self.delti_avatar)
        title = QLabel("Delti açıklıyor")
        title.setObjectName("cardTitle")
        head.addWidget(title)
        self.ai_chip = QLabel("")
        self.ai_chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        head.addWidget(self.ai_chip)
        head.addStretch(1)
        lay.addLayout(head)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.why_button = QPushButton("Neden bu saat?")
        self.why_button.setToolTip("Standart ve seçilen saatlerin şebeke üretim karışımını açıklar.")
        self.why_button.clicked.connect(lambda: self.request_manual(ai_context.hour_reason))
        actions.addWidget(self.why_button)
        self.compare_button = QPushButton("Karşılaştır")
        self.compare_button.setToolTip("Mevcut senaryoyu en son kaydedilen senaryoyla kıyaslar.")
        self.compare_button.clicked.connect(self.compare_with_saved)
        actions.addWidget(self.compare_button)

        more = QToolButton()
        more.setText("Daha fazla ▾")
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
        menu.addSeparator()
        menu.addAction("Delti ayarları…  (Ctrl+,)", self.open_delti_settings)
        more.setMenu(menu)
        actions.addWidget(more)
        actions.addStretch(1)
        for b in (self.why_button, self.compare_button, more):
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.ai_text = QTextBrowser()
        self.ai_text.setOpenLinks(False)
        self.ai_text.setMinimumHeight(80)
        lay.addWidget(self.ai_text, 1)
        lay.addLayout(actions)
        return card

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
                  self.restricted_box, self.param_check, self.param_row):
            w.setEnabled(shiftable)
        self.non_shiftable_box.setVisible(not shiftable)
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
        self.param_row.setVisible(on)
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
        self.param_row.setVisible(i.parametric)
        self.param_spin.setValue(i.param_kwh)
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
        if self.tabs.currentWidget() not in (self.annual_tab, self.plan_tab, self.sources_tab):
            self._set_footer(data.source_label(i.asset_id, i.date), data.is_real(i.asset_id))
        self._update_card(self.current)
        self.calc_tab.update_computation(self.current)
        if auto_ai:
            self._schedule_auto_ai()

    def _set_footer(self, text: str, real: bool) -> None:
        self.footer.setText(text)
        self.footer.setStyleSheet(f"color: {theme.PRIMARY_DARK if real else MUTED}; padding: 3px; font-size: 8.5pt;"
                                  + (" font-weight: 600;" if real else ""))

    def _tab_footer(self, tab: QWidget, text: str, real: bool) -> None:
        """Yıllık Etki / Tesis Planı kendi kapsamlarının kaynak etiketini gösterir (yalnızca açıkken)."""
        if self.tabs.currentWidget() is tab and text:
            self._set_footer(text, real)

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
        self.saved_label.setText("✓ Geçmişe kaydedildi")
        self._saved_timer.start()
        return row_id

    def restore_history(self, h: dict) -> None:
        if self._missing_machine(h["asset_id"]):
            return
        self.set_inputs(ScenarioInputs(
            asset_id=h["asset_id"], date=h["date"], s=h["s"], L=h["L"], t=h["t"], p=h["p"],
            restricted=h["restricted"], ci_kind=h["ci_kind"],
            parametric=h["mode"] == "parametric",
            param_kwh=h["param_kwh"] if h["param_kwh"] is not None else 50.0,
        ))
        self.tabs.setCurrentWidget(self.scenario_tab)
        opened = self.inputs().date
        if opened != h["date"]:
            QMessageBox.information(
                self, "Gün değişti",
                f"Kaydın günü ({fmt.date(h['date'])}) artık veride yok (şebeke ya da makine paketi kapatılmış "
                f"olabilir). En yakın gün olan {fmt.date(opened)} açıldı; sonuç kayıttakinden farklı olabilir.")

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
            self.verdict_label.setText(status_message(r, set(c.inputs.restricted), c.inputs.p))
        self.delta_label.setStyleSheet(f"color: {color};")
        self.verdict_label.setStyleSheet(f"color: {verdict_color}; font-weight: 600;")
        text = result_explanation(c)
        self.explain_label.setText(text)
        self.explain_label.setVisible(bool(text))

        computed = r.status in ("ok", "same_window", "no_load")
        self.detail_labels["baseline"].setText(f"{fmt.num(r.baseline_kg)} {unit}" if computed else "—")
        self.detail_labels["scenario"].setText(f"{fmt.num(r.scenario_kg)} {unit}" if computed else "—")
        self.detail_labels["shifted"].setText(f"{fmt.num(r.shifted_kwh)} kWh" if computed else "—")
        self.detail_labels["daily"].setText(fmt.pct(r.daily_delta_pct))
        i = c.inputs
        rs = shifted_renewable(i.date, c.load, i.s, i.L, i.t, i.p) if r.status in ("ok", "same_window") else None
        lab = self.detail_labels["renewable"]
        if rs is None:
            lab.setText("—")
            lab.setStyleSheet("font-weight: 600;")
        else:
            lab.setText(f"%{fmt.num(rs[0], 1)} → %{fmt.num(rs[1], 1)}")
            lab.setStyleSheet(f"font-weight: 600; color: {GOOD if rs[1] >= rs[0] else BAD};")
        lab.setToolTip("Kaydırılan enerjinin, tüketildiği saatlerde şebekedeki yenilenebilir (rüzgâr, güneş, hidro, "
                       "jeotermal, biyokütle) üretim payı: standart pencere → seçilen pencere.")
        fl = self.detail_labels["fossil"]
        fp = None
        if r.status == "ok":
            fp = fossil_sensitivity(c.load, data.ci_fossil_24(i.date, i.ci_kind), i.s, i.L, i.t, i.p)[2]
        fl.setText(fmt.pct(fp))
        fl.setStyleSheet("font-weight: 600;" + ("" if fp is None else f" color: {GOOD if fp <= 0 else BAD};"))
        fl.setToolTip("Duyarlılık: kaydırılan yükü o saatlerde yalnızca fosil santrallerin karşıladığı varsayımıyla "
                      "aynı hesap (marjinal santral yaklaşımı). Ana sonuç ortalama yoğunlukla hesaplanır; bu değer "
                      "daha temkinli bir alt sınır gösterir.")

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

    # ------------------------------------------------------------ başlangıç
    def refresh_start(self) -> None:
        """Başlangıç ekranındaki eğriyi, son senaryo kartını ve durum satırını günceller."""
        self.start.set_curve(data.ci_24(DEMO_DATE))
        self.start.set_status(self.ai.online, len(data.machines()))
        self.start.source_label.setText(data.overall_source_label())
        latest = self.db.latest()
        if latest is not None and latest["delta_pct"] is not None and data.has_machine(latest["asset_id"]):
            name = data.machine(latest["asset_id"])["name"]
            self.start.set_resume("Son senaryo", f"{name} · {fmt.hour(latest['s'])} → {fmt.hour(latest['t'])}",
                                  fmt.pct(latest["delta_pct"]), latest["delta_pct"] <= 0)
            return
        # Kayıt yoksa demo senaryo; yüzde motordan hesaplanır.
        demo = self._demo_inputs()
        load, ci = self._series(demo)
        r = simulate(load, ci, demo.s, demo.L, demo.t, demo.p)
        name = data.machine(demo.asset_id)["name"]
        self.start.set_resume("Demo senaryo", f"{name} · {fmt.hour(demo.s)} → {fmt.hour(demo.t)}",
                              fmt.pct(r.delta_pct), (r.delta_pct or 0) <= 0)

    def _apply_data_change(self, message: str) -> None:
        """Veri paketi eklendi/açıldı/kapandı/silindi: her şeyi yeniden oku ve tazele."""
        data.reload()
        self.data_tab.refresh()
        self.reload_machines()
        self.best_tab.reload_machines()
        self.annual_tab.reload_machines()
        self.plan_tab.reload_machines()
        self.calc_tab._fill_etkb()
        self.sources_tab.refresh()
        if self.tabs.currentWidget() is self.sources_tab:
            self._on_tab_changed(self.tabs.currentIndex())
        self.history_tab.refresh()
        self.refresh_start()
        self.data_tab.show_message(message)

    def reload_machines(self) -> None:
        current = self.machine_combo.currentData()
        self._loading = True
        self.machine_combo.blockSignals(True)  # boşaltırken "makine değişti" tetiklenmesin
        self.machine_combo.clear()
        for m in data.machines():
            self.machine_combo.addItem(machine_label(m), m["id"])
        idx = self.machine_combo.findData(current)
        self.machine_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.machine_combo.blockSignals(False)
        self._loading = False
        self._on_machine_changed()

    def _missing_machine(self, asset_id: str) -> bool:
        if data.has_machine(asset_id):
            return False
        QMessageBox.information(self, "Senaryo açılamadı",
                                "Bu kaydın makinesi artık yüklü değil (veri paketi kapatılmış ya da silinmiş). "
                                "Veri sekmesinden paketi yeniden açabilirsiniz.")
        return True

    @staticmethod
    def _demo_inputs() -> ScenarioInputs:
        return ScenarioInputs("comp_b", DEMO_DATE, 3, 3, 18, 1.0)

    def go_home(self) -> None:
        self.refresh_start()
        self.pages.setCurrentIndex(0)
        self.start._select(0)
        self.start.setFocus()

    def toggle_fullscreen(self) -> None:
        """Sunum modu: projeksiyonda pencere çerçevesi ve görev çubuğu olmadan."""
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def open_delti_settings(self) -> None:
        dlg = DeltiSettingsDialog(self.ai.cfg, self)
        if dlg.exec():
            self.ai.set_config(load_config())
            self._apply_ai_state()

    def _apply_ai_state(self) -> None:
        """Delti açıldı/kapandı: durum satırları ve mevcut senaryonun açıklaması yenilenir."""
        online = self.ai.online
        self.nl_tab.set_online(online)
        self.start.set_status(online, len(data.machines()))
        self._set_nl_status("Delti uyanık." if online else "Delti uyuyor: Delti ayarlarından anahtar girin (Ctrl+,).",
                            "ok" if online else "info")
        if self.current is not None:
            self._schedule_auto_ai()

    def _open_app(self, tab: QWidget) -> None:
        self.pages.setCurrentIndex(1)
        if self.tabs.currentWidget() is tab:
            # Sekme zaten açıksa currentChanged gelmez; Senaryo'daki yeni değerleri yine de alsın.
            self._on_tab_changed(self.tabs.currentIndex())
        else:
            self.tabs.setCurrentWidget(tab)
        QTimer.singleShot(0, self._focus_current_tab)

    def _on_start_action(self, key: str) -> None:
        if key == "resume":
            latest = self.db.latest()
            if latest is not None and latest["delta_pct"] is not None and data.has_machine(latest["asset_id"]):
                self.restore_history(latest)
            else:
                self.set_inputs(self._demo_inputs())
            self._open_app(self.scenario_tab)
        elif key == "new":
            self.new_scenario()
            self._open_app(self.scenario_tab)
        elif key == "best":
            self._open_app(self.best_tab)
        elif key == "annual":
            self._open_app(self.annual_tab)
        elif key == "plan":
            self._open_app(self.plan_tab)
        elif key == "nl":
            self._open_app(self.nl_tab)
            self.nl_tab.focus_input()
        elif key == "history":
            self._open_app(self.history_tab)
        elif key == "calc":
            self._open_app(self.calc_tab)
        elif key == "guide":
            self.open_guide()
        elif key == "data":
            self._open_app(self.data_tab)
        elif key == "contact":
            self._open_app(self.contact_tab)
        elif key == "sources":
            self._open_app(self.sources_tab)
        elif key == "delti_settings":
            self.open_delti_settings()

    def new_scenario(self) -> None:
        """Temiz başlangıç: makine ve gün korunur; kısıtlar, oran ve mod sıfırlanır."""
        cur = self.inputs()
        self.set_inputs(ScenarioInputs(cur.asset_id, cur.date, 3, 3, 18, 1.0))

    def _on_tab_changed(self, _index: int) -> None:
        if self.tabs.currentWidget() is self.best_tab:
            i = self.inputs()
            self.best_tab.load_inputs(i.asset_id, i.date, i.s, i.L, i.p, i.restricted)
        elif self.tabs.currentWidget() is self.annual_tab:
            i = self.inputs()
            self.annual_tab.load_inputs(i.asset_id, i.date, i.s, i.L, i.t, i.p, i.restricted, i.ci_kind,
                                        i.param_kwh if i.parametric else None)
        elif self.tabs.currentWidget() is self.plan_tab:
            i = self.inputs()
            self.plan_tab.load_inputs(i.date, i.s, i.L, i.p, i.restricted, i.ci_kind)
        if self.tabs.currentWidget() is self.sources_tab:
            sm = data.source_summary()
            self._set_footer(data.overall_source_label(), bool(sm["real"]) and not sm["sample"])
        elif self.tabs.currentWidget() not in (self.annual_tab, self.plan_tab) and self.current is not None:
            i = self.current.inputs
            self._set_footer(data.source_label(i.asset_id, i.date), data.is_real(i.asset_id))
        QTimer.singleShot(0, self._focus_current_tab)

    def _focus_current_tab(self) -> None:
        """Faresiz kullanım: her sekmede klavye odağı mantıklı bir öğede başlar."""
        if self.pages.currentIndex() != 1:
            return
        tab = self.tabs.currentWidget()
        if tab is self.scenario_tab:
            self.machine_combo.setFocus(Qt.TabFocusReason)
        elif tab is self.best_tab:
            self.best_tab.table.setFocus(Qt.TabFocusReason)
        elif tab is self.annual_tab:
            self.annual_tab.focus_default()
        elif tab is self.plan_tab:
            self.plan_tab.focus_default()
        elif tab is self.nl_tab:
            self.nl_tab.focus_input()
        elif tab is self.calc_tab:
            self.calc_tab.table.setFocus(Qt.TabFocusReason)
        elif tab is self.history_tab:
            self.history_tab.table.setFocus(Qt.TabFocusReason)
        elif tab is self.guide_tab:
            self.guide_tab.focus_default()
        elif tab is self.data_tab:
            self.data_tab.focus_default()
        elif tab is self.contact_tab:
            self.contact_tab.focus_default()
        else:
            tab.setFocus(Qt.TabFocusReason)

    # --------------------------------------------------------------- klavye
    def _install_keyboard(self) -> None:
        self.kbd = KeyboardHelper(self)
        QApplication.instance().installEventFilter(self.kbd)
        self.kbd.register_grid(self.hour_chips, 8)

        def sc(keys: str, fn, app_only: bool = False) -> None:
            def run():
                if app_only and self.pages.currentIndex() != 1:
                    return
                fn()
            QShortcut(QKeySequence(keys), self, activated=run, context=Qt.WindowShortcut)

        sc("Esc", self._on_escape)
        sc("F1", self.open_guide)
        sc("Ctrl+,", self.open_delti_settings)
        sc("F11", self.toggle_fullscreen)
        for n in range(min(self.tabs.count(), 10)):  # Ctrl+1 … Ctrl+0 ilk on sekme
            sc(f"Ctrl+{(n + 1) % 10}", lambda n=n: self._open_app(self.tabs.widget(n)))
        sc("Ctrl+Tab", lambda: self._cycle_tab(1), app_only=True)
        sc("Ctrl+Shift+Tab", lambda: self._cycle_tab(-1), app_only=True)
        sc("Ctrl+Backtab", lambda: self._cycle_tab(-1), app_only=True)
        sc("Ctrl+S", self.save_current, app_only=True)
        sc("Ctrl+B", self._best_shortcut, app_only=True)

    def _on_escape(self) -> None:
        if self.pages.currentIndex() == 1:
            self.go_home()

    def open_guide(self, section: str | None = None) -> None:
        self._open_app(self.guide_tab)
        if section:
            self.guide_tab.show_section(section)

    def _cycle_tab(self, step: int) -> None:
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % self.tabs.count())

    def _best_shortcut(self) -> None:
        self.tabs.setCurrentWidget(self.scenario_tab)
        self.apply_best_window()

    def apply_best_choice(self, choice: dict) -> None:
        cur = self.inputs()
        self.set_inputs(ScenarioInputs(choice["asset_id"], choice["date"], choice["s"], choice["L"],
                                       choice["t"], choice["p"], restricted=cur.restricted,
                                       ci_kind=cur.ci_kind))
        self.tabs.setCurrentWidget(self.scenario_tab)

    def submit_nl_page(self, sentence: str) -> None:
        self.ai.submit(ai_context.nl_input(sentence, self.inputs()), ("nlpage", sentence))

    def _nl_merge(self, sentence: str, reply: AIReply) -> tuple[dict | None, str, str]:
        """AI ve kural çözümleyiciyi birleştirir: cümlede açıkça yazan sayılar (saat, süre, yüzde)
        kural çözümleyiciden alınır; AI yalnızca eksikleri tamamlar. Oran yazılmadıysa %100."""
        rule = ai_context.parse_nl_rule(sentence)
        ai_obj = None
        if reply.source == "ai":
            try:
                ai_obj = parse_json_reply(reply.text)
            except Exception:
                ai_obj = None
        if ai_obj is None:
            obj, via = dict(rule), "kural çözümleyici (Delti çevrimdışı)"
        else:
            obj, via = {**ai_obj, **rule}, "Delti (AI)"
        if not any(k in obj for k in ("asset_id", "s", "L", "t", "p")):
            return None, "Cümleden senaryo bilgisi çıkarılamadı.", via
        obj.setdefault("p", 1.0)
        merged, err = ai_context.validate_nl(obj, self.inputs())
        return merged, err, via

    def _apply_nl_page(self, sentence: str, reply: AIReply) -> None:
        merged, err, via = self._nl_merge(sentence, reply)
        if merged is None:
            self.nl_tab.show_error(err)
            return
        cur = self.inputs()
        merged["date"] = cur.date

        def explain(m, mg, r):
            c = Computation(ScenarioInputs(mg["asset_id"], mg["date"], mg["s"], mg["L"], mg["t"], mg["p"]),
                            m, [], [], r)
            return result_explanation(c) or status_message(r, set(), mg["p"])

        # Anlaşılan senaryo hemen Senaryo sekmesine uygulanır (önizleme ayrıca gösterilir).
        self.set_inputs(ScenarioInputs(merged["asset_id"], merged["date"], merged["s"], merged["L"],
                                       merged["t"], merged["p"], restricted=cur.restricted,
                                       ci_kind=cur.ci_kind))
        self.nl_tab.show_result(merged, via, explain)

    def open_nl_result(self, _merged: dict) -> None:
        self.tabs.setCurrentWidget(self.scenario_tab)

    # ------------------------------------------------------------------ AI
    def _start_batch(self, items: list[tuple[str, str, str]]) -> int:
        """Açıklama kartında yeni bir metin grubu başlatır; eski yanıtlar yok sayılır."""
        self._ai_gen += 1
        self._ai_slots = list(items)
        self._render_ai()
        return self._ai_gen

    def _show_local(self, title: str, text: str) -> None:
        self._ai_debounce.stop()
        self._start_batch([(title, text, "local")])

    def _render_ai(self) -> None:
        sources = [s for _, _, s in self._ai_slots]
        # Kart başlığındaki etiket: en "zayıf" kaynağı göster.
        for key in ("fallback_invalid", "fallback_offline", "pending", "local", "ai"):
            if key in sources:
                self.ai_chip.setText(SOURCE_CHIPS[key][0])
                self.ai_chip.setStyleSheet(chip_style(key))
                self.delti_avatar.setPixmap(delti.pixmap(delti.STATE_FOR_SOURCE[key], 34,
                                                         self.devicePixelRatioF() or 1.0))
                break
        notes = []
        if "fallback_offline" in sources:
            notes.append(prompts()["offline_message"])
        if "fallback_invalid" in sources:
            notes.append(prompts()["invalid_message"])
        parts = []
        if notes:
            parts.append(f"<p style='color:{MUTED}; font-size:8.5pt; margin:0 0 6px 0;'><i>"
                         + "<br>".join(html.escape(n) for n in notes) + "</i></p>")
        multi = len(self._ai_slots) > 1
        for title, text, source in self._ai_slots:
            heading = (f"<b style='color:{theme.PRIMARY_DARK if source != 'fallback_invalid' else theme.WARN}'>"
                       f"{html.escape(title)}</b><br>") if multi else ""
            parts.append(f"<p style='margin:0 0 8px 0; line-height:140%;'>{heading}"
                         f"{html.escape(text).replace(chr(10), '<br>')}</p>")
        self.ai_text.setHtml("".join(parts))

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
            self._show_local("Durum", status_message(c.result, set(c.inputs.restricted), c.inputs.p))
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
                             f"({status_message(self.current.result, set(self.current.inputs.restricted), self.current.inputs.p) or 'hesap yok'}).")
            return
        self._submit_batch([req])

    def compare_with_saved(self) -> None:
        saved = self.db.latest()
        if saved is None:
            self._show_local("Senaryo kıyası", "Karşılaştırmak için önce bir senaryoyu \"Senaryoyu kaydet\" ile geçmişe ekleyin.")
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
            self.history_tab.show_summary("Özetlenecek kayıt yok.", "local")
            return
        self.history_tab.show_summary(req.fallback(), "pending" if self.ai.online else "fallback_offline")
        self.ai.submit(req, ("history",))

    def _set_nl_status(self, text: str, kind: str = "info") -> None:
        color = {"info": "#cfe9df", "ok": "#b9f3d2", "error": "#ffd0d0"}[kind]
        self.nl_status.setStyleSheet(f"color: {color}; font-size: 8.5pt; padding-left: 14px;")
        self.nl_status.setText(text)

    def submit_nl(self) -> None:
        sentence = self.nl_edit.text().strip()
        if not sentence:
            return
        self._set_nl_status("Çözümleniyor…" if self.ai.online else "")
        self.ai.submit(ai_context.nl_input(sentence, self.inputs()), ("nl", sentence))

    def _apply_nl(self, sentence: str, reply: AIReply) -> None:
        merged, err, via = self._nl_merge(sentence, reply)
        if merged is None:
            self._set_nl_status(f"Uygulanamadı: {err}", "error")
            self._show_local("Doğal dil girişi", prompts()["by_id"]["nl_input"]["fallback_template"])
            return
        cur = self.inputs()
        self.set_inputs(ScenarioInputs(
            asset_id=merged["asset_id"], date=cur.date, s=merged["s"], L=merged["L"],
            t=merged["t"], p=merged["p"], restricted=cur.restricted, ci_kind=cur.ci_kind,
            parametric=cur.parametric, param_kwh=cur.param_kwh,
        ))
        self.tabs.setCurrentWidget(self.scenario_tab)
        self._set_nl_status(f"✓ Uygulandı · {via}", "ok")

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
            self.history_tab.show_summary(reply.text, reply.source)
        elif kind == "annual":
            self.annual_tab.show_ai(reply.text, reply.source, tag[1])
        elif kind == "nl":
            self._apply_nl(tag[1], reply)
        elif kind == "nlpage":
            self._apply_nl_page(tag[1], reply)

    def closeEvent(self, event) -> None:
        self.ai.shutdown()
        super().closeEvent(event)
