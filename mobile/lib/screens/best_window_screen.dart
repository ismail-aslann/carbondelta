// En Temiz Saat sekmesi: bir gün için tüm geçerli hedef pencereleri emisyona
// göre sıralar (desktop/tools_tabs.py BestWindowTab).

// ignore_for_file: non_constant_identifier_names

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../engine/best_window.dart';
import '../engine/core.dart' as core;
import '../engine/data.dart';
import '../state/app_state.dart';
import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;
import '../widgets/inputs.dart';

class BestWindowScreen extends StatefulWidget {
  const BestWindowScreen({super.key, required this.app, required this.onApplied});

  final AppState app;
  final VoidCallback onApplied;

  @override
  State<BestWindowScreen> createState() => _BestWindowScreenState();
}

class _BestWindowScreenState extends State<BestWindowScreen> {
  late String _asset;
  late String _date;
  late int _s;
  late int _L;
  late double _p;
  late Set<int> _restricted;
  int _selected = 0;

  AppState get app => widget.app;

  List<Machine> get _machines => [for (final m in app.data.machines()) if (m.shiftable) m];

  @override
  void initState() {
    super.initState();
    _loadInputs();
  }

  /// Senaryo sekmesindeki değerlerle başlar (kaydırılamaz makinede ilk uygun makine).
  void _loadInputs() {
    final i = app.inputs;
    final ms = _machines;
    _asset = ms.any((m) => m.id == i.assetId) ? i.assetId : ms.first.id;
    _date = nearestDay(app.data.daysFor(_asset), i.date);
    _s = i.s;
    _L = i.L;
    _p = i.p;
    _restricted = i.restricted.toSet();
    _selected = 0;
  }

  Future<void> _pickDate() async {
    final m = app.data.machine(_asset);
    final valid = m.days.toSet();
    String iso(DateTime d) =>
        '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
    final picked = await showDatePicker(
      context: context,
      initialDate: DateTime.parse(_date),
      firstDate: DateTime.parse(m.firstDay),
      lastDate: DateTime.parse(m.lastDay),
      selectableDayPredicate: (d) => valid.contains(iso(d)),
    );
    if (picked != null) {
      setState(() {
        _date = nearestDay(m.days, iso(picked));
        _selected = 0;
      });
    }
  }

  void _apply(List<(int, core.Result)> ranked, int row) {
    if (row < 0 || row >= ranked.length) return;
    final t = ranked[row].$1;
    final cur = app.inputs;
    app.setInputs(ScenarioInputs(
      assetId: _asset, date: _date, s: _s, L: _L, t: t, p: _p,
      restricted: cur.restricted, ciKind: cur.ciKind,
    ));
    widget.onApplied();
  }

