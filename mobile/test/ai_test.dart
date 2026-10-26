// AI katmanı testleri: sayı doğrulayıcı ve kural tabanlı doğal dil çözümleyici.

import 'dart:io';

import 'package:carbondelta_mobile/ai/ai_client.dart';
import 'package:carbondelta_mobile/ai/ai_context.dart';
import 'package:carbondelta_mobile/engine/data.dart';
import 'package:carbondelta_mobile/engine/packages.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Sayı doğrulayıcı', () {
    final allowed = allowedNumbers({
      'delta': -15.618956685621868,
      'baseline': 42.613384003600004,
      'window': '03:00–06:00',
      'date': '15.07.2025',
    });

    test('İzinli sayılar geçer (Türkçe ondalık dahil)', () {
      expect(validateNumbers('Emisyon −15,62 % değişir; 42,61 kgCO2 yerine.', allowed), isTrue);
      expect(validateNumbers('03:00–06:00 aralığı, 15.07.2025 günü.', allowed), isTrue);
      expect(validateNumbers('Değişim yaklaşık -15,6 %.', allowed), isTrue);
    });

    test('Uydurma sayı reddedilir', () {
      expect(validateNumbers('Emisyon −17,40 % azalır.', allowed), isFalse);
      expect(validateNumbers('Bu 42,613 kg demektir.', allowed), isFalse);
    });

    test('extract_numbers', () {
      expect(extractNumbers('−15,62 % ve 3'), [(15.62, 2), (3.0, 0)]);
    });

    test('Python round eşitlikte çift', () {
      expect(pyRound(2.5, 0), 2.0);
      expect(pyRound(3.5, 0), 4.0);
      expect(pyRound(0.125, 2), 0.12);
      expect(pyRound(15.618956, 2), 15.62);
    });
  });

  group('Kural tabanlı çözümleyici', () {
    setUpAll(() async {
      TestWidgetsFlutterBinding.ensureInitialized();
      setDataDirForTests(Directory.systemTemp.createTempSync('cd_test'));
      await DataStore.instance.load();
    });

    test("Kompresörü 3'ten 18'e al", () {
      final r = parseNlRule("Kompresörü 3'ten 18'e al");
      expect(r['asset_id'], 'comp_b');
      expect(r['s'], 3);
      expect(r['t'], 18);
    });

    test("Presi %50 ile 2 saat 21'e kaydır", () {
      final r = parseNlRule("Presi %50 ile 2 saat 21'e kaydır");
      expect(r['asset_id'], 'p_i');
      expect(r['p'], 0.5);
      expect(r['L'], 2);
      expect(r['t'], 21);
    });

    test("Karıştırıcıyı 10'dan 19'a al", () {
      final r = parseNlRule("Karıştırıcıyı 10'dan 19'a al");
      expect(r['asset_id'], 'mix_c');
      expect(r['s'], 10);
      expect(r['t'], 19);
    });
  });
}
