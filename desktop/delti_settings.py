"""Delti ayarları penceresi: API anahtarı uygulama içinden girilir, denenir ve saklanır."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout)

from desktop import ai_settings, delti, theme
from desktop.ai_client import DEFAULT_MODELS, AIConfig, check_connection

PROVIDERS = [("gemini", "Google Gemini"), ("claude", "Anthropic Claude")]
KEY_PAGES = {"gemini": "https://aistudio.google.com/apikey", "claude": "https://console.anthropic.com/"}
SOURCE_TEXT = {
    "uygulama": "Anahtar bu pencereden kaydedildi (bu bilgisayarda şifreli saklanıyor).",
    ".env": "Anahtar program klasöründeki .env dosyasından okunuyor. Buradan kaydederseniz bu ayar öncelikli olur.",
    "ortam": "Anahtar ortam değişkeninden (LLM_API_KEY) okunuyor; buradaki ayardan önce gelir.",
}


class _Tester(QThread):
    done = Signal(bool, str)

    def __init__(self, cfg: AIConfig, parent=None):
        super().__init__(parent)
        self.cfg = cfg

    def run(self) -> None:
        self.done.emit(*check_connection(self.cfg))


class DeltiSettingsDialog(QDialog):
    """Kaydet/Kaldır sonrası accept() döner; çağıran yapılandırmayı yeniden yükler."""

    def __init__(self, cfg: AIConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delti ayarları")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._tester: _Tester | None = None
        dpr = self.devicePixelRatioF() or 1.0
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(12)
        self.avatar = QLabel()
        self.avatar.setFixedSize(48, 48)
        self.avatar.setPixmap(delti.pixmap("ready" if cfg.enabled else "sleep", 48, dpr))
        top.addWidget(self.avatar)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        t = QLabel("Delti ayarları")
        t.setStyleSheet("font-size: 14pt; font-weight: 700;")
        titles.addWidget(t)
        titles.addWidget(theme.muted("Delti'nin çalışması için bir yapay zekâ API anahtarı gerekir. "
                                     "Hesaplar anahtarsız da çalışır.", wrap=True))
        top.addLayout(titles, 1)
        root.addLayout(top)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        self.provider = QComboBox()
        for key, label in PROVIDERS:
            self.provider.addItem(label, key)
        idx = self.provider.findData(cfg.provider)
        self.provider.setCurrentIndex(max(idx, 0))
        self.provider.currentIndexChanged.connect(self._provider_changed)
        form.addRow("Sağlayıcı", self.provider)

        key_row = QHBoxLayout()
        self.key = QLineEdit(cfg.api_key)
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("API anahtarını buraya yapıştırın")
        self.key.textChanged.connect(lambda: self._set_status("", None))
        key_row.addWidget(self.key, 1)
        self.show_key = QCheckBox("Göster")
        self.show_key.toggled.connect(lambda on: self.key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        key_row.addWidget(self.show_key)
        form.addRow("API anahtarı", key_row)

        self.model = QLineEdit("" if cfg.model == DEFAULT_MODELS.get(cfg.provider) else cfg.model)
        form.addRow("Model", self.model)
        root.addLayout(form)

        self.link = QLabel()
        self.link.setWordWrap(True)
        self.link.setOpenExternalLinks(True)
        self.link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        root.addWidget(self.link)
        self._provider_changed()

        self.source = theme.muted(SOURCE_TEXT.get(cfg.source, ""), wrap=True)
        self.source.setVisible(bool(cfg.source))
        root.addWidget(self.source)

        root.addWidget(self.status)

        btns = QHBoxLayout()
        self.remove_button = QPushButton("Anahtarı kaldır")
        self.remove_button.setToolTip("Bu pencereden kaydedilen anahtarı siler")
        self.remove_button.setEnabled(bool(ai_settings.load().get("api_key")))
        self.remove_button.clicked.connect(self._remove)
        btns.addWidget(self.remove_button)
        btns.addStretch(1)
        self.test_button = QPushButton("Bağlantıyı dene")
        self.test_button.clicked.connect(self._test)
        btns.addWidget(self.test_button)
        cancel = QPushButton("Vazgeç")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        self.save_button = QPushButton("Kaydet")
        self.save_button.setObjectName("primary")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)
        btns.addWidget(self.save_button)
        root.addLayout(btns)

        root.addWidget(theme.muted("Delti'ye yalnızca hesap sonuçlarındaki sayılar gider; tesis verisi gönderilmez. "
                                   "Anahtar yalnızca bu bilgisayardaki bu kullanıcı hesabıyla çözülebilir.", wrap=True))
        self.key.setFocus()

    # ---------------------------------------------------------------- yardımcı
    def _provider_key(self) -> str:
        return self.provider.currentData()

    def _provider_changed(self) -> None:
        p = self._provider_key()
        self.model.setPlaceholderText(f"Boş bırakın: {DEFAULT_MODELS[p]}")
        self.link.setText(f"Anahtarınız yoksa: <a href='{KEY_PAGES[p]}' style='color:{theme.PRIMARY};'>"
                          f"{KEY_PAGES[p]}</a> adresinden ücretsiz/ücretli anahtar alabilirsiniz.")
        self._set_status("", None)

    def config(self) -> AIConfig:
        p = self._provider_key()
        return AIConfig(provider=p, api_key=self.key.text().strip(),
                        model=self.model.text().strip() or DEFAULT_MODELS[p], source="uygulama")

    def _set_status(self, text: str, ok: bool | None) -> None:
        self.status.setVisible(bool(text))
        self.status.setText(text)
        if ok is None:
            fg, bg = theme.MUTED, theme.BG
        else:
            fg, bg = (theme.GOOD, theme.PRIMARY_SOFT) if ok else (theme.BAD, theme.BAD_SOFT)
        self.status.setStyleSheet(f"color: {fg}; background: {bg}; border-radius: 8px; padding: 8px 10px;")

    def _busy(self, on: bool) -> None:
        for w in (self.test_button, self.save_button, self.provider, self.key, self.model):
            w.setEnabled(not on)

    # ------------------------------------------------------------------ işler
    def _test(self) -> None:
        cfg = self.config()
        if not cfg.api_key:
            self._set_status("Önce API anahtarını girin.", False)
            self.key.setFocus()
            return
        self._set_status("Deneniyor… (en fazla 15 saniye)", None)
        self.avatar.setPixmap(delti.pixmap("think", 48, self.devicePixelRatioF() or 1.0))
        self._busy(True)
        self._tester = _Tester(cfg, self)
        self._tester.done.connect(self._tested)
        self._tester.start()

    def _tested(self, ok: bool, msg: str) -> None:
        self._busy(False)
        self.avatar.setPixmap(delti.pixmap("ready" if ok else "sleep", 48, self.devicePixelRatioF() or 1.0))
        self._set_status(msg, ok)

    def _save(self) -> None:
        cfg = self.config()
        if not cfg.api_key:
            self._set_status("Kaydetmek için API anahtarını girin (anahtarı silmek için 'Anahtarı kaldır').", False)
            self.key.setFocus()
            return
        try:
            ai_settings.save(cfg.provider, cfg.api_key, self.model.text().strip())
        except OSError as e:
            self._set_status(f"Ayar kaydedilemedi: {e}", False)
            return
        self.accept()

    def _remove(self) -> None:
        ai_settings.clear()
        self.accept()

    def done(self, r: int) -> None:
        if self._tester is not None and self._tester.isRunning():
            self._tester.wait(16000)
        super().done(r)
