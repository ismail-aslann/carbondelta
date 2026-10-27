"""Kaydırma oranı denetimi: kaydırıcı + sayı kutusu + %25 çentikler (bütün sekmelerde aynı)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QSlider, QSpinBox, QWidget


class RatioControl(QWidget):
    """QSlider ile aynı arayüz: value(), setValue(int), valueChanged(int) — değer 0–100 (%)."""

    valueChanged = Signal(int)

    def __init__(self, parent=None, slider_width: int = 110):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(100)
        self.slider.setSingleStep(5)
        self.slider.setPageStep(25)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(25)
        self.slider.setMinimumWidth(slider_width)
        self.spin = QSpinBox()
        self.spin.setRange(0, 100)
        self.spin.setValue(100)
        self.spin.setPrefix("%")
        self.spin.setSingleStep(5)
        self.spin.setFixedWidth(68)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.setToolTip("Standart penceredeki yükün ne kadarının taşınacağı. Yüzde değişim orandan bağımsızdır; "
                        "oran taşınan kWh'ı ve kg değerlerini değiştirir.")
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

    def value(self) -> int:
        return self.slider.value()

    def setValue(self, v: int) -> None:
        self.slider.setValue(int(v))

    def _from_slider(self, v: int) -> None:
        if self.spin.value() != v:
            self.spin.blockSignals(True)
            self.spin.setValue(v)
            self.spin.blockSignals(False)
        self.valueChanged.emit(v)

    def _from_spin(self, v: int) -> None:
        if self.slider.value() != v:
            self.slider.setValue(v)   # kaydırıcı sinyali valueChanged'i yayar
