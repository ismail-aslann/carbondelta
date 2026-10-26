// EXE 1.1.3 yenilikleri: yıllık etki, tesis geneli, tesis günlük planı, fosil marjinal duyarlılık ve
// yenilenebilir pay. Beklenen değerler Python motorundan (engine/annual.py, engine/plan.py) üretildi:
// test/golden/v113.json. Toleranslar: göreli 1e-9.

import 'dart:convert';
import 'dart:io';

import 'package:carbondelta_mobile/ai/ai_client.dart' show allowedNumbers, loadPrompts, prompts, validateNumbers;
import 'package:carbondelta_mobile/ai/ai_context.dart' as ctx;
import 'package:carbondelta_mobile/engine/annual.dart' as annual;
import 'package:carbondelta_mobile/engine/data.dart';
import 'package:carbondelta_mobile/engine/insights.dart';
import 'package:carbondelta_mobile/engine/packages.dart' show setDataDirForTests;
import 'package:carbondelta_mobile/engine/plan.dart' as plan;
import 'package:carbondelta_mobile/report/annual_export.dart';
import 'package:carbondelta_mobile/report/plan_export.dart';
import 'package:flutter_test/flutter_test.dart';

double _d(Object? v) => (v as num).toDouble();
List<double> _dl(Object? v) => [for (final x in v as List) _d(x)];

void near(double? actual, Object? expected, String name) {
  if (expected == null) {
    expect(actual, isNull, reason: name);
    return;
  }
  expect(actual, isNotNull, reason: name);
  final e = _d(expected);
  expect(actual!, closeTo(e, 1e-9 * (e.abs() > 1 ? e.abs() : 1)), reason: name);
}

