"""Yıllık Etki sekmesi: senaryo yılın tüm günlerinde uygulanırsa toplam emisyon değişimi."""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from PySide6.QtCore import Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QSlider, QSpinBox,
    QVBoxLayout, QWidget,
)

from desktop import fmt, theme  # noqa: E402
from desktop.tabs import _item, _raw, _stat, _table  # noqa: E402
from engine import annual, data  # noqa: E402

MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
MONTH_NAMES = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
               "Kasım", "Aralık"]


def mass(kg: float, digits: int = 2) -> str:
    """1000 kg ve üstünü ton olarak gösterir."""
    return f"{fmt.num(kg / 1000, digits)} t CO2" if abs(kg) >= 1000 else f"{fmt.num(kg, 1)} kg CO2"


class _MonthChart(FigureCanvasQTAgg):
    def __init__(self):
        self.figure = Figure(figsize=(4, 2.4), dpi=100, layout="constrained", facecolor="white")
        super().__init__(self.figure)
        self.setMinimumHeight(200)
        self.ax = self.figure.add_subplot(111)

    def update_chart(self, months: list[annual.MonthTotal]) -> None:
        ax = self.ax
        ax.clear()
        vals = [m.delta_kg for m in months]
        colors = ["#1f9254" if v <= 0 else "#d03c3c" for v in vals]
        alphas = [0.85 if m.days else 0.0 for m in months]
        bars = ax.bar(range(12), vals, width=0.7, color=colors)
        for b, a in zip(bars, alphas):
            b.set_alpha(a)
        for i, m in enumerate(months):
            if not m.days:
                ax.text(i, 0, "veri\nyok", ha="center", va="bottom", fontsize=6.5, color="#9aa5b1")
        ax.axhline(0, color="#9aa5b1", linewidth=0.8)
        ax.set_xticks(range(12))
        ax.set_xticklabels(MONTHS, fontsize=8, color="#5b6776")
        ax.tick_params(axis="y", labelsize=8, colors="#5b6776", length=0)
        ax.tick_params(axis="x", length=0)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: fmt.num(v, 0)))
        ax.set_ylabel("Değişim (kg CO2)", fontsize=8.5, color="#5b6776")
        ax.grid(axis="y", color="#e9edf1", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#cfd6de")
        self.draw_idle()


class AnnualTab(QWidget):
    apply_requested = Signal(dict)  # {"asset_id", "date", "s", "L", "t", "p"}

    def __init__(self, hour_spin_cls, parent=None):
        super().__init__(parent)
        self._restricted: set[int] = set()
        self._date = ""
        self._kind = "tCO2"
        self._loading = False
        self._series_key = None
        self._series: list = []
        self.result: annual.AnnualResult | None = None
        self.best: list[annual.AnnualResult] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self.recompute)

        root = QVBoxLayout(self)
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
        for label, w in (("Makine", self.machine), ("Yıl", self.year), ("Standart", self.s),
                         ("Uzunluk", self.L), ("Hedef", self.t)):
            row.addWidget(theme.muted(label))
            row.addWidget(w)
        row.addWidget(theme.muted("Oran"))
        row.addWidget(self.p)
        row.addWidget(self.p_label)
        row.addStretch(1)
        self.export_button = QPushButton("CSV olarak dışa aktar")
        self.export_button.clicked.connect(self.export_csv)
        row.addWidget(self.export_button)
        lay.addLayout(row)
        self.restricted_note = theme.muted("", wrap=True)
        lay.addWidget(self.restricted_note)
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
        f3, self.v_daily = _stat("Makinenin toplam emisyonunda")
        f4, self.v_days = _stat("Hesaba giren gün")
        for f in (f1, f2, f3, f4):
            stats.addWidget(f, 1)
        root.addLayout(stats)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        scard, sl = theme.card(margins=(16, 10, 16, 10))
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
        cl.addWidget(theme.muted("Yeşil çubuk o ay emisyonun düştüğünü, kırmızı arttığını gösterir. "
                                 "Verisi olmayan aylar boş kalır.", wrap=True))
        body.addWidget(ccard, 2)
        root.addLayout(body, 1)

        self.reload_machines()

    # ---------------------------------------------------------- girdiler
    def reload_machines(self) -> None:
        current = self.machine.currentData()
        self._loading = True
        self.machine.clear()
        for m in data.machines():
            if m["shiftable"]:
                self.machine.addItem(m["name"], m["id"])
        idx = self.machine.findData(current)
        self.machine.setCurrentIndex(idx if idx >= 0 else 0)
        self._fill_years()
        self._series_key = None
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
                    restricted: list[int], kind: str = "tCO2") -> None:
        """Senaryo sekmesindeki değerlerle başlar (kaydırılamaz makinede ilk uygun makine)."""
        self._loading = True
        idx = self.machine.findData(asset_id)
        self.machine.setCurrentIndex(idx if idx >= 0 else 0)
        self._fill_years(prefer=int(date[:4]) if date else None)
        self.s.setValue(s)
        self.L.setValue(L)
        self.t.setValue(t)
        self.p.setValue(round(p * 100))
        self.p_label.setText(f"%{round(p * 100)}")
        self._restricted = set(restricted)
        self._date = date
        self._kind = kind
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
    def _year_series(self, asset: str, year: int) -> list:
        key = (asset, year, self._kind)
        if key != self._series_key:
            self._series = annual.year_series(asset, year, self._kind)
            self._series_key = key
        return self._series

    def recompute(self) -> None:
        asset, year = self.machine.currentData(), self.year.currentData()
        self.restricted_note.setText(
            "Kısıtlı saatler (Senaryo sekmesinden): " + ", ".join(fmt.hour(h) for h in sorted(self._restricted))
            if self._restricted else "Kısıtlı saat yok. Kısıtlı saatleri Senaryo sekmesinden işaretleyebilirsiniz.")
        if asset is None or year is None:
            self._clear("Kaydırılabilir makine yok.")
            return
        s, L, t, p = self.s.value(), self.L.value(), self.t.value(), self.p.value() / 100
        series = self._year_series(asset, year)
        r = annual.annual_impact(asset, year, s, L, t, p, self._restricted, self._kind, series)
        self.result = r
        self.best = [annual.annual_impact(asset, year, s, L, tt, p, self._restricted, self._kind, series)
                     for tt in range(0, 25 - L)]
        self.best = sorted((b for b in self.best if b.days_ok > 0), key=lambda b: (b.scenario_kg, b.t))
        self._show(r)

    def _clear(self, msg: str) -> None:
        self.result = None
        for v in (self.v_delta, self.v_pct, self.v_daily, self.v_days):
            v.setText("—")
        self.summary.setText(msg)
        self.best_label.setText("")
        self.table.setRowCount(0)
        self.chart.update_chart([annual.MonthTotal(m) for m in range(1, 13)])
        self.use_best.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.export_button.setEnabled(False)

    def _show(self, r: annual.AnnualResult) -> None:
        name = data.machine(r.asset_id)["name"]
        what = f"{name} · {fmt.window(r.s, r.L)} → {fmt.window(r.t, r.L)} · %{fmt.num(r.p * 100, 0)}"
        self.v_days.setText(f"{r.days_ok} / {r.days_total}")
        if r.days_ok == 0:
            reasons = {"restricted_conflict": "hedef saat kısıtlı", "same_window": "hedef standart pencereyle aynı",
                       "no_load": "standart pencerede yük yok", "out_of_range": "pencere gün dışına taşıyor"}
            why = ", ".join(reasons.get(k, k) for k in r.status_counts) or "veri yok"
            self._clear(f"{what}: {r.year} yılında hesaba girebilen gün yok ({why}).")
            self.v_days.setText(f"0 / {r.days_total}")
            return
        good = r.delta_kg <= 0
        color = theme.GOOD if good else theme.BAD
        self.v_delta.setText(mass(r.delta_kg))
        self.v_delta.setStyleSheet(f"color: {color};")
        self.v_pct.setText(fmt.pct(r.delta_pct))
        self.v_pct.setStyleSheet(f"color: {color};")
        self.v_daily.setText(fmt.pct(r.daily_delta_pct))
        verb = "azalırdı" if good else "artardı"
        skipped = r.days_total - r.days_ok
        skip_txt = f" {skipped} gün standart pencerede yük olmadığı ya da kısıt nedeniyle hesaba girmedi." \
            if skipped else ""
        text = (f"<b>{what}</b><br>Bu kaydırma {r.year} yılında verisi olan {r.days_ok} günün her birinde "
                f"uygulansaydı, kaydırılan yükün emisyonu {mass(r.baseline_kg)} yerine {mass(r.scenario_kg)} olur; "
                f"toplam emisyon <b style='color:{color}'>{mass(abs(r.delta_kg))} {verb}</b>. "
                f"{r.better_days} günde emisyon düştü, {r.worse_days} günde arttı.{skip_txt}")
        if r.best_day and r.worst_day:
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
                                        f"→ {mass(b.delta_kg)} ({fmt.pct(b.delta_pct)}).")
            self.use_best.setEnabled(b.t != r.t)
        self.apply_button.setEnabled(True)
        self.export_button.setEnabled(True)

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
        self.chart.update_chart(r.months)

    # ------------------------------------------------------------- işler
    def _use_best(self) -> None:
        if self.best:
            self.t.setValue(self.best[0].t)

    def _apply(self) -> None:
        r = self.result
        if r is None:
            return
        days = [d for d, *_ in self._series]
        date = self._date if self._date in days else (r.best_day[0] if r.best_day else days[0])
        self.apply_requested.emit({"asset_id": r.asset_id, "date": date, "s": r.s, "L": r.L, "t": r.t, "p": r.p})

    def export_csv(self) -> None:
        r = self.result
        if r is None:
            return
        name = f"CarbonDelta_yillik_{r.asset_id}_{r.year}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Yıllık etkiyi kaydet", name, "CSV (*.csv)")
        if not path:
            return
        try:
            export_annual_csv(path, r, self._restricted)
        except OSError as e:
            QMessageBox.warning(self, "Kaydedilemedi", str(e))

    def focus_default(self) -> None:
        self.machine.setFocus(Qt.TabFocusReason)


