import 'package:carbondelta_mobile/ui/fmt.dart' as fmt;
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Biçimlendirme masaüstüyle aynı', () {
    expect(fmt.pct(-15.618956685621868), '−15,62 %');
    expect(fmt.pct(2.5), '+2,50 %');
    expect(fmt.pct(null), '—');
    expect(fmt.num(1234.5), '1.234,50');
    expect(fmt.num(-0.001), '0,00');
    expect(fmt.hour(3), '03:00');
    expect(fmt.window(22, 2), '22:00–24:00');
    expect(fmt.date('2025-07-15'), '15.07.2025');
    expect(fmt.datetime('2026-10-20T11:03:03'), '20.10.2026 11:03');
  });
}