  @override
  Widget build(BuildContext context) {
    final ms = _machines;
    final (load, ci) = app.data.scenarioSeries(_asset, _date);
    final cands = scanWindows(load, ci, _s, _L, _p, restricted: _restricted, shiftable: true);
    final ranked = [...cands]
      ..sort((a, b) {
        final c = a.$2.scenarioKg.compareTo(b.$2.scenarioKg);
        return c != 0 ? c : a.$1.compareTo(b.$1);
      });
    final name = app.data.machine(_asset).name;
    Widget summary;
    if (ranked.isEmpty) {
      summary = const Text(
          'Bu girdilerle geçerli hedef pencere yok (standart pencerede yük yok veya tüm saatler kısıtlı).');
    } else {
      final (bestT, best) = ranked.first;
      if (bestT == _s) {
        summary = Text('$name için ${fmt.date(_date)} gününde standart pencereden (${fmt.window(_s, _L)}) '
            'daha temiz bir saat yok.');
      } else {
        summary = Text.rich(TextSpan(children: [
          TextSpan(text: 'En temiz pencere: ${fmt.window(bestT, _L)}', style: const TextStyle(fontWeight: FontWeight.w700)),
          TextSpan(text: ' — $name, ${fmt.date(_date)}. Standart ${fmt.window(_s, _L)} yerine bu saatte emisyon '),
          TextSpan(text: fmt.pct(best.deltaPct), style: const TextStyle(fontWeight: FontWeight.w700, color: th.good)),
          TextSpan(text: ' değişir (${ranked.length} geçerli pencere tarandı).'),
        ]));
      }
    }
    final byT = [for (final (t, r) in [...cands]..sort((a, b) => a.$1.compareTo(b.$1))) (t, r.deltaPct ?? 0.0)];
    final sel = ranked.isEmpty ? -1 : _selected.clamp(0, ranked.length - 1);
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
      children: [
        th.SectionCard(
          title: 'En temiz saat',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              LabeledDropdown<String>(
                label: 'Makine',
                value: _asset,
                items: [for (final m in ms) m.id],
                itemLabel: (id) => ms.firstWhere((m) => m.id == id).name,
                onChanged: (id) => setState(() {
                  _asset = id;
                  _date = nearestDay(app.data.daysFor(id), _date);
                  _selected = 0;
                }),
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: _pickDate,
                icon: const Icon(Icons.calendar_today, size: 18),
                label: Text('Gün: ${fmt.date(_date)}'),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: HourDropdown(
                      label: 'Standart',
                      value: _s,
                      onChanged: (v) => setState(() {
                        _s = v;
                        _selected = 0;
                      }),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: LabeledDropdown<int>(
                      label: 'Uzunluk',
                      value: _L,
                      items: List.generate(12, (k) => k + 1),
                      itemLabel: (l) => '$l saat',
                      onChanged: (v) => setState(() {
                        _L = v;
                        _selected = 0;
                      }),
                    ),
                  ),
                ],
              ),
              Row(
                children: [
                  const th.Muted('Oran'),
                  Expanded(
                    child: Slider(
                      value: (_p * 100).roundToDouble(),
                      min: 0,
                      max: 100,
                      divisions: 100,
                      onChanged: (v) => setState(() {
                        _p = v.round() / 100;
                        _selected = 0;
                      }),
                    ),
                  ),
                  SizedBox(width: 44, child: Text('%${(_p * 100).round()}', textAlign: TextAlign.right)),
                ],
              ),
              th.Muted(_restricted.isNotEmpty
                  ? 'Kısıtlı saatler (Senaryo sekmesinden): ${(_restricted.toList()..sort()).map(fmt.hour).join(', ')}'
                  : 'Kısıtlı saat yok. Kısıtlı saatleri Senaryo sekmesinden işaretleyebilirsiniz.'),
            ],
          ),
        ),
        const SizedBox(height: 10),
        th.SectionCard(
          title: 'Hedef pencere sıralaması',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              summary,
              const SizedBox(height: 8),
              for (var n = 0; n < ranked.length; n++)
                _RankRow(
                  rank: n + 1,
                  label: fmt.window(ranked[n].$1, _L) + (ranked[n].$1 == _s ? '  (standart)' : ''),
                  r: ranked[n].$2,
                  bold: n == 0,
                  selected: n == sel,
                  onTap: () => setState(() => _selected = n),
                  onDoubleTap: () => _apply(ranked, n),
                ),
              const SizedBox(height: 8),
              const th.Muted('Satıra dokunup seçin; iki kez dokunursanız doğrudan uygulanır.', size: 12),
              const SizedBox(height: 6),
              FilledButton(
                onPressed: ranked.isEmpty ? null : () => _apply(ranked, sel),
                child: const Text('Seçili saati senaryoya uygula'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 10),
        th.SectionCard(
          title: 'Saate göre emisyon değişimi',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SizedBox(
                height: 200,
                child: CustomPaint(
                  painter: _DeltaChartPainter(byT, ranked.isEmpty ? null : ranked.first.$1, _s),
                ),
              ),
              const SizedBox(height: 6),
              const th.Muted(
                  'Yeşil çubuklar emisyonu düşüren, kırmızılar artıran hedef saatlerdir. Çerçeveli çubuk en temiz penceredir.'),
            ],
          ),
        ),
      ],
    );
  }
}

class _RankRow extends StatelessWidget {
  const _RankRow({
    required this.rank,
    required this.label,
    required this.r,
    required this.bold,
    required this.selected,
    required this.onTap,
    required this.onDoubleTap,
  });

  final int rank;
  final String label;
  final core.Result r;
  final bool bold, selected;
  final VoidCallback onTap, onDoubleTap;

  @override
  Widget build(BuildContext context) {
    final w = bold ? FontWeight.w700 : FontWeight.normal;
    final d = r.deltaPct;
    final dColor = (d == null || d == 0) ? th.text : (d < 0 ? th.good : th.bad);
    return InkWell(
      onTap: onTap,
      onDoubleTap: onDoubleTap,
      child: Container(
        color: selected ? th.primarySoft : null,
        padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
        child: Row(
          children: [
            SizedBox(width: 26, child: Text('$rank', style: TextStyle(fontWeight: w))),
            Expanded(
              flex: 5,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: TextStyle(fontWeight: w)),
                  th.Muted('${fmt.num(r.scenarioKg)} kgCO2 · günlük ${fmt.pct(r.dailyDeltaPct)}', size: 12),
                ],
              ),
            ),
            Text(fmt.pct(d), style: TextStyle(fontWeight: w, color: dColor)),
          ],
        ),
      ),
    );
  }
}

