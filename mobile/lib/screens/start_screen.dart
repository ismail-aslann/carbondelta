// Başlangıç ekranı: logo, son senaryo kartı ve bölüm listesi (koyu tema)
// (desktop/start_screen.py).

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../ui/fmt.dart' as fmt;
import '../widgets/delti.dart';

const bgCenter = Color(0xFF0D4A3D);
const bgEdge = Color(0xFF062720);
const mint = Color(0xFF5FE0B0);
const startText = Color(0xFFF2FBF7);
const startMuted = Color(0xFF9FC4B7);
const peak = Color(0xFFFF8A7A);

class StartItem {
  const StartItem(this.key, this.title, this.sub, this.icon);
  final String key;
  final String title;
  final String sub;
  final IconData? icon; // null → Delti
}

const List<StartItem> startItems = [
  StartItem('new', 'Yeni senaryo', 'Yük kaydırmayı hesapla', Icons.show_chart),
  StartItem('best', 'En temiz saat', 'Otomatik öneri', Icons.search),
  StartItem('nl', "Delti'ye sor", 'Yazarak senaryo kur', null),
  StartItem('history', 'Geçmiş', 'Kayıtlı senaryolar', Icons.schedule),
  StartItem('calc', 'Hesap dökümü', 'Formül ve tablolar', Icons.description_outlined),
  StartItem('data', 'Veri yönetimi', 'Makine · yıl · katsayı ekle', Icons.storage),
  StartItem('guide', 'Kullanma kılavuzu', 'Her şey adım adım', Icons.menu_book_outlined),
  StartItem('sources', 'Kaynaklar', 'EPİAŞ · ETKB · Zenodo', Icons.dataset_outlined),
  StartItem('contact', 'İletişim', 'Geliştiriciler ve danışman', Icons.mail_outline),
];

class StartScreen extends StatelessWidget {
  const StartScreen({
    super.key,
    required this.curve,
    required this.resumeSmall,
    required this.resumeText,
    required this.resumeDelta,
    required this.resumeGood,
    required this.aiOnline,
    required this.machineCount,
    required this.onAction,
  });

