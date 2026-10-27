// ignore_for_file: non_constant_identifier_names
// Her AI işlevi için LLM'e giden ham sayılar (payload) ve şablon değerleri
// (display). Buradaki tüm sayılar motordan gelir (desktop/ai_context.py).

import 'dart:convert';

import '../data/history_db.dart';
import '../engine/annual.dart' as annual;
import '../engine/best_window.dart';
import '../engine/core.dart' as core;
import '../engine/data.dart';
import '../engine/insights.dart';
import '../engine/sources.dart';
import '../state/app_state.dart';
import '../ui/fmt.dart' as fmt;
import 'ai_client.dart';

const Map<String, String> units = {'tCO2': 'kgCO2', 'tCO2esd': 'kgCO2-eşd'};
const List<String> inRangeStatuses = ['ok', 'same_window', 'no_load', 'restricted_conflict'];

DataStore get _data => DataStore.instance;

/// Kaynak kodlarını Türkçe adlara çevirir (yalnızca metin alanları).
Map<String, Object?> _named(Map<String, Object?> mix) {
  final out = Map<String, Object?>.from(mix);
  final dom = mix['dominant'] as String;
  out['dominant'] = sourceNamesLower[dom] ?? dom;
  out['top_sources'] = [
    for (final t in mix['top_sources'] as List)
      {
        ...(t as Map<String, Object?>),
        'source': sourceNamesLower[t['source']] ?? t['source'],
      },
  ];
  return out;
}

String _ci(double v) => fmt.num(v, 3);

List<int> _range(int start, int len) => [for (var k = start; k < start + len; k++) k];

(Map<String, Object?>, Map<String, Object?>) _base(Computation c) {
  final m = c.machine;
  final r = c.result;
  final i = c.inputs;
  final payload = <String, Object?>{
    'machine': m.name,
    'date': fmt.date(i.date),
    'emission_type': i.ciKind,
    'status': r.status,
    'source_window': fmt.window(i.s, i.L),
    'target_window': fmt.window(i.t, i.L),
    'shift_ratio_pct': i.p * 100,
  };
  if (i.parametric) payload['parametric_kwh_per_hour'] = i.paramKwh;
  if (r.status == core.ok || r.status == core.sameWindow || r.status == core.noLoad) {
    payload.addAll({
      'kaydirilan_enerji_kwh': r.shiftedKwh,
      'standart_pencere_emisyonu_kg': r.baselineKg,
      'secilen_pencere_emisyonu_kg': r.scenarioKg,
      'pencere_emisyon_degisimi_yuzde': r.deltaPct,
      'makinenin_gunluk_toplam_emisyonu_kg_KAYDIRMA_ONCESI': r.dailyKg,
      'gunluk_toplam_emisyona_etkisi_yuzde': r.dailyDeltaPct,
    });
  }
  if (r.status == core.ok) {
    payload['direction'] = r.deltaPct! < 0
        ? 'Seçilen (hedef) pencerede emisyon standart pencereden DAHA DÜŞÜK.'
        : r.deltaPct! > 0
            ? 'Seçilen (hedef) pencerede emisyon standart pencereden DAHA YÜKSEK.'
            : 'Emisyon değişmiyor.';
  }
  final display = <String, Object?>{
    'machine': m.name,
    'date': fmt.date(i.date),
    'source_window': fmt.window(i.s, i.L),
    'target_window': fmt.window(i.t, i.L),
    'ratio_pct': fmt.num(i.p * 100, 0),
    'unit': units[i.ciKind],
    'baseline_kg': fmt.num(r.baselineKg),
    'scenario_kg': fmt.num(r.scenarioKg),
    'shifted_kwh': fmt.num(r.shiftedKwh),
    'delta_pct': fmt.pct(r.deltaPct),
    'daily_pct': fmt.pct(r.dailyDeltaPct),
    'daily_kg': fmt.num(r.dailyKg),
  };
  return (payload, display);
}

