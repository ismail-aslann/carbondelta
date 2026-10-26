// Yıllık Etki: aylık emisyon değişimi çubuk grafiği (desktop/annual_tab.py _MonthChart).
// Yeşil çubuk o ay emisyonun düştüğünü, kırmızı arttığını gösterir; verisi olmayan aylar boş kalır.

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../engine/annual.dart' as annual;
import '../ui/fmt.dart' as fmt;

const List<String> monthShort = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
const _axis = Color(0xFF5B6776);

class MonthChart extends StatelessWidget {
  const MonthChart({super.key, required this.months, required this.unit});
  final List<annual.MonthTotal> months;

  /// 'CO2' ya da 'CO2-eşd'
  final String unit;

  @override
  Widget build(BuildContext context) =>
      SizedBox(height: 210, child: CustomPaint(size: Size.infinite, painter: _MonthPainter(months, unit)));
}

class _MonthPainter extends CustomPainter {
  _MonthPainter(this.months, this.unit);
  final List<annual.MonthTotal> months;
  final String unit;

  TextPainter _tp(String t, [double size = 10, Color color = _axis]) => TextPainter(
        text: TextSpan(text: t, style: TextStyle(fontSize: size, color: color)),
        textDirection: TextDirection.ltr,
      )..layout();

  @override
  void paint(Canvas canvas, Size size) {
    const left = 46.0, right = 6.0, top = 20.0, bottom = 22.0;
    final plot = Rect.fromLTRB(left, top, size.width - right, size.height - bottom);
    final vals = [for (final m in months) m.deltaKg];
    var lo = 0.0, hi = 0.0;
    for (final v in vals) {
      lo = math.min(lo, v);
      hi = math.max(hi, v);
    }
    if (hi - lo < 1e-9) {
      hi += 1;
      lo -= 1;
    }
    // Yuvarlak eksen adımı (1, 2, 5 × 10ⁿ): -60, -119, -179 gibi değerler yerine -50, -100, -150…
    final step = _niceStep((hi - lo) / 4);
    lo = (lo / step).floorToDouble() * step;
    hi = (hi / step).ceilToDouble() * step;
    if (hi - lo < step) hi = lo + step;
    double yOf(double v) => plot.bottom - (v - lo) / (hi - lo) * plot.height;

    final grid = Paint()
      ..color = const Color(0xFFE9EDF1)
      ..strokeWidth = 0.8;
    final digits = step < 1 ? (step < 0.1 ? 2 : 1) : 0;
    for (var v = lo; v <= hi + step * 1e-6; v += step) {
      canvas.drawLine(Offset(plot.left, yOf(v)), Offset(plot.right, yOf(v)), grid);
      final tp = _tp(fmt.num(v.abs() < step * 1e-6 ? 0.0 : v, digits));
      tp.paint(canvas, Offset(plot.left - tp.width - 4, yOf(v) - tp.height / 2));
    }
    final slot = plot.width / 12;
    final bw = slot * 0.7;
    for (var i = 0; i < 12; i++) {
      final cx = plot.left + slot * (i + 0.5);
      final m = months[i];
      if (m.days > 0) {
        final v = vals[i];
        final color = (v <= 0 ? const Color(0xFF1F9254) : const Color(0xFFD03C3C)).withValues(alpha: 0.85);
        canvas.drawRect(
            Rect.fromLTRB(cx - bw / 2, math.min(yOf(v), yOf(0)), cx + bw / 2, math.max(yOf(v), yOf(0))),
            Paint()..color = color);
      } else {
        // Sıfır çizgisinin boş tarafına yazılır (üstte başlıkla çakışmasın).
        final tp = _tp('veri\nyok', 7.5, const Color(0xFF9AA5B1));
        final above = yOf(0) - tp.height - 2;
        final y = above >= plot.top ? above : yOf(0) + 3;
        tp.paint(canvas, Offset(cx - tp.width / 2, y));
      }
      final tl = _tp(monthShort[i], slot < 22 ? 8.5 : 10);
      tl.paint(canvas, Offset(cx - tl.width / 2, plot.bottom + 4));
    }
    canvas.drawLine(Offset(plot.left, yOf(0)), Offset(plot.right, yOf(0)),
        Paint()
          ..color = const Color(0xFF9AA5B1)
          ..strokeWidth = 0.8);
    _tp('Değişim (kg $unit)', 9.5).paint(canvas, const Offset(0, 0));
  }

  @override
  bool shouldRepaint(covariant _MonthPainter old) => true;
}

/// En yakın "güzel" adım: 1, 2, 2,5 veya 5 × 10ⁿ.
double _niceStep(double raw) {
  if (raw <= 0 || raw.isNaN) return 1;
  final mag = math.pow(10, (math.log(raw) / math.ln10).floor()).toDouble();
  for (final m in const [1.0, 2.0, 2.5, 5.0, 10.0]) {
    if (raw <= m * mag) return m * mag;
  }
  return 10 * mag;
}
