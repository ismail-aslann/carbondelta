// Tesis Planı: kaynak etiketi ve CSV (desktop/plan_tab.py plan_source, export_plan_csv).

import '../engine/data.dart';
import '../engine/plan.dart' as pl;
import '../ui/csv.dart';
import '../ui/fmt.dart' as fmt;

(String, bool) planSource(DataStore data, pl.FacilityPlan p) {
  final ids = [for (final r in p.rows) if (r.status != pl.noData) r.assetId];
  if (ids.isEmpty) return (data.gridLabel(p.date), false);
  final reals = [for (final a in ids) data.isReal(a)];
  if (reals.every((x) => x) || !reals.any((x) => x)) {
    return (data.sourceLabel(ids.first, p.date), reals.every((x) => x));
  }
  return (
    'Tesis planı: tesis ölçümü ve örnek yük birlikte · Kaynak: ${data.gridLabel(p.date)}, ${data.factorsLabel()}',
    false,
  );
}

/// Tesis planı (UTF-8 BOM, ';' ayraç, tam hassasiyet).
String planCsv(DataStore data, pl.FacilityPlan p, Set<int> restricted) {
  final rows = <List<Object?>>[
    ['CarbonDelta tesis günlük planı'],
    ['Gün', fmt.date(p.date), 'Emisyon tipi', p.kind, 'Tepe sınırı (kWh)', rawNum(p.peakLimit), 'Kısıtlı saatler',
      (restricted.toList()..sort()).join(',')],
    [],
    ['Makine', 'Durum', 'Standart başlangıç', 'Uzunluk', 'Hedef başlangıç', 'Kaydırılan (kWh)', 'B (kg)', 'S (kg)',
      'Değişim (kg)', 'Değişim (%)', 'Yenilenebilir payı standart (%)', 'Yenilenebilir payı hedef (%)', 'Not'],
    for (final r in p.rows)
      [
        r.name,
        r.status,
        r.result != null ? r.s : '',
        r.result != null ? r.L : '',
        r.t ?? '',
        r.result != null ? rawNum(r.result!.shiftedKwh) : '',
        r.result != null ? rawNum(r.result!.baselineKg) : '',
        r.result != null ? rawNum(r.result!.scenarioKg) : '',
        r.result != null ? rawNum(r.deltaKg) : '',
        r.result != null ? rawNum(r.result!.deltaPct) : '',
        r.renewable != null ? rawNum(r.renewable!.$1) : '',
        r.renewable != null ? rawNum(r.renewable!.$2) : '',
        r.note,
      ],
    [],
    ['Toplam değişim (kg)', rawNum(p.deltaKg)],
    ['Kaydırılan yükte değişim (%)', rawNum(p.deltaPct)],
    ['Tesisin günlük emisyonunda (%)', rawNum(p.dailyDeltaPct)],
    ['Fosil marjinal duyarlılık (%)', rawNum(p.fossilDeltaPct)],
    ['Tepe yük önce (kWh)', rawNum(p.peakBefore)],
    ['Tepe yük sonra (kWh)', rawNum(p.peakAfter)],
    [],
    [planSource(data, p).$1],
  ];
  return csvText(rows);
}