void _withMix(Computation c, Map<String, Object?> payload, Map<String, Object?> display) {
  final i = c.inputs;
  final src = _named(windowMix(_data, i.date, _range(i.s, i.L), i.ciKind));
  final tgt = _named(windowMix(_data, i.date, _range(i.t, i.L), i.ciKind));
  payload['source_mix'] = src;
  payload['target_mix'] = tgt;
  display.addAll({
    'src_ci': _ci(src['ci_avg'] as double),
    'tgt_ci': _ci(tgt['ci_avg'] as double),
    'src_ren': fmt.num(src['renewable_pct_avg'] as double, 1),
    'tgt_ren': fmt.num(tgt['renewable_pct_avg'] as double, 1),
    'src_dom': src['dominant'],
    'tgt_dom': tgt['dominant'],
  });
}

AIRequest _req(String funcId, Map<String, Object?> payload, Map<String, Object?> display,
        {Map<String, Object?>? extra, bool jsonMode = false}) =>
    AIRequest(funcId, payload, display, extra: extra, jsonMode: jsonMode);

/// Her hesapta otomatik: duruma göre uyarı veya özet (+ ters etki uyarısı).
List<AIRequest> autoRequests(Computation c) {
  final r = c.result;
  if (r.status == core.ok) {
    final reqs = [scenarioSummary(c)];
    if (r.deltaPct! > 0) reqs.add(reverseEffectWarn(c));
    return reqs;
  }
  if (r.status == core.nonShiftable) return [nonShiftableWarn(c)];
  if (r.status == core.restrictedConflict) return [restrictedWarn(c)];
  if (r.status == core.noLoad) return [noLoadWarn(c)];
  return [];
}

AIRequest scenarioSummary(Computation c) {
  final (payload, display) = _base(c);
  _withMix(c, payload, display);
  return _req('scenario_summary', payload, display);
}

AIRequest reverseEffectWarn(Computation c) {
  final (payload, display) = _base(c);
  _withMix(c, payload, display);
  return _req('reverse_effect_warn', payload, display);
}

AIRequest nonShiftableWarn(Computation c) {
  final m = c.machine;
  return _req(
    'non_shiftable_warn',
    {'machine': m.name, 'shiftable': false, 'reason': 'sürekli veya süreç gereği saati değiştirilemeyen yük'},
    {'machine': m.name},
  );
}

AIRequest restrictedWarn(Computation c) {
  final (payload, display) = _base(c);
  final restricted = c.inputs.restricted.toSet();
  final conflict = [for (final h in c.result.targetHours) if (restricted.contains(h)) h];
  payload['restricted_hours'] = c.inputs.restricted.toList()..sort();
  payload['conflict_hours'] = conflict;
  display['conflict_hours'] = conflict.map(fmt.hour).join(', ');
  return _req('restricted_warn', payload, display);
}

AIRequest noLoadWarn(Computation c) {
  final (payload, display) = _base(c);
  return _req('no_load_warn', payload, display);
}

AIRequest? hourReason(Computation c) {
  if (!inRangeStatuses.contains(c.result.status)) return null;
  final (payload, display) = _base(c);
  _withMix(c, payload, display);
  return _req('hour_reason', payload, display);
}

AIRequest? bestWindowExplain(Computation c) {
  final r = c.result;
  final i = c.inputs;
  if (!(r.status == core.ok || r.status == core.sameWindow)) return null;
  final cands = scanWindows(c.load, c.ci, i.s, i.L, i.p,
      restricted: i.restricted.toSet(), shiftable: c.machine.shiftable);
  final (payload, display) = _base(c);
  _withMix(c, payload, display);
  payload['candidate_count'] = cands.length;
  display['candidates'] = '${cands.length}';
  return _req('best_window_explain', payload, display);
}

AIRequest? dailyImpact(Computation c) {
  if (c.result.status != core.ok) return null;
  final (payload, display) = _base(c);
  return _req('daily_impact', payload, display);
}

AIRequest? reportSentence(Computation c) {
  if (c.result.status != core.ok) return null;
  final (payload, display) = _base(c);
  return _req('report_sentence', payload, display);
}

