"""Her AI işlevi için LLM'e giden ham sayılar (payload) ve şablon değerleri (display).

Buradaki tüm sayılar motordan (engine) gelir; arayüz formül içermez.
"""
from __future__ import annotations

import re

from desktop import fmt
from desktop.ai_client import AIRequest, prompts
from engine import data
from engine.best_window import scan_windows
from engine.insights import compare, season_profile, window_mix

UNITS = {"tCO2": "kgCO2", "tCO2esd": "kgCO2-eşd"}
IN_RANGE_STATUSES = ("ok", "same_window", "no_load", "restricted_conflict")


SOURCE_NAMES = {
    "Dogal_Gaz": "doğal gaz", "Barajli": "barajlı hidro", "Linyit": "linyit",
    "Akarsu": "akarsu hidro", "Ithal_Komur": "ithal kömür", "Ruzgar": "rüzgâr",
    "Gunes": "güneş", "Fuel_Oil": "fuel oil", "Jeotermal": "jeotermal",
    "Asfaltit_Komur": "asfaltit", "Tas_Komur": "taş kömürü", "Biyokutle": "biyokütle",
    "Atik_Isi": "atık ısı",
}


def _named(mix: dict) -> dict:
    """Kaynak kodlarını Türkçe adlara çevirir (yalnızca metin alanları)."""
    out = dict(mix)
    out["dominant"] = SOURCE_NAMES.get(mix["dominant"], mix["dominant"])
    out["top_sources"] = [{**t, "source": SOURCE_NAMES.get(t["source"], t["source"])}
                          for t in mix["top_sources"]]
    return out


def _ci(v: float) -> str:
    return fmt.num(v, 3)


def _base(c) -> tuple[dict, dict]:
    i, r, m = c.inputs, c.result, c.machine
    payload = {
        "machine": m["name"],
        "date": fmt.date(i.date),
        "emission_type": i.ci_kind,
        "status": r.status,
        "source_window": fmt.window(i.s, i.L),
        "target_window": fmt.window(i.t, i.L),
        "shift_ratio_pct": i.p * 100,
    }
    if i.parametric:
        payload["parametric_kwh_per_hour"] = i.param_kwh
    if r.status in ("ok", "same_window", "no_load"):
        # Alan adları LLM'in sayıları karıştırmaması için ne olduklarını açıkça söyler.
        payload.update({
            "kaydirilan_enerji_kwh": r.shifted_kwh,
            "standart_pencere_emisyonu_kg": r.baseline_kg,
            "secilen_pencere_emisyonu_kg": r.scenario_kg,
            "pencere_emisyon_degisimi_yuzde": r.delta_pct,
            "makinenin_gunluk_toplam_emisyonu_kg_KAYDIRMA_ONCESI": r.daily_kg,
            "gunluk_toplam_emisyona_etkisi_yuzde": r.daily_delta_pct,
        })
    if r.status == "ok":
        # LLM'in yönü ters anlatmaması için sonucun yönü açıkça metin olarak verilir.
        payload["direction"] = ("Seçilen (hedef) pencerede emisyon standart pencereden DAHA DÜŞÜK."
                                if r.delta_pct < 0 else
                                "Seçilen (hedef) pencerede emisyon standart pencereden DAHA YÜKSEK."
                                if r.delta_pct > 0 else "Emisyon değişmiyor.")
    display = {
        "machine": m["name"],
        "date": fmt.date(i.date),
        "source_window": fmt.window(i.s, i.L),
        "target_window": fmt.window(i.t, i.L),
        "ratio_pct": fmt.num(i.p * 100, 0),
        "unit": UNITS[i.ci_kind],
        "baseline_kg": fmt.num(r.baseline_kg),
        "scenario_kg": fmt.num(r.scenario_kg),
        "shifted_kwh": fmt.num(r.shifted_kwh),
        "delta_pct": fmt.pct(r.delta_pct),
        "daily_pct": fmt.pct(r.daily_delta_pct),
        "daily_kg": fmt.num(r.daily_kg),
    }
    return payload, display


def _with_mix(c, payload: dict, display: dict) -> None:
    i, r = c.inputs, c.result
    src = _named(window_mix(i.date, list(range(i.s, i.s + i.L)), i.ci_kind))
    tgt = _named(window_mix(i.date, list(range(i.t, i.t + i.L)), i.ci_kind))
    payload["source_mix"] = src
    payload["target_mix"] = tgt
    display.update({
        "src_ci": _ci(src["ci_avg"]), "tgt_ci": _ci(tgt["ci_avg"]),
        "src_ren": fmt.num(src["renewable_pct_avg"], 1), "tgt_ren": fmt.num(tgt["renewable_pct_avg"], 1),
        "src_dom": src["dominant"], "tgt_dom": tgt["dominant"],
    })


