"""Yıllık Etki sekmesi: senaryo yılın tüm günlerinde (bir makinede ya da tesis genelinde) uygulanırsa
toplam emisyon değişimi, aylık kırılım, yenilenebilir pay, Delti yorumu ve PDF rapor."""
from __future__ import annotations

import csv
import html
import io
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from PySide6.QtCore import QMarginsF, Qt, QTimer, QUrl, Signal  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPdfWriter, QTextDocument  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QSizePolicy, QSlider,
    QSpinBox, QVBoxLayout, QWidget,
)

from desktop import delti, fmt, theme  # noqa: E402
from desktop.tabs import _item, method_html, _raw, _stat, _table  # noqa: E402
from engine import annual, data  # noqa: E402
from engine.appinfo import APP_NAME  # noqa: E402

MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
MONTH_NAMES = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
               "Kasım", "Aralık"]
FACILITY_LABEL = "Tesis geneli (tüm kaydırılabilir makineler)"
AI_CHIPS = {"ai": ("AI", theme.PRIMARY, theme.PRIMARY_SOFT), "pending": ("Düşünüyor…", theme.MUTED, "#eef1f4"),
            "fallback_offline": ("Çevrimdışı · şablon", theme.MUTED, "#eef1f4"),
            "fallback_invalid": ("Şablon · doğrulanamadı", theme.WARN, theme.WARN_SOFT)}


def unit_for(kind: str) -> str:
    return "CO2" if kind == "tCO2" else "CO2-eşd"


def mass(kg: float, kind: str = "tCO2", digits: int = 2) -> str:
    """1000 kg ve üstünü ton olarak gösterir."""
    u = unit_for(kind)
    return f"{fmt.num(kg / 1000, digits)} t {u}" if abs(kg) >= 1000 else f"{fmt.num(kg, 1)} kg {u}"


def ren(v: float | None) -> str:
    return "—" if v is None else f"%{fmt.num(v, 1)}"


def scope_name(r: annual.AnnualResult) -> str:
    return FACILITY_LABEL if r.is_facility else data.machine(r.asset_id)["name"]


def source_for(r: annual.AnnualResult) -> tuple[str, bool]:
    """Alt bilgi etiketi ve 'tesis ölçümü mü' bilgisi (tesis genelinde makinelerin karışımına göre)."""
    ids = [p.asset_id for p in r.parts if p.days_total] if r.is_facility else [r.asset_id]
    if not ids:
        return "", False
    day = next((d for d in data.days_for(ids[0]) if d.startswith(str(r.year))), data.days_for(ids[0])[0])
    reals = [data.is_real(a) for a in ids]
    if all(reals) or not any(reals):
        return data.source_label(ids[0], day), all(reals)
    return (f"Tesis geneli: tesis ölçümü ve örnek yük birlikte · Kaynak: {data.grid_label(day)}, "
            f"{data.factors_label()}"), False


