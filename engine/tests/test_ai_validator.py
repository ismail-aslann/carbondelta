import pytest

from desktop.ai_client import (allowed_numbers, extract_numbers, prompts, render,
                               validate_numbers)

PAYLOAD = {
    "machine": "comp_b",
    "date": "2025-07-15",
    "emission_type": "tCO2",
    "source_window_hours": [3, 6],
    "target_window_hours": [18, 21],
    "shift_ratio_pct": 100.0,
    "baseline_kg": 42.613384003600004,
    "scenario_kg": 35.9576180138,
    "delta_pct": -15.618956685621868,
    "daily_delta_pct": -2.154159573642247,
}
ALLOWED = allowed_numbers(PAYLOAD)


def test_turkish_decimal_is_parsed():
    assert extract_numbers("−15,62") == [(15.62, 2)]
    assert extract_numbers("-15.62 %") == [(15.62, 2)]
    assert extract_numbers("%100") == [(100.0, 0)]


def test_units_and_ranges_are_not_numbers():
    # tCO2'deki 2 ve saat aralığındaki tire sayı sayılmaz.
    assert extract_numbers("kgCO2 ve tCO2-eşd") == []
    assert [v for v, _ in extract_numbers("03:00–06:00")] == [3.0, 0.0, 6.0, 0.0]


def test_allowed_text_passes():
    text = ("comp_b yükünün %100'ü 03:00–06:00 yerine 18:00–21:00 aralığına alınırsa "
            "emisyon 42,61 kgCO2'den 35,96 kgCO2'ye iner (−15,62 %). "
            "Günlük etki −2,15 %, 2025-07-15 için yaklaşık −15,6 %.")
    assert validate_numbers(text, ALLOWED)


def test_rounded_to_zero_decimals_passes():
    assert validate_numbers("Emisyon yaklaşık %16 azalır.", ALLOWED)


def test_invented_number_is_rejected():
    assert not validate_numbers("Bu kaydırma emisyonu −18,40 % azaltır.", ALLOWED)
    assert not validate_numbers("Yılda 12.500 TL tasarruf sağlar.", ALLOWED)
    assert not validate_numbers("Saat 27'de çalıştırın.", ALLOWED)


def test_turkish_date_is_not_a_decimal():
    assert [v for v, _ in extract_numbers("15.07.2025 tarihinde")] == [15.0, 7.0, 2025.0]
    assert validate_numbers("15.07.2025 tarihinde −15,62 % değişim.", ALLOWED)
    assert not validate_numbers("26.09.2031 tarihinde", ALLOWED)


def test_too_many_decimals_rejected():
    assert not validate_numbers("Delta −15,619 %.", ALLOWED)


@pytest.mark.parametrize("text,expected", [
    ("Ben Delti, tesisteki karbon azaltım çalışmalarınızda size rehberlik etmek için buradayım. "
     "Kaydırma emisyonu düşürür.", "Kaydırma emisyonu düşürür."),
    ("Merhaba! Ben Delti. Emisyon −15,62 % değişir.", "Emisyon −15,62 % değişir."),
    ("Delti olarak açıklayayım: emisyon düşer. Günlük etki küçük.", "Günlük etki küçük."),
    ("Emisyon −15,62 % değişir. Ben Delti olarak önermem.", "Emisyon −15,62 % değişir. Ben Delti olarak önermem."),
])
def test_strip_intro(text, expected):
    from desktop.ai_client import strip_intro
    assert strip_intro(text) == expected


def test_render_keeps_unknown_braces():
    assert render('{"a": 1} {x}', {"x": "ok"}) == '{"a": 1} ok'


def test_prompts_have_all_functions():
    ids = {f["id"] for f in prompts()["functions"]}
    assert len(ids) == 16  # talimattaki 15 işlev + yıllık etki yorumu
    for f in prompts()["functions"]:
        assert {"id", "title", "system", "user_template", "fallback_template"} <= f.keys()


@pytest.mark.parametrize("sentence,expected", [
    ("Kompresörü 3'ten 18'e al", {"asset_id": "comp_b", "s": 3, "t": 18}),
    ("Presi %50 oranla 2 saat 21'e kaydır", {"asset_id": "p_i", "p": 0.5, "L": 2, "t": 21}),
    ("mix_c 5:00'ten 19:00'a", {"asset_id": "mix_c", "s": 5, "t": 19}),
])
def test_rule_parser(sentence, expected):
    from desktop.ai_context import parse_nl_rule
    got = parse_nl_rule(sentence)
    for k, v in expected.items():
        assert got[k] == v, (k, got)
