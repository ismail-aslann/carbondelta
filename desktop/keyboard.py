"""Faresiz kullanım: Enter ile düğmeye basma, saat çiplerinde oklarla gezinme."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractButton, QCheckBox, QDateEdit, QPushButton, QRadioButton, QToolButton, QWidget,
)

ENTER_KEYS = (Qt.Key_Return, Qt.Key_Enter)
ARROWS = {Qt.Key_Left: (0, -1), Qt.Key_Right: (0, 1), Qt.Key_Up: (-1, 0), Qt.Key_Down: (1, 0)}


class KeyboardHelper(QObject):
    """Uygulama genelinde olay süzgeci.

    - Odaktaki düğme / onay kutusu / seçenek Enter ile tetiklenir (Qt varsayılanı yalnızca Boşluk).
    - Kayıtlı ızgaralarda (kısıtlı saat çipleri) ok tuşları komşu çipe geçer.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grids: dict[int, tuple[list, int]] = {}

    def register_grid(self, buttons: list, columns: int) -> None:
        for b in buttons:
            self._grids[id(b)] = (buttons, columns)

    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.KeyPress or not isinstance(obj, QAbstractButton):
            return False
        key = event.key()
        if event.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
            return False

        grid = self._grids.get(id(obj))
        if grid and key in ARROWS:
            buttons, cols = grid
            i = buttons.index(obj)
            dr, dc = ARROWS[key]
            r, c = divmod(i, cols)
            j = (r + dr) * cols + (c + dc)
            if 0 <= c + dc < cols and 0 <= j < len(buttons):
                buttons[j].setFocus(Qt.TabFocusReason)
            return True

        if key in ENTER_KEYS and obj.isEnabled():
            if isinstance(obj, QToolButton) and obj.menu() is not None:
                obj.showMenu()
            elif isinstance(obj, (QPushButton, QToolButton, QCheckBox, QRadioButton)):
                obj.animateClick()
            else:
                return False
            return True
        return False


class DateEdit(QDateEdit):
    """Tab tek basışta sonraki alana geçer; gün/ay/yıl arasında ← → ile gezilir."""

    def focusNextPrevChild(self, next_: bool) -> bool:
        return QWidget.focusNextPrevChild(self, next_)
