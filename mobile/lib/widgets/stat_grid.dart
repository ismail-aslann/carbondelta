// İkişerli özet kutucukları (desktop tabs._stat); yükseklik içeriğe göre.

import 'package:flutter/material.dart';

import '../ui/theme.dart' as th;

class Stat {
  const Stat(this.title, this.value, [this.color]);
  final String title;
  final String value;
  final Color? color;
}

class StatGrid extends StatelessWidget {
  const StatGrid(this.stats, {super.key});
  final List<Stat> stats;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var k = 0; k < stats.length; k += 2) ...[
          if (k > 0) const SizedBox(height: 8),
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(child: StatCard(stats[k])),
                const SizedBox(width: 8),
                Expanded(child: k + 1 < stats.length ? StatCard(stats[k + 1]) : const SizedBox()),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class StatCard extends StatelessWidget {
  const StatCard(this.stat, {super.key});
  final Stat stat;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            th.Muted(stat.title, size: 12),
            const SizedBox(height: 2),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(stat.value,
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: stat.color ?? th.text)),
            ),
          ],
        ),
      ),
    );
  }
}
