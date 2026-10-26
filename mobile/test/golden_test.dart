// Golden test: EXE'nin (Python engine/make_golden.py) ürettiği 30 senaryo Dart
// motorunda çalıştırılır; tüm alanlar 1e-9 toleransla karşılaştırılır.
// Kaynak: ismail-aslann/carbondelta → shared/golden/vectors.json

import 'dart:convert';
import 'dart:io';

import 'package:carbondelta_mobile/engine/core.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final doc = jsonDecode(File('test/golden/vectors.json').readAsStringSync()) as Map<String, dynamic>;
  final tol = (doc['tolerance'] as num).toDouble();
  final scenarios = doc['scenarios'] as List;

  test('Golden dosyası 30 senaryo içeriyor', () => expect(scenarios.length, 30));

  for (final sc in scenarios) {
    final s = sc as Map<String, dynamic>;
    test('${s['id']} · ${s['kind']} · ${s['asset_id']} ${s['date']}', () {
      final i = s['inputs'] as Map<String, dynamic>;
      final e = s['expected'] as Map<String, dynamic>;
      List<double> dl(Object? v) => [for (final x in v as List) (x as num).toDouble()];
      final r = simulate(
        dl(i['load_kwh']),
        dl(i['ci']),
        i['s'] as int,
        i['L'] as int,
        i['t'] as int,
        (i['p'] as num).toDouble(),
        restricted: {for (final h in i['restricted'] as List) h as int},
        shiftable: i['shiftable'] as bool,
      );
      expect(r.status, e['status']);
      void near(String name, double? actual, Object? expected) {
        if (expected == null) {
          expect(actual, isNull, reason: name);
        } else {
          expect(actual, isNotNull, reason: name);
          expect(actual!, closeTo((expected as num).toDouble(), tol), reason: name);
        }
      }

      near('shifted_kwh', r.shiftedKwh, e['shifted_kwh']);
      near('baseline_kg', r.baselineKg, e['baseline_kg']);
      near('scenario_kg', r.scenarioKg, e['scenario_kg']);
      near('delta_pct', r.deltaPct, e['delta_pct']);
      near('daily_kg', r.dailyKg, e['daily_kg']);
      near('daily_delta_pct', r.dailyDeltaPct, e['daily_delta_pct']);
      expect(r.sourceHours, [for (final h in e['source_hours'] as List) h as int]);
      expect(r.targetHours, [for (final h in e['target_hours'] as List) h as int]);
    });
  }
}