AIRequest? seasonNote(Computation c) {
  final i = c.inputs;
  if (!inRangeStatuses.contains(c.result.status) || i.s == i.t) return null;
  final year = int.parse(i.date.substring(0, 4));
  final prof = seasonProfile(_data, _range(i.s, i.L), _range(i.t, i.L), i.ciKind, year);
  final payload = <String, Object?>{
    'year': year,
    'source_window': fmt.window(i.s, i.L),
    'target_window': fmt.window(i.t, i.L),
    'emission_type': i.ciKind,
    ...prof,
  };
  final display = <String, Object?>{
    'year': '$year',
    'source_window': fmt.window(i.s, i.L),
    'target_window': fmt.window(i.t, i.L),
    'better_months': '${prof['better_month_count']}',
    'worse_months': '${prof['worse_month_count']}',
    'best_month': prof['best_month'],
    'best_month_pct': fmt.pct(prof['best_month_diff_pct'] as double),
    'worst_month': prof['worst_month'],
    'worst_month_pct': fmt.pct(prof['worst_month_diff_pct'] as double),
  };
  return _req('season_note', payload, display);
}

String _historyLabel(String assetId, String date, int s, int L, int t) {
  final name = _data.hasMachine(assetId) ? _data.machine(assetId).name : assetId;
  return '$name ${fmt.date(date)} ${fmt.window(s, L)} → ${fmt.window(t, L)}';
}

String historyLabel(HistoryRow h) => _historyLabel(h.assetId, h.date, h.s, h.L, h.t);

AIRequest scenarioCompare(HistoryRow saved, Computation c) {
  final aDelta = saved.deltaPct;
  final bDelta = c.result.deltaPct;
  final cmp = compare(aDelta, bDelta);
  final i = c.inputs;
  final payload = <String, Object?>{
    'a': {
      'label': historyLabel(saved),
      'machine': _data.hasMachine(saved.assetId) ? _data.machine(saved.assetId).name : saved.assetId,
      'date': fmt.date(saved.date),
      'status': saved.status,
      'delta_pct': aDelta,
      'daily_delta_pct': saved.dailyDeltaPct,
    },
    'b': {
      'label': _historyLabel(i.assetId, i.date, i.s, i.L, i.t),
      'machine': c.machine.name,
      'date': fmt.date(i.date),
      'status': c.result.status,
      'delta_pct': bDelta,
      'daily_delta_pct': c.result.dailyDeltaPct,
    },
    ...cmp,
  };
  String verdict;
  if (cmp['better'] == null) {
    verdict = 'İki senaryodan en az birinde yüzde hesaplanmadığı için kıyas yapılamıyor.';
  } else if (cmp['better'] == 'equal') {
    verdict = 'İki senaryo aynı emisyon değişimini veriyor.';
  } else {
    final who = cmp['better'] == 'a' ? 'Kayıtlı' : 'Mevcut';
    verdict = '$who senaryo ${fmt.num(cmp['diff_points'] as double)} yüzde puan daha düşük emisyon değişimi veriyor.';
  }
  final display = <String, Object?>{
    'a_label': (payload['a'] as Map)['label'],
    'b_label': (payload['b'] as Map)['label'],
    'a_delta': fmt.pct(aDelta),
    'b_delta': fmt.pct(bDelta),
    'verdict': verdict,
  };
  return _req('scenario_compare', payload, display);
}

AIRequest? historySummary(List<HistoryRow> rows) {
  rows = rows.take(10).toList();
  if (rows.isEmpty) return null;
  final items = [
    for (final h in rows)
      {
        'label': historyLabel(h),
        'status': h.status,
        'delta_pct': h.deltaPct,
        'daily_delta_pct': h.dailyDeltaPct,
      },
  ];
  final withPct = [for (final h in rows) if (h.deltaPct != null) h];
  final payload = <String, Object?>{'count': rows.length, 'ok_count': withPct.length, 'records': items};
  final display = <String, Object?>{
    'count': '${rows.length}',
    'ok_count': '${withPct.length}',
    'best_label': '—',
    'best_delta': '—',
    'worst_label': '—',
    'worst_delta': '—',
  };
  if (withPct.isNotEmpty) {
    var best = withPct.first, worst = withPct.first;
    for (final h in withPct) {
      if (h.deltaPct! < best.deltaPct!) best = h;
      if (h.deltaPct! > worst.deltaPct!) worst = h;
    }
    payload['best'] = {'label': historyLabel(best), 'delta_pct': best.deltaPct};
    payload['worst'] = {'label': historyLabel(worst), 'delta_pct': worst.deltaPct};
    display.addAll({
      'best_label': historyLabel(best),
      'best_delta': fmt.pct(best.deltaPct),
      'worst_label': historyLabel(worst),
      'worst_delta': fmt.pct(worst.deltaPct),
    });
  }
  return _req('history_summary', payload, display);
}