class _DeltaChartPainter extends CustomPainter {
  _DeltaChartPainter(this.items, this.bestT, this.sourceT);
  final List<(int, double)> items;
  final int? bestT;
  final int sourceT;

  static const _axis = Color(0xFF5B6776);

  TextPainter _tp(String t, [double size = 10]) => TextPainter(
        text: TextSpan(text: t, style: TextStyle(fontSize: size, color: _axis)),
        textDirection: TextDirection.ltr,
      )..layout();

  @override
  void paint(Canvas canvas, Size size) {
    const left = 40.0, right = 8.0, top = 8.0, bottom = 30.0;
    final plot = Rect.fromLTRB(left, top, size.width - right, size.height - bottom);
    double xOf(double v) => plot.left + (v + 0.6) / 24.2 * plot.width;
    var lo = 0.0, hi = 0.0;
    for (final (_, d) in items) {
      lo = math.min(lo, d);
      hi = math.max(hi, d);
    }
    if (hi - lo < 1e-9) {
      hi += 1;
      lo -= 1;
    }
    final pad = (hi - lo) * 0.1;
    lo -= pad;
    hi += pad;
    double yOf(double v) => plot.bottom - (v - lo) / (hi - lo) * plot.height;

    final grid = Paint()
      ..color = const Color(0xFFE9EDF1)
      ..strokeWidth = 0.8;
    for (var k = 0; k <= 4; k++) {
      final v = lo + (hi - lo) * k / 4;
      canvas.drawLine(Offset(plot.left, yOf(v)), Offset(plot.right, yOf(v)), grid);
      final tp = _tp(fmt.num(v, 1));
      tp.paint(canvas, Offset(plot.left - tp.width - 4, yOf(v) - tp.height / 2));
    }
    final bw = plot.width / 24.2 * 0.75;
    for (final (t, d) in items) {
      final good = d <= 0;
      final color = (good ? const Color(0xFF1F9254) : const Color(0xFFD03C3C))
          .withValues(alpha: t == bestT ? 1.0 : 0.75);
      final rect = Rect.fromLTRB(xOf(t.toDouble()) - bw / 2, math.min(yOf(d), yOf(0)), xOf(t.toDouble()) + bw / 2,
          math.max(yOf(d), yOf(0)));
      canvas.drawRect(rect, Paint()..color = color);
      if (t == bestT) {
        canvas.drawRect(
            rect,
            Paint()
              ..color = const Color(0xFF0F5B46)
              ..style = PaintingStyle.stroke
              ..strokeWidth = 1.6);
      }
    }
    canvas.drawLine(Offset(plot.left, yOf(0)), Offset(plot.right, yOf(0)),
        Paint()
          ..color = const Color(0xFF9AA5B1)
          ..strokeWidth = 0.8);
    if (items.isNotEmpty) {
      final x = xOf(sourceT.toDouble());
      final dash = Paint()
        ..color = const Color(0xFF7F8A96)
        ..strokeWidth = 1;
      for (var y = plot.top; y < plot.bottom; y += 6) {
        canvas.drawLine(Offset(x, y), Offset(x, math.min(y + 3, plot.bottom)), dash);
      }
      _tp(' standart', 9.5).paint(canvas, Offset(x, plot.top));
    }
    canvas.drawLine(Offset(plot.left, plot.bottom), Offset(plot.right, plot.bottom),
        Paint()..color = const Color(0xFFCFD6DE));
    for (var h = 0; h < 24; h += 3) {
      final tp = _tp(h.toString().padLeft(2, '0'));
      tp.paint(canvas, Offset(xOf(h.toDouble()) - tp.width / 2, plot.bottom + 3));
    }
    final xl = _tp('Hedef başlangıç saati', 10.5);
    xl.paint(canvas, Offset(plot.center.dx - xl.width / 2, plot.bottom + 16));
    _tp('Değişim (%)', 9.5).paint(canvas, const Offset(0, 0));
  }

  @override
  bool shouldRepaint(covariant _DeltaChartPainter old) => true;
}
