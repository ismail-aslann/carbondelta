"""Veri yönetimi sekmesi: makine, yıl (EPİAŞ) ve emisyon katsayısı paketleri."""
from __future__ import annotations

import html

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QRadioButton, QScrollArea, QStackedWidget,
    QVBoxLayout, QWidget,
)

from desktop import fmt, theme
from engine import data
from engine import packages as pk

FILE_FILTER = "Veri dosyaları (*.csv *.txt *.xlsx *.xls);;Tüm dosyalar (*)"
KIND_LABEL = {pk.KIND_MACHINE: "Makine", pk.KIND_GRID: "Şebeke", pk.KIND_FACTORS: "Katsayı"}


def report_html(rep: pk.Report) -> str:
    icons = {"ok": ("✓", theme.GOOD), "warn": ("!", theme.WARN), "err": ("✕", theme.BAD)}
    rows = []
    for level, text in rep.lines:
        sym, color = icons[level]
        rows.append(f"<tr><td style='color:{color}; font-weight:700; padding-right:8px;' valign='top'>{sym}</td>"
                    f"<td style='padding:2px 0;'>{html.escape(text)}</td></tr>")
    return "<table cellspacing='0'>" + "".join(rows) + "</table>"


class ProfileBars(QWidget):
    """24 saatlik ortalama yük önizlemesi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values: list[float] = []
        self.setMinimumHeight(90)

    def set_values(self, values: list[float]) -> None:
        self.values = [v if v == v else 0.0 for v in values]
        self.update()

    def paintEvent(self, _e) -> None:
        if not self.values:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height() - 16
        top = max(self.values) or 1.0
        bw = w / 24
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#a9bfd3"))
        for i, v in enumerate(self.values):
            bh = v / top * (h - 4)
            p.drawRoundedRect(QRectF(i * bw + 1.5, h - bh, bw - 3, bh), 2, 2)
        p.setPen(QColor(theme.MUTED))
        f = p.font()
        f.setPointSizeF(7.5)
        p.setFont(f)
        for i in (0, 6, 12, 18, 23):
            p.drawText(QRectF(i * bw - 6, h + 2, bw + 12, 14), Qt.AlignHCenter, f"{i:02d}")
        p.end()


class _FileRow(QWidget):
    chosen = Signal(str)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.path = QLineEdit()
        self.path.setReadOnly(True)
        self.path.setPlaceholderText("Dosya seçilmedi")
        lay.addWidget(self.path, 1)
        self.button = QPushButton("Dosya seç…")
        self.button.clicked.connect(lambda: self._pick(title))
        lay.addWidget(self.button)

    def _pick(self, title: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, title, "", FILE_FILTER)
        if path:
            self.path.setText(path)
            self.chosen.emit(path)

    def value(self) -> str:
        return self.path.text()

    def clear(self) -> None:
        self.path.clear()


class _Wizard(QWidget):
    """Ortak akış: dosya → kontrol → (önizleme) → ekle."""

    added = Signal(str)  # eklenen paketin adı

    STEPS = ["1 · Dosya", "2 · Bilgiler", "3 · Kontrol ve önizleme", "4 · Ekle"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.check = None
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(10)
        steps = QHBoxLayout()
        steps.setSpacing(6)
        self.step_labels = []
        for s in self.STEPS:
            lbl = QLabel(s)
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            steps.addWidget(lbl, 1)
            self.step_labels.append(lbl)
        self.lay.addLayout(steps)
        self.set_step(0)

    def set_step(self, n: int) -> None:
        for i, lbl in enumerate(self.step_labels):
            if i < n:
                css = f"background:{theme.PRIMARY_SOFT}; color:{theme.PRIMARY_DARK};"
            elif i == n:
                css = f"background:{theme.PRIMARY}; color:white; font-weight:600;"
            else:
                css = f"background:#eef1f4; color:{theme.MUTED};"
            lbl.setStyleSheet(css + " border-radius:6px; padding:6px 10px; font-size:8.5pt;")

    def _report_box(self) -> QLabel:
        box = QLabel("")
        box.setWordWrap(True)
        box.setTextFormat(Qt.RichText)
        box.setStyleSheet("font-size: 9.5pt;")
        return box


class MachineWizard(_Wizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        body = QHBoxLayout()
        body.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(8)
        title = QLabel("Makine bilgileri")
        title.setObjectName("cardTitle")
        left.addWidget(title)
        form = QFormLayout()
        form.setVerticalSpacing(8)
        self.file = _FileRow("Makine yük dosyası seç")
        self.file.chosen.connect(lambda _p: self.run_check())
        form.addRow("Dosya", self.file)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ör. Kompresör (Hat 2)")
        self.name.textChanged.connect(self._update_add)
        form.addRow("Makine adı", self.name)
        self.mtype = QLineEdit()
        self.mtype.setPlaceholderText("Ör. Basınçlı hava")
        form.addRow("Tür", self.mtype)
        self.shift_yes = QRadioButton("Evet")
        self.shift_no = QRadioButton("Hayır (sürekli / kısıtlı süreç)")
        self.shift_yes.setChecked(True)
        g1 = QButtonGroup(self)
        row1 = QHBoxLayout()
        for b in (self.shift_yes, self.shift_no):
            g1.addButton(b)
            row1.addWidget(b)
        row1.addStretch(1)
        form.addRow("Kaydırılabilir mi?", row1)
        self.src_sample = QRadioButton("Örnek yük")
        self.src_real = QRadioButton("Tesis ölçümü (Balıkesir)")
        self.src_real.setChecked(True)
        g2 = QButtonGroup(self)
        row2 = QHBoxLayout()
        for b in (self.src_sample, self.src_real):
            g2.addButton(b)
            row2.addWidget(b)
        row2.addStretch(1)
        form.addRow("Veri türü", row2)
        left.addLayout(form)
        left.addWidget(theme.muted("Beklenen biçim (ayraç ; veya ,  — ondalık virgül olabilir):"))
        sample = QLabel("Tarih;Saat;kWh\n2026-01-01;0;12,40\n2026-01-01;1;11,85\n…")
        sample.setStyleSheet("font-family: Consolas; font-size: 9pt; background:#f6f8fa; border:1px solid #e1e6ec;"
                             " border-radius:6px; padding:6px 8px;")
        left.addWidget(sample)
        tpl = QPushButton("Şablon dosyayı kaydet…")
        tpl.clicked.connect(self._save_template)
        left.addWidget(tpl, 0, Qt.AlignLeft)
        left.addStretch(1)
        body.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        t2 = QLabel("Otomatik kontrol")
        t2.setObjectName("cardTitle")
        right.addWidget(t2)
        self.report = self._report_box()
        self.report.setText(f"<span style='color:{theme.MUTED}'>Dosya seçince kontrol otomatik yapılır.</span>")
        right.addWidget(self.report)
        t3 = QLabel("Önizleme · ortalama günlük profil")
        t3.setObjectName("cardTitle")
        right.addWidget(t3)
        self.bars = ProfileBars()
        right.addWidget(self.bars)
        right.addStretch(1)
        body.addLayout(right, 1)
        self.lay.addLayout(body)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.recheck = QPushButton("Yeniden kontrol et")
        self.recheck.clicked.connect(self.run_check)
        btns.addWidget(self.recheck)
        self.add_button = QPushButton("Ekle")
        self.add_button.setObjectName("primary")
        self.add_button.clicked.connect(self.add)
        btns.addWidget(self.add_button)
        self.lay.addLayout(btns)
        self._update_add()

    def _save_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Şablon dosyayı kaydet", "makine_sablonu.csv", "CSV (*.csv)")
        if path:
            pk.write_machine_template(path)

    def run_check(self) -> None:
        if not self.file.value():
            return
        self.check = pk.check_machine_file(self.file.value(), set(data.all_dates()))
        self.report.setText(report_html(self.check.report))
        self.bars.set_values(self.check.profile)
        self.set_step(2)
        self._update_add()

    def _update_add(self, *_a) -> None:
        ok = bool(self.check and not self.check.report.has_errors and self.name.text().strip())
        self.add_button.setEnabled(ok)
        if self.check and not self.check.report.has_errors:
            self.add_button.setText(f"{fmt.num(len(self.check.days), 0)} günü ekle →")
        else:
            self.add_button.setText("Ekle")
        if self.check is None:
            self.set_step(1 if self.name.text().strip() else 0)

    def add(self) -> None:
        if not self.add_button.isEnabled():
            return
        name = self.name.text().strip()
        pk.add_machine_package(self.check, name, self.mtype.text().strip(), self.shift_yes.isChecked(),
                               "real" if self.src_real.isChecked() else "sample")
        self.set_step(3)
        self.added.emit(name)
        self.reset()

    def reset(self) -> None:
        self.check = None
        self.file.clear()
        self.name.clear()
        self.mtype.clear()
        self.bars.set_values([])
        self.report.setText(f"<span style='color:{theme.MUTED}'>Dosya seçince kontrol otomatik yapılır.</span>")
        self._update_add()


class GridWizard(_Wizard):
    STEPS = ["1 · Dosya", "2 · Kontrol", "3 · Ekle"]

    def __init__(self, parent=None):
        super().__init__(parent)
        info = QLabel("EPİAŞ Şeffaflık Platformu › Üretim › <b>Gerçek Zamanlı Üretim</b> sayfasından istediğiniz "
                      "tarih aralığını Excel/CSV olarak dışa aktarın. Ondalık yazımları düzeltilir, negatif gece "
                      "güneş değerleri 0 yapılır ve karbon yoğunluğu varsayılan veriyle aynı yöntemle "
                      f"(kaynak üretimi × {data.factors_label()} katsayıları) hesaplanır.")
        info.setWordWrap(True)
        info.setTextFormat(Qt.RichText)
        info.setStyleSheet(f"color:{theme.MUTED};")
        self.lay.addWidget(info)
        form = QFormLayout()
        self.file = _FileRow("EPİAŞ üretim dosyası seç")
        self.file.chosen.connect(lambda _p: self.run_check())
        form.addRow("Dosya", self.file)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ör. EPİAŞ 2026")
        self.name.textChanged.connect(self._update_add)
        form.addRow("Paket adı", self.name)
        self.lay.addLayout(form)
        t = QLabel("Otomatik kontrol")
        t.setObjectName("cardTitle")
        self.lay.addWidget(t)
        self.report = self._report_box()
        self.lay.addWidget(self.report)
        self.lay.addStretch(1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.add_button = QPushButton("Ekle")
        self.add_button.setObjectName("primary")
        self.add_button.clicked.connect(self.add)
        btns.addWidget(self.add_button)
        self.lay.addLayout(btns)
        self._update_add()

    def run_check(self) -> None:
        if not self.file.value():
            return
        self.check = pk.check_grid_file(self.file.value(), data.factors(), set(data.all_dates()))
        self.report.setText(report_html(self.check.report))
        if self.check.years and not self.name.text().strip():
            self.name.setText("EPİAŞ " + "–".join(str(y) for y in (self.check.years[0], self.check.years[-1]))
                              if len(self.check.years) > 1 else f"EPİAŞ {self.check.years[0]}")
        self.set_step(1)
        self._update_add()

    def _update_add(self, *_a) -> None:
        ok = bool(self.check and not self.check.report.has_errors and self.name.text().strip())
        self.add_button.setEnabled(ok)
        self.add_button.setText(f"{fmt.num(len(self.check.days), 0)} günü ekle →" if ok else "Ekle")

    def add(self) -> None:
        if not self.add_button.isEnabled():
            return
        name = self.name.text().strip()
        pk.add_grid_package(self.check, name)
        self.set_step(2)
        self.added.emit(name)
        self.check = None
        self.file.clear()
        self.name.clear()
        self.report.setText("")
        self._update_add()


class FactorsWizard(_Wizard):
    STEPS = ["1 · Dosya", "2 · Kontrol", "3 · Ekle"]

    def __init__(self, parent=None):
        super().__init__(parent)
        info = QLabel("ETKB yeni emisyon faktörlerini yayımladığında yakıt türü başına tCO2/MWh ve tCO2-eşd/MWh "
                      "değerlerini içeren bir dosya seçin (ör. <i>Kaynak;tCO2/MWh;tCO2-eşd/MWh</i>). Etkin olduğunda "
                      "tüm yılların karbon yoğunluğu yeni katsayılarla yeniden hesaplanır; formül değişmez.")
        info.setWordWrap(True)
        info.setTextFormat(Qt.RichText)
        info.setStyleSheet(f"color:{theme.MUTED};")
        self.lay.addWidget(info)
        form = QFormLayout()
        self.file = _FileRow("Emisyon katsayısı dosyası seç")
        self.file.chosen.connect(lambda _p: self.run_check())
        form.addRow("Dosya", self.file)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ör. ETKB 2025")
        self.name.textChanged.connect(self._update_add)
        form.addRow("Paket adı", self.name)
        self.lay.addLayout(form)
        t = QLabel("Otomatik kontrol")
        t.setObjectName("cardTitle")
        self.lay.addWidget(t)
        self.report = self._report_box()
        self.lay.addWidget(self.report)
        self.lay.addStretch(1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.add_button = QPushButton("Katsayıları etkinleştir")
        self.add_button.setObjectName("primary")
        self.add_button.clicked.connect(self.add)
        btns.addWidget(self.add_button)
        self.lay.addLayout(btns)
        self._update_add()

    def run_check(self) -> None:
        if not self.file.value():
            return
        self.check = pk.check_factors_file(self.file.value(), data.factors())
        self.report.setText(report_html(self.check.report))
        self.set_step(1)
        self._update_add()

    def _update_add(self, *_a) -> None:
        self.add_button.setEnabled(bool(self.check and not self.check.report.has_errors
                                        and self.name.text().strip()))

    def add(self) -> None:
        if not self.add_button.isEnabled():
            return
        name = self.name.text().strip()
        pk.add_factors_package(self.check, name)
        self.set_step(2)
        self.added.emit(name)
        self.check = None
        self.file.clear()
        self.name.clear()
        self.report.setText("")
        self._update_add()


class DataTab(QWidget):
    data_changed = Signal(str)  # kullanıcıya gösterilecek mesaj

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(12)

        # Sol: paketler
        left = QVBoxLayout()
        left.setSpacing(10)
        card, lay = theme.card("Yüklü veri paketleri")
        card.setFixedWidth(360)
        self.list = QListWidget()
        self.list.setStyleSheet(
            "QListWidget { border: none; background: transparent; outline: none; }"
            "QListWidget::item { border: 1px solid #e1e6ec; border-radius: 8px; padding: 8px 6px; margin-bottom: 6px; }"
            f"QListWidget::item:selected {{ border: 2px solid {theme.PRIMARY}; background: {theme.PRIMARY_SOFT};"
            f" color: {theme.TEXT}; }}"
            "QListWidget::indicator { width: 16px; height: 16px; border: 1px solid #9aa5b1; border-radius: 4px;"
            " background: white; }"
            f"QListWidget::indicator:checked {{ background: {theme.PRIMARY}; border-color: {theme.PRIMARY}; }}")
        self.list.setWordWrap(True)
        self.list.setTextElideMode(Qt.ElideNone)
        self.list.itemChanged.connect(self._on_item_changed)
        self.list.installEventFilter(self)
        lay.addWidget(self.list, 1)
        btns = QHBoxLayout()
        self.toggle_button = QPushButton("Aç / Kapat")
        self.toggle_button.clicked.connect(self._toggle_selected)
        btns.addWidget(self.toggle_button)
        self.delete_button = QPushButton("Sil")
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(self._delete_selected)
        btns.addWidget(self.delete_button)
        btns.addStretch(1)
        lay.addLayout(btns)
        lay.addWidget(theme.muted("↑ ↓ seç · Boşluk aç/kapat · Delete sil. Paketler "
                                  "%APPDATA%\\CarbonDelta\\veri\\ klasöründe tutulur.", wrap=True))
        left.addWidget(card, 1)
        note, nl = theme.card(name="noteCard", margins=(12, 10, 12, 10))
        n = QLabel("<b>Formül bu ekrandan değiştirilmez.</b> Hesap formülü masaüstü, mobil ve Excel'de aynı "
                   "kalmalıdır; değişiklik FORMUL.md sürüm süreciyle yapılır. Emisyon katsayıları ise veri olarak "
                   "güncellenebilir.")
        n.setWordWrap(True)
        nl.addWidget(n)
        note.setFixedWidth(360)
        left.addWidget(note)
        root.addLayout(left)

        # Sağ: işlemler
        right = QVBoxLayout()
        right.setSpacing(10)
        acts = QHBoxLayout()
        acts.setSpacing(10)
        self.action_buttons = []
        self.stack = QStackedWidget()
        self.wizards = [MachineWizard(), GridWizard(), FactorsWizard()]
        titles = [("Makine ekle", "Saatlik kWh dosyası (CSV / Excel)"),
                  ("Yıl ekle", "EPİAŞ gerçek zamanlı üretim dışa aktarımı"),
                  ("Emisyon katsayıları", "Yeni ETKB yakıt faktörleri")]
        for i, ((t, sub), wiz) in enumerate(zip(titles, self.wizards)):
            b = QPushButton(f"{t}\n{sub}")
            b.setCheckable(True)
            b.setMinimumHeight(56)
            b.setStyleSheet(
                "QPushButton { text-align: left; padding: 8px 12px; border-radius: 10px; font-weight: 600; }"
                f"QPushButton:checked {{ border: 2px solid {theme.PRIMARY}; background: {theme.PRIMARY_SOFT}; }}")
            b.clicked.connect(lambda _c=False, i=i: self.show_action(i))
            acts.addWidget(b, 1)
            self.action_buttons.append(b)
            wrap = QScrollArea()
            wrap.setWidgetResizable(True)
            wrap.setFrameShape(QScrollArea.NoFrame)
            inner, il = theme.card()
            il.addWidget(wiz)
            wrap.setWidget(inner)
            self.stack.addWidget(wrap)
            wiz.added.connect(self._on_added)
        right.addLayout(acts)
        self.msg = QLabel("")
        self.msg.setStyleSheet(f"color: {theme.GOOD}; font-weight: 600;")
        self.msg.hide()
        right.addWidget(self.msg)
        right.addWidget(self.stack, 1)
        root.addLayout(right, 1)
        self.show_action(0)
        self.refresh()

    # ------------------------------------------------------------- liste
    def refresh(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        base = QListWidgetItem(f"Varsayılan veri (2025)\n{data.BASE_GRID_LABEL} · 8.760 saat · 7 makine · "
                               f"{data.BASE_FACTORS_LABEL}\nYerleşik · Örnek yük")
        base.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        base.setData(Qt.UserRole, None)
        base.setSizeHint(QSize(0, 90))
        self.list.addItem(base)
        errors = data.package_errors()
        for p in pk.list_packages():
            if p.id in errors:
                item = QListWidgetItem(f"{p.name}\n⚠ Okunamadı — paket atlandı\n{errors[p.id][:60]}")
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setForeground(QColor(theme.BAD))
                item.setData(Qt.UserRole, p.id)
                item.setSizeHint(QSize(0, 90))
                item.setToolTip(f"{errors[p.id]}\nDelete ile silip dosyayı yeniden ekleyin.")
                self.list.addItem(item)
                continue
            item = QListWidgetItem(self._describe(p))
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if p.enabled else Qt.Unchecked)
            item.setData(Qt.UserRole, p.id)
            item.setSizeHint(QSize(0, 90))
            item.setToolTip(f"Eklendi: {fmt.datetime(p.created_at)}" if p.created_at else "")
            if not p.enabled:
                item.setForeground(QColor(theme.MUTED))
            self.list.addItem(item)
        self.list.blockSignals(False)
        if self.list.currentRow() < 0:
            self.list.setCurrentRow(0)

    @staticmethod
    def _describe(p: pk.Package) -> str:
        m = p.meta
        if p.kind == pk.KIND_MACHINE:
            src = "Tesis ölçümü" if m.get("source") == "real" else "Örnek yük"
            line = f"{m.get('days', 0)} gün · {fmt.date(m['first_day'])} – {fmt.date(m['last_day'])}"
            tag = f"Makine · {src}"
        elif p.kind == pk.KIND_GRID:
            line = f"{fmt.num(m.get('hours', 0), 0)} saat · {fmt.date(m['first_day'])} – {fmt.date(m['last_day'])}"
            tag = "Şebeke verisi"
        else:
            line = "Emisyon faktörleri"
            tag = "Katsayı · tüm yıllar bununla hesaplanır"
        return f"{p.name}\n{line}\n{tag}"

    def _selected_id(self) -> str | None:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        pkg_id = item.data(Qt.UserRole)
        if pkg_id:
            pk.set_enabled(pkg_id, item.checkState() == Qt.Checked)
            self.data_changed.emit("Veri paketi " + ("açıldı." if item.checkState() == Qt.Checked else "kapatıldı."))

    def _toggle_selected(self) -> None:
        item = self.list.currentItem()
        if item and item.data(Qt.UserRole) and item.flags() & Qt.ItemIsUserCheckable:
            item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)

    def _delete_selected(self) -> None:
        pkg_id = self._selected_id()
        if not pkg_id:
            return
        name = self.list.currentItem().text().split("\n")[0]
        box = QMessageBox(QMessageBox.Question, "Paketi sil",
                          f"“{name}” paketi kalıcı olarak silinsin mi?\nBu paketle kaydedilmiş geçmiş senaryolar "
                          "artık açılamaz.", parent=self)
        delete = box.addButton("Sil", QMessageBox.DestructiveRole)
        cancel = box.addButton("Vazgeç", QMessageBox.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        if box.clickedButton() is delete:
            pk.delete_package(pkg_id)
            self.data_changed.emit(f"“{name}” silindi.")

    def eventFilter(self, obj, event) -> bool:
        if obj is self.list and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Delete:
                self._delete_selected()
                return True
            if event.key() == Qt.Key_Space:
                self._toggle_selected()
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------ işlemler
    def show_action(self, i: int) -> None:
        for k, b in enumerate(self.action_buttons):
            b.setChecked(k == i)
        self.stack.setCurrentIndex(i)

    def _on_added(self, name: str) -> None:
        self.data_changed.emit(f"“{name}” eklendi.")

    def show_message(self, text: str) -> None:
        self.msg.setText("✓ " + text + "  Makine listeleri ve hesaplar güncellendi.")
        self.msg.show()

    def focus_default(self) -> None:
        self.list.setFocus()