AIRequest termExplain(String term) {
  final glossary = Map<String, dynamic>.from(prompts()['glossary'] as Map);
  final definition = (glossary[term] ?? 'Bu terim için kayıtlı tanım yok.').toString();
  return _req('term_explain', {}, {'term': term, 'definition': definition}, extra: {'term': term});
}

AIRequest dataSourceExplain() {
  final payload = <String, Object?>{
    'sources': [
      '$baseGridLabel saatlik üretim (+ eklenen yıllar)',
      '${_data.factorsLabel()} emisyon faktörleri',
      'Zenodo imalat tesisi makine yükleri',
    ],
    'load_is_sample': true,
  };
  return _req('data_source_explain', payload, {});
}

AIRequest nlInput(String sentence, ScenarioInputs current) {
  final machines = [
    for (final m in _data.machines()) {'id': m.id, 'name': m.name, 'type': m.type, 'shiftable': m.shiftable},
  ];
  final cur = {'asset_id': current.assetId, 's': current.s, 'L': current.L, 't': current.t, 'p': current.p};
  return AIRequest('nl_input', cur, {}, jsonMode: true, extra: {
    'sentence': sentence,
    'machines_json': jsonEncode(machines),
    'current_json': jsonEncode(cur),
  });
}

const List<(String, List<String>)> machineKeywords = [
  ('php_c', ['ısıt', 'isit', 'fırın', 'firin']),
  ('ex_a', ['havaland', 'aspirat', 'fan', 'egzoz']),
  ('comp_b', ['kompres', 'basınçlı hava', 'basincli hava']),
  ('mix_c', ['mikser', 'karıştır', 'karistir']),
  ('mh_a', ['taşıma', 'tasima', 'otomasyon', 'robot', 'konvey']),
  ('p_i', ['pres']),
  ('u_e', ['yardımcı', 'yardimci', 'utilit', 'hizmet']),
];

const String _trFrom = 'çğıöşüâîû';
const String _trTo = 'cgiosuaiu';

bool _isAsciiAlnum(String c) {
  final u = c.codeUnitAt(0);
  return c.length == 1 &&
      ((u >= 48 && u <= 57) || (u >= 65 && u <= 90) || (u >= 97 && u <= 122));
}

/// Türkçe harfleri sadeleştirip harf/rakam dışını atar; her karakterin özgün konumunu tutar.
(String, List<int>) _foldWithIndex(String text) {
  final out = StringBuffer();
  final idx = <int>[];
  final s = text.toLowerCase().replaceAll('i̇', 'i');
  for (var i = 0; i < s.length; i++) {
    var ch = s[i];
    final k = _trFrom.indexOf(ch);
    if (k >= 0) ch = _trTo[k];
    if (_isAsciiAlnum(ch)) {
      out.write(ch);
      idx.add(i);
    }
  }
  return (out.toString(), idx);
}

