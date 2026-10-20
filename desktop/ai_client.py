"""AI açıklama katmanı: LLM yalnızca motorun ürettiği sayıları metne çevirir.

- .env: LLM_PROVIDER (gemini | claude), LLM_API_KEY, LLM_MODEL
- İstekler QThread içinde, 15 sn zaman aşımı; arayüz donmaz.
- Metindeki her sayı girdilerdeki sayılarla doğrulanır; uymazsa şablon metin gösterilir.
- Anahtar/internet yoksa veya hata olursa: çevrimdışı mesajı + şablon metin.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from desktop.resources import resource_path

TIMEOUT_S = 15
DEFAULT_MODELS = {"gemini": "gemini-flash-lite-latest", "claude": "claude-opus-5-5"}
# Sunucu tarafı ret yedeği ("fallbacks": "default") yalnızca bu modellerde geçerli.
CLAUDE_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
ALLOWED_HOURS = range(0, 25)


# --------------------------------------------------------------------- config
def env_path() -> Path:
    """.env EXE'ye gömülmez: paketliyken EXE'nin yanında, geliştirmede repo kökünde."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / ".env"
    return Path(__file__).resolve().parent.parent / ".env"


@dataclass(frozen=True)
class AIConfig:
    provider: str
    api_key: str
    model: str

    @property
    def enabled(self) -> bool:
        return bool(self.api_key) and self.provider in DEFAULT_MODELS


def load_config() -> AIConfig:
    try:
        from dotenv import dotenv_values
        file_vals = dotenv_values(env_path()) if env_path().exists() else {}
    except ImportError:
        file_vals = {}

    def get(key: str) -> str:
        return (os.environ.get(key) or file_vals.get(key) or "").strip()

    provider = (get("LLM_PROVIDER") or "gemini").lower()
    return AIConfig(provider=provider, api_key=get("LLM_API_KEY"),
                    model=get("LLM_MODEL") or DEFAULT_MODELS.get(provider, ""))


@lru_cache(maxsize=1)
def prompts() -> dict:
    with open(resource_path("shared/prompts/ai_functions.json"), encoding="utf-8") as f:
        doc = json.load(f)
    doc["by_id"] = {fn["id"]: fn for fn in doc["functions"]}
    return doc


_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def render(template: str, values: dict) -> str:
    """{anahtar} yer tutucularını doldurur; bilinmeyen anahtarlara dokunmaz."""
    return _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values
                            else m.group(0), template)


# ------------------------------------------------------------------ validator
# Önünde harf/rakam/ondalık ayıracı olmayan sayı: "tCO2"deki 2 veya "06:00–09"daki
# tire sayı sayılmaz. Türkçe virgül ve nokta ondalık, eksi (- veya −) desteklenir.
_NUMBER = re.compile(r"(?<![\w.,])[-−+]?\d+(?:[.,]\d+)?")
# 15.07.2025 / 15/07/2025 gibi tarihler: gün, ay, yıl ayrı tam sayılar olarak okunur.
_DATE = re.compile(r"(?<![\w.,])(\d{1,2})[./](\d{1,2})[./](\d{4})(?![\w])")


def extract_numbers(text: str) -> list[tuple[float, int]]:
    """Metindeki sayılar: (mutlak değer, ondalık basamak sayısı)."""
    out = []
    text = _DATE.sub(r"\1 \2 \3", text)
    for tok in _NUMBER.findall(text):
        tok = tok.lstrip("+-−").replace(",", ".")
        decimals = len(tok.split(".")[1]) if "." in tok else 0
        out.append((abs(float(tok)), decimals))
    return out


