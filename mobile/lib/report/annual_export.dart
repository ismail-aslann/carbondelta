// Yıllık Etki: ortak metin yardımcıları, CSV ve tek sayfalık PDF rapor
// (desktop/annual_tab.py: mass, ren, scope_name, source_for, export_annual_csv, annual_report_html).
// PDF, `pdf` paketiyle telefonda üretilir; Türkçe karakterler için Liberation Sans gömülür.

import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

import '../ai/ai_context.dart' show monthNames;
import '../engine/annual.dart' as annual;
import '../engine/data.dart';
import '../screens/sources_screen.dart' show methodItems;
import '../ui/csv.dart';
import '../ui/fmt.dart' as fmt;

const String appName = 'CarbonDelta';
const String facilityLabel = 'Tesis geneli (tüm kaydırılabilir makineler)';

String unitFor(String kind) => kind == 'tCO2' ? 'CO2' : 'CO2-eşd';

/// 1000 kg ve üstünü ton olarak gösterir.
String mass(double kg, [String kind = 'tCO2', int digits = 2]) {
  final u = unitFor(kind);
  return kg.abs() >= 1000 ? '${fmt.num(kg / 1000, digits)} t $u' : '${fmt.num(kg, 1)} kg $u';
}

String ren(double? v) => v == null ? '—' : '%${fmt.num(v, 1)}';

String scopeName(DataStore data, annual.AnnualResult r) =>
    r.isFacility ? facilityLabel : data.machine(r.assetId).name;

/// Alt bilgi etiketi ve 'tesis ölçümü mü' bilgisi (tesis genelinde makinelerin karışımına göre).
(String, bool) sourceFor(DataStore data, annual.AnnualResult r) {
  final ids = r.isFacility ? [for (final p in r.parts) if (p.daysTotal > 0) p.assetId] : [r.assetId];
  if (ids.isEmpty) return ('', false);
  final days = data.daysFor(ids.first);
  final day = days.firstWhere((d) => d.startsWith('${r.year}'), orElse: () => days.first);
  final reals = [for (final a in ids) data.isReal(a)];
  if (reals.every((x) => x) || !reals.any((x) => x)) {
    return (data.sourceLabel(ids.first, day), reals.every((x) => x));
  }
  return (
    'Tesis geneli: tesis ölçümü ve örnek yük birlikte · Kaynak: ${data.gridLabel(day)}, ${data.factorsLabel()}',
    false,
  );
}

// ------------------------------------------------------------------ CSV
/// Yıllık özet ve aylık döküm (UTF-8 BOM, ';' ayraç, tam hassasiyet).
String annualCsv(DataStore data, annual.AnnualResult r, Set<int> restricted, [String kind = 'tCO2']) {
  final u = unitFor(kind);
  final rows = <List<Object?>>[
    ['CarbonDelta yıllık etki'],
    ['Kapsam', scopeName(data, r), 'Kod', r.assetId, 'Yıl', r.year, 'Emisyon tipi', kind],
    ['Standart başlangıç', r.s, 'Uzunluk', r.L, 'Hedef başlangıç', r.t, 'Kaydırma oranı', rawNum(r.p),
      'Kısıtlı saatler', (restricted.toList()..sort()).join(',')],
    [],
    ['Ay', 'Gün', 'Standart emisyon (kg $u)', 'Seçilen emisyon (kg $u)', 'Değişim (kg $u)', 'Değişim (%)'],
    for (final m in r.months)
      if (m.days > 0)
        [monthNames[m.month - 1], m.days, rawNum(m.baselineKg), rawNum(m.scenarioKg), rawNum(m.deltaKg),
          rawNum(m.deltaPct)],
    if (r.isFacility) ...[
      [],
      ['Makine', 'Gün', 'Değişim (kg $u)', 'Değişim (%)'],
      for (final x in r.parts) [data.machine(x.assetId).name, x.daysOk, rawNum(x.deltaKg), rawNum(x.deltaPct)],
    ],
    [],
    ['Hesaba giren gün${r.isFacility ? ' (makine-gün)' : ''}', r.daysOk, 'Toplam', r.daysTotal],
    ['Taşınan enerji (kWh)', rawNum(r.shiftedKwh)],
    ['ΣB (kg $u)', rawNum(r.baselineKg)],
    ['ΣS (kg $u)', rawNum(r.scenarioKg)],
    ['Yıllık değişim (kg $u)', rawNum(r.deltaKg)],
    ['Yıllık değişim (%)', rawNum(r.deltaPct)],
    ['Toplam emisyon içindeki pay (%)', rawNum(r.dailyDeltaPct)],
    ['Yenilenebilir payı, standart pencere (%)', rawNum(r.renSourcePct)],
    ['Yenilenebilir payı, hedef pencere (%)', rawNum(r.renTargetPct)],
    ['Fosil marjinal duyarlılık, değişim (kg $u)', rawNum(r.fossilDeltaKg)],
    ['Fosil marjinal duyarlılık, değişim (%)', rawNum(r.fossilDeltaPct)],
    [],
    [sourceFor(data, r).$1],
  ];
  return csvText(rows);
}

