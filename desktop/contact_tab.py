"""İletişim sekmesi: geliştiriciler ve danışman."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from desktop import theme
from desktop.version import VERSION

PEOPLE = [
    {"role": "Geliştirici", "name": "İsmail Ali ASLAN", "phone": "05527987865",
     "email": "ismailaliaslan11@gmail.com"},
    {"role": "Geliştirici", "name": "Emin Burak ÖZTÜRK", "phone": "05550392314",
     "email": "eminburak1410@gmail.com"},
    {"role": "Danışman", "name": "Öğr. Gör. Ali ERFİDAN", "phone": "05414597933",
     "email": "ali.erfidan@balikesir.edu.tr", "org": "Balıkesir Üniversitesi"},
]


def fmt_phone(p: str) -> str:
    """05527987865 → 0552 798 78 65"""
    d = "".join(ch for ch in p if ch.isdigit())
    return f"{d[:4]} {d[4:7]} {d[7:9]} {d[9:11]}" if len(d) == 11 else p


def _initials(name: str) -> str:
    parts = [w for w in name.replace("Öğr.", "").replace("Gör.", "").split() if w]
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else parts[0][:2].upper()


class ContactTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 18, 0, 0)
        root.setSpacing(14)
        root.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        head = QLabel("İletişim")
        head.setStyleSheet("font-size: 16pt; font-weight: 700;")
        head.setAlignment(Qt.AlignCenter)
        root.addWidget(head)
        sub = theme.muted("CarbonDelta hakkında soru, öneri ve geri bildirimleriniz için bize ulaşın.")
        sub.setAlignment(Qt.AlignCenter)
        root.addWidget(sub)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.focus_first = None
        for i, p in enumerate(PEOPLE):
            grid.addWidget(self._card(p), 0, i)
        root.addLayout(grid)

        self.toast = QLabel("")
        self.toast.setAlignment(Qt.AlignCenter)
        self.toast.setStyleSheet(f"color: {theme.GOOD}; font-weight: 600;")
        root.addWidget(self.toast)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(2200)
        self._timer.timeout.connect(lambda: self.toast.setText(""))

        about, al = theme.card(margins=(18, 12, 18, 12))
        about.setFixedWidth(960)
        a = QLabel(f"<b>CarbonDelta</b> · Sürüm {VERSION} · Emisyon Potansiyeli Karar Destek. Endüstriyel yükleri "
                   "daha temiz saatlere kaydırmanın şebeke emisyonuna etkisini hesaplar; karar her zaman "
                   "kullanıcıdadır.")
        a.setWordWrap(True)
        al.addWidget(a)
        root.addWidget(about, 0, Qt.AlignHCenter)

    def _card(self, p: dict) -> QWidget:
        frame, lay = theme.card(margins=(18, 16, 18, 16), spacing=6)
        frame.setFixedWidth(310)
        top = QHBoxLayout()
        top.setSpacing(12)
        avatar = QLabel(_initials(p["name"]))
        avatar.setFixedSize(46, 46)
        avatar.setAlignment(Qt.AlignCenter)
        color = theme.PRIMARY if p["role"] == "Geliştirici" else "#1f4e79"
        avatar.setStyleSheet(f"background: {color}; color: white; border-radius: 23px; font-weight: 700; font-size: 12pt;")
        top.addWidget(avatar)
        names = QVBoxLayout()
        names.setSpacing(0)
        # Python'un upper()'ı Türkçe i'yi I yapar; büyük harf etiketi açıkça yazılır.
        role = QLabel({"Geliştirici": "GELİŞTİRİCİ", "Danışman": "DANIŞMAN"}.get(p["role"], p["role"]))
        role.setStyleSheet(f"color: {color}; font-size: 8pt; font-weight: 700; letter-spacing: 1px;")
        names.addWidget(role)
        n = QLabel(p["name"])
        n.setStyleSheet("font-size: 11.5pt; font-weight: 700;")
        names.addWidget(n)
        if p.get("org"):
            names.addWidget(theme.muted(p["org"]))
        top.addLayout(names, 1)
        lay.addLayout(top)

        lay.addSpacing(4)
        phone = QLabel(f"☎  <a href='tel:{p['phone']}' style='color:{theme.TEXT}; text-decoration:none;'>"
                       f"{fmt_phone(p['phone'])}</a>")
        phone.setTextInteractionFlags(Qt.TextBrowserInteraction)
        phone.setOpenExternalLinks(False)
        lay.addWidget(phone)
        mail = QLabel(f"✉  <a href='mailto:{p['email']}' style='color:{theme.PRIMARY};'>{p['email']}</a>")
        mail.setTextInteractionFlags(Qt.TextBrowserInteraction)
        mail.setOpenExternalLinks(True)
        lay.addWidget(mail)

        btns = QHBoxLayout()
        send = QPushButton("E-posta gönder")
        send.setObjectName("primary")
        send.clicked.connect(lambda _c=False, e=p["email"]: QDesktopServices.openUrl(QUrl(f"mailto:{e}")))
        btns.addWidget(send)
        copy = QPushButton("Kopyala")
        copy.setToolTip("E-posta ve telefonu panoya kopyalar")
        copy.clicked.connect(lambda _c=False, p=p: self._copy(p))
        btns.addWidget(copy)
        lay.addLayout(btns)
        if self.focus_first is None:
            self.focus_first = send
        return frame

    def _copy(self, p: dict) -> None:
        QApplication.clipboard().setText(f"{p['name']} · {fmt_phone(p['phone'])} · {p['email']}")
        self.toast.setText(f"✓ {p['name']} iletişim bilgileri panoya kopyalandı")
        self._timer.start()

    def focus_default(self) -> None:
        if self.focus_first:
            self.focus_first.setFocus(Qt.TabFocusReason)
