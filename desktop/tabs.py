"""Hesabı Göster, Geçmiş ve Kaynaklar sekmeleri."""
from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from desktop import fmt
from engine import data
from engine.explain import breakdown

FORMULA_HTML = """
<h3 style="margin-bottom:4px">Hesap nasıl yapılıyor?</h3>
<p>Seçilen gün için her saatin şebeke karbon yoğunluğu (EPİAŞ 2025, ETKB 2023 katsayıları)
ve makinenin o saatteki tüketimi kullanılır. Hesapta yapay zekâ yoktur.</p>
<ol>
<li><b>Taşınan enerji:</b> standart penceredeki her saat için
    <i>E = kaydırma oranı × o saatin tüketimi (kWh)</i>.</li>
<li><b>Standart emisyon (B):</b> her E, kendi saatinin karbon yoğunluğuyla çarpılıp toplanır.</li>
<li><b>Seçilen saat emisyonu (S):</b> aynı E değerleri, hedef penceredeki karşılık gelen saatin
    karbon yoğunluğuyla çarpılıp toplanır.</li>
<li><b>Ana yüzde:</b> (S − B) / B × 100. Eksi değer daha düşük emisyon potansiyeli demektir.</li>
<li><b>Günlük etki:</b> (S − B) / (makinenin o günkü toplam emisyonu) × 100.</li>
</ol>
<p style="color:#6b7785">Birim: tCO2/MWh = kgCO2/kWh. İç hesap tam hassasiyetle yapılır;
yalnızca ekranda yuvarlanır.</p>
"""