def _req(func_id: str, payload: dict, display: dict, **kw) -> AIRequest:
    return AIRequest(func_id, payload, display, **kw)


# ----------------------------------------------------------------- per status
def auto_requests(c) -> list[AIRequest]:
    """Her hesapta otomatik: duruma göre uyarı veya özet (+ ters etki uyarısı)."""
    r = c.result
    if r.status == "ok":
        reqs = [scenario_summary(c)]
        if r.delta_pct > 0:
            reqs.append(reverse_effect_warn(c))
        return reqs
    if r.status == "non_shiftable":
        return [non_shiftable_warn(c)]
    if r.status == "restricted_conflict":
        return [restricted_warn(c)]
    if r.status == "no_load":
        return [no_load_warn(c)]
    return []  # out_of_range, same_window: yerel durum mesajı yeterli


def scenario_summary(c) -> AIRequest:
    payload, display = _base(c)
    _with_mix(c, payload, display)  # "neden" açıklaması için pencere karışımları
    return _req("scenario_summary", payload, display)


def reverse_effect_warn(c) -> AIRequest:
    payload, display = _base(c)
    _with_mix(c, payload, display)
    return _req("reverse_effect_warn", payload, display)


def non_shiftable_warn(c) -> AIRequest:
    m = c.machine
    payload = {"machine": m["name"], "shiftable": False,
               "reason": "sürekli veya süreç gereği saati değiştirilemeyen yük"}
    display = {"machine": m["name"]}
    return _req("non_shiftable_warn", payload, display)


def restricted_warn(c) -> AIRequest:
    payload, display = _base(c)
    conflict = [h for h in c.result.target_hours if h in set(c.inputs.restricted)]
    payload["restricted_hours"] = sorted(c.inputs.restricted)
    payload["conflict_hours"] = conflict
    display["conflict_hours"] = ", ".join(fmt.hour(h) for h in conflict)
    return _req("restricted_warn", payload, display)


def no_load_warn(c) -> AIRequest:
    return _req("no_load_warn", *_base(c))


# -------------------------------------------------------------- on demand
def hour_reason(c) -> AIRequest | None:
    if c.result.status not in IN_RANGE_STATUSES:
        return None
    payload, display = _base(c)
    _with_mix(c, payload, display)
    return _req("hour_reason", payload, display)


def best_window_explain(c) -> AIRequest | None:
    i, r = c.inputs, c.result
    if r.status not in ("ok", "same_window"):
        return None
    cands = scan_windows(c.load, c.ci, i.s, i.L, i.p, set(i.restricted), c.machine["shiftable"])
    payload, display = _base(c)
    _with_mix(c, payload, display)
    payload["candidate_count"] = len(cands)
    display["candidates"] = str(len(cands))
    return _req("best_window_explain", payload, display)


def daily_impact(c) -> AIRequest | None:
    if c.result.status != "ok":
        return None
    return _req("daily_impact", *_base(c))


def report_sentence(c) -> AIRequest | None:
    if c.result.status != "ok":
        return None
    return _req("report_sentence", *_base(c))


def season_note(c) -> AIRequest | None:
    i = c.inputs
    if c.result.status not in IN_RANGE_STATUSES or i.s == i.t:
        return None
    year = int(i.date[:4])
    prof = season_profile(list(range(i.s, i.s + i.L)), list(range(i.t, i.t + i.L)), i.ci_kind, year)
    payload = {
        "year": year,
        "source_window": fmt.window(i.s, i.L),
        "target_window": fmt.window(i.t, i.L),
        "emission_type": i.ci_kind,
        **prof,
    }
    display = {
        "year": str(year),
        "source_window": fmt.window(i.s, i.L),
        "target_window": fmt.window(i.t, i.L),
        "better_months": str(prof["better_month_count"]),
        "worse_months": str(prof["worse_month_count"]),
        "best_month": prof["best_month"],
        "best_month_pct": fmt.pct(prof["best_month_diff_pct"]),
        "worst_month": prof["worst_month"],
        "worst_month_pct": fmt.pct(prof["worst_month_diff_pct"]),
    }
    return _req("season_note", payload, display)


def _history_label(h: dict) -> str:
    name = data.machine(h["asset_id"])["name"] if data.has_machine(h["asset_id"]) else h["asset_id"]
    return f"{name} {fmt.date(h['date'])} {fmt.window(h['s'], h['L'])} → {fmt.window(h['t'], h['L'])}"