def chart_png(months: list[annual.MonthTotal], kind: str = "tCO2") -> bytes:
    """PDF rapor için geniş aylık değişim grafiği (ekrandaki grafikten bağımsız çizilir)."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=(8, 2.6), dpi=160, facecolor="white")
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    vals = [m.delta_kg for m in months]
    bars = ax.bar(range(12), vals, width=0.65, color=["#1f9254" if v <= 0 else "#d03c3c" for v in vals])
    for b, m in zip(bars, months):
        b.set_alpha(0.9 if m.days else 0.0)
    ax.axhline(0, color="#9aa5b1", linewidth=0.8)
    ax.set_xticks(range(12))
    ax.set_xticklabels(MONTHS, fontsize=8, color="#5b6776")
    ax.tick_params(axis="y", labelsize=8, colors="#5b6776", length=0)
    ax.tick_params(axis="x", length=0)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: fmt.num(v, 0)))
    ax.set_ylabel(f"Değişim (kg {unit_for(kind)})", fontsize=8.5, color="#5b6776")
    ax.set_title("Aylık emisyon değişimi", fontsize=9.5, color="#1d2733")
    ax.grid(axis="y", color="#e9edf1", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    return buf.getvalue()


class _MonthChart(FigureCanvasQTAgg):
    def __init__(self):
        self.figure = Figure(figsize=(4, 2.4), dpi=100, layout="constrained", facecolor="white")
        super().__init__(self.figure)
        self.setMinimumHeight(150)
        self.ax = self.figure.add_subplot(111)

    def update_chart(self, months: list[annual.MonthTotal], kind: str = "tCO2") -> None:
        ax = self.ax
        ax.clear()
        vals = [m.delta_kg for m in months]
        colors = ["#1f9254" if v <= 0 else "#d03c3c" for v in vals]
        bars = ax.bar(range(12), vals, width=0.7, color=colors)
        for b, m in zip(bars, months):
            b.set_alpha(0.85 if m.days else 0.0)
        for i, m in enumerate(months):
            if not m.days:
                ax.text(i, 0, "veri\nyok", ha="center", va="bottom", fontsize=6.5, color="#9aa5b1")
        ax.axhline(0, color="#9aa5b1", linewidth=0.8)
        ax.set_xticks(range(12))
        ax.set_xticklabels(MONTHS, fontsize=8, color="#5b6776")
        ax.tick_params(axis="y", labelsize=8, colors="#5b6776", length=0)
        ax.tick_params(axis="x", length=0)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: fmt.num(v, 0)))
        ax.set_ylabel(f"Değişim (kg {unit_for(kind)})", fontsize=8.5, color="#5b6776")
        ax.grid(axis="y", color="#e9edf1", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#cfd6de")
        self.draw_idle()



class AnnualTab(QWidget):
    apply_requested = Signal(dict)       # {"asset_id", "date", "s", "L", "t", "p"}
    explain_requested = Signal(object)   # ai_client.AIRequest (ana pencere Delti'ye gönderir)
    footer_changed = Signal(str, bool)   # kaynak etiketi, tesis ölçümü mü

    def __init__(self, hour_spin_cls, parent=None):
        super().__init__(parent)
        self._restricted: set[int] = set()
        self._date = ""
        self._kind = "tCO2"
        self._param: float | None = None
        self._loading = False
        self._series_cache: dict = {}
        self.result: annual.AnnualResult | None = None
        self.best: list[annual.AnnualResult] = []
        self._ai_text = ""
        self._ai_source = ""
        self._dpr = self.devicePixelRatioF() or 1.0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self.recompute)

        root = theme.scroll_page(self, 640)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(10)

        # Girdiler
        card, lay = theme.card()
        row = QHBoxLayout()
        row.setSpacing(10)
        t = QLabel("Yıllık etki")
        t.setObjectName("cardTitle")
        row.addWidget(t)
        row.addSpacing(8)
        self.machine = QComboBox()
        self.machine.setMinimumWidth(170)
        self.year = QComboBox()
        self.s = hour_spin_cls()
        self.s.setRange(0, 23)
        self.L = QSpinBox()
        self.L.setRange(1, 12)
        self.L.setSuffix(" saat")
        self.t = hour_spin_cls()
        self.t.setRange(0, 23)
        self.p = QSlider(Qt.Horizontal)
        self.p.setRange(0, 100)
        self.p.setValue(100)
        self.p.setFixedWidth(100)
        self.p_label = QLabel("%100")
        self.p_label.setMinimumWidth(38)
        for label, w in (("Kapsam", self.machine), ("Yıl", self.year), ("Standart", self.s),
                         ("Uzunluk", self.L), ("Hedef", self.t)):
            row.addWidget(theme.muted(label))
            row.addWidget(w)
        row.addWidget(theme.muted("Oran"))
        row.addWidget(self.p)
        row.addWidget(self.p_label)
        row.addStretch(1)
        self.pdf_button = QPushButton("PDF rapor")
        self.pdf_button.setToolTip("Yıllık sonucu, aylık dökümü, Delti yorumunu ve yöntemi tek sayfalık raporda kaydeder")
        self.pdf_button.clicked.connect(self.export_pdf)
        row.addWidget(self.pdf_button)
        self.export_button = QPushButton("CSV")
        self.export_button.setToolTip("Özet ve aylık dökümü CSV olarak kaydeder")
        self.export_button.clicked.connect(self.export_csv)
        row.addWidget(self.export_button)
        lay.addLayout(row)
        self.note = theme.muted("", wrap=True)
        lay.addWidget(self.note)
        root.addWidget(card)

        self.machine.currentIndexChanged.connect(self._on_machine)
        self.year.currentIndexChanged.connect(self._schedule)
        for sig in (self.s.valueChanged, self.L.valueChanged, self.t.valueChanged):
            sig.connect(self._schedule)
        self.p.valueChanged.connect(lambda v: (self.p_label.setText(f"%{v}"), self._schedule()))

        # Özet kutucukları
        stats = QHBoxLayout()
        stats.setSpacing(10)
        f1, self.v_delta = _stat("Yıllık emisyon değişimi")
        f2, self.v_pct = _stat("Kaydırılan yükte değişim")
        f3, self.v_ren = _stat("Yenilenebilir payı (kaydırılan enerji)")
        f4, self.v_days = _stat("Hesaba giren gün")
        self.v_days_title = f4.findChild(QLabel, "statLabel")
        for f in (f1, f2, f3, f4):
            stats.addWidget(f, 1)
        root.addLayout(stats)

        scard, sl = theme.card(margins=(16, 10, 16, 10))
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        sl.addWidget(self.summary)
        best_row = QHBoxLayout()
        self.best_label = QLabel("")
        self.best_label.setWordWrap(True)
        self.best_label.setTextFormat(Qt.RichText)
        best_row.addWidget(self.best_label, 1)
        self.use_best = QPushButton("Bu hedefi dene")
        self.use_best.setToolTip("Yıl boyunca en düşük emisyonu veren hedef saati bu ekranda seçer")
        self.use_best.clicked.connect(self._use_best)
        best_row.addWidget(self.use_best)
        self.apply_button = QPushButton("Senaryoya uygula")
        self.apply_button.setObjectName("primary")
        self.apply_button.setToolTip("Bu ekrandaki saatleri Senaryo sekmesine aktarır")
        self.apply_button.clicked.connect(self._apply)
        best_row.addWidget(self.apply_button)
        sl.addLayout(best_row)

        # Delti'nin yıllık yorumu
        ai_row = QHBoxLayout()
        ai_row.setSpacing(10)
        self.ai_avatar = QLabel()
        self.ai_avatar.setFixedSize(30, 30)
        self.ai_avatar.setPixmap(delti.pixmap("ready", 30, self._dpr))
        ai_row.addWidget(self.ai_avatar, 0, Qt.AlignTop)
        self.ai_label = QLabel("Delti bu yıllık sonucu sizin için yorumlayabilir.")
        self.ai_label.setWordWrap(True)
        self.ai_label.setStyleSheet(f"color: {theme.MUTED};")
        ai_row.addWidget(self.ai_label, 1)
        self.ai_chip = QLabel("")
        self.ai_chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.ai_chip.hide()
        ai_row.addWidget(self.ai_chip, 0, Qt.AlignTop)
        self.ai_button = QPushButton("Delti yorumlasın")
        self.ai_button.clicked.connect(self._ask_delti)
        ai_row.addWidget(self.ai_button, 0, Qt.AlignTop)
        sl.addLayout(ai_row)
        root.addWidget(scard)

        # Aylık tablo + grafik
        body = QHBoxLayout()
        body.setSpacing(10)
        tcard, tl = theme.card("Aylara göre")
        self.table = _table(["Ay", "Gün", "Standart (kg)", "Seçilen (kg)", "Değişim (kg)", "Değişim"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setFocusPolicy(Qt.StrongFocus)
        tl.addWidget(self.table, 1)
        body.addWidget(tcard, 3)
        ccard, cl = theme.card("Aylık emisyon değişimi")
        self.chart = _MonthChart()
        cl.addWidget(self.chart, 1)
        self.chart.setToolTip("Yeşil çubuk o ay emisyonun düştüğünü, kırmızı arttığını gösterir. "
                              "Verisi olmayan aylar boş kalır.")
        body.addWidget(ccard, 2)
        root.addLayout(body, 1)

        self.reload_machines()

    # ---------------------------------------------------------- girdiler
    def reload_machines(self) -> None:
        current = self.machine.currentData()
        self._loading = True
        self.machine.clear()
        self.machine.addItem("Tesis geneli (tümü)", annual.ALL)
        self.machine.setItemData(0, FACILITY_LABEL, Qt.ToolTipRole)
        for m in data.machines():
            if m["shiftable"]:
                self.machine.addItem(m["name"], m["id"])
        idx = self.machine.findData(current)
        self.machine.setCurrentIndex(idx if idx >= 0 else 1)
        self._fill_years()
        self._series_cache.clear()
        self._loading = False

    def _fill_years(self, prefer: int | None = None) -> None:
        cur = prefer or self.year.currentData()
        self.year.blockSignals(True)
        self.year.clear()
        asset = self.machine.currentData()
        for y in (annual.years_for(asset) if asset else []):
            self.year.addItem(str(y), y)
        idx = self.year.findData(cur)
        self.year.setCurrentIndex(idx if idx >= 0 else self.year.count() - 1)
        self.year.blockSignals(False)

    def load_inputs(self, asset_id: str, date: str, s: int, L: int, t: int, p: float,
                    restricted: list[int], kind: str = "tCO2", param_kwh: float | None = None) -> None:
        """Senaryo sekmesindeki değerlerle başlar (tesis geneli seçiliyse kapsam korunur)."""
        self._loading = True
        if self.machine.currentData() != annual.ALL:
            idx = self.machine.findData(asset_id)
            self.machine.setCurrentIndex(idx if idx >= 0 else 1)
        self._fill_years(prefer=int(date[:4]) if date else None)
        self.s.setValue(s)
        self.L.setValue(L)
        self.t.setValue(t)
        self.p.setValue(round(p * 100))
        self.p_label.setText(f"%{round(p * 100)}")
        self._restricted = set(restricted)
        self._date = date
        if (kind, param_kwh) != (self._kind, self._param):
            self._series_cache.clear()
        self._kind = kind
        self._param = param_kwh
        self._loading = False
        self.recompute()

    def _on_machine(self) -> None:
        if self._loading:
            return
        self._fill_years()
        self._schedule()

    def _schedule(self, *_a) -> None:
        if not self._loading:
            self._timer.start()

    # ------------------------------------------------------------- hesap
    def _series(self, asset: str, year: int) -> list:
        key = (asset, year)
        if key not in self._series_cache:
            self._series_cache[key] = annual.year_series(asset, year, self._kind, self._param)
        return self._series_cache[key]

    def _compute(self, asset: str, year: int, t: int) -> annual.AnnualResult:
        s, L, p = self.s.value(), self.L.value(), self.p.value() / 100
        if asset == annual.ALL:
            series = {a: self._series(a, year) for a in annual.facility_machines()}
            return annual.facility_impact(year, s, L, t, p, self._restricted, self._kind, series, self._param)
        return annual.annual_impact(asset, year, s, L, t, p, self._restricted, self._kind, self._series(asset, year))

    def recompute(self) -> None:
        asset, year = self.machine.currentData(), self.year.currentData()
        notes = []
        if self._restricted:
            notes.append("Kısıtlı saatler (Senaryo sekmesinden): " +
                         ", ".join(fmt.hour(h) for h in sorted(self._restricted)))
        else:
            notes.append("Kısıtlı saat yok; Senaryo sekmesinden işaretlenebilir.")
        if self._param is not None:
            notes.append(f"Parametrik mod: her makinede her saat sabit {fmt.num(self._param, 1)} kWh yük varsayılır.")
        if self._kind != "tCO2":
            notes.append("Emisyon tipi: tCO2-eşd.")
        self.note.setText(" · ".join(notes))
        self._reset_ai()
        if asset is None or year is None:
            self._clear("Kaydırılabilir makine yok.")
            return
        r = self._compute(asset, year, self.t.value())
        self.result = r
        self.best = sorted((b for b in (self._compute(asset, year, tt) for tt in range(0, 25 - self.L.value()))
                            if b.days_ok > 0), key=lambda b: (b.scenario_kg, b.t))
        self._show(r)

    def _clear(self, msg: str) -> None:
        self.result = None
        for v in (self.v_delta, self.v_pct, self.v_ren, self.v_days):
            v.setText("—")
            v.setStyleSheet("")
        self.summary.setText(msg)
        self.best_label.setText("")
        self.table.setRowCount(0)
        self.chart.update_chart([annual.MonthTotal(m) for m in range(1, 13)], self._kind)
        for b in (self.use_best, self.apply_button, self.export_button, self.pdf_button, self.ai_button):
            b.setEnabled(False)

    def _show(self, r: annual.AnnualResult) -> None:
        kind = self._kind
        what = f"{scope_name(r)} · {fmt.window(r.s, r.L)} → {fmt.window(r.t, r.L)} · %{fmt.num(r.p * 100, 0)}"
        self.v_days_title.setText("Hesaba giren makine-gün" if r.is_facility else "Hesaba giren gün")
        self.v_days.setText(f"{r.days_ok} / {r.days_total}")
        label, real = source_for(r)
        self.footer_changed.emit(label, real)
        if r.days_ok == 0:
            reasons = {"restricted_conflict": "hedef saat kısıtlı", "same_window": "hedef standart pencereyle aynı",
                       "no_load": "standart pencerede yük yok", "out_of_range": "pencere gün dışına taşıyor"}
            why = ", ".join(reasons.get(k, k) for k in r.status_counts) or "veri yok"
            self._clear(f"{what}: {r.year} yılında hesaba girebilen gün yok ({why}).")
            self.v_days.setText(f"0 / {r.days_total}")
            return
        good = r.delta_kg <= 0
        color = theme.GOOD if good else theme.BAD
        self.v_delta.setText(mass(r.delta_kg, kind))
        self.v_delta.setStyleSheet(f"color: {color};")
        self.v_pct.setText(fmt.pct(r.delta_pct))
        self.v_pct.setStyleSheet(f"color: {color};")
        self.v_ren.setText(f"{ren(r.ren_source_pct)} → {ren(r.ren_target_pct)}")
        up = (r.ren_target_pct or 0) >= (r.ren_source_pct or 0)
        self.v_ren.setStyleSheet(f"color: {theme.GOOD if up else theme.BAD};")
        verb = "azalırdı" if good else "artardı"
        unit = "makine-gün" if r.is_facility else "gün"
        loc = unit + "de"   # gün → günde, makine-gün → makine-günde
        skipped = r.days_total - r.days_ok
        skip_txt = (f" {skipped} {unit} standart pencerede yük olmadığı ya da kısıt nedeniyle hesaba girmedi."
                    if skipped else "")
        text = (f"<b>{html.escape(what)}</b><br>Bu kaydırma {r.year} yılında verisi olan {r.days_ok} {loc} "
                f"uygulansaydı, kaydırılan yükün emisyonu {mass(r.baseline_kg, kind)} yerine "
                f"{mass(r.scenario_kg, kind)} olur; toplam emisyon "
                f"<b style='color:{color}'>{mass(abs(r.delta_kg), kind)} {verb}</b>. Kaydırılan enerjinin "
                f"yenilenebilir kaynaklı payı {ren(r.ren_source_pct)} yerine {ren(r.ren_target_pct)} olur. "
                f"{r.better_days} {loc} emisyon düştü, {r.worse_days} {loc} arttı.{skip_txt}")
        if r.fossil_delta_pct is not None:
            text += (f"<br><span style='color:{theme.MUTED}'>Duyarlılık: kaydırılan yükü yalnızca fosil santrallerin "
                     f"karşıladığı varsayımıyla değişim <b>{fmt.pct(r.fossil_delta_pct)}</b> "
                     f"({mass(r.fossil_delta_kg, kind)}); gerçek etki büyük olasılıkla bu iki değer arasındadır.</span>")
        if r.is_facility:
            parts = sorted((x for x in r.parts if x.days_ok), key=lambda x: x.delta_kg)
            text += " Katkılar: " + ", ".join(f"{html.escape(data.machine(x.asset_id)['name'])} "
                                              f"{mass(x.delta_kg, kind)}" for x in parts) + "."
        elif r.best_day and r.worst_day:
            text += (f" En iyi gün {fmt.date(r.best_day[0])} ({fmt.pct(r.best_day[1])}), "
                     f"en zayıf gün {fmt.date(r.worst_day[0])} ({fmt.pct(r.worst_day[1])}).")
        self.summary.setText(text)

        if self.best:
            b = self.best[0]
            if b.t == r.t:
                self.best_label.setText(f"✓ Seçtiğiniz hedef <b>{fmt.window(b.t, b.L)}</b>, yıl boyunca sabit "
                                        "tutulabilecek en temiz hedef pencere.")
            else:
                self.best_label.setText(f"Yıl boyunca sabit tutulacak en temiz hedef: <b>{fmt.window(b.t, b.L)}</b> "
                                        f"→ {mass(b.delta_kg, kind)} ({fmt.pct(b.delta_pct)}).")
            self.use_best.setEnabled(b.t != r.t)
        self.apply_button.setEnabled(True)
        self.export_button.setEnabled(True)
        self.pdf_button.setEnabled(True)
        self.ai_button.setEnabled(True)

        months = [m for m in r.months if m.days]
        self.table.setRowCount(len(months))
        for n, m in enumerate(months):
            vals = [MONTH_NAMES[m.month - 1], str(m.days), fmt.num(m.baseline_kg, 1), fmt.num(m.scenario_kg, 1),
                    fmt.num(m.delta_kg, 1), fmt.pct(m.delta_pct)]
            for col, v in enumerate(vals):
                it = _item(v, Qt.AlignCenter)
                if col in (4, 5) and m.delta_kg:
                    it.setForeground(QColor(theme.GOOD if m.delta_kg < 0 else theme.BAD))
                self.table.setItem(n, col, it)
        self.chart.update_chart(r.months, kind)

    def emit_footer(self) -> None:
        if self.result is not None:
            self.footer_changed.emit(*source_for(self.result))

    # --------------------------------------------------------------- Delti
    def _reset_ai(self) -> None:
        self._ai_text, self._ai_source = "", ""
        self.ai_label.setText("Delti bu yıllık sonucu sizin için yorumlayabilir.")
        self.ai_label.setStyleSheet(f"color: {theme.MUTED};")
        self.ai_avatar.setPixmap(delti.pixmap("ready", 30, self._dpr))
        self.ai_chip.hide()

    def _ask_delti(self) -> None:
        from desktop import ai_context
        req = ai_context.annual_explain(self.result, self.best[0] if self.best else None, self._kind, self._param)
        if req is None:
            return
        self._ai_key = req.cache_key()
        self.show_ai(req.fallback(), "pending", self._ai_key)
        self.explain_requested.emit(req)

    def show_ai(self, text: str, source: str, key: str | None = None) -> None:
        """Ana pencere Delti'nin yanıtını buraya yollar; eski bir sonuca ait yanıt yok sayılır."""
        if key is not None and key != getattr(self, "_ai_key", None):
            return
        self._ai_text, self._ai_source = text, source
        self.ai_label.setText(text)
        self.ai_label.setStyleSheet(f"color: {theme.TEXT if source == 'ai' else theme.MUTED};")
        state = {"ai": "ready", "pending": "think"}.get(source, "sleep" if source == "fallback_offline" else "ready")
        self.ai_avatar.setPixmap(delti.pixmap(state, 30, self._dpr))
        label, fg, bg = AI_CHIPS.get(source, AI_CHIPS["pending"])
        self.ai_chip.setText(label)
        self.ai_chip.setStyleSheet(f"color: {fg}; background: {bg}; border-radius: 9px; padding: 2px 10px;"
                                   " font-size: 8.5pt; font-weight: 600;")
        self.ai_chip.show()

    # ------------------------------------------------------------- işler
    def _use_best(self) -> None:
        if self.best:
            self.t.setValue(self.best[0].t)

    def _apply(self) -> None:
        r = self.result
        if r is None:
            return
        asset = r.asset_id
        if r.is_facility:
            # Senaryo tek makine çalışır: mevcut senaryonun makinesi varsa o, yoksa en çok katkı yapan makine.
            parts = sorted((x for x in r.parts if x.days_ok), key=lambda x: x.delta_kg)
            asset = parts[0].asset_id if parts else annual.facility_machines()[0]
        days = data.days_for(asset)
        year_days = [d for d in days if d.startswith(str(r.year))] or days
        date = self._date if self._date in year_days else year_days[0]
        self.apply_requested.emit({"asset_id": asset, "date": date, "s": r.s, "L": r.L, "t": r.t, "p": r.p})

    def export_csv(self) -> None:
        r = self.result
        if r is None:
            return
        name = f"CarbonDelta_yillik_{'tesis' if r.is_facility else r.asset_id}_{r.year}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Yıllık etkiyi kaydet", name, "CSV (*.csv)")
        if not path:
            return
        try:
            export_annual_csv(path, r, self._restricted, self._kind)
        except OSError as e:
            QMessageBox.warning(self, "Kaydedilemedi", str(e))

    def export_pdf(self) -> None:
        r = self.result
        if r is None:
            return
        name = f"CarbonDelta_rapor_{'tesis' if r.is_facility else r.asset_id}_{r.year}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "PDF raporu kaydet", name, "PDF (*.pdf)")
        if not path:
            return
        try:
            export_annual_pdf(path, r, self.best[0] if self.best else None, self._restricted, self._kind,
                              self._param, chart_png(r.months, self._kind), self._ai_text, self._ai_source)
        except OSError as e:
            QMessageBox.warning(self, "Kaydedilemedi", str(e))

    def focus_default(self) -> None:
        self.machine.setFocus(Qt.TabFocusReason)


