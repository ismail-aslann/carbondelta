import pytest

from engine.best_window import best_window
from engine.core import simulate


def _day(load_pairs=None, ci_pairs=None, load_default=0.0, ci_default=0.45):
    """24 saatlik liste kur; verilen {saat: değer} çiftlerini yerleştir."""
    load = [load_default] * 24
    ci = [ci_default] * 24
    for h, v in (load_pairs or {}).items():
        load[h] = v
    for h, v in (ci_pairs or {}).items():
        ci[h] = v
    return load, ci


@pytest.fixture
def hand():
    # El hesabı: kaynak saatler 2-3, hedef saatler 10-11.
    return _day({2: 10.0, 3: 20.0}, {2: 0.5, 3: 0.4, 10: 0.4, 11: 0.3})


def test_hand_reference(hand):
    load, ci = hand
    r = simulate(load, ci, s=2, L=2, t=10, p=1.0)
    assert r.status == "ok"
    assert r.baseline_kg == pytest.approx(13.0, abs=1e-12)
    assert r.scenario_kg == pytest.approx(10.0, abs=1e-12)
    assert r.delta_pct == pytest.approx(-23.076923076923077, abs=1e-9)
    assert r.shifted_kwh == pytest.approx(30.0)
    assert r.source_hours == [2, 3]
    assert r.target_hours == [10, 11]
    assert r.daily_kg == pytest.approx(13.0)
    assert r.daily_delta_pct == pytest.approx(-3 / 13 * 100)


def test_half_shift(hand):
    load, ci = hand
    full = simulate(load, ci, s=2, L=2, t=10, p=1.0)
    half = simulate(load, ci, s=2, L=2, t=10, p=0.5)
    assert half.status == "ok"
    assert half.shifted_kwh == pytest.approx(15.0)
    assert half.baseline_kg == pytest.approx(6.5)
    assert half.scenario_kg == pytest.approx(5.0)
    # Yüzde oran p'den bağımsız; günlük etki yarıya iner.
    assert half.delta_pct == pytest.approx(full.delta_pct)
    assert half.daily_delta_pct == pytest.approx(full.daily_delta_pct / 2)


def test_reverse_effect_positive_delta(hand):
    load, ci = hand
    load[10], load[11] = 5.0, 5.0
    r = simulate(load, ci, s=10, L=2, t=2, p=1.0)
    assert r.status == "ok"
    assert r.delta_pct > 0


def test_non_shiftable(hand):
    load, ci = hand
    r = simulate(load, ci, s=2, L=2, t=10, p=1.0, shiftable=False)
    assert r.status == "non_shiftable"
    assert r.delta_pct is None and r.daily_delta_pct is None


def test_non_shiftable_has_priority_over_range(hand):
    load, ci = hand
    r = simulate(load, ci, s=22, L=4, t=10, p=1.0, shiftable=False)
    assert r.status == "non_shiftable"


@pytest.mark.parametrize("s,L,t,p", [
    (21, 4, 2, 1.0),    # s+L > 24
    (2, 4, 21, 1.0),    # t+L > 24
    (2, 0, 10, 1.0),    # L < 1
    (2, 2, 10, 1.5),    # p > 1
    (2, 2, 10, -0.1),   # p < 0
    (-1, 2, 10, 1.0),   # negatif saat
])
def test_out_of_range(hand, s, L, t, p):
    load, ci = hand
    r = simulate(load, ci, s=s, L=L, t=t, p=p)
    assert r.status == "out_of_range"
    assert r.delta_pct is None


def test_full_day_window_is_in_range(hand):
    load, ci = hand
    r = simulate(load, ci, s=0, L=24, t=0, p=1.0)
    assert r.status == "same_window"


def test_restricted_conflict(hand):
    load, ci = hand
    r = simulate(load, ci, s=2, L=2, t=10, p=1.0, restricted={11, 15})
    assert r.status == "restricted_conflict"
    assert r.delta_pct is None
    assert r.target_hours == [10, 11]


def test_restricted_outside_target_is_ok(hand):
    load, ci = hand
    r = simulate(load, ci, s=2, L=2, t=10, p=1.0, restricted={2, 3, 12})
    assert r.status == "ok"


def test_same_window(hand):
    load, ci = hand
    r = simulate(load, ci, s=2, L=2, t=2, p=1.0)
    assert r.status == "same_window"
    assert r.delta_pct == 0.0
    assert r.daily_delta_pct == 0.0
    assert r.baseline_kg == r.scenario_kg == pytest.approx(13.0)


def test_no_load(hand):
    load, ci = hand
    r = simulate(load, ci, s=5, L=3, t=10, p=1.0)
    assert r.status == "no_load"
    assert r.baseline_kg == 0.0
    assert r.delta_pct is None and r.daily_delta_pct is None


def test_zero_ratio_is_no_load(hand):
    load, ci = hand
    r = simulate(load, ci, s=2, L=2, t=10, p=0.0)
    assert r.status == "no_load"


def test_parametric_constant_load():
    _, ci = _day(ci_pairs={0: 0.6, 1: 0.6, 18: 0.3, 19: 0.3})
    load = [50.0] * 24
    r = simulate(load, ci, s=0, L=2, t=18, p=1.0)
    assert r.status == "ok"
    assert r.delta_pct == pytest.approx(-50.0)


def test_inputs_must_be_24_long(hand):
    load, ci = hand
    with pytest.raises(ValueError):
        simulate(load[:23], ci, s=2, L=2, t=10, p=1.0)


# --- best_window -----------------------------------------------------------

def _brute_min_s(load, ci, s, L, p, restricted):
    best = None
    for t in range(0, 25 - L):
        r = simulate(load, ci, s, L, t, p, restricted)
        if r.status in ("ok", "same_window") and (best is None or r.scenario_kg < best):
            best = r.scenario_kg
    return best


def test_best_window_is_minimum(hand):
    load, ci = hand
    ci[20], ci[21] = 0.1, 0.2
    t, r = best_window(load, ci, s=2, L=2, p=1.0)
    assert t == 20
    assert r.scenario_kg == pytest.approx(_brute_min_s(load, ci, 2, 2, 1.0, set()))


def test_best_window_skips_restricted(hand):
    load, ci = hand
    ci[20], ci[21] = 0.1, 0.2
    t, r = best_window(load, ci, s=2, L=2, p=1.0, restricted={21})
    assert t not in (20, 21)
    assert not set(r.target_hours) & {21}
    assert r.scenario_kg == pytest.approx(_brute_min_s(load, ci, 2, 2, 1.0, {21}))


def test_best_window_tie_smallest_t():
    load = [10.0] * 24
    ci = [0.5] * 24
    ci[5] = ci[15] = 0.1
    t, _ = best_window(load, ci, s=10, L=1, p=1.0)
    assert t == 5


def test_best_window_none_cases(hand):
    load, ci = hand
    assert best_window(load, ci, s=2, L=2, p=1.0, shiftable=False) is None
    assert best_window(load, ci, s=23, L=2, p=1.0) is None
    assert best_window(load, ci, s=5, L=2, p=1.0) is None  # yük yok
    assert best_window(load, ci, s=2, L=2, p=1.0, restricted=set(range(24))) is None
