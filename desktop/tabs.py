"""Hesabı Göster, Geçmiş ve Kaynaklar sekmeleri."""
from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QTextBrowser,
    QVBoxLayout, QWidget,
)

from desktop import fmt, theme
from engine import data
from engine.explain import breakdown

FORMULA_HTML = f"""
<p style="margin-top:0">Seçilen gün için her saatin şebeke karbon yoğunluğu (EPİAŞ 2025 üretimi ×
ETKB 2023 katsayıları) ve makinenin o saatteki tüketimi kullanılır. <b>Hesapta yapay zekâ yoktur.</b></p>
<table cellspacing="0" cellpadding="3">
<tr><td valign="top"><b>1.</b></td><td><b>Taşınan enerji</b> — standart penceredeki her saat için
 <i>E = kaydırma oranı × o saatin tüketimi</i> (kWh)</td></tr>
<tr><td valign="top"><b>2.</b></td><td><b>Standart emisyon (B)</b> — her E × kendi saatinin
 karbon yoğunluğu, toplamı</td></tr>
<tr><td valign="top"><b>3.</b></td><td><b>Seçilen emisyon (S)</b> — aynı E × hedef penceredeki
 karşılık gelen saatin karbon yoğunluğu, toplamı</td></tr>
<tr><td valign="top"><b>4.</b></td><td><b>Değişim</b> = (S − B) / B × 100 — eksi değer daha düşük
 emisyon potansiyeli demektir</td></tr>
<tr><td valign="top"><b>5.</b></td><td><b>Günlük etki</b> = (S − B) / makinenin o günkü toplam
 emisyonu × 100</td></tr>
</table>
<p style="color:{theme.MUTED}; margin-bottom:0">Birim: tCO2/MWh = kgCO2/kWh. İç hesap tam
hassasiyetle yapılır; yalnızca ekranda yuvarlanır.</p>
"""

SOURCE_CARDS = [
    ("EPİAŞ 2025", "8.760 saat",
     "Şeffaflık Platformu saatlik gerçek zamanlı üretim verisi. Doğal gaz, linyit, ithal kömür, "
     "rüzgâr, güneş, hidro gibi kaynakların her saatteki üretimi. Her saatin karbon yoğunluğu, "
     "kaynak üretimlerinin ETKB katsayılarıyla çarpılıp yurtiçi toplam üretime bölünmesiyle bulunur."),
    ("ETKB 2023", "15 yakıt katsayısı",
     "Enerji ve Tabii Kaynaklar Bakanlığı'nın yakıt türü başına resmî tCO2/MWh ve tCO2-eşd/MWh "
     "emisyon faktörleri. Yenilenebilir kaynaklar için doğrudan yakıt emisyonu sıfır kabul edilir. "
     "Tablo \"Hesabı Göster\" sekmesindedir."),
    ("Zenodo", "7 makine · 1.839 gün",
     "Bir imalat tesisindeki makinelerin 15 dakikalık enerji ölçümleri. Faz tekrarları, sensör hatalı "
     "cihazlar ve eksik günler temizlenmiş, saatlik toplama çevrilmiştir. Havalandırma ve pres ısıtma "
     "sürekli/kısıtlı süreç olduğu için kaydırılamaz."),
]

NOTE_HTML = """
<b>Önemli not: örnek yük</b><br>
Yük verisi İrlanda'daki bir tesisten alınmış ve saat numarasıyla Türkiye şebekesine eşlenmiş
<b>örnek</b> veridir; Balıkesir tesisinin ölçümü değildir. Sonuçlar yöntemi ve büyüklük mertebesini gösterir.
"""

SCOPE_HTML = f"""
<b>Kapsam</b><br>
<span style="color:{theme.MUTED}">Uygulama karar destek amaçlıdır; hiçbir makineye müdahale etmez ve karar her zaman
kullanıcıdadır. Para/TL kazanç vaadi, CBAM hesabı, IoT/sensör bağlantısı ve otomatik makine kontrolü
kapsam dışıdır. Yapay zekâ yalnızca hesaplanmış sayıları açıklama metnine çevirir; internet yoksa
hesap yine çalışır.</span>
"""

