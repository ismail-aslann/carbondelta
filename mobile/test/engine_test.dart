// ignore_for_file: non_constant_identifier_names
// Hesap motoru testleri — EXE 1.1.0 talimatındaki referans sonuçlar.

import 'dart:io';

import 'package:carbondelta_mobile/engine/best_window.dart';
import 'package:carbondelta_mobile/engine/core.dart';
import 'package:carbondelta_mobile/engine/data.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('El hesabı: B=13, S=10, delta=-23.0769...', () {
    final load = List<double>.filled(24, 0)
      ..[0] = 10
      ..[1] = 20;
    final ci = List<double>.filled(24, 0.45)
      ..[0] = 0.5
      ..[1] = 0.4
      ..[10] = 0.4
      ..[11] = 0.3;
    final r = simulate(load, ci, 0, 2, 10, 1.0);
    expect(r.status, ok);
    expect(r.baselineKg, closeTo(13.0, 1e-12));
    expect(r.scenarioKg, closeTo(10.0, 1e-12));
    expect(r.deltaPct, closeTo(-23.076923076923077, 1e-9));
  });

  test('Durumlar: öncelik sırası ve özel durumlar', () {
    final load = List<double>.filled(24, 10);
    final ci = List<double>.generate(24, (h) => 0.4 + h / 100);
    expect(simulate(load, ci, 3, 3, 18, 1.0, shiftable: false).status, nonShiftable);
    expect(simulate(load, ci, 22, 3, 18, 1.0).status, outOfRange);
    expect(simulate(load, ci, 3, 3, 22, 1.0).status, outOfRange);
    expect(simulate(load, ci, 3, 0, 18, 1.0).status, outOfRange);
    expect(simulate(load, ci, 3, 3, 18, 1.5).status, outOfRange);
    expect(simulate(load, ci, 3, 3, 18, 1.0, restricted: {19}).status, restrictedConflict);
    final same = simulate(load, ci, 5, 2, 5, 1.0);
    expect(same.status, sameWindow);
    expect(same.deltaPct, 0.0);
    final zero = simulate(List<double>.filled(24, 0), ci, 3, 3, 18, 1.0);
    expect(zero.status, noLoad);
    expect(zero.deltaPct, isNull);
  });

  test('p=0.5 yüzdeyi değiştirmez, kg yarıya iner', () {
    final load = List<double>.filled(24, 10);
    final ci = List<double>.generate(24, (h) => 0.4 + h / 100);
    final a = simulate(load, ci, 3, 3, 18, 1.0);
    final b = simulate(load, ci, 3, 3, 18, 0.5);
    expect(b.deltaPct, closeTo(a.deltaPct!, 1e-12));
    expect(b.baselineKg, closeTo(a.baselineKg / 2, 1e-12));
  });

  test('Gerçek veri referansı: comp_b 2025-07-15 03:00→18:00 = -15,62 %', () {
    final grid = parseGridCsv(File('assets/shared/epias_2025.csv').readAsStringSync(), 'EPİAŞ 2025');
    final loads = parseLoadsCsv(File('assets/shared/loads_hourly.csv').readAsStringSync());
    final ci = [for (final r in grid['2025-07-15']!) r.ciT];
    final load = loads['comp_b|2025-07-15']!;
    final r = simulate(load, ci, 3, 3, 18, 1.0);
    expect(r.baselineKg, closeTo(42.613384, 1e-4));
    expect(r.scenarioKg, closeTo(35.957618, 1e-4));
    expect(r.deltaPct, closeTo(-15.6190, 1e-4));
    expect(r.dailyDeltaPct, closeTo(-2.1542, 1e-4));
  });

  test('best_window: en düşük S, kısıtlı saatleri atlar', () {
    final load = List<double>.filled(24, 10);
    final ci = List<double>.generate(24, (h) => (h - 19).abs() / 10 + 0.3);
    final best = bestWindow(load, ci, 3, 1, 1.0)!;
    expect(best.$1, 19);
    final best2 = bestWindow(load, ci, 3, 1, 1.0, restricted: {19})!;
    expect(best2.$1, 18);
    for (final (t, r) in scanWindows(load, ci, 3, 1, 1.0)) {
      expect(r.scenarioKg >= best.$2.scenarioKg, isTrue, reason: 't=$t');
    }
  });
}