// ------------------------------------------------------------------ PDF
const _primary = PdfColor.fromInt(0xFF16785C);
const _primaryDark = PdfColor.fromInt(0xFF0F5B46);
const _soft = PdfColor.fromInt(0xFFE7F3EF);
const _muted = PdfColor.fromInt(0xFF6B7785);
const _text = PdfColor.fromInt(0xFF1D2733);
const _good = PdfColor.fromInt(0xFF1F9254);
const _bad = PdfColor.fromInt(0xFFD03C3C);
const _gridLine = PdfColor.fromInt(0xFF9AA5B1);

/// **kalın** işaretli metni PDF metin parçalarına çevirir (_italik_ düz yazılır; gömülü yazıda italik yok).
pw.TextSpan _rich(String s, {pw.TextStyle? style}) {
  final spans = <pw.InlineSpan>[];
  final re = RegExp(r'\*\*(.+?)\*\*|_(.+?)_');
  var last = 0;
  for (final m in re.allMatches(s)) {
    if (m.start > last) spans.add(pw.TextSpan(text: s.substring(last, m.start)));
    if (m.group(1) != null) {
      spans.add(pw.TextSpan(text: m.group(1), style: pw.TextStyle(fontWeight: pw.FontWeight.bold)));
    } else {
      spans.add(pw.TextSpan(text: m.group(2)));
    }
    last = m.end;
  }
  if (last < s.length) spans.add(pw.TextSpan(text: s.substring(last)));
  return pw.TextSpan(style: style, children: spans);
}

pw.Widget _statBox(String title, String value, [PdfColor? color]) => pw.Expanded(
      child: pw.Container(
        margin: const pw.EdgeInsets.symmetric(horizontal: 3),
        padding: const pw.EdgeInsets.all(7),
        color: _soft,
        child: pw.Column(crossAxisAlignment: pw.CrossAxisAlignment.start, children: [
          pw.Text(title, style: const pw.TextStyle(color: _muted, fontSize: 8)),
          pw.SizedBox(height: 2),
          pw.Text(value, style: pw.TextStyle(fontSize: 12.5, fontWeight: pw.FontWeight.bold, color: color ?? _text)),
        ]),
      ),
    );

/// Aylık değişim çubukları (yeşil azalma, kırmızı artış; verisi olmayan ay boş).
pw.Widget _monthChart(annual.AnnualResult r, String kind) {
  const h = 120.0;
  var lo = 0.0, hi = 0.0;
  for (final m in r.months) {
    if (m.days == 0) continue;
    if (m.deltaKg < lo) lo = m.deltaKg;
    if (m.deltaKg > hi) hi = m.deltaKg;
  }
  if (hi - lo < 1e-9) hi = 1;
  final span = hi - lo;
  final hPos = h * hi / span, hNeg = h * -lo / span;
  pw.Widget col(annual.MonthTotal m) {
    final v = m.deltaKg;
    final bar = m.days == 0 ? 0.0 : v.abs() / span * h;
    final color = v <= 0 ? _good : _bad;
    return pw.Expanded(
      child: pw.Column(children: [
        pw.SizedBox(
          height: hPos,
          child: pw.Align(
            alignment: pw.Alignment.bottomCenter,
            child: v > 0 && m.days > 0 ? pw.Container(width: 22, height: bar, color: color) : pw.SizedBox(),
          ),
        ),
        pw.Container(height: 0.6, color: _gridLine),
        pw.SizedBox(
          height: hNeg,
          child: pw.Align(
            alignment: pw.Alignment.topCenter,
            child: v <= 0 && m.days > 0 ? pw.Container(width: 22, height: bar, color: color) : pw.SizedBox(),
          ),
        ),
        pw.SizedBox(height: 3),
        pw.Text(monthNames[m.month - 1].substring(0, 3), style: const pw.TextStyle(fontSize: 7.5, color: _muted)),
        pw.Text(m.days == 0 ? 'veri yok' : fmt.num(v, 0), style: const pw.TextStyle(fontSize: 6.5, color: _muted)),
      ]),
    );
  }

  return pw.Column(crossAxisAlignment: pw.CrossAxisAlignment.stretch, children: [
    pw.Text('Aylık emisyon değişimi (kg ${unitFor(kind)})',
        textAlign: pw.TextAlign.center, style: const pw.TextStyle(fontSize: 9.5, color: _text)),
    pw.SizedBox(height: 6),
    pw.Row(crossAxisAlignment: pw.CrossAxisAlignment.start, children: [for (final m in r.months) col(m)]),
  ]);
}

