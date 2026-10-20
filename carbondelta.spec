# -*- mode: python ; coding: utf-8 -*-
# PyInstaller tanımı — onedir (hızlı açılış). Çalıştır: build.bat
# .env EXE'ye GÖMÜLMEZ; uygulama .env'i EXE'nin yanındaki klasörden okur.
from pathlib import Path

ROOT = Path(SPECPATH)
ICON = ROOT / "desktop" / "icon.ico"

EXCLUDES = [
    # Gereksiz Qt modülleri
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "PySide6.QtQuick3D", "PySide6.Qt3DCore", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtBluetooth",
    "PySide6.QtPositioning", "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets", "PySide6.QtSvgWidgets", "PySide6.QtNetwork",
    # Başka GUI arka uçları ve geliştirme araçları
    "tkinter", "matplotlib.backends.backend_tkagg", "matplotlib.backends.backend_gtk3agg",
    "matplotlib.backends.backend_wxagg", "PyQt5", "PyQt6", "IPython", "pytest",
    "openpyxl", "PyInstaller",
]

a = Analysis(
    [str(ROOT / "desktop" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "shared" / "assets"), "shared/assets"),
        (str(ROOT / "shared" / "prompts"), "shared/prompts"),
    ],
    hiddenimports=["matplotlib.backends.backend_qtagg", "dotenv"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CarbonDelta",
    console=False,          # --windowed
    icon=str(ICON) if ICON.exists() else None,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="CarbonDelta",
    upx=False,
)
