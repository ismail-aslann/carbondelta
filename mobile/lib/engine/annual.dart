// Yıllık etki: aynı senaryo bir yılın tüm günlerinde uygulanırsa toplam emisyon değişimi
// (EXE 1.1.3 engine/annual.py satır satır).
//
// Formül değişmez: her gün simulate() ile hesaplanır, yalnızca B, S ve günlük emisyon toplanır.
// Yıllık değişim = (ΣS − ΣB) / ΣB × 100; yıllık günlük etki = (ΣS − ΣB) / Σ günlük emisyon × 100.
// Durumu "ok" olmayan günler (yük yok, kısıtlı vb.) toplama girmez ve ayrıca sayılır.
//
// Yenilenebilir pay: kaydırılan enerjinin, tüketildiği saatteki şebeke yenilenebilir payıyla ağırlıklı
// ortalaması (standart ve hedef pencere için ayrı).
// Tesis geneli (all): aynı kaydırma tüm kaydırılabilir makinelere uygulanır, sonuçlar toplanır.
// Fosil marjinal duyarlılık: aynı günler ve pencereler, saatlik yoğunluk yerine yalnızca fosil
// santrallerin yoğunluğu (ciFossil24) ile; ana sonuca alternatif bir alt sınır göstergesidir.

// ignore_for_file: non_constant_identifier_names

import 'core.dart';
import 'data.dart';

/// Tesis geneli: tüm kaydırılabilir makineler.
const String all = '__tesis__';

class MonthTotal {
  MonthTotal(this.month);
  final int month; // 1..12
  int days = 0;
  double baselineKg = 0.0;
  double scenarioKg = 0.0;

  double get deltaKg => scenarioKg - baselineKg;
  double? get deltaPct => baselineKg > 0 ? deltaKg / baselineKg * 100 : null;
}

/// Bir günün yıllık hesap girdisi: (tarih, yük, CI, yenilenebilir %, fosil marjinal CI).
typedef DaySeries = ({String date, List<double> load, List<double> ci, List<double> ren, List<double> ciFossil});

class AnnualResult {
  AnnualResult(this.assetId, this.year, this.s, this.L, this.t, this.p, {this.daysTotal = 0});

  final String assetId;
  final int year;
  final int s;
  final int L;
  final int t;
  final double p;
  int daysTotal; // makinenin o yıldaki gün sayısı
  int daysOk = 0; // toplama giren günler
  final Map<String, int> statusCounts = {};
  double shiftedKwh = 0.0;
  double baselineKg = 0.0; // ΣB
  double scenarioKg = 0.0; // ΣS
  double dailyKg = 0.0; // toplama giren günlerin toplam emisyonu
  int betterDays = 0; // S < B
  int worseDays = 0; // S > B
  (String, double)? bestDay; // (tarih, değişim %) en çok düşüren gün
  (String, double)? worstDay;
  final List<MonthTotal> months = [for (var m = 1; m <= 12; m++) MonthTotal(m)];
  double renSourceKwh = 0.0; // kaydırılan enerjinin standart pencerede yenilenebilir karşılığı
  double renTargetKwh = 0.0; // aynı enerjinin hedef pencerede yenilenebilir karşılığı
  final List<AnnualResult> parts = []; // tesis genelinde makine sonuçları
  double fossilBaselineKg = 0.0; // ΣB_fosil
  double fossilScenarioKg = 0.0; // ΣS_fosil

  double get fossilDeltaKg => fossilScenarioKg - fossilBaselineKg;
  double? get fossilDeltaPct => fossilBaselineKg > 0 ? fossilDeltaKg / fossilBaselineKg * 100 : null;
  bool get isFacility => assetId == all;
  double? get renSourcePct => shiftedKwh > 0 ? renSourceKwh / shiftedKwh * 100 : null;
  double? get renTargetPct => shiftedKwh > 0 ? renTargetKwh / shiftedKwh * 100 : null;
  double get deltaKg => scenarioKg - baselineKg;
  double? get deltaPct => baselineKg > 0 ? deltaKg / baselineKg * 100 : null;
  double? get dailyDeltaPct => dailyKg > 0 ? deltaKg / dailyKg * 100 : null;
}

List<String> facilityMachines(DataStore data) => [for (final m in data.machines()) if (m.shiftable) m.id];

List<int> yearsFor(DataStore data, String assetId) {
  final ids = assetId == all ? facilityMachines(data) : [assetId];
  final years = <int>{
    for (final a in ids)
      for (final d in data.daysFor(a)) int.parse(d.substring(0, 4)),
  };
  return years.toList()..sort();
}

/// Parametrik modda yük her saat sabit kWh.
List<DaySeries> yearSeries(DataStore data, String assetId, int year, String kind, [double? parametricKwh]) {
  final prefix = '${year.toString().padLeft(4, '0')}-';
  final out = <DaySeries>[];
  for (final d in data.daysFor(assetId)) {
    if (d.startsWith(prefix)) {
      final (load, ci) = data.scenarioSeries(assetId, d, kind: kind, parametricKwh: parametricKwh);
      out.add((
        date: d,
        load: load,
        ci: ci,
        ren: [for (var h = 0; h < hours; h++) data.mixAt(d, h).renewablePct],
        ciFossil: data.ciFossil24(d, kind),
      ));
    }
  }
  return out;
}

