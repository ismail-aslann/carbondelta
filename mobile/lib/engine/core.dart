// ignore_for_file: non_constant_identifier_names
// Saf hesap çekirdeği — EXE 1.1.0 engine/core.py ile satır satır aynı.
//
// Düz liste ve double. Toplama sırası her zaman i = 0'dan L-1'e
// (h = 0'dan 23'e). Yuvarlama yok; yuvarlama yalnızca ekranda (ui/fmt.dart).

const int hours = 24;

const String ok = 'ok';
const String nonShiftable = 'non_shiftable';
const String outOfRange = 'out_of_range';
const String restrictedConflict = 'restricted_conflict';
const String sameWindow = 'same_window';
const String noLoad = 'no_load';

class Result {
  const Result({
    required this.status,
    required this.shiftedKwh,
    required this.baselineKg,
    required this.scenarioKg,
    required this.deltaPct,
    required this.dailyKg,
    required this.dailyDeltaPct,
    this.sourceHours = const [],
    this.targetHours = const [],
  });

  final String status;
  final double shiftedKwh;
  final double baselineKg; // B
  final double scenarioKg; // S
  final double? deltaPct;
  final double dailyKg;
  final double? dailyDeltaPct;
  final List<int> sourceHours;
  final List<int> targetHours;
}

Result _empty(String status,
        [List<int>? sourceHours, List<int>? targetHours]) =>
    Result(
      status: status,
      shiftedKwh: 0.0,
      baselineKg: 0.0,
      scenarioKg: 0.0,
      deltaPct: null,
      dailyKg: 0.0,
      dailyDeltaPct: null,
      sourceHours: sourceHours ?? const [],
      targetHours: targetHours ?? const [],
    );

Result simulate(
  List<double> loadKwh,
  List<double> ci,
  int s,
  int L,
  int t,
  double p, {
  Set<int> restricted = const {},
  bool shiftable = true,
}) {
  if (loadKwh.length != hours || ci.length != hours) {
    throw ArgumentError('load_kwh ve ci 24 elemanlı olmalı');
  }

  if (!shiftable) {
    return _empty(nonShiftable);
  }

  if (L < 1 || s < 0 || t < 0 || s + L > hours || t + L > hours || p < 0.0 || p > 1.0) {
    return _empty(outOfRange);
  }

  final sourceHours = [for (var i = 0; i < L; i++) s + i];
  final targetHours = [for (var i = 0; i < L; i++) t + i];

  for (final h in targetHours) {
    if (restricted.contains(h)) {
      return _empty(restrictedConflict, sourceHours, targetHours);
    }
  }

  var shiftedKwh = 0.0;
  var baselineKg = 0.0;
  var scenarioKg = 0.0;
  for (var i = 0; i < L; i++) {
    final eI = p * loadKwh[s + i];
    shiftedKwh += eI;
    baselineKg += eI * ci[s + i];
    scenarioKg += eI * ci[t + i];
  }

  var dailyKg = 0.0;
  for (var h = 0; h < hours; h++) {
    dailyKg += loadKwh[h] * ci[h];
  }

  if (s == t) {
    return Result(
      status: sameWindow,
      shiftedKwh: shiftedKwh,
      baselineKg: baselineKg,
      scenarioKg: scenarioKg,
      deltaPct: 0.0,
      dailyKg: dailyKg,
      dailyDeltaPct: 0.0,
      sourceHours: sourceHours,
      targetHours: targetHours,
    );
  }

  if (baselineKg == 0.0) {
    return Result(
      status: noLoad,
      shiftedKwh: shiftedKwh,
      baselineKg: baselineKg,
      scenarioKg: scenarioKg,
      deltaPct: null,
      dailyKg: dailyKg,
      dailyDeltaPct: null,
      sourceHours: sourceHours,
      targetHours: targetHours,
    );
  }

  final deltaPct = (scenarioKg - baselineKg) / baselineKg * 100;
  final dailyDeltaPct = (scenarioKg - baselineKg) / dailyKg * 100;
  return Result(
    status: ok,
    shiftedKwh: shiftedKwh,
    baselineKg: baselineKg,
    scenarioKg: scenarioKg,
    deltaPct: deltaPct,
    dailyKg: dailyKg,
    dailyDeltaPct: dailyDeltaPct,
    sourceHours: sourceHours,
    targetHours: targetHours,
  );
}
