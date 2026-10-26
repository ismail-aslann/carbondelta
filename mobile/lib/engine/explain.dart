// Şeffaflık: B ve S toplamlarının saat saat dökümü (explain.py).

import 'core.dart';

class BreakdownRow {
  const BreakdownRow({
    required this.window,
    required this.hour,
    required this.fromHour,
    required this.kwh,
    required this.ci,
    required this.kg,
  });

  /// 'standard' | 'scenario'
  final String window;
  final int hour;
  final int fromHour;
  final double kwh;
  final double ci;
  final double kg;
}

List<BreakdownRow> breakdown(
    List<double> loadKwh, List<double> ci, Result result, double p) {
  if (!(result.status == ok ||
      result.status == sameWindow ||
      result.status == noLoad)) {
    return [];
  }
  final rows = <BreakdownRow>[];
  for (final src in result.sourceHours) {
    final e = p * loadKwh[src];
    rows.add(BreakdownRow(
        window: 'standard', hour: src, fromHour: src, kwh: e, ci: ci[src], kg: e * ci[src]));
  }
  for (var k = 0; k < result.sourceHours.length && k < result.targetHours.length; k++) {
    final src = result.sourceHours[k];
    final tgt = result.targetHours[k];
    final e = p * loadKwh[src];
    rows.add(BreakdownRow(
        window: 'scenario', hour: tgt, fromHour: src, kwh: e, ci: ci[tgt], kg: e * ci[tgt]));
  }
  return rows;
}