/// AI yokken basit kural tabanlı çözümleyici (Türkçe kalıplar).
Map<String, Object?> parseNlRule(String sentence) {
  var text = sentence.toLowerCase();
  final out = <String, Object?>{};
  final machines = _data.machines();
  final ids = {for (final m in machines) m.id};
  for (final tok in RegExp(r'[a-z]+_[a-z0-9_]+').allMatches(text)) {
    if (ids.contains(tok.group(0))) {
      out['asset_id'] = tok.group(0);
      break;
    }
  }
  if (!out.containsKey('asset_id')) {
    final (folded, index) = _foldWithIndex(text);
    // Uzun adlar önce (kararlı sıralama: eşitlikte özgün sıra).
    final order = [for (var k = 0; k < machines.length; k++) k]
      ..sort((a, b) {
        final c = _foldWithIndex(machines[b].name).$1.length.compareTo(_foldWithIndex(machines[a].name).$1.length);
        return c != 0 ? c : a.compareTo(b);
      });
    for (final m in [for (final k in order) machines[k]]) {
      final name = _foldWithIndex(m.name.toLowerCase()).$1;
      final pos = name.length >= 3 ? folded.indexOf(name) : -1;
      if (pos >= 0) {
        out['asset_id'] = m.id;
        final a = index[pos], b = index[pos + name.length - 1] + 1;
        if (b <= text.length) {
          text = text.substring(0, a) + ' ' * (b - a) + text.substring(b);
        }
        break;
      }
    }
  }
  if (!out.containsKey('asset_id')) {
    for (final (assetId, keys) in machineKeywords) {
      if (keys.any(text.contains)) {
        out['asset_id'] = assetId;
        break;
      }
    }
  }
  var m = RegExp(r'(?:%|yüzde|yuzde)\s*(\d{1,3})').firstMatch(text);
  if (m != null) {
    out['p'] = int.parse(m.group(1)!) / 100;
    text = '${text.substring(0, m.start)} ${text.substring(m.end)}';
  }
  m = RegExp(r'(\d{1,2})\s*saat').firstMatch(text);
  if (m != null) {
    out['L'] = int.parse(m.group(1)!);
    text = '${text.substring(0, m.start)} ${text.substring(m.end)}';
  }
  final hours = <(int, String)>[];
  for (final hm in RegExp(r"(\d{1,2})(?:[:.]00)?\s*(?:['’]?\s*(den|dan|ten|tan|de|da|te|ta|e|a|ye|ya))?\b")
      .allMatches(text)) {
    hours.add((int.parse(hm.group(1)!), hm.group(2) ?? ''));
  }
  const srcSuf = ['den', 'dan', 'ten', 'tan'];
  const tgtSuf = ['e', 'a', 'ye', 'ya'];
  final sourcesH = [for (final (h, suf) in hours) if (srcSuf.contains(suf)) h];
  final targets = [for (final (h, suf) in hours) if (tgtSuf.contains(suf)) h];
  final plain = [for (final (h, suf) in hours) if (!srcSuf.contains(suf) && !tgtSuf.contains(suf)) h];
  if (sourcesH.isNotEmpty) out['s'] = sourcesH.first;
  if (targets.isNotEmpty) out['t'] = targets.first;
  for (final h in plain) {
    if (!out.containsKey('s')) {
      out['s'] = h;
    } else if (!out.containsKey('t')) {
      out['t'] = h;
    }
  }
  return out;
}

int? _toInt(Object? v) {
  if (v is int) return v;
  if (v is double) return v.truncate();
  if (v is String) return int.tryParse(v.trim());
  return null;
}

double? _toDouble(Object? v) {
  if (v is num) return v.toDouble();
  if (v is String) return double.tryParse(v.trim());
  return null;
}

/// LLM/kural çıktısını motor kurallarıyla doğrular; mevcut girdilerle tamamlar.
(Map<String, Object?>?, String) validateNl(Map<String, Object?> obj, ScenarioInputs current) {
  final ids = {for (final m in _data.machines()) m.id};
  final merged = <String, Object?>{
    'asset_id': current.assetId,
    's': current.s,
    'L': current.L,
    't': current.t,
    'p': current.p,
  };
  for (final key in merged.keys.toList()) {
    if (obj.containsKey(key) && obj[key] != null) merged[key] = obj[key];
  }
  final s = _toInt(merged['s']), L = _toInt(merged['L']), t = _toInt(merged['t']);
  final p = _toDouble(merged['p']);
  if (s == null || L == null || t == null || p == null) return (null, 'Sayısal alanlar okunamadı.');
  merged['s'] = s;
  merged['L'] = L;
  merged['t'] = t;
  merged['p'] = p;
  merged['asset_id'] = merged['asset_id'].toString();
  if (!ids.contains(merged['asset_id'])) return (null, 'Bilinmeyen makine: ${merged['asset_id']}');
  if (!(0 <= s && s <= 23 && 0 <= t && t <= 23 && 1 <= L && L <= 12)) {
    return (null, 'Saatler 0–23, uzunluk 1–12 aralığında olmalı.');
  }
  if (!(0.0 <= p && p <= 1.0)) return (null, 'Kaydırma oranı %0–100 olmalı.');
  if (s + L > 24 || t + L > 24) return (null, 'Pencere aynı gün içinde kalmalı (başlangıç + uzunluk ≤ 24).');
  if (!const ['asset_id', 's', 'L', 't', 'p'].any(obj.containsKey)) {
    return (null, 'Cümleden senaryo bilgisi çıkarılamadı.');
  }
  return (merged, '');
}

