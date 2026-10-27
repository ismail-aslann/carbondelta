// 24 saatlik karbon yoğunluğu + makine yükü grafiği (desktop/chart_widget.py).
// Sol eksen: karbon yoğunluğu (çizgi), sağ eksen: yük (çubuk). Standart pencere
// gri, seçilen pencere yeşil/kırmızı/turuncu gölge; kısıtlı saatler taralı.
// Bir saate dokununca değerler görünür.

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../engine/core.dart' as core;
import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;

const _loadColor = Color(0xFFA9BFD3);
const _sourceColor = Color(0xFF7F8A96);
const _goodColor = Color(0xFF2E9D4F);
const _badColor = Color(0xFFD03C3C);
const _neutralColor = Color(0xFFE0A030);
const _restrictedColor = Color(0xFFB04040);
const _axisText = Color(0xFF5B6776);

class ScenarioChart extends StatefulWidget {
  const ScenarioChart({
    super.key,
    required this.ci,
    required this.load,
    required this.s,
    required this.L,
    required this.t,
    required this.restricted,
    required this.status,
    required this.deltaPct,
    required this.ciLabel,
  });

  final List<double> ci;
  final List<double> load;
  final int s;
  final int L;
  final int t;
  final Set<int> restricted;
  final String status;
  final double? deltaPct;
  final String ciLabel;

  @override
  State<ScenarioChart> createState() => _ScenarioChartState();
}

class _ScenarioChartState extends State<ScenarioChart> {
  int? _hover;

  @override
  Widget build(BuildContext context) {
    final legend = <Widget>[
      _legend(_loadColor.withValues(alpha: 0.55), 'Makine yükü'),
      _legend(th.ciColor, 'Karbon yoğunluğu'),
      if (widget.restricted.isNotEmpty) _legend(_restrictedColor, 'Kısıtlı saat', hatched: true),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(spacing: 14, runSpacing: 4, children: legend),
        const SizedBox(height: 6),
        LayoutBuilder(builder: (context, c) {
          return GestureDetector(
            onTapDown: (d) => _touch(d.localPosition.dx, c.maxWidth),
            onHorizontalDragUpdate: (d) => _touch(d.localPosition.dx, c.maxWidth),
            child: SizedBox(
              height: 240,
              child: CustomPaint(
                size: Size(c.maxWidth, 240),
                painter: _ChartPainter(widget, _hover),
              ),
            ),
          );
        }),
        if (_hover != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(
              '${fmt.window(_hover!, 1)} · Karbon yoğunluğu: ${fmt.num(widget.ci[_hover!], 3)} '
              '${widget.ciLabel}/MWh · Yük: ${fmt.num(widget.load[_hover!])} kWh',
              style: const TextStyle(fontSize: 12.5, color: th.text),
            ),
          ),
      ],
    );
  }

  void _touch(double x, double width) {
    final plotLeft = _ChartPainter.padLeft;
    final plotW = width - _ChartPainter.padLeft - _ChartPainter.padRight;
    final h = ((x - plotLeft) / plotW * 24).floor();
    setState(() => _hover = (h >= 0 && h < 24) ? h : null);
  }

  Widget _legend(Color c, String label, {bool hatched = false}) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 14,
            height: 10,
            decoration: BoxDecoration(
              color: hatched ? null : c,
              border: hatched ? Border.all(color: c) : null,
            ),
            child: hatched ? CustomPaint(painter: _HatchPainter(c)) : null,
          ),
          const SizedBox(width: 5),
          Text(label, style: const TextStyle(fontSize: 11.5, color: _axisText)),
        ],
      );
}

class _HatchPainter extends CustomPainter {
  _HatchPainter(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) => _hatch(canvas, Offset.zero & size, color, 0.9);

  @override
  bool shouldRepaint(covariant _HatchPainter old) => old.color != color;
}