SOURCES_HTML = """
<h3>Veri kaynakları</h3>
<p><b>EPİAŞ Şeffaflık Platformu — 2025 saatlik gerçek zamanlı üretim.</b>
8.760 saatin kaynak bazında (doğal gaz, linyit, ithal kömür, rüzgâr, güneş, hidro vb.) üretimi.
Her saatin karbon yoğunluğu, kaynak üretimlerinin ETKB katsayılarıyla çarpılıp yurtiçi toplam
üretime bölünmesiyle bulunmuştur.</p>
<p><b>ETKB 2023 — Türkiye Elektrik Üretimi Emisyon Faktörleri.</b>
Enerji ve Tabii Kaynaklar Bakanlığı'nın yakıt türü başına resmi tCO2/MWh ve tCO2-eşd/MWh
katsayıları. Yenilenebilir kaynaklar için doğrudan yakıt emisyonu sıfır kabul edilir.
Tablo "Hesabı Göster" sekmesindedir.</p>
<p><b>Zenodo — imalat tesisi makine yük veri seti.</b>
Bir üretim tesisindeki makinelerin 15 dakikalık enerji ölçümleri; faz tekrarları, sensör hatalı
cihazlar ve eksik günler temizlenmiş, saatlik toplama çevrilmiştir. Ana pakette 7 makine vardır;
ex_a (havalandırma) ve php_c (pres ısıtma) sürekli/kısıtlı süreç olduğu için kaydırılamaz.</p>
<h3>Önemli not: örnek yük</h3>
<p>Yük verisi İrlanda'daki bir tesisten alınmış ve saat numarasıyla Türkiye şebekesine
eşlenmiş <b>örnek</b> veridir; Balıkesir tesisinin ölçümü değildir. Sonuçlar yöntemi ve
büyüklük mertebesini gösterir. Para/TL kazancı, CBAM hesabı veya makineye otomatik müdahale
kapsam dışıdır; karar her zaman kullanıcıdadır.</p>
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
        w.writerow(["Makine", i.asset_id, "Gün", i.date, "Mod", i.mode, "Emisyon tipi", i.ci_kind])
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
        w.writerow(["Durum", r.status])
        w.writerow(["B (kg)", _raw(r.baseline_kg)])
        w.writerow(["S (kg)", _raw(r.scenario_kg)])
        w.writerow(["Delta (%)", _raw(r.delta_pct)])
        w.writerow(["Günlük emisyon (kg)", _raw(r.daily_kg)])
        w.writerow(["Günlük etki (%)", _raw(r.daily_delta_pct)])
        w.writerow([])
        w.writerow(["Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo"])


class CalcTab(QWidget):
    """Hesabı Göster: formül, saat saat döküm, ETKB tablosu, CSV dışa aktarma."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.computation = None
        lay = QHBoxLayout(self)

        left = QVBoxLayout()
        formula = QTextBrowser()
        formula.setHtml(FORMULA_HTML)
        formula.setMaximumWidth(430)
        left.addWidget(formula, 2)
        left.addWidget(QLabel("<b>ETKB 2023 emisyon faktörleri</b>"))
        self.etkb_table = QTableWidget()
        self._fill_etkb()
        left.addWidget(self.etkb_table, 3)
        lay.addLayout(left, 0)

        right = QVBoxLayout()
        head = QHBoxLayout()
        self.title = QLabel("")
        self.title.setStyleSheet("font-weight: 600;")
        head.addWidget(self.title, 1)
        self.export_button = QPushButton("CSV olarak dışa aktar")
        self.export_button.clicked.connect(self._export)
        head.addWidget(self.export_button)
        right.addLayout(head)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Pencere", "Saat", "Yükün geldiği saat", "Taşınan enerji (kWh)",
             "Karbon yoğunluğu", "Emisyon (kg)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        right.addWidget(self.table, 1)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        right.addWidget(self.summary)
        lay.addLayout(right, 1)

    def _fill_etkb(self) -> None:
        rows = data.etkb_factors()
        cols = [("Yakit_Turu_EPIAS_Sutunu", "Kaynak"), ("Emisyon_Faktoru_tCO2_MWh", "tCO2/MWh"),
                ("Emisyon_Faktoru_tCO2esd_MWh", "tCO2-eşd/MWh"), ("Kategori", "Kategori")]
        t = self.etkb_table
        t.setColumnCount(len(cols))
        t.setRowCount(len(rows))
        t.setHorizontalHeaderLabels([c[1] for c in cols])
        t.verticalHeader().hide()
        for r, row in enumerate(rows):
            for c, (key, _) in enumerate(cols):
                left = key in ("Yakit_Turu_EPIAS_Sutunu", "Kategori")
                text = row[key] if left else row[key].replace(".", ",")
                t.setItem(r, c, _item(text, Qt.AlignLeft | Qt.AlignVCenter if left
                                      else Qt.AlignRight | Qt.AlignVCenter))
        t.resizeColumnsToContents()

    def update_computation(self, c) -> None:
        self.computation = c
        i, r = c.inputs, c.result
        unit = "tCO2/MWh" if i.ci_kind == "tCO2" else "tCO2-eşd/MWh"
        self.table.setHorizontalHeaderItem(4, QTableWidgetItem(f"CI ({unit})"))
        mode = f"parametrik {fmt.num(i.param_kwh)} kWh/saat" if i.parametric else "ölçülen yük"
        self.title.setText(f"{i.asset_id} · {i.date} · {fmt.window(i.s, i.L)} → "
                           f"{fmt.window(i.t, i.L)} · %{fmt.num(i.p * 100, 0)} · {mode}")

        rows = breakdown(c.load, c.ci, r, i.p)
        self.table.setRowCount(len(rows))
        for n, row in enumerate(rows):
            vals = [WINDOW_LABELS[row["window"]], fmt.hour(row["hour"]), fmt.hour(row["from_hour"]),
                    fmt.num(row["kwh"]), fmt.num(row["ci"], 6), fmt.num(row["kg"])]
            for col, v in enumerate(vals):
                self.table.setItem(n, col, _item(v, Qt.AlignCenter if col < 3
                                                 else Qt.AlignRight | Qt.AlignVCenter))

        if rows:
            self.summary.setText(
                f"B = <b>{fmt.num(r.baseline_kg)} kg</b> · S = <b>{fmt.num(r.scenario_kg)} kg</b> · "
                f"(S − B) / B × 100 = <b>{fmt.pct(r.delta_pct)}</b> · "
                f"günlük emisyon {fmt.num(r.daily_kg)} kg · günlük etki <b>{fmt.pct(r.daily_delta_pct)}</b>")
        else:
            self.summary.setText(f"Bu senaryoda hesap yapılmadı (durum: "
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
        lay = QVBoxLayout(self)

        bar = QHBoxLayout()
        hint = QLabel("Çift tıklayarak senaryoyu geri yükleyin.")
        hint.setStyleSheet("color: #6b7785;")
        bar.addWidget(hint, 1)
        self.summarize_button = QPushButton("Özetle")
        self.summarize_button.clicked.connect(self.summarize_requested.emit)
        bar.addWidget(self.summarize_button)
        self.delete_button = QPushButton("Sil")
        self.delete_button.clicked.connect(self._delete_selected)
        bar.addWidget(self.delete_button)
        lay.addLayout(bar)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.cellDoubleClicked.connect(self._restore_row)
        lay.addWidget(self.table, 1)

        self.summary_source = QLabel("")
        self.summary_source.setStyleSheet("color: #6b7785;")
        self.summary_source.hide()
        lay.addWidget(self.summary_source)
        self.summary_text = QTextBrowser()
        self.summary_text.setMaximumHeight(110)
        self.summary_text.hide()
        lay.addWidget(self.summary_text)
        self.refresh()

    def show_summary(self, text: str, source: str) -> None:
        self.summary_source.setText(f"Geçmiş özeti · {source}" if source else "Geçmiş özeti")
        self.summary_text.setPlainText(text)
        self.summary_source.show()
        self.summary_text.show()

    def refresh(self) -> None:
        rows = self.db.list()
        self.table.setRowCount(len(rows))
        for n, h in enumerate(rows):
            mode = "Parametrik" if h["mode"] == "parametric" else "Ölçülen"
            vals = [h["created_at"].replace("T", " "), h["asset_id"], h["date"],
                    fmt.window(h["s"], h["L"]), fmt.window(h["t"], h["L"]),
                    f"%{fmt.num(h['p'] * 100, 0)}", "tCO2-eşd" if h["ci_kind"] == "tCO2esd" else "tCO2",
                    mode, STATUS_LABELS.get(h["status"], h["status"]),
                    fmt.pct(h["delta_pct"]), fmt.pct(h["daily_delta_pct"])]
            for col, v in enumerate(vals):
                it = _item(v, Qt.AlignCenter)
                it.setData(Qt.UserRole, h["id"])
                self.table.setItem(n, col, it)

    def _selected_id(self) -> int | None:
        items = self.table.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    def _restore_row(self, row: int, _col: int) -> None:
        h = self.db.get(self.table.item(row, 0).data(Qt.UserRole))
        if h:
            self.restore_requested.emit(h)

    def _delete_selected(self) -> None:
        row_id = self._selected_id()
        if row_id is None:
            return
        self.db.delete(row_id)
        self.refresh()


class SourcesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        text = QTextBrowser()
        text.setHtml(SOURCES_HTML)
        lay.addWidget(text)