WINDOW_LABELS = {"standard": "Standart", "scenario": "Seçilen"}
STATUS_LABELS = {
    "ok": "Tamam",
    "non_shiftable": "Kaydırılamaz",
    "out_of_range": "Aralık dışı",
    "restricted_conflict": "Kısıtlı saat",
    "same_window": "Aynı pencere",
    "no_load": "Yük yok",
}


def _item(text: str, align=Qt.AlignRight | Qt.AlignVCenter) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setTextAlignment(align)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def _table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().hide()
    t.verticalHeader().setDefaultSectionSize(30)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.setFocusPolicy(Qt.NoFocus)
    t.setTabKeyNavigation(False)  # Tab tablodan çıkar (faresiz kullanımda tuzak olmasın)
    t.setSelectionMode(QAbstractItemView.NoSelection)
    t.horizontalHeader().setHighlightSections(False)
    return t


def _raw(v: float | None) -> str:
    """CSV için tam hassasiyet, Türkçe Excel uyumlu ondalık virgül."""
    return "" if v is None else repr(float(v)).replace(".", ",")


def export_calc_csv(path: Path | str, computation) -> None:
    """Hesabı Göster tablosunu ve özet değerleri CSV'ye yazar (UTF-8 BOM, ';' ayraç)."""
    c = computation
    i, r = c.inputs, c.result
    rows = breakdown(c.load, c.ci, r, i.p)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["CarbonDelta hesap dökümü"])
        w.writerow(["Makine", c.machine["name"], "Kod", i.asset_id, "Gün", fmt.date(i.date),
                    "Mod", "Parametrik" if i.parametric else "Ölçülen yük",
                    "Emisyon tipi", i.ci_kind])
        w.writerow(["Standart başlangıç", i.s, "Uzunluk", i.L, "Hedef başlangıç", i.t,
                    "Kaydırma oranı", _raw(i.p), "Kısıtlı saatler",
                    ",".join(str(h) for h in i.restricted)])
        w.writerow([])
        w.writerow(["Pencere", "Saat", "Yükün geldiği saat", "Taşınan enerji (kWh)",
                    "Karbon yoğunluğu (t/MWh)", "Emisyon (kg)"])
        for row in rows:
            w.writerow([WINDOW_LABELS[row["window"]], row["hour"], row["from_hour"],
                        _raw(row["kwh"]), _raw(row["ci"]), _raw(row["kg"])])
        w.writerow([])
        w.writerow(["Durum", STATUS_LABELS.get(r.status, r.status)])
        w.writerow(["B (kg)", _raw(r.baseline_kg)])
        w.writerow(["S (kg)", _raw(r.scenario_kg)])
        w.writerow(["Değişim (%)", _raw(r.delta_pct)])
        w.writerow(["Günlük emisyon (kg)", _raw(r.daily_kg)])
        w.writerow(["Günlük etki (%)", _raw(r.daily_delta_pct)])
        w.writerow([])
        w.writerow([data.source_label(i.asset_id, i.date)])


def _stat(title: str) -> tuple[QWidget, QLabel]:
    frame, lay = theme.card(margins=(14, 10, 14, 10), spacing=2)
    t = QLabel(title)
    t.setObjectName("statLabel")
    v = QLabel("—")
    v.setObjectName("statValue")
    lay.addWidget(t)
    lay.addWidget(v)
    return frame, v


