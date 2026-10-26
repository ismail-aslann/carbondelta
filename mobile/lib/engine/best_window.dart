// ignore_for_file: non_constant_identifier_names
// Otomatik pencere önerisi — deterministik tarama, AI yok (best_window.py).

import 'core.dart';

/// t = 0..24-L içindeki geçerli hedef pencereler, t sırasıyla.
List<(int, Result)> scanWindows(
  List<double> loadKwh,
  List<double> ci,
  int s,
  int L,
  double p, {
  Set<int> restricted = const {},
  bool shiftable = true,
}) {
  final out = <(int, Result)>[];
  for (var t = 0; t < hours - L + 1; t++) {
    final r = simulate(loadKwh, ci, s, L, t, p,
        restricted: restricted, shiftable: shiftable);
    if (!(r.status == ok || r.status == sameWindow) || r.baselineKg == 0.0) {
      continue;
    }
    out.add((t, r));
  }
  return out;
}

/// Geçerli pencerelerden en düşük S'yi döndürür. Eşitlikte en küçük t kazanır.
/// Geçerli pencere yoksa null.
(int, Result)? bestWindow(
  List<double> loadKwh,
  List<double> ci,
  int s,
  int L,
  double p, {
  Set<int> restricted = const {},
  bool shiftable = true,
}) {
  (int, Result)? best;
  for (final (t, r) in scanWindows(loadKwh, ci, s, L, p,
      restricted: restricted, shiftable: shiftable)) {
    if (best == null || r.scenarioKg < best.$2.scenarioKg) {
      best = (t, r);
    }
  }
  return best;
}
