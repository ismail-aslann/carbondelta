"""Delti sohbet: niyet tanıma, hazır cevaplar, ön izleme ve sayı doğrulama."""
import pytest

from desktop import delti_chat as dc
from desktop.ai_client import allowed_numbers, validate_numbers
from desktop.ai_context import parse_nl_rule, validate_nl
from desktop.main_window import ScenarioInputs
from engine import data
from engine.core import simulate

CUR = ScenarioInputs("comp_b", "2025-07-15", 3, 3, 18, 1.0)


@pytest.mark.parametrize("text, kind", [
    ("Merhaba", dc.GREETING), ("selam!", dc.GREETING), ("teşekkürler", dc.THANKS),
    ("Bu program ne yapıyor?", dc.QUESTION), ("Yıllık etki nedir", dc.QUESTION), ("hava nasıl?", dc.QUESTION),
    ("Kompresörü 3'ten 18'e alırsak ne olur?", dc.SCENARIO), ("presi %50 ile 21'e kaydırsak nasıl olur", dc.SCENARIO),
    ("karıştırıcıyı 10'dan 19'a al", dc.SCENARIO),
])
def test_classify(text, kind):
    assert dc.classify(text) == kind


def test_faq_and_help():
    assert "emisyon" in dc.faq("bu uygulama ne işe yarıyor")
    assert "EPİAŞ" in dc.faq("verileri nereden alıyorsunuz")
    assert dc.faq("hava nasıl") is None
    assert dc.local_reply(dc.GREETING).startswith("Merhaba")


def test_preview_does_not_change_inputs_and_matches_engine():
    rule = parse_nl_rule("Kompresörü 3'ten 18'e alırsak ne olur?")
    rule.setdefault("p", 1.0)
    merged, err = validate_nl(rule, CUR)
    pv = dc.preview(merged, CUR)
    load, ci = data.scenario_series("comp_b", "2025-07-15")
    r = simulate(load, ci, 3, 3, 18, 1.0)
    assert pv.ok and "−15,62 %" in pv.text and "Senaryo sekmesi değişmedi" in pv.text
    assert "19:00–22:00" in pv.text            # daha temiz saat önerisi
    assert "206 gün" in pv.text                 # yıllık etki
    assert round(r.delta_pct, 2) == -15.62
    assert (CUR.s, CUR.t) == (3, 18)


def test_preview_reports_problems():
    pv = dc.preview({"asset_id": "ex_a", "s": 3, "L": 3, "t": 18, "p": 1.0, "date": "2025-07-15"}, CUR)
    assert not pv.ok and "kaydırılamaz" in pv.text.lower()


def test_chat_request_fallback_and_validator():
    req = dc.chat_request("Bu program ne yapıyor?", None, [("kullanıcı", "merhaba")])
    assert req.func_id == "chat" and "CarbonDelta" in req.fallback()
    allowed = allowed_numbers([req.payload, req.extra])
    assert validate_numbers("Varsayılan veri 8760 saatlik EPİAŞ 2025 üretimidir.", allowed)
    assert not validate_numbers("Bununla emisyonunuzu %73 azaltırsınız.", allowed)