class CalcTab(QWidget):
    """Hesabı Göster: özet, saat saat döküm, formül, ETKB tablosu, CSV dışa aktarma."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.computation = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(10)

        head = QHBoxLayout()
        self.title = QLabel("")
        self.title.setStyleSheet("font-size: 11pt; font-weight: 600;")
        head.addWidget(self.title, 1)
        self.export_button = QPushButton("CSV olarak dışa aktar")
        self.export_button.setObjectName("primary")
        self.export_button.clicked.connect(self._export)
        head.addWidget(self.export_button)
        root.addLayout(head)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.stat_values: dict[str, QLabel] = {}
        for key, title in [("B", "Standart emisyon (B)"), ("S", "Seçilen emisyon (S)"),
                           ("delta", "Değişim (S − B) / B"), ("daily", "Günlük etki")]:
            frame, val = _stat(title)
            stats.addWidget(frame, 1)
            self.stat_values[key] = val
        root.addLayout(stats)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(10)

        left, left_lay = theme.card("Saat saat döküm")
        self.status_note = theme.muted("", wrap=True)
        left_lay.addWidget(self.status_note)
        self.table = _table(["Pencere", "Saat", "Yükün geldiği saat", "Taşınan enerji (kWh)",
                             "Karbon yoğunluğu", "Emisyon (kg)"])
        self.table.setFocusPolicy(Qt.StrongFocus)  # klavyeyle ↑ ↓ kaydırma
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        left_lay.addWidget(self.table, 1)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)
        fcard, flay = theme.card("Hesap nasıl yapılıyor?")
        formula = QTextBrowser()
        formula.setHtml(FORMULA_HTML)
        formula.setMinimumHeight(250)
        flay.addWidget(formula)
        rl.addWidget(fcard, 6)

        ecard, elay = theme.card("ETKB 2023 emisyon faktörleri")
        self.etkb_table = _table(["Kaynak", "tCO2/MWh", "tCO2-eşd/MWh"])
        self.etkb_table.verticalHeader().setDefaultSectionSize(24)
        self._fill_etkb()
        elay.addWidget(self.etkb_table)
        rl.addWidget(ecard, 4)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([700, 440])
        root.addWidget(split, 1)

    def _fill_etkb(self) -> None:
        rows = data.etkb_factors()
        t = self.etkb_table
        t.setRowCount(len(rows))
        for r, row in enumerate(rows):
            t.setItem(r, 0, _item(row["Yakit_Turu_EPIAS_Sutunu"], Qt.AlignLeft | Qt.AlignVCenter))
            t.setItem(r, 1, _item(row["Emisyon_Faktoru_tCO2_MWh"].replace(".", ",")))
            t.setItem(r, 2, _item(row["Emisyon_Faktoru_tCO2esd_MWh"].replace(".", ",")))
        h = t.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)

    def update_computation(self, c) -> None:
        self.computation = c
        i, r = c.inputs, c.result
        unit = "tCO2/MWh" if i.ci_kind == "tCO2" else "tCO2-eşd/MWh"
        kg = "kgCO2" if i.ci_kind == "tCO2" else "kgCO2-eşd"
        self.table.setHorizontalHeaderItem(4, QTableWidgetItem(f"Yoğunluk ({unit})"))
        mode = f"sabit {fmt.num(i.param_kwh)} kWh/saat" if i.parametric else "ölçülen yük"
        self.title.setText(f"{c.machine['name']} · {fmt.date(i.date)} · {fmt.window(i.s, i.L)} → "
                           f"{fmt.window(i.t, i.L)} · %{fmt.num(i.p * 100, 0)} · {mode}")

        rows = breakdown(c.load, c.ci, r, i.p)
        self.table.setRowCount(len(rows))
        for n, row in enumerate(rows):
            vals = [WINDOW_LABELS[row["window"]], fmt.hour(row["hour"]), fmt.hour(row["from_hour"]),
                    fmt.num(row["kwh"]), fmt.num(row["ci"], 6), fmt.num(row["kg"])]
            for col, v in enumerate(vals):
                self.table.setItem(n, col, _item(v, Qt.AlignCenter if col < 3
                                                 else Qt.AlignRight | Qt.AlignVCenter))

        computed = bool(rows)
        self.stat_values["B"].setText(f"{fmt.num(r.baseline_kg)} {kg}" if computed else "—")
        self.stat_values["S"].setText(f"{fmt.num(r.scenario_kg)} {kg}" if computed else "—")
        self.stat_values["delta"].setText(fmt.pct(r.delta_pct))
        self.stat_values["daily"].setText(fmt.pct(r.daily_delta_pct))
        color = theme.TEXT
        if r.status == "ok":
            color = theme.GOOD if r.delta_pct <= 0 else theme.BAD
        self.stat_values["delta"].setStyleSheet(f"color: {color};")
        if computed:
            self.status_note.setText(
                f"Günlük toplam emisyon {fmt.num(r.daily_kg)} {kg}. Seçilen satırlardaki enerji, "
                "aynı sıradaki standart saatten taşınır.")
        else:
            self.status_note.setText(f"Bu senaryoda hesap yapılmadı (durum: "
                                     f"{STATUS_LABELS.get(r.status, r.status)}).")
        self.export_button.setEnabled(True)

    def _export(self) -> None:
        if self.computation is None:
            return
        i = self.computation.inputs
        default = f"carbondelta_{i.asset_id}_{i.date}_{i.s:02d}-{i.t:02d}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "CSV olarak dışa aktar", default,
                                              "CSV dosyası (*.csv)")
        if not path:
            return
        try:
            export_calc_csv(path, self.computation)
        except OSError as e:
            QMessageBox.warning(self, "Dışa aktarma", f"Dosya yazılamadı:\n{e}")
            return
        QMessageBox.information(self, "Dışa aktarma", f"Kaydedildi:\n{path}")


class HistoryTab(QWidget):
    """Kaydedilmiş senaryoların listesi."""

    restore_requested = Signal(dict)
    summarize_requested = Signal()

    HEADERS = ["Kayıt zamanı", "Makine", "Gün", "Standart", "Seçilen", "Oran", "Tip", "Mod",
               "Durum", "Değişim", "Günlük etki"]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(10)

        card, lay = theme.card()
        bar = QHBoxLayout()
        title = QLabel("Kayıtlı senaryolar")
        title.setObjectName("cardTitle")
        bar.addWidget(title)
        bar.addSpacing(10)
        bar.addWidget(theme.muted("↑ ↓ seç · Enter geri yükle · Delete sil (çift tıklama da olur)"), 1)
        self.summarize_button = QPushButton("Özetle")
        self.summarize_button.setObjectName("primary")
        self.summarize_button.clicked.connect(self.summarize_requested.emit)
        bar.addWidget(self.summarize_button)
        self.delete_button = QPushButton("Seçili kaydı sil")
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(self._delete_selected)
        bar.addWidget(self.delete_button)
        lay.addLayout(bar)

        self.stack = QStackedWidget()
        self.table = _table(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setFocusPolicy(Qt.StrongFocus)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Stretch)
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.cellDoubleClicked.connect(self._restore_row)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.installEventFilter(self)
        self.stack.addWidget(self.table)
        empty = QLabel("Henüz kayıt yok.\nSenaryo sekmesinde “Senaryoyu kaydet” ile ekleyebilirsiniz.")
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet(f"color: {theme.MUTED}; font-size: 10.5pt;")
        self.stack.addWidget(empty)
        lay.addWidget(self.stack, 1)
        root.addWidget(card, 1)

        self.summary_card, sl = theme.card()
        sh = QHBoxLayout()
        st = QLabel("Geçmiş özeti")
        st.setObjectName("cardTitle")
        sh.addWidget(st)
        self.summary_chip = QLabel("")
        sh.addWidget(self.summary_chip)
        sh.addStretch(1)
        sl.addLayout(sh)
        self.summary_text = QTextBrowser()
        self.summary_text.setMaximumHeight(90)
        sl.addWidget(self.summary_text)
        self.summary_card.hide()
        root.addWidget(self.summary_card)
        self.refresh()

    def refresh(self) -> None:
        rows = self.db.list()
        self.stack.setCurrentIndex(0 if rows else 1)
        self.summarize_button.setEnabled(bool(rows))
        self.table.setRowCount(len(rows))
        names = {m["id"]: m["name"] for m in data.machines()}
        for n, h in enumerate(rows):
            mode = "Parametrik" if h["mode"] == "parametric" else "Ölçülen"
            vals = [fmt.datetime(h["created_at"]), names.get(h["asset_id"], h["asset_id"]),
                    fmt.date(h["date"]), fmt.window(h["s"], h["L"]), fmt.window(h["t"], h["L"]),
                    f"%{fmt.num(h['p'] * 100, 0)}", "tCO2-eşd" if h["ci_kind"] == "tCO2esd" else "tCO2",
                    mode, STATUS_LABELS.get(h["status"], h["status"]),
                    fmt.pct(h["delta_pct"]), fmt.pct(h["daily_delta_pct"])]
            for col, v in enumerate(vals):
                it = _item(v, Qt.AlignCenter)
                it.setData(Qt.UserRole, h["id"])
                if col == 9 and h["delta_pct"] is not None:
                    it.setForeground(QColor(theme.GOOD if h["delta_pct"] <= 0 else theme.BAD))
                self.table.setItem(n, col, it)
        self.refresh_selection()
        self._update_buttons()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.table and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                items = self.table.selectedItems()
                if items:
                    self._restore_row(items[0].row(), 0)
                return True
            if event.key() == Qt.Key_Delete:
                self._delete_selected()
                return True
        return super().eventFilter(obj, event)

    def refresh_selection(self) -> None:
        if self.table.rowCount() and not self.table.selectedItems():
            self.table.selectRow(0)

    def _update_buttons(self) -> None:
        self.delete_button.setEnabled(self._selected_id() is not None)

    def _selected_id(self) -> int | None:
        items = self.table.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    def _restore_row(self, row: int, _col: int) -> None:
        h = self.db.get(self.table.item(row, 0).data(Qt.UserRole))
        if h:
            self.restore_requested.emit(h)

    def _delete_selected(self, confirm: bool = True) -> None:
        row_id = self._selected_id()
        if row_id is None:
            return
        if confirm:
            box = QMessageBox(QMessageBox.Question, "Kaydı sil", "Seçili kayıt geçmişten silinsin mi?",
                              parent=self)
            delete = box.addButton("Sil", QMessageBox.DestructiveRole)
            cancel = box.addButton("Vazgeç", QMessageBox.RejectRole)
            box.setDefaultButton(cancel)  # Enter → Vazgeç; Tab ile Sil seçilir, Esc kapatır
            box.setEscapeButton(cancel)
            box.exec()
            if box.clickedButton() is not delete:
                return
        self.db.delete(row_id)
        self.refresh()

    def show_summary(self, text: str, source: str) -> None:
        from desktop.main_window import SOURCE_CHIPS, chip_style
        from desktop.ai_client import prompts
        note = ""
        if source == "fallback_offline":
            note = prompts()["offline_message"]
        elif source == "fallback_invalid":
            note = prompts()["invalid_message"]
        self.summary_chip.setText(SOURCE_CHIPS[source][0])
        self.summary_chip.setStyleSheet(chip_style(source))
        body = (f"<p style='color:{theme.MUTED}; font-size:8.5pt; margin:0 0 4px 0;'><i>{note}</i></p>"
                if note else "")
        self.summary_text.setHtml(body + f"<p style='margin:0'>{text}</p>")
        self.summary_card.show()


class SourcesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(12)
        for col, (title, stat, text) in enumerate(SOURCE_CARDS):
            frame, lay = theme.card(title, margins=(16, 14, 16, 14))
            chip = QLabel(stat)
            chip.setStyleSheet(f"color: {theme.PRIMARY}; background: {theme.PRIMARY_SOFT};"
                               " border-radius: 9px; padding: 2px 10px; font-weight: 600;")
            chip.setMaximumWidth(chip.sizeHint().width() + 24)
            lay.addWidget(chip)
            body = QLabel(text)
            body.setWordWrap(True)
            body.setStyleSheet("line-height: 140%;")
            lay.addWidget(body)
            lay.addStretch(1)
            grid.addWidget(frame, 0, col)
        root.addLayout(grid)

        note, nl = theme.card(name="noteCard", margins=(16, 12, 16, 12))
        n = QLabel(NOTE_HTML)
        n.setWordWrap(True)
        nl.addWidget(n)
        root.addWidget(note)

        scope, sl = theme.card(margins=(16, 12, 16, 12))
        s = QLabel(SCOPE_HTML)
        s.setWordWrap(True)
        sl.addWidget(s)
        root.addWidget(scope)
        root.addStretch(1)