Future<Uint8List> annualPdf(
  DataStore data,
  annual.AnnualResult r,
  annual.AnnualResult? best,
  Set<int> restricted,
  String kind,
  double? param, {
  String aiText = '',
  String aiSource = '',
  DateTime? now,
}) async {
  final base = pw.Font.ttf(await rootBundle.load('assets/fonts/LiberationSans-Regular.ttf'));
  final bold = pw.Font.ttf(await rootBundle.load('assets/fonts/LiberationSans-Bold.ttf'));
  final u = unitFor(kind);
  final good = r.deltaKg <= 0;
  final color = good ? _good : _bad;
  final unitDays = r.isFacility ? 'makine-gün' : 'gün';
  final t = now ?? DateTime.now();
  String two(int v) => v.toString().padLeft(2, '0');
  final stamp = '${two(t.day)}.${two(t.month)}.${t.year} ${two(t.hour)}:${two(t.minute)}';
  final conds = [
    'Standart pencere ${fmt.window(r.s, r.L)} → hedef ${fmt.window(r.t, r.L)}, kaydırma oranı %${fmt.num(r.p * 100, 0)}',
    'Emisyon tipi: $kind',
    'Kısıtlı saatler: ${restricted.isEmpty ? 'yok' : (restricted.toList()..sort()).map(fmt.hour).join(', ')}',
    if (param != null) 'Parametrik mod: her saat sabit ${fmt.num(param, 1)} kWh',
  ];
  const h3 = pw.TextStyle(fontSize: 11, color: _primaryDark);
  pw.Widget heading(String s) =>
      pw.Padding(padding: const pw.EdgeInsets.only(top: 8, bottom: 4), child: pw.Text(s, style: h3.copyWith(fontWeight: pw.FontWeight.bold)));
  final headStyle = pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 8.5);
  const cellStyle = pw.TextStyle(fontSize: 8.5);

  final theme = pw.ThemeData.withFont(base: base, bold: bold).copyWith(
    defaultTextStyle: pw.TextStyle(font: base, fontNormal: base, fontBold: bold, fontSize: 9.5, color: _text),
  );
  final doc = pw.Document(title: '$appName yıllık karbon etkisi raporu', creator: appName, theme: theme);
  doc.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4.copyWith(
      marginLeft: 14 * PdfPageFormat.mm,
      marginRight: 14 * PdfPageFormat.mm,
      marginTop: 12 * PdfPageFormat.mm,
      marginBottom: 12 * PdfPageFormat.mm,
    ),
    theme: theme,
    build: (ctx) => [
      pw.Text(appName, style: pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold, color: _primaryDark)),
      pw.Text('Yıllık karbon etkisi raporu · $stamp', style: const pw.TextStyle(color: _muted)),
      pw.SizedBox(height: 8),
      pw.Text('${scopeName(data, r)} · ${r.year}',
          style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold, color: _primary)),
      pw.SizedBox(height: 4),
      pw.Text(conds.join(' · ')),
      pw.SizedBox(height: 8),
      pw.Row(children: [
        _statBox('Yıllık emisyon değişimi', mass(r.deltaKg, kind), color),
        _statBox('Kaydırılan yükte değişim', fmt.pct(r.deltaPct), color),
        _statBox('Yenilenebilir payı', '${ren(r.renSourcePct)} → ${ren(r.renTargetPct)}'),
        _statBox('Hesaba giren $unitDays', '${r.daysOk} / ${r.daysTotal}'),
      ]),
      pw.SizedBox(height: 8),
      pw.Text('Kaydırılan ${fmt.num(r.shiftedKwh, 0)} kWh enerjinin emisyonu ${mass(r.baselineKg, kind)} yerine '
          '${mass(r.scenarioKg, kind)} olur. Makinelerin aynı günlerdeki toplam emisyonu içindeki payı '
          '${fmt.pct(r.dailyDeltaPct)}. ${r.betterDays} ${unitDays}de emisyon düştü, ${r.worseDays} ${unitDays}de arttı.'),
      pw.SizedBox(height: 4),
      pw.RichText(
          text: _rich('**Duyarlılık (fosil marjinal):** Kaydırılan yükü yalnızca fosil santrallerin karşıladığı '
              'varsayımıyla değişim ${fmt.pct(r.fossilDeltaPct)} (${mass(r.fossilDeltaKg, kind)}). Ana sonuç ortalama '
              'saatlik yoğunlukla hesaplanır; gerçek etki büyük olasılıkla bu iki değer arasındadır.')),
      if (best != null) ...[
        pw.SizedBox(height: 4),
        pw.RichText(
            text: _rich('Yıl boyunca sabit tutulabilecek en temiz hedef pencere: **${fmt.window(best.t, best.L)}** '
                '(${mass(best.deltaKg, kind)}, ${fmt.pct(best.deltaPct)}).')),
      ],
      if (aiText.isNotEmpty) ...[
        heading(aiSource == 'ai' ? 'Delti (AI) yorumu' : 'Özet (şablon metin; Delti çevrimdışıydı)'),
        pw.Text(aiText),
      ],
      pw.SizedBox(height: 10),
      _monthChart(r, kind),
      heading('Aylık döküm'),
      pw.TableHelper.fromTextArray(
        headers: ['Ay', 'Gün', 'Standart (kg $u)', 'Seçilen (kg $u)', 'Değişim (kg $u)', 'Değişim'],
        data: [
          for (final m in r.months)
            if (m.days > 0)
              [monthNames[m.month - 1], '${m.days}', fmt.num(m.baselineKg, 1), fmt.num(m.scenarioKg, 1),
                fmt.num(m.deltaKg, 1), fmt.pct(m.deltaPct)],
        ],
        headerStyle: headStyle,
        cellStyle: cellStyle,
        headerDecoration: const pw.BoxDecoration(color: _soft),
        cellAlignments: {
          0: pw.Alignment.centerLeft,
          1: pw.Alignment.center,
          2: pw.Alignment.centerRight,
          3: pw.Alignment.centerRight,
          4: pw.Alignment.centerRight,
          5: pw.Alignment.centerRight,
        },
        cellPadding: const pw.EdgeInsets.symmetric(horizontal: 4, vertical: 2.5),
      ),
      if (r.isFacility) ...[
        heading('Makine katkıları'),
        pw.TableHelper.fromTextArray(
          headers: ['Makine', 'Gün', 'Değişim (kg $u)', 'Değişim'],
          data: [
            for (final x in [for (final x in r.parts) if (x.daysOk > 0) x]
              ..sort((a, b) => a.deltaKg.compareTo(b.deltaKg)))
              [data.machine(x.assetId).name, '${x.daysOk}', fmt.num(x.deltaKg, 1), fmt.pct(x.deltaPct)],
          ],
          headerStyle: headStyle,
          cellStyle: cellStyle,
          headerDecoration: const pw.BoxDecoration(color: _soft),
          cellAlignments: {
            0: pw.Alignment.centerLeft,
            1: pw.Alignment.center,
            2: pw.Alignment.centerRight,
            3: pw.Alignment.centerRight,
          },
          cellPadding: const pw.EdgeInsets.symmetric(horizontal: 4, vertical: 2.5),
        ),
      ],
      heading('Yöntem ve sınırlılıklar'),
      for (final m in methodItems)
        pw.Padding(
          padding: const pw.EdgeInsets.only(bottom: 3),
          child: pw.Row(crossAxisAlignment: pw.CrossAxisAlignment.start, children: [
            pw.SizedBox(width: 10, child: pw.Text('•', style: const pw.TextStyle(fontSize: 8.5))),
            pw.Expanded(child: pw.RichText(text: _rich(m, style: const pw.TextStyle(fontSize: 8.5)))),
          ]),
        ),
      pw.SizedBox(height: 6),
      pw.Text(
          'Yıllık değişim = (ΣS − ΣB) / ΣB × 100. Karar destek amaçlıdır; karar kullanıcıdadır. '
          '${sourceFor(data, r).$1}',
          style: const pw.TextStyle(color: _muted, fontSize: 8.5)),
    ],
  ));
  return doc.save();
}