def scenario_compare(saved: dict, c) -> AIRequest:
    a_delta, b_delta = saved["delta_pct"], c.result.delta_pct
    cmp = compare(a_delta, b_delta)
    payload = {
        "a": {"label": _history_label(saved),
              "machine": (data.machine(saved["asset_id"])["name"] if data.has_machine(saved["asset_id"])
                          else saved["asset_id"]),
              "date": fmt.date(saved["date"]),
              "status": saved["status"], "delta_pct": a_delta,
              "daily_delta_pct": saved["daily_delta_pct"]},
        "b": {"label": _history_label({"asset_id": c.inputs.asset_id, "date": c.inputs.date,
                                       "s": c.inputs.s, "L": c.inputs.L, "t": c.inputs.t}),
              "machine": c.machine["name"], "date": fmt.date(c.inputs.date), "status": c.result.status,
              "delta_pct": b_delta, "daily_delta_pct": c.result.daily_delta_pct},
        **cmp,
    }
    if cmp["better"] is None:
        verdict = "İki senaryodan en az birinde yüzde hesaplanmadığı için kıyas yapılamıyor."
    elif cmp["better"] == "equal":
        verdict = "İki senaryo aynı emisyon değişimini veriyor."
    else:
        who = "Kayıtlı" if cmp["better"] == "a" else "Mevcut"
        verdict = f"{who} senaryo {fmt.num(cmp['diff_points'])} yüzde puan daha düşük emisyon değişimi veriyor."
    display = {"a_label": payload["a"]["label"], "b_label": payload["b"]["label"],
               "a_delta": fmt.pct(a_delta), "b_delta": fmt.pct(b_delta), "verdict": verdict}
    return _req("scenario_compare", payload, display)


def history_summary(rows: list[dict]) -> AIRequest | None:
    rows = rows[:10]
    if not rows:
        return None
    items = [{"label": _history_label(h), "status": h["status"], "delta_pct": h["delta_pct"],
              "daily_delta_pct": h["daily_delta_pct"]} for h in rows]
    with_pct = [h for h in rows if h["delta_pct"] is not None]
    payload = {"count": len(rows), "ok_count": len(with_pct), "records": items}
    display = {"count": str(len(rows)), "ok_count": str(len(with_pct)),
               "best_label": "—", "best_delta": "—", "worst_label": "—", "worst_delta": "—"}
    if with_pct:
        best = min(with_pct, key=lambda h: h["delta_pct"])
        worst = max(with_pct, key=lambda h: h["delta_pct"])
        payload["best"] = {"label": _history_label(best), "delta_pct": best["delta_pct"]}
        payload["worst"] = {"label": _history_label(worst), "delta_pct": worst["delta_pct"]}
        display.update({"best_label": _history_label(best), "best_delta": fmt.pct(best["delta_pct"]),
                        "worst_label": _history_label(worst), "worst_delta": fmt.pct(worst["delta_pct"])})
    return _req("history_summary", payload, display)


def term_explain(term: str) -> AIRequest:
    definition = prompts()["glossary"].get(term, "Bu terim için kayıtlı tanım yok.")
    return _req("term_explain", {}, {"term": term, "definition": definition},
                extra={"term": term})


def data_source_explain() -> AIRequest:
    payload = {"sources": [f"{data.BASE_GRID_LABEL} saatlik üretim (+ eklenen yıllar)",
                           f"{data.factors_label()} emisyon faktörleri",
                           "Zenodo imalat tesisi makine yükleri"],
               "load_is_sample": True}
    return _req("data_source_explain", payload, {})


# ------------------------------------------------------------- natural language
def nl_input(sentence: str, current) -> AIRequest:
    import json
    machines = [{"id": m["id"], "name": m["name"], "type": m["type"], "shiftable": m["shiftable"]}
                for m in data.machines()]
    cur = {"asset_id": current.asset_id, "s": current.s, "L": current.L, "t": current.t,
           "p": current.p}
    return AIRequest("nl_input", cur, {}, json_mode=True, extra={
        "sentence": sentence,
        "machines_json": json.dumps(machines, ensure_ascii=False),
        "current_json": json.dumps(cur, ensure_ascii=False),
    })


MACHINE_KEYWORDS = [
    ("php_c", ("ısıt", "isit", "fırın", "firin")),
    ("ex_a", ("havaland", "aspirat", "fan", "egzoz")),
    ("comp_b", ("kompres", "basınçlı hava", "basincli hava")),
    ("mix_c", ("mikser", "karıştır", "karistir")),
    ("mh_a", ("taşıma", "tasima", "otomasyon", "robot", "konvey")),
    ("p_i", ("pres",)),
    ("u_e", ("yardımcı", "yardimci", "utilit", "hizmet")),
]


