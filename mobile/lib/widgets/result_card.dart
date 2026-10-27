// Sonuç kartı (MainWindow._build_result_card / _update_card).

import 'package:flutter/material.dart';

import '../engine/core.dart' as core;
import '../engine/data.dart';
import '../engine/insights.dart';
import '../state/app_state.dart';
import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;

class ResultCard extends StatelessWidget {
  const ResultCard({super.key, required this.c, required this.savedLabel, required this.onSave});

  final Computation c;
  final String savedLabel;
  final VoidCallback onSave;

  @override
  Widget build(BuildContext context) {
    final r = c.result;
    final unit = c.inputs.ciKind == 'tCO2' ? 'kgCO2' : 'kgCO2-eşd';
    Color color, verdictColor;
    String deltaText, verdict;
    if (r.status == core.ok) {
      final good = r.deltaPct! <= 0;
      color = verdictColor = good ? th.good : th.bad;
      deltaText = fmt.pct(r.deltaPct);
      verdict = good ? 'Daha düşük emisyon potansiyeli' : 'Bu kaydırma emisyonu ARTIRIR';
    } else {
      color = th.muted;
      verdictColor = r.status == core.sameWindow ? th.muted : th.bad;
      deltaText = r.status == core.sameWindow ? fmt.pct(0.0) : '—';
      verdict = statusMessage(r, c.inputs.restricted.toSet(), c.inputs.p);
    }
    final text = resultExplanation(c);
    final computed = r.status == core.ok || r.status == core.sameWindow || r.status == core.noLoad;
    final i = c.inputs;
    final data = DataStore.instance;
    // EXE 1.1.1–1.1.2: kaydırılan enerjinin yenilenebilir payı ve fosil marjinal duyarlılık.
    final rs = (r.status == core.ok || r.status == core.sameWindow)
        ? shiftedRenewable(data, i.date, c.load, i.s, i.L, i.t, i.p)
        : null;
    final fp = r.status == core.ok
        ? fossilSensitivity(c.load, data.ciFossil24(i.date, i.ciKind), i.s, i.L, i.t, i.p).$3
        : null;
    final rows = <(String, String, Color?, String?)>[
      ('Standart pencere emisyonu', computed ? '${fmt.num(r.baselineKg)} $unit' : '—', null, null),
      ('Seçilen pencere emisyonu', computed ? '${fmt.num(r.scenarioKg)} $unit' : '—', null, null),
      ('Kaydırılan enerji', computed ? '${fmt.num(r.shiftedKwh)} kWh' : '—', null, null),
      ('Günlük etki', fmt.pct(r.dailyDeltaPct), null, null),
      (
        'Yenilenebilir payı (kaydırılan enerji)',
        rs == null ? '—' : '%${fmt.num(rs.$1, 1)} → %${fmt.num(rs.$2, 1)}',
        rs == null ? null : (rs.$2 >= rs.$1 ? th.good : th.bad),
        'Kaydırılan enerjinin, tüketildiği saatlerde şebekedeki yenilenebilir (rüzgâr, güneş, hidro, '
            'jeotermal, biyokütle) üretim payı: standart pencere → seçilen pencere.',
      ),
      (
        'Fosil marjinal varsayımla',
        fmt.pct(fp),
        fp == null ? null : (fp <= 0 ? th.good : th.bad),
        'Duyarlılık: kaydırılan yükü o saatlerde yalnızca fosil santrallerin karşıladığı varsayımıyla '
            'aynı hesap (marjinal santral yaklaşımı). Ana sonuç ortalama yoğunlukla hesaplanır; bu değer '
            'daha temkinli bir alt sınır gösterir.',
      ),
    ];
    return th.SectionCard(
      title: 'Sonuç',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(deltaText, style: TextStyle(fontSize: 36, fontWeight: FontWeight.w700, color: color)),
          Text(verdict, style: TextStyle(color: verdictColor, fontWeight: FontWeight.w600)),
          if (text.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(text, style: const TextStyle(color: th.text, fontSize: 13, height: 1.35)),
          ],
          const Divider(height: 20, color: th.border),
          for (final (k, v, col, tip) in rows)
            _tip(
              tip,
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    Expanded(flex: 5, child: th.Muted(k)),
                    const SizedBox(width: 8),
                    Flexible(
                      flex: 4,
                      child: Text(v,
                          textAlign: TextAlign.right,
                          style: TextStyle(fontWeight: FontWeight.w600, color: col)),
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: Text(savedLabel,
                    style: const TextStyle(color: th.good, fontWeight: FontWeight.w600)),
              ),
              FilledButton(onPressed: onSave, child: const Text('Senaryoyu kaydet')),
            ],
          ),
        ],
      ),
    );
  }

  /// Satıra dokununca açıklama görünür (masaüstündeki ipucu).
  Widget _tip(String? message, Widget child) => message == null
      ? child
      : Tooltip(message: message, triggerMode: TooltipTriggerMode.tap, showDuration: const Duration(seconds: 6), child: child);
}