// ------------------------------------------------------------------ yıllık (EXE 1.1.1)
const List<String> monthNames = [
  'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık',
];

/// r: makine ya da tesis geneli yıllık sonuç; best: yıl boyu en temiz hedef sonucu.
AIRequest? annualExplain(annual.AnnualResult? r, annual.AnnualResult? best,
    [String kind = 'tCO2', double? parametricKwh]) {
  if (r == null || r.daysOk == 0) return null;
  final what = r.isFacility ? 'Tesis geneli (kaydırılabilir makineler)' : _data.machine(r.assetId).name;
  final months = [for (final m in r.months) if (m.days > 0) m];
  var strongest = months.first;
  for (final m in months) {
    if (m.deltaKg < strongest.deltaKg) strongest = m; // min(): eşitlikte ilk
  }
  final unit = kind == 'tCO2' ? 'CO2' : 'CO2-eşd';
  final payload = <String, Object?>{
    'kapsam': what,
    'yil': r.year,
    'emission_type': kind,
    'standart_pencere': fmt.window(r.s, r.L),
    'hedef_pencere': fmt.window(r.t, r.L),
    'kaydirma_orani_yuzde': r.p * 100,
    'hesaba_giren_gun': r.daysOk,
    'toplam_gun': r.daysTotal,
    'gun_birimi': r.isFacility ? 'makine-gün' : 'gün',
    'kaydirilan_enerji_kwh': r.shiftedKwh,
    'standart_emisyon_kg': r.baselineKg,
    'secilen_emisyon_kg': r.scenarioKg,
    'yillik_degisim_kg': r.deltaKg,
    'yillik_degisim_ton': r.deltaKg / 1000,
    'kaydirilan_yukte_degisim_yuzde': r.deltaPct,
    'toplam_emisyon_icindeki_pay_yuzde': r.dailyDeltaPct,
    'azalan_gun': r.betterDays,
    'artan_gun': r.worseDays,
    'yenilenebilir_pay_standart_yuzde': r.renSourcePct,
    'yenilenebilir_pay_hedef_yuzde': r.renTargetPct,
    'fosil_marjinal_duyarlilik_degisim_yuzde': r.fossilDeltaPct,
    'fosil_marjinal_duyarlilik_degisim_kg': r.fossilDeltaKg,
    'aylar': [
      for (final m in months)
        {'ay': monthNames[m.month - 1], 'degisim_kg': m.deltaKg, 'degisim_yuzde': m.deltaPct},
    ],
    'en_guclu_ay': monthNames[strongest.month - 1],
  };
  if (parametricKwh != null) payload['parametrik_kwh_saat'] = parametricKwh;
  if (best != null) {
    payload['yil_boyu_en_temiz_hedef'] = fmt.window(best.t, best.L);
    payload['en_temiz_hedef_degisim_kg'] = best.deltaKg;
    payload['en_temiz_hedef_degisim_yuzde'] = best.deltaPct;
  }
  if (r.isFacility) {
    final parts = [for (final x in r.parts) if (x.daysOk > 0) x]..sort((a, b) => a.deltaKg.compareTo(b.deltaKg));
    payload['makine_katkilari'] = [
      for (final x in parts)
        {'makine': _data.machine(x.assetId).name, 'degisim_kg': x.deltaKg, 'degisim_yuzde': x.deltaPct},
    ];
  }
  final kg = r.deltaKg.abs();
  final display = <String, Object?>{
    'what': what,
    'year': '${r.year}',
    'days': '${r.daysOk}',
    'day_unit': r.isFacility ? 'makine-günde' : 'günde',
    'delta': kg >= 1000 ? '${fmt.num(kg / 1000)} t $unit' : '${fmt.num(kg, 1)} kg $unit',
    'verb': r.deltaKg <= 0 ? 'azalırdı' : 'artardı',
    'pct': fmt.pct(r.deltaPct),
    'ren_src': r.renSourcePct == null ? '—' : '%${fmt.num(r.renSourcePct!, 1)}',
    'ren_tgt': r.renTargetPct == null ? '—' : '%${fmt.num(r.renTargetPct!, 1)}',
    'best_month': monthNames[strongest.month - 1],
    'best_target': best != null ? fmt.window(best.t, best.L) : '—',
  };
  return _req('annual_explain', payload, display);
}