_TR = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def _fold_with_index(text: str) -> tuple[str, list[int]]:
    """Türkçe harfleri sadeleştirip harf/rakam dışını atar; her karakterin özgün konumunu tutar."""
    out, idx = [], []
    for i, ch in enumerate(text.lower().replace("i̇", "i")):
        c = ch.translate(_TR)
        if c.isascii() and c.isalnum():
            out.append(c)
            idx.append(i)
    return "".join(out), idx


def parse_nl_rule(sentence: str) -> dict:
    """AI yokken basit kural tabanlı çözümleyici (Türkçe kalıplar)."""
    text = sentence.lower()
    out: dict = {}
    ids = {m["id"] for m in data.machines()}
    for token in re.findall(r"[a-z]+_[a-z0-9_]+", text):
        if token in ids:
            out["asset_id"] = token
            break
    if "asset_id" not in out:
        # Kayıtlı makine adları (eklenen makineler dahil); en uzun ad önce. Eşleşen ad metinden
        # çıkarılır ki "Hat 2" gibi adlardaki sayılar saat sanılmasın.
        folded, index = _fold_with_index(text)
        for m in sorted(data.machines(), key=lambda m: -len(_fold_with_index(m["name"])[0])):
            name = _fold_with_index(m["name"].lower())[0]
            pos = folded.find(name) if len(name) >= 3 else -1
            if pos >= 0:
                out["asset_id"] = m["id"]
                a, b = index[pos], index[pos + len(name) - 1] + 1
                text = text[:a] + " " * (b - a) + text[b:]
                break
    if "asset_id" not in out:
        for asset_id, keys in MACHINE_KEYWORDS:
            if any(k in text for k in keys):
                out["asset_id"] = asset_id
                break

    m = re.search(r"(?:%|yüzde|yuzde)\s*(\d{1,3})", text)
    if m:
        out["p"] = int(m.group(1)) / 100
        text = text[:m.start()] + " " + text[m.end():]
    m = re.search(r"(\d{1,2})\s*saat", text)
    if m:
        out["L"] = int(m.group(1))
        text = text[:m.start()] + " " + text[m.end():]

    hours = []
    for hm in re.finditer(r"(\d{1,2})(?:[:.]00)?\s*(?:['’]?\s*(den|dan|ten|tan|de|da|te|ta|e|a|ye|ya))?\b", text):
        hours.append((int(hm.group(1)), hm.group(2) or ""))
    sources = [h for h, suf in hours if suf in ("den", "dan", "ten", "tan")]
    targets = [h for h, suf in hours if suf in ("e", "a", "ye", "ya")]
    plain = [h for h, suf in hours if suf not in ("den", "dan", "ten", "tan", "e", "a", "ye", "ya")]
    if sources:
        out["s"] = sources[0]
    if targets:
        out["t"] = targets[0]
    for h in plain:
        if "s" not in out:
            out["s"] = h
        elif "t" not in out:
            out["t"] = h
    return out


def validate_nl(obj: dict, current) -> tuple[dict | None, str]:
    """LLM/kural çıktısını motor kurallarıyla doğrular; mevcut girdilerle tamamlar."""
    ids = {m["id"] for m in data.machines()}
    merged = {"asset_id": current.asset_id, "s": current.s, "L": current.L,
              "t": current.t, "p": current.p}
    for key in merged:
        if key in obj and obj[key] is not None:
            merged[key] = obj[key]
    try:
        merged["s"], merged["L"], merged["t"] = int(merged["s"]), int(merged["L"]), int(merged["t"])
        merged["p"] = float(merged["p"])
    except (TypeError, ValueError):
        return None, "Sayısal alanlar okunamadı."
    if merged["asset_id"] not in ids:
        return None, f"Bilinmeyen makine: {merged['asset_id']}"
    if not (0 <= merged["s"] <= 23 and 0 <= merged["t"] <= 23 and 1 <= merged["L"] <= 12):
        return None, "Saatler 0–23, uzunluk 1–12 aralığında olmalı."
    if not 0.0 <= merged["p"] <= 1.0:
        return None, "Kaydırma oranı %0–100 olmalı."
    if merged["s"] + merged["L"] > 24 or merged["t"] + merged["L"] > 24:
        return None, "Pencere aynı gün içinde kalmalı (başlangıç + uzunluk ≤ 24)."
    if not any(k in obj for k in ("asset_id", "s", "L", "t", "p")):
        return None, "Cümleden senaryo bilgisi çıkarılamadı."
    return merged, ""
