// Ekran biçimlendirme — yuvarlama yalnızca burada (2 ondalık, Türkçe virgül).
// desktop/fmt.py ile aynı çıktı.

const String minus = '−';

String _group(String intPart) {
  final b = StringBuffer();
  for (var i = 0; i < intPart.length; i++) {
    if (i > 0 && (intPart.length - i) % 3 == 0) b.write('.');
    b.write(intPart[i]);
  }
  return b.toString();
}

bool _roundsNegative(double v, int digits) => double.parse(v.toStringAsFixed(digits)) < 0;
bool _roundsPositive(double v, int digits) => double.parse(v.toStringAsFixed(digits)) > 0;

String num(double v, [int digits = 2]) {
  final s = v.abs().toStringAsFixed(digits);
  final parts = s.split('.');
  final body = parts.length > 1 ? '${_group(parts[0])},${parts[1]}' : _group(parts[0]);
  return _roundsNegative(v, digits) ? '$minus$body' : body;
}

String signed(double v, [int digits = 2]) =>
    _roundsPositive(v, digits) ? '+${num(v, digits)}' : num(v, digits);

String pct(double? v, [int digits = 2]) => v == null ? '—' : '${signed(v, digits)} %';

String hour(int h) => '${h.toString().padLeft(2, '0')}:00';

String window(int start, int length) => '${hour(start)}–${hour(start + length)}';

/// 2025-07-15 → 15.07.2025
String date(String iso) {
  final p = iso.substring(0, 10).split('-');
  return '${p[2]}.${p[1]}.${p[0]}';
}

/// 2026-10-20T11:03:03 → 20.10.2026 11:03
String datetime(String iso) =>
    iso.length >= 16 ? '${date(iso)} ${iso.substring(11, 16)}' : date(iso);
