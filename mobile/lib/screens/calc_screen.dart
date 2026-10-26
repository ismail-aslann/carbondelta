// Hesabı Göster sekmesi (desktop/tabs.py CalcTab): özet, saat saat döküm,
// formül, ETKB tablosu, CSV dışa aktarma.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../engine/core.dart' as core;
import '../engine/explain.dart';
import '../state/app_state.dart';
import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;

const Map<String, String> windowLabels = {'standard': 'Standart', 'scenario': 'Seçilen'};
const Map<String, String> statusLabels = {
  'ok': 'Tamam',
  'non_shiftable': 'Kaydırılamaz',
  'out_of_range': 'Aralık dışı',
  'restricted_conflict': 'Kısıtlı saat',
  'same_window': 'Aynı pencere',
  'no_load': 'Yük yok',
};

/// CSV için tam hassasiyet, Türkçe Excel uyumlu ondalık virgül.
String _raw(double? v) => v == null ? '' : v.toString().replaceAll('.', ',');

String _csvField(Object? v) {
  final s = (v ?? '').toString();
  if (s.contains(';') || s.contains('"') || s.contains('\n') || s.contains('\r')) {
    return '"${s.replaceAll('"', '""')}"';
  }
  return s;
}

/// Hesabı Göster tablosunu ve özet değerleri CSV'ye yazar (UTF-8 BOM, ';' ayraç).
String exportCalcCsv(Computation c, String sourceLabel) {
  final i = c.inputs;
  final r = c.result;
  final rows = breakdown(c.load, c.ci, r, i.p);
  final out = <List<Object?>>[
    ['CarbonDelta hesap dökümü'],
    ['Makine', c.machine.name, 'Kod', i.assetId, 'Gün', fmt.date(i.date), 'Mod',
      i.parametric ? 'Parametrik' : 'Ölçülen yük', 'Emisyon tipi', i.ciKind],
    ['Standart başlangıç', i.s, 'Uzunluk', i.L, 'Hedef başlangıç', i.t, 'Kaydırma oranı',
      _raw(i.p), 'Kısıtlı saatler', i.restricted.join(',')],
    [],
    ['Pencere', 'Saat', 'Yükün geldiği saat', 'Taşınan enerji (kWh)', 'Karbon yoğunluğu (t/MWh)', 'Emisyon (kg)'],
    for (final row in rows)
      [windowLabels[row.window], row.hour, row.fromHour, _raw(row.kwh), _raw(row.ci), _raw(row.kg)],
    [],
    ['Durum', statusLabels[r.status] ?? r.status],
    ['B (kg)', _raw(r.baselineKg)],
    ['S (kg)', _raw(r.scenarioKg)],
    ['Değişim (%)', _raw(r.deltaPct)],
    ['Günlük emisyon (kg)', _raw(r.dailyKg)],
    ['Günlük etki (%)', _raw(r.dailyDeltaPct)],
    [],
    [sourceLabel],
  ];
  return '﻿${out.map((r) => r.map(_csvField).join(';')).join('\r\n')}\r\n';
}

const String _formulaIntro =
    'Seçilen gün için her saatin şebeke karbon yoğunluğu (EPİAŞ 2025 üretimi × ETKB 2023 katsayıları) '
    've makinenin o saatteki tüketimi kullanılır. ';

class CalcScreen extends StatelessWidget {
  const CalcScreen({super.key, required this.app});
  final AppState app;