void _hatch(Canvas canvas, Rect r, Color color, double alpha) {
  final paint = Paint()
    ..color = color.withValues(alpha: alpha)
    ..strokeWidth = 1;
  canvas.save();
  canvas.clipRect(r);
  for (var x = r.left - r.height; x < r.right; x += 6) {
    canvas.drawLine(Offset(x, r.bottom), Offset(x + r.height, r.top), paint);
  }
  canvas.restore();
}

class _ChartPainter extends CustomPainter {
  _ChartPainter(this.w, this.hover);

  final ScenarioChart w;
  final int? hover;

  static const double padLeft = 40;
  static const double padRight = 38;
  static const double padTop = 22;
  static const double padBottom = 30;

  TextPainter _tp(String text, {double size = 10, Color color = _axisText, FontWeight? weight}) {
    final tp = TextPainter(
      text: TextSpan(text: text, style: TextStyle(fontSize: size, color: color, fontWeight: weight)),
      textDirection: TextDirection.ltr,
    )..layout();
    return tp;
  }

  @override
  void paint(Canvas canvas, Size size) {
    final plot = Rect.fromLTRB(padLeft, padTop, size.width - padRight, size.height - padBottom);
    double xOf(double hour) => plot.left + hour / 24 * plot.width;

    final ciMin = w.ci.reduce(math.min);
    final ciMax = w.ci.reduce(math.max);
    final pad = math.max((ciMax - ciMin) * 0.15, 0.01);
    final yLo = ciMin - pad, yHi = ciMax + pad * 2.2;
    double yCi(double v) => plot.bottom - (v - yLo) / (yHi - yLo) * plot.height;

    final loadTop = math.max(w.load.reduce(math.max) * 1.25, 1.0);
    double yLoad(double v) => plot.bottom - v / loadTop * plot.height;

    // ızgara (sol eksen)
    final grid = Paint()
      ..color = const Color(0xFFE9EDF1)
      ..strokeWidth = 0.8;
    for (var k = 0; k <= 4; k++) {
      final v = yLo + (yHi - yLo) * k / 4;
      final y = yCi(v);
      canvas.drawLine(Offset(plot.left, y), Offset(plot.right, y), grid);
      final tp = _tp(fmt.num(v, 2), color: th.ciColor);
      tp.paint(canvas, Offset(plot.left - tp.width - 4, y - tp.height / 2));
      final lv = loadTop * k / 4;
      final tl = _tp(fmt.num(lv, lv >= 10 ? 0 : 1));
      tl.paint(canvas, Offset(plot.right + 4, yLoad(lv) - tl.height / 2));
    }

    // yük çubukları
    final barPaint = Paint()..color = _loadColor.withValues(alpha: 0.55);
    final bw = plot.width / 24 * 0.8;
    for (var h = 0; h < 24; h++) {
      final cx = xOf(h + 0.5);
      canvas.drawRect(Rect.fromLTRB(cx - bw / 2, yLoad(w.load[h]), cx + bw / 2, plot.bottom), barPaint);
    }

    // pencereler
    final inRange = w.L >= 1 && 0 <= w.s && w.s + w.L <= 24 && 0 <= w.t && w.t + w.L <= 24;
    if (inRange && w.status != core.nonShiftable) {
      final srcRect = Rect.fromLTRB(xOf(w.s.toDouble()), plot.top, xOf((w.s + w.L).toDouble()), plot.bottom);
      canvas.drawRect(srcRect, Paint()..color = _sourceColor.withValues(alpha: 0.18));
      final srcBox = _label(canvas, 'Standart', srcRect, const Color(0xFF4A5562), maxX: plot.right);
      if (w.s != w.t) {
        Color color;
        if (w.status == core.ok && w.deltaPct != null) {
          color = w.deltaPct! <= 0 ? _goodColor : _badColor;
        } else if (w.status == core.restrictedConflict) {
          color = _badColor;
        } else {
          color = _neutralColor;
        }
        final tgtRect = Rect.fromLTRB(xOf(w.t.toDouble()), plot.top, xOf((w.t + w.L).toDouble()), plot.bottom);
        canvas.drawRect(tgtRect, Paint()..color = color.withValues(alpha: 0.2));
        _label(canvas, 'Seçilen', tgtRect, color, avoid: srcBox, maxX: plot.right);
      }
    }

    // kısıtlı saatler
    for (final h in w.restricted.toList()..sort()) {
      _hatch(canvas, Rect.fromLTRB(xOf(h.toDouble()), plot.top, xOf(h + 1.0), plot.bottom),
          _restrictedColor, 0.55);
    }

    // karbon yoğunluğu çizgisi
    final linePaint = Paint()
      ..color = th.ciColor
      ..strokeWidth = 2.2
      ..style = PaintingStyle.stroke
      ..strokeJoin = StrokeJoin.round;
    final path = Path();
    for (var h = 0; h < 24; h++) {
      final pt = Offset(xOf(h + 0.5), yCi(w.ci[h]));
      if (h == 0) {
        path.moveTo(pt.dx, pt.dy);
      } else {
        path.lineTo(pt.dx, pt.dy);
      }
    }
    canvas.drawPath(path, linePaint);
    final dot = Paint()..color = th.ciColor;
    for (var h = 0; h < 24; h++) {
      canvas.drawCircle(Offset(xOf(h + 0.5), yCi(w.ci[h])), 2.4, dot);
    }

    // seçili saat
    if (hover != null) {
      final x = xOf(hover! + 0.5);
      canvas.drawLine(Offset(x, plot.top), Offset(x, plot.bottom),
          Paint()
            ..color = th.text.withValues(alpha: 0.35)
            ..strokeWidth = 1);
    }

    // x ekseni
    canvas.drawLine(Offset(plot.left, plot.bottom), Offset(plot.right, plot.bottom),
        Paint()..color = const Color(0xFFCFD6DE));
    final xStep = plot.width / 12 < 20 ? 4 : 2; // dar ekranda etiketler birbirine değmesin
    for (var h = 0; h <= 24; h += xStep) {
      final tp = _tp(h.toString().padLeft(2, '0'));
      tp.paint(canvas, Offset(xOf(h.toDouble()) - tp.width / 2, plot.bottom + 3));
    }
    final xl = _tp('Saat', size: 10.5);
    xl.paint(canvas, Offset(plot.center.dx - xl.width / 2, plot.bottom + 16));

    // eksen başlıkları
    // (üst kenar boşluğuna; eksen değerleriyle üst üste binmez)
    final ly = _tp('${w.ciLabel}/MWh', size: 9.5, color: th.ciColor);
    ly.paint(canvas, const Offset(2, 0));
    final ry = _tp('kWh', size: 9.5);
    ry.paint(canvas, Offset(size.width - ry.width - 2, 0));
  }

  /// Pencere etiketini çizer; [avoid] ile çakışırsa bir satır aşağı iner.
  /// Etiket grafik alanından taşmaz.
  Rect _label(Canvas canvas, String text, Rect r, Color color, {Rect? avoid, double minX = padLeft, double? maxX}) {
    final tp = _tp(text, size: 10, color: color, weight: FontWeight.bold);
    final bw = tp.width + 8, bh = tp.height + 2;
    final right = maxX ?? double.infinity;
    var cx = r.center.dx;
    cx = math.max(cx, minX + bw / 2);
    if (right.isFinite) cx = math.min(cx, right - bw / 2);
    var box = Rect.fromCenter(center: Offset(cx, r.top + bh / 2 + 3), width: bw, height: bh);
    if (avoid != null && box.overlaps(avoid.inflate(2))) {
      box = box.shift(Offset(0, bh + 4));
    }
    canvas.drawRRect(RRect.fromRectAndRadius(box, const Radius.circular(4)),
        Paint()..color = Colors.white.withValues(alpha: 0.85));
    tp.paint(canvas, Offset(box.left + 4, box.top + 1));
    return box;
  }

  @override
  bool shouldRepaint(covariant _ChartPainter old) => true;
}
