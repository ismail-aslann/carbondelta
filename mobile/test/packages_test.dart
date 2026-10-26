// Veri paketi kontrolleri (engine/packages.py karşılığı).

import 'dart:io';

import 'package:carbondelta_mobile/engine/packages.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('parse_num: Türkçe/İngilizce ondalık ve eksik sıfır', () {
    expect(parseNum('1.234,56'), 1234.56);
    expect(parseNum('12,40'), 12.4);
    expect(parseNum(',01'), 0.01);
    expect(parseNum('-,05'), -0.05);
    expect(parseNum('12.4'), 12.4);
    expect(parseNum('').isNaN, isTrue);
  });

  test('parse_date / parse_hour / parse_minute', () {
    expect(parseDate('01.07.2025'), '2025-07-01');
    expect(parseDate('2025-07-01 00:00:00'), '2025-07-01');
    expect(parseDate('31.02.2025'), isNull);
    expect(parseHour('2025-07-01 03:00:00'), 3);
    expect(parseHour('17'), 17);
    expect(parseMinute('03:15'), 15);
    expect(parseMinute('3'), 0);
  });

  test('Makine dosyası: 24 saatlik gün kabul, eksik gün atlanır', () async {
    final dir = Directory.systemTemp.createTempSync('cd_pkg');
    final f = File('${dir.path}/m.csv');
    final rows = ['Tarih;Saat;kWh'];
    for (var h = 0; h < 24; h++) {
      rows.add('15.07.2025;$h;${(10 + h).toString()},5');
    }
    for (var h = 0; h < 20; h++) {
      rows.add('16.07.2025;$h;1,0');
    }
    f.writeAsStringSync(rows.join('\n'));
    final c = await checkMachineFile(f.path, {'2025-07-15', '2025-07-16'});
    expect(c.report.hasErrors, isFalse);
    expect(c.days, ['2025-07-15']);
    expect(c.frame!.length, 24);
    expect(c.frame!.first.$3, 10.5);
  });

  test('Katsayı dosyası: eksik fosil kaynak hata verir', () async {
    final dir = Directory.systemTemp.createTempSync('cd_fac');
    final f = File('${dir.path}/f.csv');
    f.writeAsStringSync('Kaynak;tCO2/MWh;tCO2-eşd/MWh\nLinyit;1,2;1,21\nDoğal Gaz;0,41;0,42\n');
    final c = await checkFactorsFile(f.path, {});
    expect(c.report.hasErrors, isTrue);
    expect(c.factors['Linyit'], (1.2, 1.21));
  });
}
