"""Arayüz teması: renkler ve Qt stil sayfası (tek kaynak)."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from desktop.resources import resource_path

BG = "#f3f5f8"
SURFACE = "#ffffff"
BORDER = "#e1e6ec"
FIELD_BORDER = "#cfd6de"
TEXT = "#1d2733"
MUTED = "#6b7785"
PRIMARY = "#16785c"
PRIMARY_DARK = "#0f5b46"
PRIMARY_SOFT = "#e7f3ef"
GOOD = "#1f9254"
BAD = "#d03c3c"
BAD_SOFT = "#fdecec"
WARN = "#9a6412"
WARN_SOFT = "#fff6e5"
CI_COLOR = "#1f4e79"

_QSS = """
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-family: "Segoe UI"; font-size: 9.5pt; }}
QToolTip {{ color: {TEXT}; background: {SURFACE}; border: 1px solid {BORDER}; padding: 4px; }}

/* Başlık bandı */
QFrame#header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PRIMARY_DARK}, stop:1 #16765b);
    border: none;
}}
QFrame#header QLabel {{ color: white; background: transparent; }}
QLabel#appTitle {{ font-size: 15pt; font-weight: 700; }}
QLabel#appSubtitle {{ color: #cfe9df; font-size: 9pt; }}
QLineEdit#nlEdit {{
    background: white; border: none; border-radius: 16px; padding: 7px 14px; font-size: 10pt;
}}
QPushButton#nlButton {{
    background: rgba(255, 255, 255, 0.16); color: white; border: 1px solid rgba(255, 255, 255, 0.45);
    border-radius: 16px;
    padding: 6px 16px; font-weight: 600;
}}
QPushButton#nlButton:hover {{ background: rgba(255, 255, 255, 0.28); }}

/* Sekmeler */
QTabWidget::pane {{ border: none; background: {BG}; }}
QTabBar {{ background: {BG}; }}
QTabBar::tab {{
    background: transparent; color: {MUTED}; padding: 9px 16px; margin-right: 2px;
    border: none; border-bottom: 3px solid transparent; font-size: 10pt;
}}
QTabBar::tab:selected {{ color: {PRIMARY}; border-bottom: 3px solid {PRIMARY}; font-weight: 600; }}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}

/* Kartlar */
QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#card QLabel {{ background: transparent; }}
QLabel#cardTitle {{ font-size: 10.5pt; font-weight: 600; color: {TEXT}; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#statLabel {{ color: {MUTED}; font-size: 9pt; }}
QLabel#statValue {{ font-size: 15pt; font-weight: 700; }}
QLabel#bigDelta {{ font-size: 28pt; font-weight: 700; }}
QFrame#noteCard {{ background: {WARN_SOFT}; border: 1px solid #f0d9a8; border-radius: 10px; }}
QFrame#noteCard QLabel {{ background: transparent; color: #5c3d07; }}
QFrame#alert {{ background: {BAD_SOFT}; border: 1px solid #f3c3c3; border-radius: 8px; }}
QFrame#alert QLabel {{ color: {BAD}; background: transparent; font-weight: 600; }}

