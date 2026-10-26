// AI açıklamalarına giden yardımcı istatistikler (deterministik, emisyon formülü
// değil). Buradaki sayılar LLM'e girdi olarak gönderilir (engine/insights.py).

import 'data.dart';
import 'sources.dart';

const int topSources = 3;

/// Bir pencerenin ortalama karbon yoğunluğu ve üretim karışımı.
Map<String, Object?> windowMix(DataStore data, String date, List<int> hours, [String kind = 'tCO2']) {
  if (hours.isEmpty) return {};
  final ci = data.ci24(date, kind);
  final mixes = [for (final h in hours) data.mixAt(date, h)];
  final n = hours.length;
  final shares = <String, double>{};
  for (final m in mixes) {
    for (final src in sources) {
      final v = m.shares[src]!;
      shares[src] = (shares[src] ?? 0.0) + v / n;
    }
  }
  final top = shares.entries.toList()
    ..sort((a, b) {
      final c = b.value.compareTo(a.value);
      return c != 0 ? c : a.key.compareTo(b.key);
    });
  // Counter.most_common: eşitlikte ilk görülen.
  final counts = <String, int>{};
  for (final m in mixes) {
    counts[m.dominant] = (counts[m.dominant] ?? 0) + 1;
  }
  var dominant = counts.keys.first;
  for (final e in counts.entries) {
    if (e.value > counts[dominant]!) dominant = e.key;
  }
  var ciSum = 0.0;
  for (final h in hours) {
    ciSum += ci[h];
  }
  var renSum = 0.0;
  for (final m in mixes) {
    renSum += m.renewablePct;
  }
  return {
    'ci_avg': ciSum / n,
    'renewable_pct_avg': renSum / n,
    'dominant': dominant,
    'top_sources': [
      for (final e in top.take(topSources)) {'source': e.key, 'share_pct': e.value},
    ],
  };
}

/// İki senaryonun ana yüzdelerini kıyaslar. Eksi yönde olan daha iyidir.
Map<String, Object?> compare(double? deltaA, double? deltaB) {
  if (deltaA == null || deltaB == null) return {'better': null, 'diff_points': null};
  if (deltaA == deltaB) return {'better': 'equal', 'diff_points': 0.0};
  final better = deltaA < deltaB ? 'a' : 'b';
  return {'better': better, 'diff_points': (deltaA - deltaB).abs()};
}

/// Aynı saatlerin aylık ortalama karbon yoğunluğu (yükten bağımsız); year verilirse o yıl.
Map<String, Object?> seasonProfile(DataStore data, List<int> sourceHours, List<int> targetHours,
    [String kind = 'tCO2', int? year]) {
  final byMonth = <String, List<(double, double)>>{};
  for (final date in data.allDates()) {
    if (year != null && !date.startsWith('$year-')) continue;
    final ci = data.ci24(date, kind);
    var s = 0.0;
    for (final h in sourceHours) {
      s += ci[h];
    }
    var t = 0.0;
    for (final h in targetHours) {
      t += ci[h];
    }
    byMonth.putIfAbsent(date.substring(0, 7), () => []).add((s / sourceHours.length, t / targetHours.length));
  }
  final months = <Map<String, Object?>>[];
  for (final month in byMonth.keys.toList()..sort()) {
    final vals = byMonth[month]!;
    var s = 0.0, t = 0.0;
    for (final v in vals) {
      s += v.$1;
    }
    for (final v in vals) {
      t += v.$2;
    }
    final src = s / vals.length, tgt = t / vals.length;
    months.add({
      'month': month,
      'source_ci_avg': src,
      'target_ci_avg': tgt,
      'diff_pct': (tgt - src) / src * 100,
    });
  }
  final better = [for (final m in months) if ((m['diff_pct'] as double) < 0) m];
  var best = months.first, worst = months.first;
  for (final m in months) {
    if ((m['diff_pct'] as double) < (best['diff_pct'] as double)) best = m;
    if ((m['diff_pct'] as double) > (worst['diff_pct'] as double)) worst = m;
  }
  return {
    'months': months,
    'better_month_count': better.length,
    'worse_month_count': months.length - better.length,
    'best_month': best['month'],
    'best_month_diff_pct': best['diff_pct'],
    'worst_month': worst['month'],
    'worst_month_diff_pct': worst['diff_pct'],
  };
}
