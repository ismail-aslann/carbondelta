"""Beklenmeyen hataları yakalar: hata.log dosyasına yazar ve kullanıcıya Türkçe bir pencere gösterir.

Pencereli EXE'de konsol olmadığı için yakalanmayan hatalar aksi halde sessizce kaybolur.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from engine.appinfo import user_dir

_last_shown = 0.0


def log_path() -> Path:
    return user_dir() / "hata.log"


def write_log(exc_type, exc, tb) -> Path:
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.now().isoformat(timespec='seconds')} =====\n")
            f.write("".join(traceback.format_exception(exc_type, exc, tb)))
    except OSError:
        pass
    return path


def _show(exc, path: Path) -> None:
    global _last_shown
    if time.time() - _last_shown < 5:  # art arda aynı hatada pencere yağmuru olmasın
        return
    _last_shown = time.time()
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance() is None:
            return
        box = QMessageBox(QMessageBox.Warning, "Beklenmeyen bir hata oluştu",
                          "İşlem tamamlanamadı. Hesaplar ve kayıtlı veriler etkilenmedi; çalışmaya devam "
                          "edebilirsiniz.\n\n"
                          f"Ayrıntılar şu dosyaya yazıldı:\n{path}\n\n"
                          "Sorun tekrarlarsa bu dosyayı İletişim sekmesindeki geliştiricilere gönderin.")
        box.setDetailedText(f"{type(exc).__name__}: {exc}")
        box.exec()
    except Exception:  # noqa: BLE001 — hata penceresi de hata verirse sessiz kal
        pass


def _hook(exc_type, exc, tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return
    path = write_log(exc_type, exc, tb)
    if sys.stderr is not None:
        traceback.print_exception(exc_type, exc, tb)
    _show(exc, path)


def install() -> None:
    sys.excepthook = _hook
    threading.excepthook = lambda args: write_log(args.exc_type, args.exc_value, args.exc_traceback)
