// Tesis günlük planı: bir günde her kaydırılabilir makine için en temiz hedef pencere
// (EXE 1.1.3 engine/plan.py satır satır).
//
// Formül değişmez: her makine için simulate()/scanWindows() kullanılır. Planlayıcı yalnızca hangi hedef
// pencerenin seçileceğine karar verir:
//   1. Makineler, kendi başlarına elde edebilecekleri en büyük azaltıma göre büyükten küçüğe sıralanır.
//   2. Her makine için hedefler S'ye göre (eşitlikte küçük t) denenir; isteğe bağlı saatlik tepe yük sınırı
//      aşılıyorsa sonraki hedefe geçilir. Uygun hedef yoksa makine standart penceresinde kalır.
// Tesis yük profili kaydırılamayan makineleri de içerir (tepe yük hesabı için); kaydırılan enerji korunur.

// ignore_for_file: non_constant_identifier_names

import 'dart:math' as math;

import 'best_window.dart';
import 'core.dart';
import 'data.dart';
import 'insights.dart';

// Satır durumları
const String planned = 'planned'; // daha temiz bir hedefe kaydırıldı
const String keep = 'keep'; // daha temiz saat yok / sınır nedeniyle standartta kaldı
const String planNonShiftable = 'non_shiftable';
const String noData = 'no_data'; // bu gün makine verisi yok
const String excluded = 'excluded'; // kullanıcı plana dahil etmedi
const String planNoLoad = 'no_load'; // standart pencerede yük yok

class MachineSetting {
  MachineSetting(this.s, this.L, [this.p = 1.0, this.include = true]);
  int? s; // null: otomatik (makinenin o gün en çok emisyon ürettiği pencere)
  int L;
  double p;
  bool include;
}

/// O gün en yüksek emisyonlu L saatlik pencerenin başlangıcı (eşitlikte küçük s); yük yoksa null.
int? heaviestWindow(List<double> load, List<double> ci, int L, [double p = 1.0]) {
  int? best;
  var bestB = 0.0;
  for (var s = 0; s < hours - L + 1; s++) {
    var b = 0.0;
    for (var i = 0; i < L; i++) {
      b += p * load[s + i] * ci[s + i];
    }
    if (b > bestB + 1e-12) {
      best = s;
      bestB = b;
    }
  }
  return best;
}

class PlanRow {
  PlanRow(this.assetId, this.name, this.status);
  final String assetId;
  final String name;
  String status;
  int s = 0;
  int L = 0;
  double p = 1.0;
  int? t;
  Result? result;
  (double, double)? renewable; // kaydırılan enerjinin yenilenebilir payı (standart, hedef)
  (double, double)? fossil; // (B_fosil, S_fosil)
  String note = '';
  double dailyKg = 0.0;

  double get deltaKg {
    final r = result;
    return r != null ? r.scenarioKg - r.baselineKg : 0.0;
  }
}

class FacilityPlan {
  FacilityPlan(this.date, this.kind, {required this.ci, this.peakLimit});
  final String date;
  final String kind;
  final List<PlanRow> rows = [];
  final List<double> before = List<double>.filled(hours, 0.0); // tesis saatlik yükü (kWh)
  List<double> after = List<double>.filled(hours, 0.0);
  final List<double> ci;
  final double? peakLimit;

  bool _counted(PlanRow r) => r.result != null && (r.status == planned || r.status == keep);

  double _sum(double Function(Result) f) {
    var out = 0.0;
    for (final r in rows) {
      if (_counted(r)) out += f(r.result!);
    }
    return out;
  }

  double get baselineKg => _sum((r) => r.baselineKg);
  double get scenarioKg => _sum((r) => r.scenarioKg);
  double get shiftedKwh => _sum((r) => r.shiftedKwh);
  double get deltaKg => scenarioKg - baselineKg;

  double? get deltaPct {
    final b = baselineKg;
    return b > 0 ? deltaKg / b * 100 : null;
  }

  /// Plandaki günün tesis toplam emisyonu (verisi olan tüm makineler, kaydırma öncesi).
  double get dailyKg {
    var out = 0.0;
    for (final r in rows) {
      if (r.status != noData) out += r.dailyKg;
    }
    return out;
  }

  double? get dailyDeltaPct {
    final d = dailyKg;
    return d > 0 ? deltaKg / d * 100 : null;
  }

  double? get fossilDeltaPct {
    var b = 0.0, sc = 0.0;
    for (final r in rows) {
      if (r.fossil != null && (r.status == planned || r.status == keep)) b += r.fossil!.$1;
    }
    for (final r in rows) {
      if (r.fossil != null && (r.status == planned || r.status == keep)) sc += r.fossil!.$2;
    }
    return b > 0 ? (sc - b) / b * 100 : null;
  }

  double get peakBefore => before.isEmpty ? 0.0 : before.reduce(math.max);
  double get peakAfter => after.isEmpty ? 0.0 : after.reduce(math.max);
  int get plannedCount => rows.where((r) => r.status == planned).length;
}

(double, double)? _renewable(DataStore data, String date, List<double> load, int s, int L, int t, double p) {
  final ren = [for (var h = 0; h < hours; h++) data.mixAt(date, h).renewablePct];
  final e = [for (var i = 0; i < L; i++) p * load[s + i]];
  var tot = 0.0;
  for (final v in e) {
    tot += v;
  }
  if (tot <= 0) return null;
  var a = 0.0, b = 0.0;
  for (var i = 0; i < L; i++) {
    a += e[i] * ren[s + i];
  }
  for (var i = 0; i < L; i++) {
    b += e[i] * ren[t + i];
  }
  return (a / tot, b / tot);
}