  Future<void> _export(BuildContext context) async {
    final c = app.current;
    final i = c.inputs;
    final name =
        'carbondelta_${i.assetId}_${i.date}_${i.s.toString().padLeft(2, '0')}-${i.t.toString().padLeft(2, '0')}.csv';
    try {
      final dir = await getTemporaryDirectory();
      final f = File('${dir.path}${Platform.pathSeparator}$name');
      await f.writeAsString(exportCalcCsv(c, app.data.sourceLabel(i.assetId, i.date)));
      await SharePlus.instance.share(ShareParams(files: [XFile(f.path)], subject: name));
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Dosya yazılamadı:\n$e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        final c = app.current;
        final i = c.inputs;
        final r = c.result;
        final unit = i.ciKind == 'tCO2' ? 'tCO2/MWh' : 'tCO2-eşd/MWh';
        final kg = i.ciKind == 'tCO2' ? 'kgCO2' : 'kgCO2-eşd';
        final mode = i.parametric ? 'sabit ${fmt.num(i.paramKwh)} kWh/saat' : 'ölçülen yük';
        final rows = breakdown(c.load, c.ci, r, i.p);
        final computed = rows.isNotEmpty;
        var color = th.text;
        if (r.status == core.ok) color = r.deltaPct! <= 0 ? th.good : th.bad;
        final stats = <(String, String, Color)>[
          ('Standart emisyon (B)', computed ? '${fmt.num(r.baselineKg)} $kg' : '—', th.text),
          ('Seçilen emisyon (S)', computed ? '${fmt.num(r.scenarioKg)} $kg' : '—', th.text),
          ('Değişim (S − B) / B', fmt.pct(r.deltaPct), color),
          ('Günlük etki', fmt.pct(r.dailyDeltaPct), th.text),
        ];
        final etkb = app.data.etkbFactors();
        return ListView(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
          children: [
            Text(
              '${c.machine.name} · ${fmt.date(i.date)} · ${fmt.window(i.s, i.L)} → ${fmt.window(i.t, i.L)} · '
              '%${fmt.num(i.p * 100, 0)} · $mode',
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerLeft,
              child: OutlinedButton.icon(
                onPressed: () => _export(context),
                icon: const Icon(Icons.ios_share, size: 18),
                label: const Text('CSV olarak dışa aktar'),
              ),
            ),
            const SizedBox(height: 8),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: 2.1,
              children: [
                for (final (t, v, col) in stats)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          th.Muted(t, size: 12),
                          const SizedBox(height: 2),
                          FittedBox(
                            child: Text(v,
                                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: col)),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            th.SectionCard(
              title: 'Saat saat döküm',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  th.Muted(computed
                      ? 'Günlük toplam emisyon ${fmt.num(r.dailyKg)} $kg. Seçilen satırlardaki enerji, '
                          'aynı sıradaki standart saatten taşınır.'
                      : 'Bu senaryoda hesap yapılmadı (durum: ${statusLabels[r.status] ?? r.status}).'),
                  const SizedBox(height: 6),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: DataTable(
                      headingRowHeight: 40,
                      dataRowMinHeight: 34,
                      dataRowMaxHeight: 38,
                      columnSpacing: 16,
                      headingTextStyle:
                          const TextStyle(color: th.muted, fontWeight: FontWeight.w600, fontSize: 12.5),
                      columns: [
                        const DataColumn(label: Text('Pencere')),
                        const DataColumn(label: Text('Saat')),
                        const DataColumn(label: Text('Yükün geldiği saat')),
                        const DataColumn(label: Text('Taşınan enerji (kWh)'), numeric: true),
                        DataColumn(label: Text('Yoğunluk ($unit)'), numeric: true),
                        const DataColumn(label: Text('Emisyon (kg)'), numeric: true),
                      ],
                      rows: [
                        for (final row in rows)
                          DataRow(cells: [
                            DataCell(Text(windowLabels[row.window]!)),
                            DataCell(Text(fmt.hour(row.hour))),
                            DataCell(Text(fmt.hour(row.fromHour))),
                            DataCell(Text(fmt.num(row.kwh))),
                            DataCell(Text(fmt.num(row.ci, 6))),
                            DataCell(Text(fmt.num(row.kg))),
                          ]),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            const th.SectionCard(
              title: 'Hesap nasıl yapılıyor?',
              child: _FormulaText(),
            ),
            const SizedBox(height: 10),
            th.SectionCard(
              title: 'ETKB 2023 emisyon faktörleri',
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: DataTable(
                  headingRowHeight: 38,
                  dataRowMinHeight: 30,
                  dataRowMaxHeight: 34,
                  columnSpacing: 18,
                  headingTextStyle:
                      const TextStyle(color: th.muted, fontWeight: FontWeight.w600, fontSize: 12.5),
                  columns: const [
                    DataColumn(label: Text('Kaynak')),
                    DataColumn(label: Text('tCO2/MWh'), numeric: true),
                    DataColumn(label: Text('tCO2-eşd/MWh'), numeric: true),
                  ],
                  rows: [
                    for (final e in etkb)
                      DataRow(cells: [
                        DataCell(Text(e.name)),
                        DataCell(Text(e.tco2.replaceAll('.', ','))),
                        DataCell(Text(e.tco2esd.replaceAll('.', ','))),
                      ]),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _FormulaText extends StatelessWidget {
  const _FormulaText();

  @override
  Widget build(BuildContext context) {
    const b = TextStyle(fontWeight: FontWeight.w700);
    const i = TextStyle(fontStyle: FontStyle.italic);
    Widget step(String n, List<InlineSpan> spans) => Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(width: 20, child: Text(n, style: b)),
            Expanded(child: Text.rich(TextSpan(children: spans))),
          ]),
        );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text.rich(TextSpan(children: [
          TextSpan(text: _formulaIntro),
          TextSpan(text: 'Hesapta yapay zekâ yoktur.', style: b),
        ])),
        const SizedBox(height: 8),
        step('1.', const [
          TextSpan(text: 'Taşınan enerji', style: b),
          TextSpan(text: ' — standart penceredeki her saat için '),
          TextSpan(text: 'E = kaydırma oranı × o saatin tüketimi', style: i),
          TextSpan(text: ' (kWh)'),
        ]),
        step('2.', const [
          TextSpan(text: 'Standart emisyon (B)', style: b),
          TextSpan(text: ' — her E × kendi saatinin karbon yoğunluğu, toplamı'),
        ]),
        step('3.', const [
          TextSpan(text: 'Seçilen emisyon (S)', style: b),
          TextSpan(text: ' — aynı E × hedef penceredeki karşılık gelen saatin karbon yoğunluğu, toplamı'),
        ]),
        step('4.', const [
          TextSpan(text: 'Değişim', style: b),
          TextSpan(text: ' = (S − B) / B × 100 — eksi değer daha düşük emisyon potansiyeli demektir'),
        ]),
        step('5.', const [
          TextSpan(text: 'Günlük etki', style: b),
          TextSpan(text: ' = (S − B) / makinenin o günkü toplam emisyonu × 100'),
        ]),
        const SizedBox(height: 4),
        const th.Muted('Birim: tCO2/MWh = kgCO2/kWh. İç hesap tam hassasiyetle yapılır; yalnızca ekranda yuvarlanır.'),
      ],
    );
  }
}
