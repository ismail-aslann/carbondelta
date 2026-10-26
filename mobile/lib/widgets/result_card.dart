// Sonuç kartı (MainWindow._build_result_card / _update_card).

import 'package:flutter/material.dart';

import '../engine/core.dart' as core;
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
      verdict = statusMessage(r, c.inputs.restricted.toSet());
    }
    final text = resultExplanation(c);
    final computed = r.status == core.ok || r.status == core.sameWindow || r.status == core.noLoad;
    final rows = <(String, String)>[
      ('Standart pencere emisyonu', computed ? '${fmt.num(r.baselineKg)} $unit' : '—'),
      ('Seçilen pencere emisyonu', computed ? '${fmt.num(r.scenarioKg)} $unit' : '—'),
      ('Kaydırılan enerji', computed ? '${fmt.num(r.shiftedKwh)} kWh' : '—'),
      ('Günlük etki', fmt.pct(r.dailyDeltaPct)),
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
          for (final (k, v) in rows)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(
                children: [
                  Expanded(child: th.Muted(k)),
                  Text(v, style: const TextStyle(fontWeight: FontWeight.w600)),
                ],
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
}