def export_annual_csv(path: Path | str, r: annual.AnnualResult, restricted: set[int]) -> None:
    """Yıllık özet ve aylık dökümü CSV'ye yazar (UTF-8 BOM, ';' ayraç, tam hassasiyet)."""
    m = data.machine(r.asset_id)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["CarbonDelta yıllık etki"])
        w.writerow(["Makine", m["name"], "Kod", r.asset_id, "Yıl", r.year])
        w.writerow(["Standart başlangıç", r.s, "Uzunluk", r.L, "Hedef başlangıç", r.t, "Kaydırma oranı", _raw(r.p),
                    "Kısıtlı saatler", ",".join(str(h) for h in sorted(restricted))])
        w.writerow([])
        w.writerow(["Ay", "Gün", "Standart emisyon (kg)", "Seçilen emisyon (kg)", "Değişim (kg)", "Değişim (%)"])
        for mt in r.months:
            if mt.days:
                w.writerow([MONTH_NAMES[mt.month - 1], mt.days, _raw(mt.baseline_kg), _raw(mt.scenario_kg),
                            _raw(mt.delta_kg), _raw(mt.delta_pct)])
        w.writerow([])
        w.writerow(["Hesaba giren gün", r.days_ok, "Toplam gün", r.days_total])
        w.writerow(["Taşınan enerji (kWh)", _raw(r.shifted_kwh)])
        w.writerow(["ΣB (kg)", _raw(r.baseline_kg)])
        w.writerow(["ΣS (kg)", _raw(r.scenario_kg)])
        w.writerow(["Yıllık değişim (kg)", _raw(r.delta_kg)])
        w.writerow(["Yıllık değişim (%)", _raw(r.delta_pct)])
        w.writerow(["Toplam emisyon içindeki pay (%)", _raw(r.daily_delta_pct)])
        w.writerow([])
        day = next((d for d in data.days_for(r.asset_id) if d.startswith(str(r.year))), None)
        if day:
            w.writerow([data.source_label(r.asset_id, day)])
