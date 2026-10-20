"""Uygulama girişi: asset'leri bir kez yükler ve ana pencereyi açar."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow

from desktop import theme
from desktop.resources import resource_path
from engine import data


def create_app(argv: list[str]) -> QApplication:
    app = QApplication(argv)
    app.setApplicationName("CarbonDelta")
    app.setStyle("Fusion")
    # Grafik ve kartlar açık renkli; Windows koyu temasında da okunur kalması için açık palet.
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:
        pass
    app.setPalette(app.style().standardPalette())
    app.setStyleSheet(theme.qss())
    icon = resource_path("desktop/icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    data.preload()
    return app


def fit_to_screen(window: QMainWindow) -> None:
    """Pencereyi ekranın kullanılabilir alanına sığdırır; küçük ekranda tam ekran açar."""
    screen = QGuiApplication.primaryScreen().availableGeometry()
    if screen.height() < 720 or screen.width() < 1100:
        window.showMaximized()
        return
    # Çerçeve ve başlık çubuğu için pay bırak.
    w = min(1440, screen.width() - 40)
    h = min(900, screen.height() - 50)
    window.resize(w, h)
    window.move(screen.x() + (screen.width() - w) // 2, screen.y() + max(0, (screen.height() - h - 30) // 2))
    window.show()


def main() -> int:
    app = create_app(sys.argv)

    from desktop.main_window import MainWindow

    window = MainWindow()
    fit_to_screen(window)
    return app.exec()