AnnualResult annualImpact(DataStore data, String assetId, int year, int s, int L, int t, double p,
    {Set<int> restricted = const {}, String kind = 'tCO2', List<DaySeries>? series}) {
  final shiftable = data.machine(assetId).shiftable;
  final days = series ?? yearSeries(data, assetId, year, kind);
  final out = AnnualResult(assetId, year, s, L, t, p, daysTotal: days.length);
  for (final day in days) {
    final load = day.load, ren = day.ren, cif = day.ciFossil;
    final r = simulate(load, day.ci, s, L, t, p, restricted: restricted, shiftable: shiftable);
    out.statusCounts[r.status] = (out.statusCounts[r.status] ?? 0) + 1;
    if (r.status != ok) continue;
    out.daysOk += 1;
    out.shiftedKwh += r.shiftedKwh;
    out.baselineKg += r.baselineKg;
    out.scenarioKg += r.scenarioKg;
    out.dailyKg += r.dailyKg;
    for (var i = 0; i < L; i++) {
      final e = p * load[s + i];
      out.renSourceKwh += e * ren[s + i] / 100;
      out.renTargetKwh += e * ren[t + i] / 100;
      out.fossilBaselineKg += e * cif[s + i];
      out.fossilScenarioKg += e * cif[t + i];
    }
    final m = out.months[int.parse(day.date.substring(5, 7)) - 1];
    m.days += 1;
    m.baselineKg += r.baselineKg;
    m.scenarioKg += r.scenarioKg;
    if (r.scenarioKg < r.baselineKg) {
      out.betterDays += 1;
    } else if (r.scenarioKg > r.baselineKg) {
      out.worseDays += 1;
    }
    final d = r.deltaPct!;
    if (out.bestDay == null || d < out.bestDay!.$2) out.bestDay = (day.date, d);
    if (out.worstDay == null || d > out.worstDay!.$2) out.worstDay = (day.date, d);
  }
  return out;
}

/// Sıralama anahtarı: en düşük ΣS, eşitlikte küçük t.
int _byScenario(AnnualResult a, AnnualResult b) {
  final c = a.scenarioKg.compareTo(b.scenarioKg);
  return c != 0 ? c : a.t.compareTo(b.t);
}

/// Yıl boyunca sabit tutulacak her hedef saat için yıllık sonuç; en düşük ΣS (eşitlikte küçük t) önce.
/// Toplama hiç gün girmeyen hedefler (kısıtlı saat, aralık dışı) listelenmez.
List<AnnualResult> bestAnnualTarget(DataStore data, String assetId, int year, int s, int L, double p,
    {Set<int> restricted = const {}, String kind = 'tCO2'}) {
  final series = yearSeries(data, assetId, year, kind);
  final results = [
    for (var t = 0; t < hours - L + 1; t++)
      annualImpact(data, assetId, year, s, L, t, p, restricted: restricted, kind: kind, series: series),
  ];
  return [for (final r in results) if (r.daysOk > 0) r]..sort(_byScenario);
}

/// Tesis geneli: aynı kaydırma her kaydırılabilir makineye; gün sayıları makine-gün olarak toplanır.
AnnualResult facilityImpact(DataStore data, int year, int s, int L, int t, double p,
    {Set<int> restricted = const {},
    String kind = 'tCO2',
    Map<String, List<DaySeries>>? seriesByAsset,
    double? parametricKwh}) {
  final out = AnnualResult(all, year, s, L, t, p);
  for (final a in facilityMachines(data)) {
    final series = seriesByAsset?[a] ?? yearSeries(data, a, year, kind, parametricKwh);
    if (series.isEmpty) continue;
    final r = annualImpact(data, a, year, s, L, t, p, restricted: restricted, kind: kind, series: series);
    out.parts.add(r);
    out.daysTotal += r.daysTotal;
    out.daysOk += r.daysOk;
    r.statusCounts.forEach((k, v) => out.statusCounts[k] = (out.statusCounts[k] ?? 0) + v);
    out.shiftedKwh += r.shiftedKwh;
    out.baselineKg += r.baselineKg;
    out.scenarioKg += r.scenarioKg;
    out.dailyKg += r.dailyKg;
    out.renSourceKwh += r.renSourceKwh;
    out.renTargetKwh += r.renTargetKwh;
    out.betterDays += r.betterDays;
    out.worseDays += r.worseDays;
    out.fossilBaselineKg += r.fossilBaselineKg;
    out.fossilScenarioKg += r.fossilScenarioKg;
    for (var k = 0; k < 12; k++) {
      final mo = out.months[k], mr = r.months[k];
      mo.days += mr.days;
      mo.baselineKg += mr.baselineKg;
      mo.scenarioKg += mr.scenarioKg;
    }
  }
  return out;
}

/// Ekran için: o kapsam ve yılda tüm hedeflerin yıllık sonuçları (geçerli olanlar, en temiz önce).
List<AnnualResult> rankTargets(List<AnnualResult> results) =>
    [for (final r in results) if (r.daysOk > 0) r]..sort(_byScenario);
