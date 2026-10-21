"""Delti (AI) ayarlarının uygulama içinden saklanması.

%APPDATA%\\CarbonDelta\\delti_ayarlar.json içinde sağlayıcı, model ve API anahtarı tutulur.
Windows'ta anahtar DPAPI ile şifrelenir: yalnızca aynı bilgisayardaki aynı kullanıcı çözebilir,
dosya başka bir bilgisayara kopyalansa da anahtar okunamaz. Güncelleme/kaldırma bu dosyayı silmez.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

FILE_NAME = "delti_ayarlar.json"


def settings_path() -> Path:
    # Testler kullanıcının kayıtlı anahtarından etkilenmesin diye klasör değiştirilebilir.
    override = os.environ.get("CARBONDELTA_SETTINGS_DIR")
    if override:
        return Path(override) / FILE_NAME
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "CarbonDelta" / FILE_NAME


# ----------------------------------------------------------------- şifreleme
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32
    for _fn in (_crypt32.CryptProtectData, _crypt32.CryptUnprotectData):
        _fn.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.POINTER(_Blob), ctypes.c_void_p,
                        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
        _fn.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _UI_FORBIDDEN = 0x1

    def _dpapi(data: bytes, protect: bool) -> bytes:
        buf = ctypes.create_string_buffer(data, len(data))
        blob_in = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        blob_out = _Blob()
        fn = _crypt32.CryptProtectData if protect else _crypt32.CryptUnprotectData
        if not fn(ctypes.byref(blob_in), None, None, None, None, _UI_FORBIDDEN, ctypes.byref(blob_out)):
            raise OSError(ctypes.get_last_error() or "DPAPI hatası")
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            _kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))

    def _encode(key: str) -> str:
        return "dpapi:" + base64.b64encode(_dpapi(key.encode("utf-8"), True)).decode("ascii")
else:
    def _dpapi(data: bytes, protect: bool) -> bytes:  # pragma: no cover - yalnızca Windows'ta şifreli
        raise OSError("DPAPI yok")

    def _encode(key: str) -> str:  # pragma: no cover
        return "plain:" + base64.b64encode(key.encode("utf-8")).decode("ascii")


def _decode(stored: str) -> str:
    """Çözülemeyen anahtar (başka kullanıcı/bilgisayar, bozuk dosya) boş sayılır."""
    try:
        kind, _, payload = stored.partition(":")
        raw = base64.b64decode(payload)
        if kind == "dpapi":
            return _dpapi(raw, False).decode("utf-8")
        if kind == "plain":
            return raw.decode("utf-8")
    except (OSError, ValueError, UnicodeDecodeError):
        pass
    return ""


# ------------------------------------------------------------------- API
def load() -> dict:
    """{'provider', 'model', 'api_key'}; dosya yoksa veya okunamazsa boş sözlük."""
    try:
        doc = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict):
        return {}
    return {"provider": str(doc.get("provider") or "").strip().lower(),
            "model": str(doc.get("model") or "").strip(),
            "api_key": _decode(str(doc.get("api_key") or "")).strip()}


def save(provider: str, api_key: str, model: str = "") -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"provider": provider.strip().lower(), "model": model.strip(),
           "api_key": _encode(api_key.strip())}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def clear() -> None:
    try:
        settings_path().unlink()
    except FileNotFoundError:
        pass