/* Düğmeler */
QPushButton {{
    background: {SURFACE}; border: 1px solid {FIELD_BORDER}; border-radius: 6px;
    padding: 6px 12px;
}}
QPushButton:hover {{ background: #f2f6f4; border-color: #b9c3cc; }}
QPushButton:pressed {{ background: #e6ece9; }}
QPushButton:disabled {{ color: #a8b1ba; background: #f6f7f9; border-color: {BORDER}; }}
QPushButton#primary {{ background: {PRIMARY}; color: white; border: 1px solid {PRIMARY}; font-weight: 600; }}
QPushButton#primary:hover {{ background: {PRIMARY_DARK}; border-color: {PRIMARY_DARK}; }}
QPushButton#primary:disabled {{ background: #9cc5b8; border-color: #9cc5b8; }}
QPushButton#danger {{ color: {BAD}; }}
QPushButton#danger:hover {{ background: {BAD_SOFT}; border-color: #f0b4b4; }}
QPushButton#danger:disabled {{ color: #b7bfc7; background: #f6f7f9; border-color: {BORDER}; }}
QToolButton {{
    background: {SURFACE}; border: 1px solid {FIELD_BORDER}; border-radius: 6px; padding: 6px 10px;
}}
QToolButton:hover {{ background: #f2f6f4; }}
QToolButton::menu-indicator {{ image: none; }}

/* Saat çipleri */
QPushButton#chip {{
    padding: 0; border-radius: 5px; background: #f6f8fa; border: 1px solid #d6dde4; font-size: 9pt;
}}
QPushButton#chip:hover {{ border-color: {BAD}; }}
QPushButton#chip:checked {{ background: {BAD}; color: white; border-color: {BAD}; }}
QPushButton#chip:disabled {{ color: #b7bfc7; background: #f8f9fa; border-color: #e8ecf0; }}

/* Giriş alanları */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
    background: white; border: 1px solid {FIELD_BORDER}; border-radius: 6px; padding: 4px 8px;
    min-height: 20px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {{
    border: 1px solid {PRIMARY};
}}
QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QDateEdit:disabled {{
    color: #a8b1ba; background: #f6f7f9;
}}
QSpinBox, QDoubleSpinBox {{ padding: 4px 0 4px 8px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: padding; subcontrol-position: top right; width: 18px; border: none;
    border-left: 1px solid #e6eaee; border-top-right-radius: 5px; background: #f7f9fb;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: padding; subcontrol-position: bottom right; width: 18px; border: none;
    border-left: 1px solid #e6eaee; border-bottom-right-radius: 5px; background: #f7f9fb;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{ background: {PRIMARY_SOFT}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({UP}); width: 9px; height: 9px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({DOWN}); width: 9px; height: 9px; }}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled {{ image: url({UP_OFF}); }}
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {{ image: url({DOWN_OFF}); }}
QComboBox, QDateEdit {{ padding-right: 24px; }}
QComboBox::drop-down, QDateEdit::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right; width: 24px; border: none;
}}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url({DOWN}); width: 10px; height: 10px; }}
QComboBox::down-arrow:disabled, QDateEdit::down-arrow:disabled {{ image: url({DOWN_OFF}); }}
QComboBox QAbstractItemView {{ background: white; selection-background-color: {PRIMARY_SOFT};
    selection-color: {TEXT}; border: 1px solid {BORDER}; }}
QSlider::groove:horizontal {{ height: 6px; background: #dde3e9; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {PRIMARY}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: white; border: 2px solid {PRIMARY}; width: 14px; height: 14px; margin: -6px 0;
    border-radius: 9px;
}}
QSlider::sub-page:horizontal:disabled {{ background: #b9c6c1; }}
QSlider::handle:horizontal:disabled {{ border-color: #b9c6c1; }}

/* Tablolar */
QTableWidget {{
    background: white; border: none; gridline-color: #eef1f4;
    selection-background-color: {PRIMARY_SOFT}; selection-color: {TEXT};
    alternate-background-color: #fafbfc;
}}
QHeaderView::section {{
    background: #f6f8fa; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 6px 8px; font-weight: 600;
}}
QTextBrowser {{ background: transparent; border: none; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QSplitter::handle {{ background: transparent; }}

/* Klavye odağı: faresiz kullanımda seçili öğe belirgin */
QPushButton:focus, QToolButton:focus {{ border: 2px solid {PRIMARY}; padding: 5px 11px; }}
QPushButton#primary:focus {{ border: 2px solid #0b3d33; }}
QPushButton#chip:focus {{ border: 2px solid {PRIMARY}; padding: 0; }}
QPushButton#chip:checked:focus {{ border: 2px solid #7a1f1f; }}
QPushButton#nlButton:focus {{ border: 2px solid white; }}
QCheckBox:focus, QRadioButton:focus {{ background: {PRIMARY_SOFT}; border-radius: 4px; }}
QSlider:focus {{ background: {PRIMARY_SOFT}; border-radius: 4px; }}
QTableWidget:focus, QListWidget:focus {{ border: 2px solid {PRIMARY_SOFT}; }}
QTextBrowser:focus {{ border: 1px solid {PRIMARY_SOFT}; }}

/* Kaydırma çubukları: ince, yuvarlak */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #cdd4db; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:horizontal {{ background: #cdd4db; border-radius: 3px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: #aab4be; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
"""


def _url(name: str) -> str:
    return resource_path(f"desktop/ui/{name}").as_posix()


def qss() -> str:
    """Stil sayfası; ok simgelerinin yolu çalışma anında (PyInstaller dahil) çözülür."""
    return _QSS.format(
        BG=BG, SURFACE=SURFACE, BORDER=BORDER, FIELD_BORDER=FIELD_BORDER, TEXT=TEXT,
        MUTED=MUTED, PRIMARY=PRIMARY, PRIMARY_DARK=PRIMARY_DARK, PRIMARY_SOFT=PRIMARY_SOFT,
        GOOD=GOOD, BAD=BAD, BAD_SOFT=BAD_SOFT, WARN=WARN, WARN_SOFT=WARN_SOFT,
        UP=_url("chevron_up.png"), DOWN=_url("chevron_down.png"),
        UP_OFF=_url("chevron_up_disabled.png"), DOWN_OFF=_url("chevron_down_disabled.png"),
    )


def card(title: str | None = None, *, margins: tuple[int, int, int, int] = (14, 12, 14, 12),
         spacing: int = 8, name: str = "card") -> tuple[QFrame, QVBoxLayout]:
    """Başlıklı beyaz kart; içerik için dikey yerleşim döndürür."""
    frame = QFrame()
    frame.setObjectName(name)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    if title:
        t = QLabel(title)
        t.setObjectName("cardTitle")
        lay.addWidget(t)
    return frame, lay


def muted(text: str = "", wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("muted")
    lbl.setWordWrap(wrap)
    return lbl


def set_role(widget: QWidget, name: str) -> QWidget:
    widget.setObjectName(name)
    return widget