List<double> _shift(List<double> profile, List<double> load, int s, int L, int t, double p) {
  final out = List<double>.of(profile);
  for (var i = 0; i < L; i++) {
    final e = p * load[s + i];
    out[s + i] -= e;
    out[t + i] += e;
  }
  return out;
}

double _max(List<double> v) => v.reduce(math.max);

/// settings: kaydırılabilir makine id → ayar. Ayarı olmayan kaydırılabilir makine dahil edilmez.
FacilityPlan facilityPlan(DataStore data, String date, Map<String, MachineSetting> settings,
    {Set<int> restricted = const {}, String kind = 'tCO2', double? peakLimit}) {
  final plan = FacilityPlan(date, kind,
      ci: data.ci24(date, kind), peakLimit: (peakLimit == null || peakLimit == 0) ? null : peakLimit);
  final ci = plan.ci, cif = data.ciFossil24(date, kind);
  // (azaltım potansiyeli, satır, yük, tarama sonucu, standart sonuç)
  final candidates = <(double, PlanRow, List<double>, List<(int, Result)>, Result)>[];
  for (final m in data.machines()) {
    final row = PlanRow(m.id, m.name, noData);
    plan.rows.add(row);
    if (!m.days.contains(date)) {
      row.note = 'Bu gün için makine verisi yok';
      continue;
    }
    final load = data.load24(m.id, date);
    var daily = 0.0;
    for (var h = 0; h < hours; h++) {
      daily += load[h] * ci[h];
    }
    row.dailyKg = daily;
    for (var h = 0; h < hours; h++) {
      plan.before[h] += load[h];
    }
    if (!m.shiftable) {
      row.status = planNonShiftable;
      row.note = 'Sürekli/kısıtlı süreç; kaydırılamaz';
      continue;
    }
    final st = settings[m.id];
    if (st == null || !st.include) {
      row.status = excluded;
      row.note = 'Plana dahil edilmedi';
      continue;
    }
    row.L = st.L;
    row.p = st.p;
    if (st.s == null) {
      final hs = heaviestWindow(load, ci, st.L, st.p);
      if (hs == null) {
        row.s = 0;
        row.status = planNoLoad;
        row.note = 'Bu gün makinede yük yok';
        continue;
      }
      row.s = hs;
    } else {
      row.s = st.s!;
    }
    if (row.s + row.L > hours) {
      row.status = keep;
      row.note = 'Pencere gün dışına taşıyor';
      continue;
    }
    final cands = scanWindows(load, ci, row.s, row.L, row.p, restricted: restricted, shiftable: true)
      ..sort((a, b) {
        final c = a.$2.scenarioKg.compareTo(b.$2.scenarioKg);
        return c != 0 ? c : a.$1.compareTo(b.$1);
      });
    if (cands.isEmpty) {
      row.status = planNoLoad;
      row.note = 'Standart pencerede yük yok veya tüm hedefler kısıtlı';
      continue;
    }
    final base = simulate(load, ci, row.s, row.L, row.s, row.p, shiftable: true);
    final potential = base.baselineKg - cands.first.$2.scenarioKg;
    candidates.add((potential, row, load, cands, base));
  }

  plan.after = List<double>.of(plan.before);
  final limit = plan.peakLimit;
  candidates.sort((a, b) {
    final c = b.$1.compareTo(a.$1); // büyük potansiyel önce
    return c != 0 ? c : a.$2.assetId.compareTo(b.$2.assetId);
  });
  for (final (_, row, load, cands, base) in candidates) {
    (int, Result, List<double>)? chosen;
    for (final (t, r) in cands) {
      if (r.scenarioKg >= r.baselineKg) break; // bundan sonrası standarttan temiz değil
      final trial = _shift(plan.after, load, row.s, row.L, t, row.p);
      if (limit == null || _max(trial) <= limit + 1e-9 || _max(trial) <= _max(plan.after) + 1e-9) {
        chosen = (t, r, trial);
        break;
      }
    }
    if (chosen == null) {
      row.status = keep;
      row.t = row.s;
      row.result = base;
      final better = cands.first.$2.scenarioKg < cands.first.$2.baselineKg;
      row.note = (better && limit != null)
          ? 'Tepe yük sınırı nedeniyle standart pencerede kaldı'
          : 'Standart pencereden daha temiz saat yok';
    } else {
      final (t, r, trial) = chosen;
      plan.after = trial;
      row.status = planned;
      row.t = t;
      row.result = r;
      if (t != cands.first.$1) {
        row.note = 'Tepe yük sınırı nedeniyle sınırı aşmayan en temiz pencere seçildi';
      }
    }
    row.renewable = _renewable(data, date, load, row.s, row.L, row.t!, row.p);
    final (bf, sf, _) = fossilSensitivity(load, cif, row.s, row.L, row.t!, row.p);
    row.fossil = (bf, sf);
  }
  return plan;
}

Map<String, MachineSetting> defaultSettings(DataStore data, int? s, int L, double p) =>
    {for (final m in data.machines()) if (m.shiftable) m.id: MachineSetting(s, L, p)};

/// Kaydırılmayan makinelerin nedenlerine göre sayısı (ekrandaki açıklama için).
Map<String, int> reasonCounts(FacilityPlan p) {
  final out = <String, int>{};
  for (final r in p.rows) {
    if (r.status == keep || r.status == planNoLoad) out[r.note] = (out[r.note] ?? 0) + 1;
  }
  return out;
}