# ------------------------------------------------------------------ dışa aktarma
def export_annual_csv(path: Path | str, r: annual.AnnualResult, restricted: set[int], kind: str = "tCO2") -> None:
    """Yıllık özet ve aylık dökümü CSV'ye yazar (UTF-8 BOM, ';' ayraç, tam hassasiyet)."""
    u = unit_for(kind)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["CarbonDelta yıllık etki"])
        w.writerow(["Kapsam", scope_name(r), "Kod", r.asset_id, "Yıl", r.year, "Emisyon tipi", kind])
        w.writerow(["Standart başlangıç", r.s, "Uzunluk", r.L, "Hedef başlangıç", r.t, "Kaydırma oranı", _raw(r.p),
                    "Kısıtlı saatler", ",".join(str(h) for h in sorted(restricted))])
        w.writerow([])
        w.writerow(["Ay", "Gün", f"Standart emisyon (kg {u})", f"Seçilen emisyon (kg {u})", f"Değişim (kg {u})",
                    "Değişim (%)"])
        for mt in r.months:
            if mt.days:
                w.writerow([MONTH_NAMES[mt.month - 1], mt.days, _raw(mt.baseline_kg), _raw(mt.scenario_kg),
                            _raw(mt.delta_kg), _raw(mt.delta_pct)])
        if r.is_facility:
            w.writerow([])
            w.writerow(["Makine", "Gün", f"Değişim (kg {u})", "Değişim (%)"])
            for x in r.parts:
                w.writerow([data.machine(x.asset_id)["name"], x.days_ok, _raw(x.delta_kg), _raw(x.delta_pct)])
        w.writerow([])
        w.writerow(["Hesaba giren gün" + (" (makine-gün)" if r.is_facility else ""), r.days_ok,
                    "Toplam", r.days_total])
        w.writerow(["Taşınan enerji (kWh)", _raw(r.shifted_kwh)])
        w.writerow([f"ΣB (kg {u})", _raw(r.baseline_kg)])
        w.writerow([f"ΣS (kg {u})", _raw(r.scenario_kg)])
        w.writerow([f"Yıllık değişim (kg {u})", _raw(r.delta_kg)])
        w.writerow(["Yıllık değişim (%)", _raw(r.delta_pct)])
        w.writerow(["Toplam emisyon içindeki pay (%)", _raw(r.daily_delta_pct)])
        w.writerow(["Yenilenebilir payı, standart pencere (%)", _raw(r.ren_source_pct)])
        w.writerow(["Yenilenebilir payı, hedef pencere (%)", _raw(r.ren_target_pct)])
        w.writerow([f"Fosil marjinal duyarlılık, değişim (kg {u})", _raw(r.fossil_delta_kg)])
        w.writerow(["Fosil marjinal duyarlılık, değişim (%)", _raw(r.fossil_delta_pct)])
        w.writerow([])
        w.writerow([source_for(r)[0]])


