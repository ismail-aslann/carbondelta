// Tesis Planı: tesis saatlik yükü (plan öncesi/sonrası) ve şebeke karbon yoğunluğu
// (desktop/plan_tab.py _LoadChart). Tepe sınırı kesikli kırmızı çizgiyle gösterilir.

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../engine/plan.dart' as pl;
import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;

const _axis = Color(0xFF5B6776);
const _beforeColor = Color(0xFFC9D3DD);
const _afterColor = Color(0xFF1F9254);
const _limitColor = Color(0xFFD03C3C);

class PlanChart extends StatelessWidget {
  const PlanChart({super.key, required this.facility, required this.ciLabel});
  final pl.FacilityPlan facility;
  final String ciLabel;

  Widget _legend(Color c, String label, {bool line = false}) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(width: 14, height: line ? 3 : 10, color: c),
          const SizedBox(width: 5),
          Text(label, style: const TextStyle(fontSize: 11.5, color: _axis)),
        ],
      );

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(spacing: 14, runSpacing: 4, children: [
          _legend(_beforeColor, 'Plan öncesi'),
          _legend(_afterColor.withValues(alpha: 0.85), 'Plan sonrası'),
          _legend(th.ciColor, 'Karbon yoğunluğu', line: true),
        ]),
        const SizedBox(height: 6),
        SizedBox(height: 230, child: CustomPaint(size: Size.infinite, painter: _PlanPainter(facility, ciLabel))),
      ],
    );
  }
}

class _PlanPainter extends CustomPainter {
  _PlanPainter(this.p, this.ciLabel);
  final pl.FacilityPlan p;
  final String ciLabel;

  TextPainter _tp(String t, {double size = 10, Color color = _axis, FontWeight? weight}) => TextPainter(
        text: TextSpan(text: t, style: TextStyle(fontSize: size, color: color, fontWeight: weight)),
        textDirection: TextDirection.ltr,
      )..layout();

  @override
  void paint(Canvas canvas, Size size) {
    const left = 40.0, right = 40.0, top = 40.0, bottom = 22.0;
    final plot = Rect.fromLTRB(left, top, size.width - right, size.height - bottom);
    final slot = plot.width / 24;
    double xOf(double h) => plot.left + slot * (h + 0.5);

    var top0 = 1.0;
    for (final v in [...p.before, ...p.after]) {
      top0 = math.max(top0, v);
    }
    final yTop = top0 * 1.18;
    double yLoad(double v) => plot.bottom - v / yTop * plot.height;

    final grid = Paint()
      ..color = const Color(0xFFE9EDF1)
      ..strokeWidth = 0.8;
    for (var k = 0; k <= 4; k++) {
      final v = yTop * k / 4;
      canvas.drawLine(Offset(plot.left, yLoad(v)), Offset(plot.right, yLoad(v)), grid);
      final tp = _tp(fmt.num(v, 0));
      tp.paint(canvas, Offset(plot.left - tp.width - 4, yLoad(v) - tp.height / 2));
    }

    // önce / sonra çubukları
    final bw = slot * 0.4;
    for (var h = 0; h < 24; h++) {
      final cx = xOf(h.toDouble());
      canvas.drawRect(Rect.fromLTRB(cx - bw, yLoad(p.before[h]), cx, plot.bottom), Paint()..color = _beforeColor);
      canvas.drawRect(Rect.fromLTRB(cx, yLoad(p.after[h]), cx + bw, plot.bottom),
          Paint()..color = _afterColor.withValues(alpha: 0.85));
    }

    // tepe sınırı
    final lim = p.peakLimit;
    if (lim != null && lim <= yTop) {
      final y = yLoad(lim);
      final dash = Paint()
        ..color = _limitColor
        ..strokeWidth = 1;
      for (var x = plot.left; x < plot.right; x += 7) {
        canvas.drawLine(Offset(x, y), Offset(math.min(x + 4, plot.right), y), dash);
      }
      final tp = _tp('sınır', size: 9.5, color: _limitColor);
      tp.paint(canvas, Offset(plot.right - tp.width - 2, y - tp.height - 1));
    } else if (lim != null) {
      final tp = _tp('sınır ${fmt.num(lim, 0)} kWh (grafik dışında)', size: 9.5, color: _limitColor);
      tp.paint(canvas, Offset(plot.right - tp.width, plot.top + 2));
    }

    // karbon yoğunluğu (sağ eksen)
    if (p.ci.length == 24) {
      final lo0 = p.ci.reduce(math.min), hi0 = p.ci.reduce(math.max);
      final pad = math.max((hi0 - lo0) * 0.15, 0.01);
      final lo = lo0 - pad, hi = hi0 + pad;
      double yCi(double v) => plot.bottom - (v - lo) / (hi - lo) * plot.height;
      final path = Path();
      for (var h = 0; h < 24; h++) {
        final pt = Offset(xOf(h.toDouble()), yCi(p.ci[h]));
        if (h == 0) {
          path.moveTo(pt.dx, pt.dy);
        } else {
          path.lineTo(pt.dx, pt.dy);
        }
      }
      canvas.drawPath(
          path,
          Paint()
            ..color = th.ciColor
            ..strokeWidth = 1.6
            ..style = PaintingStyle.stroke);
      for (var h = 0; h < 24; h++) {
        canvas.drawCircle(Offset(xOf(h.toDouble()), yCi(p.ci[h])), 1.8, Paint()..color = th.ciColor);
      }
      for (var k = 0; k <= 4; k++) {
        final v = lo + (hi - lo) * k / 4;
        final tp = _tp(fmt.num(v, 2), size: 9, color: th.ciColor);
        tp.paint(canvas, Offset(plot.right + 4, yCi(v) - tp.height / 2));
      }
    }

    // x ekseni
    canvas.drawLine(Offset(plot.left, plot.bottom), Offset(plot.right, plot.bottom),
        Paint()..color = const Color(0xFFCFD6DE));
    for (var h = 0; h < 24; h += 3) {
      final tp = _tp(h.toString().padLeft(2, '0'));
      tp.paint(canvas, Offset(xOf(h.toDouble()) - tp.width / 2, plot.bottom + 4));
    }

    // eksen başlıkları (üst boşlukta; değerlerle çakışmaz)
    _tp('Tesis yükü (kWh)', size: 9.5).paint(canvas, const Offset(0, 0));
    final ry = _tp('$ciLabel/MWh', size: 9.5, color: th.ciColor);
    ry.paint(canvas, Offset(size.width - ry.width, 0));

    // taşınan enerji kutusu (özetteki değerle aynı)
    final moved = p.plannedCount > 0 ? p.shiftedKwh : 0.0;
    final msg = moved > 1e-9 ? 'Taşınan enerji: ${fmt.num(moved, 1)} kWh' : 'Plan değişiklik önermedi';
    final tm = _tp(msg, size: 10, color: moved > 1e-9 ? th.primary : th.warn, weight: FontWeight.w600);
    final box = Rect.fromLTWH(plot.left + 2, 16, tm.width + 10, tm.height + 4);
    canvas.drawRRect(RRect.fromRectAndRadius(box, const Radius.circular(4)), Paint()..color = Colors.white);
    canvas.drawRRect(
        RRect.fromRectAndRadius(box, const Radius.circular(4)),
        Paint()
          ..color = th.border
          ..style = PaintingStyle.stroke);
    tm.paint(canvas, Offset(box.left + 5, box.top + 2));
  }

  @override
  bool shouldRepaint(covariant _PlanPainter old) => true;
}
