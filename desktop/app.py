"""Uygulama girişi: asset'leri bir kez yükler ve ana pencereyi açar."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from engine import data


def create_app(argv: list[str]) -> QApplication:
    app = QApplication(argv)
    app.setApplicationName("CarbonDelta")
    app.setStyle("Fusion")
    # Grafik ve kart açık renkli; Windows koyu temasında da okunur kalması için açık palet.
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:
        pass
    app.setPalette(app.style().standardPalette())
    data.preload()
    return app


def main() -> int:
    app = create_app(sys.argv)

    from desktop.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()