void main() {
  final doc = jsonDecode(File('test/golden/v113.json').readAsStringSync()) as Map<String, dynamic>;
  final data = DataStore.instance;
  final day = doc['day'] as String;

  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    setDataDirForTests(Directory.systemTemp.createTempSync('cd_v113'));
    await data.load();
    await loadPrompts();
  });

  void checkAnnual(annual.AnnualResult r, Map<String, dynamic> e, String tag) {
    expect(r.daysTotal, e['days_total'], reason: '$tag days_total');
    expect(r.daysOk, e['days_ok'], reason: '$tag days_ok');
    expect(r.betterDays, e['better_days'], reason: '$tag better');
    expect(r.worseDays, e['worse_days'], reason: '$tag worse');
    expect(r.statusCounts, Map<String, int>.from(e['status_counts'] as Map), reason: '$tag status');
    for (final (k, v) in [
      ('shifted_kwh', r.shiftedKwh),
      ('baseline_kg', r.baselineKg),
      ('scenario_kg', r.scenarioKg),
      ('daily_kg', r.dailyKg),
      ('ren_source_kwh', r.renSourceKwh),
      ('ren_target_kwh', r.renTargetKwh),
      ('fossil_baseline_kg', r.fossilBaselineKg),
      ('fossil_scenario_kg', r.fossilScenarioKg),
    ]) {
      near(v, e[k], '$tag $k');
    }
    final months = e['months'] as List;
    for (var m = 0; m < 12; m++) {
      final em = months[m] as List;
      expect(r.months[m].days, em[0], reason: '$tag ay ${m + 1}');
      near(r.months[m].baselineKg, em[1], '$tag ay ${m + 1} B');
      near(r.months[m].scenarioKg, em[2], '$tag ay ${m + 1} S');
    }
    for (final (name, got) in [('best_day', r.bestDay), ('worst_day', r.worstDay)]) {
      final ex = e[name] as List?;
      if (ex == null) {
        expect(got, isNull, reason: '$tag $name');
      } else {
        final (d, v) = got!;
        expect(d, ex[0], reason: '$tag $name');
        near(v, ex[1], '$tag $name');
      }
    }
    expect([for (final p in r.parts) p.assetId], List<String>.from(e['parts'] as List), reason: '$tag parts');
  }

  test('Fosil marjinal yoğunluk = CI / fosil payı', () {
    final f = doc['fossil_ci'] as Map<String, dynamic>;
    for (final kind in ['tCO2', 'tCO2esd']) {
      final got = data.ciFossil24(day, kind);
      final exp = _dl(f[kind]);
      for (var h = 0; h < 24; h++) {
        near(got[h], exp[h], '$kind saat $h');
      }
    }
  });

  test('Fosil duyarlılık ve yenilenebilir pay (referans senaryo)', () {
    final (load, _) = data.scenarioSeries('comp_b', day);
    final (b, s, pct) = fossilSensitivity(load, data.ciFossil24(day), 3, 3, 18, 1.0);
    final e = doc['fossil_sens'] as List;
    near(b, e[0], 'B_fosil');
    near(s, e[1], 'S_fosil');
    near(pct, e[2], 'yüzde');
    expect(pct! > -15.62 && pct < 0, isTrue); // ana sonuçtan daha temkinli
    final ren = shiftedRenewable(data, day, load, 3, 3, 18, 1.0)!;
    final er = doc['renewable'] as List;
    near(ren.$1, er[0], 'yenilenebilir standart');
    near(ren.$2, er[1], 'yenilenebilir hedef');
  });

  test('Yıllık etki: makine senaryoları Python ile aynı', () {
    for (final c in doc['annual'] as List) {
      final i = (c as Map<String, dynamic>)['in'] as List;
      final asset = i[0] as String, year = i[1] as int;
      final kind = i[7] as String;
      final param = i[8] == null ? null : _d(i[8]);
      final series = annual.yearSeries(data, asset, year, kind, param);
      final r = annual.annualImpact(data, asset, year, i[2] as int, i[3] as int, i[4] as int, _d(i[5]),
          restricted: {for (final h in i[6] as List) h as int}, kind: kind, series: series);
      checkAnnual(r, c['out'] as Map<String, dynamic>, '$i');
    }
  });

  test('Yıllık etki: tesis geneli makinelerin toplamı', () {
    final c = doc['facility'] as Map<String, dynamic>;
    final i = c['in'] as List;
    final r = annual.facilityImpact(data, i[0] as int, i[1] as int, i[2] as int, i[3] as int, _d(i[4]));
    checkAnnual(r, c['out'] as Map<String, dynamic>, 'tesis');
    expect(r.isFacility, isTrue);
    var sum = 0.0;
    for (final p in r.parts) {
      sum += p.deltaKg;
    }
    expect(r.deltaKg, closeTo(sum, 1e-6));
  });

  test('Yıl boyu en temiz hedef sıralaması', () {
    final c = doc['best_target'] as Map<String, dynamic>;
    final i = c['in'] as List;
    final b = annual.bestAnnualTarget(data, i[0] as String, i[1] as int, i[2] as int, i[3] as int, _d(i[4]));
    expect([for (final x in b) x.t], List<int>.from(c['ts'] as List));
    final sk = c['sk'] as List;
    for (var n = 0; n < b.length; n++) {
      near(b[n].scenarioKg, sk[n], 'ΣS t=${b[n].t}');
    }
  });

  test('Yıllar', () {
    final y = doc['years'] as Map<String, dynamic>;
    y.forEach((asset, years) {
      expect(annual.yearsFor(data, asset == '__tesis__' ? annual.all : asset), List<int>.from(years as List),
          reason: asset);
    });
  });

  test('Tesis günlük planı: otomatik/elle, tepe sınırı, kısıt, hariç', () {
    for (final c in doc['plans'] as List) {
      final i = (c as Map<String, dynamic>)['in'] as Map<String, dynamic>;
      final e = c['out'] as Map<String, dynamic>;
      final name = i['name'] as String;
      final st = plan.defaultSettings(data, i['s'] as int?, i['L'] as int, _d(i['p']));
      for (final x in (i['exclude'] as List?) ?? const []) {
        st[x as String]!.include = false;
      }
      final p = plan.facilityPlan(data, day, st,
          restricted: {for (final h in i['restricted'] as List) h as int},
          kind: i['kind'] as String,
          peakLimit: i['limit'] == null ? null : _d(i['limit']));
      final rows = e['rows'] as List;
      expect(p.rows.length, rows.length, reason: name);
      for (var n = 0; n < rows.length; n++) {
        final er = rows[n] as Map<String, dynamic>, r = p.rows[n];
        final tag = '$name ${er['id']}';
        expect(r.assetId, er['id'], reason: tag);
        expect(r.status, er['status'], reason: '$tag durum');
        expect(r.note, er['note'], reason: '$tag not');
        expect(r.t, er['t'], reason: '$tag hedef');
        if (er['status'] != 'no_data' && er['status'] != 'non_shiftable' && er['status'] != 'excluded') {
          expect(r.s, er['s'], reason: '$tag standart');
          expect(r.L, er['L'], reason: '$tag uzunluk');
        }
        near(r.dailyKg, er['daily_kg'], '$tag günlük');
        near(r.result?.scenarioKg, er['sk'], '$tag S');
        near(r.result?.baselineKg, er['bk'], '$tag B');
        final ren = er['renewable'] as List?, fos = er['fossil'] as List?;
        near(r.renewable?.$1, ren?[0], '$tag yen. std');
        near(r.renewable?.$2, ren?[1], '$tag yen. hedef');
        near(r.fossil?.$1, fos?[0], '$tag fosil B');
        near(r.fossil?.$2, fos?[1], '$tag fosil S');
      }
      final before = _dl(e['before']), after = _dl(e['after']);
      for (var h = 0; h < 24; h++) {
        near(p.before[h], before[h], '$name önce $h');
        near(p.after[h], after[h], '$name sonra $h');
      }
      near(p.deltaKg, e['delta_kg'], '$name değişim');
      near(p.deltaPct, e['delta_pct'], '$name yüzde');
      near(p.dailyDeltaPct, e['daily_delta_pct'], '$name günlük');
      near(p.fossilDeltaPct, e['fossil_delta_pct'], '$name fosil');
      near(p.peakBefore, e['peak_before'], '$name tepe önce');
      near(p.peakAfter, e['peak_after'], '$name tepe sonra');
      expect(p.plannedCount, e['planned'], reason: name);
      expect(plan.reasonCounts(p), Map<String, int>.from(e['reasons'] as Map), reason: name);
    }
  });

  test('Plan: tepe sınırı uyulur, enerji korunur', () {
    final free = plan.facilityPlan(data, day, plan.defaultSettings(data, 3, 3, 1.0));
    expect(free.peakAfter > free.peakBefore, isTrue);
    final lim = plan.facilityPlan(data, day, plan.defaultSettings(data, 3, 3, 1.0), peakLimit: free.peakBefore);
    expect(lim.peakAfter <= free.peakBefore + 1e-9, isTrue);
    expect(free.deltaKg <= lim.deltaKg && lim.deltaKg < 0, isTrue);
    var a = 0.0, b = 0.0;
    for (var h = 0; h < 24; h++) {
      a += free.before[h];
      b += free.after[h];
    }
    expect(b, closeTo(a, 1e-6));
  });

  test('Parametrik modda sabit yük', () {
    final series = annual.yearSeries(data, 'comp_b', 2025, 'tCO2', 10.0);
    final r = annual.annualImpact(data, 'comp_b', 2025, 3, 3, 18, 1.0, series: series);
    expect(r.daysOk, series.length); // sabit yükte "yük yok" günü olmaz
    expect(r.shiftedKwh, closeTo(10.0 * 3 * series.length, 1e-6));
  });

  test('Delti yıllık yorum isteği ve şablon doğrulayıcıdan geçer', () {
    expect((prompts()['functions'] as List).length, 16); // talimattaki 15 işlev + yıllık etki yorumu
    final f = annual.facilityImpact(data, 2025, 3, 3, 18, 1.0);
    final req = ctx.annualExplain(f, f)!;
    expect(req.funcId, 'annual_explain');
    expect(req.payload.containsKey('makine_katkilari'), isTrue);
    final text = req.fallback();
    expect(text.contains('makine-günde'), isTrue);
    expect(text.contains('18:00–21:00'), isTrue);
    expect(validateNumbers(text, allowedNumbers([req.payload])), isTrue);
    expect(ctx.annualExplain(annual.annualImpact(data, 'comp_b', 2025, 3, 3, 18, 1.0, restricted: {19}), null),
        isNull);
  });

  test('Birimler emisyon tipine göre', () {
    expect(mass(-1500, 'tCO2esd').endsWith('t CO2-eşd'), isTrue);
    expect(mass(-15, 'tCO2').endsWith('kg CO2'), isTrue);
  });

  test('CSV ve PDF rapor üretilir', () async {
    final f = annual.facilityImpact(data, 2025, 3, 3, 18, 1.0);
    final csv = annualCsv(data, f, {5});
    expect(csv.startsWith('﻿CarbonDelta yıllık etki'), isTrue);
    expect(csv.contains('Fosil marjinal duyarlılık, değişim (%)'), isTrue);
    final pdf = await annualPdf(data, f, f, {5}, 'tCO2', 10.0, aiText: 'Deneme yorumu', aiSource: 'ai');
    expect(String.fromCharCodes(pdf.take(5)), '%PDF-');
    expect(pdf.length > 20000, isTrue);
    final p = plan.facilityPlan(data, day, plan.defaultSettings(data, 3, 3, 1.0));
    final pc = planCsv(data, p, {});
    expect(pc.contains('Tepe yük sonra (kWh)'), isTrue);
    expect(planSource(data, p).$1.contains('Örnek yük'), isTrue);
  });
}