def collect_numbers(obj) -> list[float]:
    """JSON benzeri yapıdaki tüm sayılar (metinlerdeki tarih/saat rakamları dahil)."""
    nums: list[float] = []
    if isinstance(obj, bool) or obj is None:
        return nums
    if isinstance(obj, (int, float)):
        nums.append(float(obj))
    elif isinstance(obj, str):
        nums.extend(v for v, _ in extract_numbers(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            nums.extend(collect_numbers(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            nums.extend(collect_numbers(v))
    return nums


def allowed_numbers(payload) -> set[float]:
    """Girdilerdeki sayıların 0, 1 ve 2 ondalıklı yuvarlanmış halleri + saatler (0–24)."""
    allowed = {float(h) for h in ALLOWED_HOURS}
    for v in collect_numbers(payload):
        for d in (0, 1, 2):
            allowed.add(round(abs(v), d))
    return allowed


def validate_numbers(text: str, allowed: set[float]) -> bool:
    for value, decimals in extract_numbers(text):
        if decimals > 2:
            return False
        if round(value, decimals) not in allowed:
            return False
    return True


# ----------------------------------------------------------------------- HTTP
class AIError(Exception):
    pass


def _post_json(url: str, headers: dict, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"content-type": "application/json", **headers},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise AIError(f"HTTP {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise AIError(f"Bağlantı hatası: {e}") from e


def _call_gemini(cfg: AIConfig, system: str, user: str, json_mode: bool) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.model}:generateContent"
    gen = {"temperature": 0, "maxOutputTokens": 1024}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": gen,
    }
    data = _post_json(url, {"x-goog-api-key": cfg.api_key}, body)
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError) as e:
        raise AIError(f"Beklenmeyen Gemini yanıtı: {str(data)[:200]}") from e
    return "".join(p.get("text", "") for p in parts).strip()


def _call_claude(cfg: AIConfig, system: str, user: str, json_mode: bool) -> str:
    # Güncel Claude modelleri temperature parametresini kabul etmez (400);
    # kısa ve belirlenimci metin için effort "low" kullanılır.
    body = {
        "model": cfg.model,
        "max_tokens": 2048,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"effort": "low"},
    }
    headers = {"x-api-key": cfg.api_key, "anthropic-version": "2023-06-01"}
    if cfg.model in CLAUDE_FALLBACK_MODELS:
        body["fallbacks"] = "default"
        headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
    data = _post_json("https://api.anthropic.com/v1/messages", headers, body)
    if data.get("stop_reason") == "refusal":
        raise AIError("Model isteği reddetti.")
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    if not text.strip():
        raise AIError("Boş yanıt.")
    return text.strip()


def call_llm(cfg: AIConfig, system: str, user: str, json_mode: bool = False) -> str:
    if not cfg.enabled:
        raise AIError("AI yapılandırılmamış.")
    if cfg.provider == "claude":
        return _call_claude(cfg, system, user, json_mode)
    return _call_gemini(cfg, system, user, json_mode)


def parse_json_reply(text: str) -> dict:
    """```json ... ``` sarmalı olsa da ilk JSON nesnesini çıkarır."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise AIError("Yanıtta JSON yok.")
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise AIError("Geçersiz JSON.") from e
    if not isinstance(obj, dict):
        raise AIError("JSON nesne değil.")
    return obj


# ------------------------------------------------------------------ requests
@dataclass
class AIRequest:
    func_id: str
    payload: dict              # LLM'e giden ham sayılar
    display: dict              # şablon için biçimlenmiş değerler
    extra: dict | None = None  # user_template'e giden ek alanlar (ör. sentence)
    json_mode: bool = False

    def system_prompt(self) -> str:
        p = prompts()
        return f"{p['common_system']}\n\n{p['by_id'][self.func_id]['system']}"

    def user_prompt(self) -> str:
        values = {"payload_json": json.dumps(self.payload, ensure_ascii=False)}
        values.update(self.extra or {})
        return render(prompts()["by_id"][self.func_id]["user_template"], values)

    def fallback(self) -> str:
        return render(prompts()["by_id"][self.func_id]["fallback_template"], self.display)

    def cache_key(self) -> str:
        return json.dumps([self.func_id, self.payload, self.extra], sort_keys=True,
                          ensure_ascii=False)


@dataclass
class AIReply:
    func_id: str
    text: str
    source: str   # "ai" | "fallback_offline" | "fallback_invalid"
    error: str = ""


# "Ben Delti, …", "Merhaba!", "Delti olarak …" gibi baştaki tanıtım/selam cümleleri.
_INTRO = re.compile(r"^\s*(merhaba|selam|iyi günler|ben,?\s+delti|delti olarak|ben\s+carbondelta)\b"
                    r"[^.!?]*[.!?]+\s*", re.IGNORECASE)


def strip_intro(text: str) -> str:
    """Model talimata rağmen kendini tanıtırsa baştaki tanıtım cümlelerini siler."""
    prev = None
    while prev != text:
        prev = text
        text = _INTRO.sub("", text, count=1)
    return text.strip()


def run_request(cfg: AIConfig, req: AIRequest) -> AIReply:
    """Engelleyici çağrı (worker thread içinde çalışır)."""
    if not cfg.enabled:
        return AIReply(req.func_id, req.fallback(), "fallback_offline", "AI yapılandırılmamış.")
    try:
        text = call_llm(cfg, req.system_prompt(), req.user_prompt(), req.json_mode)
    except AIError as e:
        return AIReply(req.func_id, req.fallback(), "fallback_offline", str(e))
    if req.json_mode:
        return AIReply(req.func_id, text, "ai")
    text = strip_intro(text)
    if not text:
        return AIReply(req.func_id, req.fallback(), "fallback_invalid", "Boş yanıt (yalnızca giriş cümlesi).")
    if not validate_numbers(text, allowed_numbers([req.payload, req.extra or {}])):
        return AIReply(req.func_id, req.fallback(), "fallback_invalid", text)
    return AIReply(req.func_id, text, "ai")


class _Worker(QThread):
    done = Signal(object, object)  # (tag, AIReply)

    def __init__(self, cfg: AIConfig, req: AIRequest, tag, parent=None):
        super().__init__(parent)
        self.cfg, self.req, self.tag = cfg, req, tag

    def run(self) -> None:
        self.done.emit(self.tag, run_request(self.cfg, self.req))


class AIService(QObject):
    """İstekleri arka planda çalıştırır; sonuçları önbelleğe alır."""

    reply = Signal(object, object)  # (tag, AIReply)

    def __init__(self, cfg: AIConfig | None = None, parent=None):
        super().__init__(parent)
        self.cfg = cfg or load_config()
        self._cache: dict[str, AIReply] = {}
        self._workers: set[_Worker] = set()

    @property
    def online(self) -> bool:
        return self.cfg.enabled

    def submit(self, req: AIRequest, tag) -> None:
        key = req.cache_key()
        if key in self._cache:
            self.reply.emit(tag, self._cache[key])
            return
        if not self.cfg.enabled:
            self.reply.emit(tag, run_request(self.cfg, req))
            return
        w = _Worker(self.cfg, req, tag, self)
        w.done.connect(lambda t, r, k=key, w=w: self._finished(t, r, k, w))
        self._workers.add(w)
        w.start()

    def _finished(self, tag, rep: AIReply, key: str, w: _Worker) -> None:
        self._workers.discard(w)
        w.deleteLater()
        if rep.source == "ai":
            self._cache[key] = rep
        self.reply.emit(tag, rep)

    def shutdown(self) -> None:
        for w in list(self._workers):
            w.wait(TIMEOUT_S * 1000 + 1000)