  final List<double> curve;
  final String resumeSmall;
  final String resumeText;
  final String resumeDelta;
  final bool resumeGood;
  final bool aiOnline;
  final int machineCount;
  final ValueChanged<String> onAction;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: CustomPaint(
        painter: _StartBackground(curve),
        child: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
                  children: [
                    Center(
                      child: Container(
                        decoration: BoxDecoration(boxShadow: [
                          BoxShadow(color: mint.withValues(alpha: 0.43), blurRadius: 46, offset: const Offset(0, 8)),
                        ]),
                        child: Image.asset('assets/icon.png', width: 64, height: 64),
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Center(
                      child: Text.rich(TextSpan(
                        style: TextStyle(fontSize: 34, fontWeight: FontWeight.w700, color: startText),
                        children: [TextSpan(text: 'Carbon'), TextSpan(text: 'Delta', style: TextStyle(color: mint))],
                      )),
                    ),
                    const Center(
                      child: Text('Aynı iş, daha temiz saat.', style: TextStyle(color: startMuted, fontSize: 15)),
                    ),
                    const SizedBox(height: 14),
                    _ResumeCard(
                      small: resumeSmall,
                      text: resumeText,
                      delta: resumeDelta,
                      good: resumeGood,
                      onTap: () => onAction('resume'),
                    ),
                    const SizedBox(height: 10),
                    Container(
                      decoration: BoxDecoration(
                        color: const Color.fromRGBO(4, 30, 24, 0.62),
                        border: Border.all(color: Colors.white.withValues(alpha: 0.10)),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        children: [
                          for (var n = 0; n < startItems.length; n++)
                            _Row(item: startItems[n], separator: n > 0, onTap: () => onAction(startItems[n].key)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 10),
                child: Column(
                  children: [
                    const Text(
                      'Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: startMuted, fontSize: 11.5),
                    ),
                    const SizedBox(height: 4),
                    GestureDetector(
                      onTap: () => onAction('delti_settings'),
                      child: Text.rich(
                        TextSpan(style: const TextStyle(color: startMuted, fontSize: 11.5), children: [
                          TextSpan(text: '● ', style: TextStyle(color: aiOnline ? mint : const Color(0xFF8AA39A))),
                          TextSpan(text: aiOnline ? 'Delti (AI) çevrimiçi (' : 'Delti (AI) uyuyor ('),
                          TextSpan(
                            text: aiOnline ? 'ayarlar' : 'uyandır',
                            style: const TextStyle(color: mint, decoration: TextDecoration.underline),
                          ),
                          TextSpan(text: ')   ·   $machineCount makine   ·   İnternetsiz hesap'),
                        ]),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ResumeCard extends StatelessWidget {
  const _ResumeCard({required this.small, required this.text, required this.delta, required this.good, required this.onTap});
  final String small, text, delta;
  final bool good;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Ink(
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [
              const Color.fromRGBO(95, 224, 176, 0.22),
              const Color.fromRGBO(95, 224, 176, 0.07),
            ]),
            border: Border.all(color: const Color.fromRGBO(95, 224, 176, 0.40)),
            borderRadius: BorderRadius.circular(12),
          ),
          padding: const EdgeInsets.fromLTRB(12, 10, 14, 10),
          child: Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: const BoxDecoration(color: mint, shape: BoxShape.circle),
                child: const Icon(Icons.play_arrow, size: 20, color: Color(0xFF063A2E)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(small.toUpperCase(),
                        style: const TextStyle(color: startMuted, fontSize: 11, letterSpacing: 1)),
                    Text(text, style: const TextStyle(color: startText, fontSize: 14.5, fontWeight: FontWeight.w600)),
                  ],
                ),
              ),
              Text(delta,
                  style: TextStyle(
                      color: good ? mint : const Color(0xFFFF9A8A), fontSize: 18, fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.item, required this.separator, required this.onTap});
  final StartItem item;
  final bool separator;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          border: separator ? Border(top: BorderSide(color: Colors.white.withValues(alpha: 0.09))) : null,
        ),
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: item.icon == null ? Colors.transparent : const Color.fromRGBO(95, 224, 176, 0.14),
                borderRadius: BorderRadius.circular(8),
              ),
              child: item.icon == null ? const Delti(size: 32) : Icon(item.icon, size: 19, color: mint),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(item.title,
                      style: const TextStyle(color: startText, fontSize: 15, fontWeight: FontWeight.w600)),
                  Text(item.sub, style: const TextStyle(color: startMuted, fontSize: 12.5)),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: startMuted),
          ],
        ),
      ),
    );
  }
}

class _StartBackground extends CustomPainter {
  _StartBackground(this.curve);
  final List<double> curve;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final rect = Offset.zero & size;
    canvas.drawRect(
      rect,
      Paint()
        ..shader = RadialGradient(
          center: const Alignment(0, -1),
          radius: math.max(w, h) * 0.85 / math.min(w, h),
          colors: const [bgCenter, bgEdge, bgEdge],
          stops: const [0.0, 0.75, 1.0],
        ).createShader(rect),
    );
    final gridPaint = Paint()
      ..shader = RadialGradient(
        center: const Alignment(0, -0.2),
        radius: math.max(w, h) * 0.62 / math.min(w, h),
        colors: const [Color.fromRGBO(255, 255, 255, 0.10), Color.fromRGBO(255, 255, 255, 0)],
      ).createShader(rect)
      ..strokeWidth = 1;
    for (var x = 0.0; x <= w; x += 60) {
      canvas.drawLine(Offset(x, 0), Offset(x, h), gridPaint);
    }
    for (var y = 0.0; y <= h; y += 60) {
      canvas.drawLine(Offset(0, y), Offset(w, y), gridPaint);
    }
    if (curve.length != 24) return;
    final lo = curve.reduce(math.min), hi = curve.reduce(math.max);
    final span = (hi - lo) == 0 ? 1.0 : hi - lo;
    final top = h * 0.52, bottom = h * 0.88;
    final pts = [
      for (var i = 0; i < 24; i++)
        Offset(20 + i * (w - 40) / 23, bottom - (curve[i] - lo) / span * (bottom - top)),
    ];
    final area = Path()..moveTo(pts.first.dx, h);
    for (final p in pts) {
      area.lineTo(p.dx, p.dy);
    }
    area
      ..lineTo(pts.last.dx, h)
      ..close();
    canvas.drawPath(
      area,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color.fromRGBO(95, 224, 176, 0.12), Color.fromRGBO(95, 224, 176, 0)],
        ).createShader(Rect.fromLTRB(0, top, w, h)),
    );
    final line = Path()..moveTo(pts.first.dx, pts.first.dy);
    for (final p in pts.skip(1)) {
      line.lineTo(p.dx, p.dy);
    }
    canvas.drawPath(
      line,
      Paint()
        ..color = const Color.fromRGBO(95, 224, 176, 0.49)
        ..strokeWidth = 2.4
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
    var hmax = 0, hmin = 0;
    for (var i = 0; i < 24; i++) {
      if (curve[i] > curve[hmax]) hmax = i;
      if (curve[i] < curve[hmin]) hmin = i;
    }
    for (final (hour, color, label, above) in [(hmax, peak, 'en kirli', true), (hmin, mint, 'en temiz', false)]) {
      final pt = pts[hour];
      canvas.drawCircle(pt, 4.5, Paint()..color = color);
      final tp = TextPainter(
        text: TextSpan(text: '${fmt.hour(hour)} · $label', style: TextStyle(color: color, fontSize: 11)),
        textDirection: TextDirection.ltr,
      )..layout();
      final dx = math.max(4.0, math.min(pt.dx - tp.width / 2, w - tp.width - 4));
      tp.paint(canvas, Offset(dx, above ? pt.dy - 22 : pt.dy + 8));
    }
  }

  @override
  bool shouldRepaint(covariant _StartBackground old) => old.curve != curve;
}