def annual_report_html(r: annual.AnnualResult, best: annual.AnnualResult | None, restricted: set[int],
                       kind: str, param: float | None, ai_text: str, ai_source: str) -> str:
    e = html.escape
    u = unit_for(kind)
    good = r.delta_kg <= 0
    color = theme.GOOD if good else theme.BAD
    rows = "".join(
        f"<tr><td>{MONTH_NAMES[m.month - 1]}</td><td align='center'>{m.days}</td>"
        f"<td align='right'>{fmt.num(m.baseline_kg, 1)}</td><td align='right'>{fmt.num(m.scenario_kg, 1)}</td>"
        f"<td align='right'>{fmt.num(m.delta_kg, 1)}</td><td align='right'>{fmt.pct(m.delta_pct)}</td></tr>"
        for m in r.months if m.days)
    parts = ""
    if r.is_facility:
        parts = ("<h3>Makine katkıları</h3><table width='100%' cellspacing='0' cellpadding='3' border='1'>"
                 f"<tr bgcolor='#e7f3ef'><th align='left'>Makine</th><th>Gün</th><th>Değişim (kg {u})</th>"
                 "<th>Değişim</th></tr>" +
                 "".join(f"<tr><td>{e(data.machine(x.asset_id)['name'])}</td><td align='center'>{x.days_ok}</td>"
                         f"<td align='right'>{fmt.num(x.delta_kg, 1)}</td><td align='right'>{fmt.pct(x.delta_pct)}</td></tr>"
                         for x in sorted(r.parts, key=lambda x: x.delta_kg) if x.days_ok) + "</table>")
    conds = [f"Standart pencere {fmt.window(r.s, r.L)} → hedef {fmt.window(r.t, r.L)}, kaydırma oranı "
             f"%{fmt.num(r.p * 100, 0)}", f"Emisyon tipi: {kind}"]
    conds.append("Kısıtlı saatler: " + (", ".join(fmt.hour(h) for h in sorted(restricted)) if restricted else "yok"))
    if param is not None:
        conds.append(f"Parametrik mod: her saat sabit {fmt.num(param, 1)} kWh")
    best_txt = ""
    if best is not None:
        best_txt = (f"<p>Yıl boyunca sabit tutulabilecek en temiz hedef pencere: <b>{fmt.window(best.t, best.L)}</b> "
                    f"({mass(best.delta_kg, kind)}, {fmt.pct(best.delta_pct)}).</p>")
    ai = ""
    if ai_text:
        tag = "Delti (AI) yorumu" if ai_source == "ai" else "Özet (şablon metin; Delti çevrimdışıydı)"
        ai = f"<h3>{tag}</h3><p>{e(ai_text)}</p>"
    unit_days = "makine-gün" if r.is_facility else "gün"
    return f"""
<html><body style="font-family: 'Segoe UI', Arial; font-size: 9.5pt; color: #1d2733;">
<table width="100%"><tr><td><span style="font-size: 18pt; font-weight: bold; color: #0f5b46;">{e(APP_NAME)}</span><br>
<span style="color: #6b7785;">Yıllık karbon etkisi raporu · {datetime.now():%d.%m.%Y %H:%M}</span></td></tr></table>
<h2 style="color: #16785c;">{e(scope_name(r))} · {r.year}</h2>
<p>{e(' · '.join(conds))}</p>
<table width="100%" cellspacing="6" cellpadding="8"><tr>
<td bgcolor="#e7f3ef"><span style="color:#6b7785;">Yıllık emisyon değişimi</span><br>
<span style="font-size: 15pt; font-weight: bold; color: {color};">{mass(r.delta_kg, kind)}</span></td>
<td bgcolor="#e7f3ef"><span style="color:#6b7785;">Kaydırılan yükte değişim</span><br>
<span style="font-size: 15pt; font-weight: bold; color: {color};">{fmt.pct(r.delta_pct)}</span></td>
<td bgcolor="#e7f3ef"><span style="color:#6b7785;">Yenilenebilir payı</span><br>
<span style="font-size: 15pt; font-weight: bold;">{ren(r.ren_source_pct)} → {ren(r.ren_target_pct)}</span></td>
<td bgcolor="#e7f3ef"><span style="color:#6b7785;">Hesaba giren {unit_days}</span><br>
<span style="font-size: 15pt; font-weight: bold;">{r.days_ok} / {r.days_total}</span></td>
</tr></table>
<p>Kaydırılan {fmt.num(r.shifted_kwh, 0)} kWh enerjinin emisyonu {mass(r.baseline_kg, kind)} yerine
{mass(r.scenario_kg, kind)} olur. Makinelerin aynı günlerdeki toplam emisyonu içindeki payı
{fmt.pct(r.daily_delta_pct)}. {r.better_days} {unit_days}de emisyon düştü, {r.worse_days} {unit_days}de arttı.</p>
<p><b>Duyarlılık (fosil marjinal):</b> Kaydırılan yükü yalnızca fosil santrallerin karşıladığı varsayımıyla değişim
{fmt.pct(r.fossil_delta_pct)} ({mass(r.fossil_delta_kg, kind)}). Ana sonuç ortalama saatlik yoğunlukla
hesaplanır; gerçek etki büyük olasılıkla bu iki değer arasındadır.</p>
{best_txt}{ai}
<p align="center"><img src="chart.png" width="620"></p>
<h3>Aylık döküm</h3>
<table width="100%" cellspacing="0" cellpadding="3" border="1">
<tr bgcolor="#e7f3ef"><th align="left">Ay</th><th>Gün</th><th>Standart (kg {u})</th><th>Seçilen (kg {u})</th>
<th>Değişim (kg {u})</th><th>Değişim</th></tr>{rows}</table>
{parts}
<div style="font-size: 8.5pt;">{method_html()}</div>
<p style="color: #6b7785; font-size: 8.5pt;">Yıllık değişim = (ΣS − ΣB) / ΣB × 100. Karar destek amaçlıdır; karar
kullanıcıdadır. {e(source_for(r)[0])}</p>
</body></html>"""


def export_annual_pdf(path: Path | str, r: annual.AnnualResult, best: annual.AnnualResult | None,
                      restricted: set[int], kind: str, param: float | None, chart_png: bytes,
                      ai_text: str = "", ai_source: str = "") -> None:
    """A4 PDF rapor (Qt ile; ek bağımlılık yok)."""
    # Eski dosya başka programda açıksa silme hatası (OSError) burada yükselir; QPdfWriter sessizce başarısız olurdu.
    Path(path).unlink(missing_ok=True)
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageMargins(QMarginsF(14, 12, 14, 12), QPageLayout.Millimeter)
    writer.setResolution(110)
    writer.setTitle(f"{APP_NAME} yıllık karbon etkisi raporu")
    writer.setCreator(APP_NAME)
    doc = QTextDocument()
    img = QImage.fromData(chart_png, "PNG")
    doc.addResource(QTextDocument.ImageResource, QUrl("chart.png"), img)
    doc.setHtml(annual_report_html(r, best, restricted, kind, param, ai_text, ai_source))
    doc.setPageSize(writer.pageLayout().paintRectPixels(writer.resolution()).size().toSizeF())
    doc.print_(writer)
    if not Path(path).exists():
        raise OSError("PDF dosyası oluşturulamadı.")
