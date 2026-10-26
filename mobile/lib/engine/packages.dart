// Kullanıcı veri paketleri: yeni makine, yeni yıl (EPİAŞ) ve yeni emisyon
// katsayıları (engine/packages.py).
//
// Varsayılan 2025 verisi uygulama içinde kalır (assets/shared). Eklenen veriler
// uygulamanın kendi klasöründe veri/<paket>/ altında tutulur; her pakette
// manifest.json bulunur. Hesap formülü değişmez: yalnızca veri eklenir.

import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;

import 'package:path_provider/path_provider.dart';

import 'sources.dart';
import 'table_reader.dart';

const String kindMachine = 'machine';
const String kindGrid = 'grid';
const String kindFactors = 'factors';
const String kindBroken = 'broken';

Directory? _dataDirOverride;

/// Testler için veri klasörünü değiştirir.
void setDataDirForTests(Directory d) => _dataDirOverride = d;

Future<Directory> dataDir() async {
  if (_dataDirOverride != null) return _dataDirOverride!;
  final base = await getApplicationSupportDirectory();
  return Directory('${base.path}${Platform.pathSeparator}veri');
}

// ---------------- sayı / tarih / saat okuma ----------------

/// '1.234,56', '12,40', ',01', '-,05', '12.4' → double; boş → NaN.
double parseNum(Object? value) {
  if (value == null) return double.nan;
  if (value is num) return value.toDouble();
  var s = value.toString().trim().replaceAll(' ', '').replaceAll(' ', '');
  if (const ['', '-', 'nan', 'NaN', 'None'].contains(s)) return double.nan;
  if (s.contains(',') && s.contains('.')) {
    if (s.lastIndexOf(',') > s.lastIndexOf('.')) {
      s = s.replaceAll('.', '').replaceAll(',', '.');
    } else {
      s = s.replaceAll(',', '');
    }
  } else if (s.contains(',')) {
    s = s.replaceAll(',', '.');
  }
  return double.tryParse(s) ?? double.nan;
}

String _two(int v) => v.toString().padLeft(2, '0');

/// '2026-01-01', '01.01.2026', '01/01/2026', '2026-01-01 00:00:00' → '2026-01-01'.
String? parseDate(Object? value) {
  final s = (value ?? '').toString().trim();
  if (s.isEmpty || s.toLowerCase() == 'nan') return null;
  int y, mo, d;
  final m1 = RegExp(r'^(\d{4})-(\d{1,2})-(\d{1,2})').firstMatch(s);
  if (m1 != null) {
    y = int.parse(m1.group(1)!);
    mo = int.parse(m1.group(2)!);
    d = int.parse(m1.group(3)!);
  } else {
    final m2 = RegExp(r'^(\d{1,2})[./-](\d{1,2})[./-](\d{4})').firstMatch(s);
    if (m2 == null) return null;
    d = int.parse(m2.group(1)!);
    mo = int.parse(m2.group(2)!);
    y = int.parse(m2.group(3)!);
  }
  if (mo < 1 || mo > 12 || d < 1) return null;
  final dt = DateTime(y, mo, d);
  if (dt.year != y || dt.month != mo || dt.day != d) return null;
  return '${y.toString().padLeft(4, '0')}-${_two(mo)}-${_two(d)}';
}

int? parseHour(Object? value) {
  final s = (value ?? '').toString().trim();
  final target = s.contains(' ') ? s.split(' ').last : s;
  final m = RegExp(r'(\d{1,2})(?::\d{2})?').firstMatch(target);
  if (m == null) return null;
  final h = int.parse(m.group(1)!);
  return (0 <= h && h <= 23) ? h : null;
}

/// '03:15' / '3.30' / '03:15:00' → dakika; saat bilgisi yoksa 0.
int parseMinute(Object? timeText) {
  final m = RegExp(r'^\s*\d{1,2}[:.](\d{2})').firstMatch((timeText ?? '').toString());
  return m != null ? int.parse(m.group(1)!) : 0;
}

String? findCol(Table df, List<String> aliases) {
  final cols = <String, String>{};
  for (final c in df.columns) {
    cols.putIfAbsent(norm(c), () => c);
  }
  for (final a in aliases) {
    if (cols.containsKey(a)) return cols[a];
  }
  for (final a in aliases) {
    for (final e in cols.entries) {
      if (e.key.startsWith(a)) return e.value;
    }
  }
  return null;
}

List<int> _minutes(Table df) {
  final dcol = findCol(df, const ['tarih', 'date', 'gun']);
  for (final c in df.columns) {
    final n = norm(c);
    if (c != dcol &&
        (n.startsWith('saat') || n.startsWith('hour') || n.startsWith('time') || n.startsWith('zaman'))) {
      final mins = [for (final v in df.column(c)) parseMinute(v)];
      if (mins.any((m) => m != 0)) return mins;
    }
  }
  final hcol = findCol(df, const ['saatno', 'saat', 'hour']);
  if (hcol != null && hcol != dcol) {
    return [for (final v in df.column(hcol)) parseMinute(v)];
  }
  final tcol = findCol(df, const ['tarihsaat', 'tarihsaatanahtari', 'datetime', 'zaman', 'tarih', 'date']);
  if (tcol == null) return List.filled(df.length, 0);
  return [
    for (final v in df.column(tcol))
      v.trim().contains(' ') ? parseMinute(v.trim().split(' ').sublist(1).join(' ')) : 0,
  ];
}

(List<String?>, List<int?>)? _dateHour(Table df) {
  final dcol = findCol(df, const ['tarih', 'date', 'gun']);
  final hcol = findCol(df, const ['saatno', 'saat', 'hour']);
  if (dcol != null && hcol != null && dcol != hcol) {
    return (
      [for (final v in df.column(dcol)) parseDate(v)],
      [for (final v in df.column(hcol)) parseHour(v)],
    );
  }
  final tcol = findCol(df, const ['tarihsaat', 'tarihsaatanahtari', 'datetime', 'zaman', 'tarih', 'date']);
  if (tcol == null) return null;
  return (
    [for (final v in df.column(tcol)) parseDate(v)],
    [for (final v in df.column(tcol)) parseHour(v)],
  );
}

// ---------------- rapor ----------------

/// İçe aktarma kontrol raporu: (düzey, metin) satırları; düzey ok | warn | err.
class Report {
  final List<(String, String)> lines = [];
  void ok(String t) => lines.add(('ok', t));
  void warn(String t) => lines.add(('warn', t));
  void err(String t) => lines.add(('err', t));
  bool get hasErrors => lines.any((l) => l.$1 == 'err');
}

String _fmtDate(String iso) {
  final p = iso.split('-');
  return '${p[2]}.${p[1]}.${p[0]}';
}

String _fmtInt(int n) {
  final s = n.abs().toString();
  final b = StringBuffer();
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) b.write('.');
    b.write(s[i]);
  }
  return (n < 0 ? '-' : '') + b.toString();
}

/// Python '{:,.2f}' ve '.'↔',' takası: 1234.5 → '1.234,50'.
String _fmt2Grouped(double v) {
  final s = v.abs().toStringAsFixed(2);
  final parts = s.split('.');
  final i = _fmtInt(int.parse(parts[0]));
  return '${v < 0 ? '-' : ''}$i,${parts[1]}';
}

/// Python '{:g}' (6 anlamlı basamak, sondaki sıfırlar atılır).
String fmtG(double v) {
  if (v == 0) return '0';
  var s = v.toStringAsPrecision(6);
  if (s.contains('e')) {
    final parts = s.split('e');
    var m = parts[0];
    if (m.contains('.')) m = m.replaceAll(RegExp(r'0+$'), '').replaceAll(RegExp(r'\.$'), '');
    final exp = int.parse(parts[1]);
    return '${m}e${exp < 0 ? '-' : '+'}${exp.abs().toString().padLeft(2, '0')}';
  }
  if (s.contains('.')) s = s.replaceAll(RegExp(r'0+$'), '').replaceAll(RegExp(r'\.$'), '');
  return s;
}

// ---------------- paketler ----------------

class Package {
  Package({
    required this.id,
    required this.kind,
    required this.name,
    required this.enabled,
    required this.createdAt,
    required this.meta,
    required this.path,
  });

  final String id;
  final String kind;
  final String name;
  final bool enabled;
  final String createdAt;
  final Map<String, dynamic> meta;
  final Directory path;

  File file(String name) => File('${path.path}${Platform.pathSeparator}$name');
}

Future<String> readText(File f) async => decodeText(await f.readAsBytes());

Future<List<Package>> listPackages() async {
  final root = await dataDir();
  final out = <Package>[];
  if (!await root.exists()) return out;
  final dirs = await root.list().where((e) => e is Directory).cast<Directory>().toList();
  dirs.sort((a, b) => a.path.compareTo(b.path));
  for (final d in dirs) {
    final mf = File('${d.path}${Platform.pathSeparator}manifest.json');
    if (!await mf.exists()) continue;
    final name = d.uri.pathSegments.where((s) => s.isNotEmpty).last;
    try {
      final m = jsonDecode(await readText(mf)) as Map<String, dynamic>;
      out.add(Package(
        id: m['id'].toString(),
        kind: m['kind'].toString(),
        name: m['name'].toString(),
        enabled: (m['enabled'] ?? true) == true,
        createdAt: (m['created_at'] ?? '').toString(),
        meta: Map<String, dynamic>.from((m['meta'] ?? {}) as Map),
        path: d,
      ));
    } catch (e) {
      out.add(Package(
        id: name,
        kind: kindBroken,
        name: name,
        enabled: false,
        createdAt: '',
        meta: {'error': 'manifest okunamadı: $e'},
        path: d,
      ));
    }
  }
  return out;
}

Future<void> _writeManifest(Directory path, Map<String, dynamic> manifest) async {
  await File('${path.path}${Platform.pathSeparator}manifest.json')
      .writeAsString(const JsonEncoder.withIndent(' ').convert(manifest));
}

Future<void> setEnabled(String pkgId, bool enabled) async {
  for (final p in await listPackages()) {
    if (p.id != pkgId) continue;
    if (p.kind == kindBroken) {
      throw StateError('Okunamayan paket açılamaz; silip yeniden ekleyin.');
    }
    final m = jsonDecode(await readText(p.file('manifest.json'))) as Map<String, dynamic>;
    m['enabled'] = enabled;
    await _writeManifest(p.path, m);
    if (enabled && p.kind == kindFactors) {
      for (final q in await listPackages()) {
        if (q.kind == kindFactors && q.id != pkgId && q.enabled) {
          await setEnabled(q.id, false);
        }
      }
    }
    return;
  }
  throw StateError('Paket yok: $pkgId');
}

Future<void> deletePackage(String pkgId) async {
  for (final p in await listPackages()) {
    if (p.id == pkgId) {
      await p.path.delete(recursive: true);
      return;
    }
  }
  throw StateError('Paket yok: $pkgId');
}

String _slug(String text) {
  final s = norm(text);
  final cut = s.length > 24 ? s.substring(0, 24) : s;
  return cut.isEmpty ? 'paket' : cut;
}

String _nowIsoSeconds() {
  final n = DateTime.now();
  return '${n.year}-${_two(n.month)}-${_two(n.day)}T${_two(n.hour)}:${_two(n.minute)}:${_two(n.second)}';
}

Future<(Directory, Map<String, dynamic>)> _newPackage(
    String kind, String name, Map<String, dynamic> meta) async {
  final n = DateTime.now();
  final micro = (n.millisecond * 1000 + n.microsecond).toString().padLeft(6, '0');
  final stamp = ('${n.year}${_two(n.month)}${_two(n.day)}${_two(n.hour)}${_two(n.minute)}${_two(n.second)}$micro')
      .substring(0, 17);
  final pkgId = '$kind-$stamp-${_slug(name)}';
  final root = await dataDir();
  final path = Directory('${root.path}${Platform.pathSeparator}$pkgId');
  await path.create(recursive: true);
  final manifest = {
    'id': pkgId,
    'kind': kind,
    'name': name,
    'enabled': true,
    'created_at': _nowIsoSeconds(),
    'meta': meta,
  };
  return (path, manifest);
}

String _repr(double v) => v.toString();

// ---------------- makine paketi ----------------

class MachineCheck {
  MachineCheck(this.report,
      {this.frame, this.days = const [], this.profile = const [], this.rows = 0});
  final Report report;

  /// (Tarih, Saat_No, Saatlik_Tuketim_kWh)
  final List<(String, int, double)>? frame;
  final List<String> days;
  final List<double> profile;
  final int rows;
}

Future<MachineCheck> checkMachineFile(String path, Set<String> gridDates) async {
  final rep = Report();
  Table df;
  try {
    df = await readTable(path);
  } catch (e) {
    rep.err('Dosya okunamadı: $e');
    return MachineCheck(rep);
  }
  final rows = df.length;
  final dh = _dateHour(df);
  var kcol = findCol(df, const ['kwh', 'saatliktuketimkwh', 'saatliktuketim', 'tuketim', 'enerji', 'consumption']);
  var power = false;
  if (kcol == null) {
    kcol = findCol(df, const ['saatlikortalamaguckw', 'ortalamaguc', 'guckw', 'guc', 'kw', 'power']);
    power = kcol != null;
  }
  if (dh == null || kcol == null) {
    rep.err('Sütunlar bulunamadı. Beklenen: Tarih, Saat, kWh (ör. 2026-01-01;0;12,40).');
    return MachineCheck(rep, rows: rows);
  }
  final (dates, hours) = dh;
  final minutes = _minutes(df);
  final vals = [for (final v in df.column(kcol)) parseNum(v)];

  final badIdx = <int>[];
  for (var i = 0; i < rows; i++) {
    if (dates[i] == null || hours[i] == null) badIdx.add(i);
  }
  if (badIdx.isNotEmpty) {
    final sample = badIdx.take(4).map((i) => _fmtInt(i + 2)).join(', ');
    rep.warn('${badIdx.length} satırda tarih/saat okunamadı (satır $sample…) — atlanacak');
  }
  // (Tarih, Saat, Dakika, kWh)
  var t = <(String, int, int, double)>[
    for (var i = 0; i < rows; i++)
      if (dates[i] != null && hours[i] != null) (dates[i]!, hours[i]!, minutes[i], vals[i]),
  ];
  if (t.isEmpty) {
    rep.err('Okunabilir satır yok.');
    return MachineCheck(rep, rows: rows);
  }

  final mins = {for (final r in t) r.$3}.toList()..sort();
  List<(String, int, double)> hourly;
  if (!(mins.length == 1 && mins.first == 0)) {
    final n = mins.length;
    final expected = [for (var m = 0; m < 60; m += 60 ~/ n) m];
    if (60 % n != 0 || mins.join(',') != expected.join(',')) {
      rep.err('Desteklenmeyen zaman aralığı (dakikalar: ${mins.take(6).join(', ')}). '
          'Saatlik, 30 veya 15 dakikalık veri kullanın.');
      return MachineCheck(rep, rows: rows);
    }
    final groups = <String, List<double>>{};
    for (final r in t) {
      groups.putIfAbsent('${r.$1}|${r.$2.toString().padLeft(2, '0')}', () => []).add(r.$4);
    }
    final keys = groups.keys.toList()..sort();
    hourly = [];
    for (final k in keys) {
      final g = groups[k]!;
      final nanIn = g.any((v) => v.isNaN);
      final valid = [for (final v in g) if (!v.isNaN) v];
      final count = valid.length;
      final sum = valid.fold(0.0, (a, b) => a + b);
      final complete = count == n && !nanIn;
      final v = complete ? (power ? sum / count : sum) : double.nan;
      final parts = k.split('|');
      hourly.add((parts[0], int.parse(parts[1]), v));
    }
    final how = power ? 'saatlik ortalama güç alındı (kWh)' : 'her saatin enerjisi toplandı (kWh)';
    rep.ok('${60 ~/ n} dakikalık veri algılandı; saatliğe çevrildi — $how');
  } else {
    if (power) {
      rep.ok('Güç (kW) sütunu algılandı; saatlik ortalama güç, o saatin enerjisi (kWh) olarak alındı');
    }
    hourly = [for (final r in t) (r.$1, r.$2, r.$4)];
  }

  final allDays = {for (final r in hourly) r.$1}.toList()..sort();
  rep.ok('${_fmtInt(allDays.length)} gün okundu · ${_fmtDate(allDays.first)} – ${_fmtDate(allDays.last)}');

  final byDay = <String, List<(String, int, double)>>{};
  for (final r in hourly) {
    byDay.putIfAbsent(r.$1, () => []).add(r);
  }
  final noGrid = <String>[];
  final skipped = <(String, String)>[];
  final usable = <String>[];
  for (final day in allDays) {
    final g = byDay[day]!;
    final hrs = [for (final r in g) r.$2]..sort();
    final uniq = hrs.toSet();
    if (hrs.join(',') != List.generate(24, (i) => i).join(',')) {
      skipped.add((day, '${uniq.length} saat${hrs.length != uniq.length ? ' (tekrarlı saat)' : ''}'));
      continue;
    }
    final nanCount = g.where((r) => r.$3.isNaN).length;
    if (nanCount > 0) {
      skipped.add((day, '$nanCount saat boş'));
      continue;
    }
    if (g.any((r) => r.$3 < 0)) {
      skipped.add((day, 'negatif değer'));
      continue;
    }
    if (!gridDates.contains(day)) {
      noGrid.add(day);
      continue;
    }
    usable.add(day);
  }
  if (skipped.isNotEmpty) {
    final sample = skipped.take(3).map((x) => '${_fmtDate(x.$1)} (${x.$2})').join('; ');
    rep.warn('${skipped.length} gün eksik/hatalı — atlanacak: $sample${skipped.length > 3 ? ' …' : ''}');
  }
  if (noGrid.isNotEmpty) {
    rep.warn('${noGrid.length} gün için şebeke verisi yok — atlanacak (${_fmtDate(noGrid.first)} – '
        '${_fmtDate(noGrid.last)}). Gerekirse önce o yılı ekleyin.');
  }
  if (usable.isEmpty) {
    rep.err('Kullanılabilir gün yok (her gün 24 tekrarsız saat ve şebeke verisi gerekir).');
    return MachineCheck(rep, rows: rows);
  }
  rep.ok('${_fmtInt(usable.length)} gün kullanılabilir (her gün 24 saat, tekrarsız, şebeke verisi var)');
  final usableSet = usable.toSet();
  final keep = [for (final r in hourly) if (usableSet.contains(r.$1)) r]
    ..sort((a, b) {
      final c = a.$1.compareTo(b.$1);
      return c != 0 ? c : a.$2.compareTo(b.$2);
    });
  final maxV = keep.map((r) => r.$3).reduce(math.max);
  rep.ok('Negatif değer yok · en büyük saatlik değer ${_fmt2Grouped(maxV)} kWh');
  final profile = List<double>.generate(24, (h) {
    final vs = [for (final r in keep) if (r.$2 == h) r.$3];
    return vs.isEmpty ? double.nan : vs.fold(0.0, (a, b) => a + b) / vs.length;
  });
  return MachineCheck(rep, frame: keep, days: usable, profile: profile, rows: rows);
}

Future<Package> addMachinePackage(MachineCheck check, String name, String machineType,
    bool shiftable, String source) async {
  assert(check.frame != null && !check.report.hasErrors);
  final n = DateTime.now();
  final slug = _slug(name);
  final assetId = 'u_${slug.length > 12 ? slug.substring(0, 12) : slug}_${_two(n.hour)}${_two(n.minute)}${_two(n.second)}';
  final meta = {
    'machines': 1,
    'first_day': check.days.first,
    'last_day': check.days.last,
    'days': check.days.length,
    'source': source,
  };
  final (path, manifest) = await _newPackage(kindMachine, name, meta);
  final b = StringBuffer('AssetId,Tarih,Saat_No,Saatlik_Tuketim_kWh\n');
  for (final r in check.frame!) {
    b.write('$assetId,${r.$1},${r.$2},${_repr(r.$3)}\n');
  }
  await File('${path.path}${Platform.pathSeparator}loads.csv').writeAsString(b.toString());
  final machine = {
    'id': assetId,
    'name': name,
    'type': machineType.isNotEmpty ? machineType : 'Kullanıcı makinesi',
    'role': shiftable ? 'Esnek_Yuk' : 'Kayamayan_Kisitli_Yuk',
    'shiftable': shiftable,
    'first_day': check.days.first,
    'last_day': check.days.last,
    'days': check.days,
    'source': source,
  };
  await File('${path.path}${Platform.pathSeparator}machines.json')
      .writeAsString(const JsonEncoder.withIndent(' ').convert([machine]));
  await _writeManifest(path, manifest);
  return Package(
      id: manifest['id'] as String, kind: kindMachine, name: name, enabled: true,
      createdAt: manifest['created_at'] as String, meta: meta, path: path);
}

String machineTemplateCsv() {
  final rows = ['Tarih;Saat;kWh'];
  for (var h = 0; h < 24; h++) {
    rows.add('2026-01-01;$h;${(12.4 + (h % 6) * 0.5).toStringAsFixed(2).replaceAll('.', ',')}');
  }
  return '﻿${rows.join('\n')}\n';
}

Future<void> writeMachineTemplate(String path) async {
  await File(path).writeAsString(machineTemplateCsv());
}

// ---------------- şebeke paketi ----------------

class GridRow {
  GridRow(this.date, this.hour, this.mwh);
  final String date;
  final int hour;
  final Map<String, double> mwh;
}

class GridComputed {
  GridComputed(this.date, this.hour, this.ciT, this.ciE, this.ren, this.fos, this.dom, this.shares);
  final String date;
  final int hour;
  final double ciT, ciE, ren, fos;
  final String dom;
  final Map<String, double> shares;
}

/// Kaynak üretimlerinden (MWh) varsayılan asset şemasını üretir.
List<GridComputed> computeGrid(List<GridRow> mwh, Map<String, (double, double)> factors) {
  return [
    for (final r in mwh)
      () {
        var total = 0.0;
        for (final s in allSources) {
          total += r.mwh[s]!;
        }
        var emT = 0.0, emE = 0.0;
        for (final s in allSources) {
          emT += r.mwh[s]! * (factors[s] ?? (0.0, 0.0)).$1;
        }
        for (final s in allSources) {
          emE += r.mwh[s]! * (factors[s] ?? (0.0, 0.0)).$2;
        }
        var renSum = 0.0;
        for (final s in renewable) {
          renSum += r.mwh[s]!;
        }
        final ren = renSum / total * 100;
        var dom = allSources.first;
        for (final s in allSources) {
          if (r.mwh[s]! > r.mwh[dom]!) dom = s;
        }
        return GridComputed(r.date, r.hour, emT / total, emE / total, ren, 100 - ren, dom,
            {for (final s in allSources) s: r.mwh[s]! / total * 100});
      }(),
  ];
}

class GridCheck {
  GridCheck(this.report, {this.frame, this.days = const [], this.years = const []});
  final Report report;
  final List<GridComputed>? frame;
  final List<String> days;
  final List<int> years;
}

Future<GridCheck> checkGridFile(
    String path, Map<String, (double, double)> factors, Set<String> existingDates) async {
  final rep = Report();
  Table df;
  try {
    df = await readTable(path);
  } catch (e) {
    rep.err('Dosya okunamadı: $e');
    return GridCheck(rep);
  }
  final dh = _dateHour(df);
  if (dh == null) {
    rep.err('Tarih/saat sütunu bulunamadı (ör. Tarih + Saat).');
    return GridCheck(rep);
  }
  final cols = <String, String>{};
  for (final c in df.columns) {
    final k = sourceKey(c);
    if (k != null && !cols.containsKey(k)) cols[k] = c;
  }
  final missing = [for (final s in sources) if (!cols.containsKey(s)) sourceNames[s]!];
  if (missing.length > 3) {
    rep.err('Kaynak bazında üretim sütunları bulunamadı (Doğal Gaz, Linyit, Rüzgar …). '
        'EPİAŞ Şeffaflık Platformu › Gerçek Zamanlı Üretim dışa aktarımını kullanın.');
    return GridCheck(rep);
  }
  if (missing.isNotEmpty) {
    rep.warn('Bulunamayan kaynak sütunları 0 kabul edildi: ${missing.join(', ')}');
  }
  rep.ok('Biçim tanındı: ${cols.length} kaynak sütunu, ${_fmtInt(df.length)} satır');

  final (dates, hours) = dh;
  var neg = 0, fixed = 0;
  final values = <String, List<double>>{};
  final fixRe = RegExp(r'^\s*-?,\d');
  for (final s in allSources) {
    if (cols.containsKey(s)) {
      final raw = df.column(cols[s]!);
      fixed += raw.where((v) => fixRe.hasMatch(v)).length;
      final v = [for (final x in raw) parseNum(x)];
      neg += v.where((x) => x < 0).length;
      values[s] = [for (final x in v) x.isNaN ? x : math.max(0.0, x)];
    } else {
      values[s] = List.filled(df.length, 0.0);
    }
  }
  if (fixed > 0) rep.ok("${_fmtInt(fixed)} hücrede eksik sıfırlı ondalık (',01') düzeltildi");
  if (neg > 0) rep.warn('${_fmtInt(neg)} negatif üretim değeri (gece güneş iç tüketimi vb.) 0 yapıldı');

  var rowsT = <GridRow>[];
  var bad = 0;
  for (var i = 0; i < df.length; i++) {
    final anyNan = allSources.any((s) => values[s]![i].isNaN);
    if (dates[i] == null || hours[i] == null || anyNan) {
      bad++;
      continue;
    }
    rowsT.add(GridRow(dates[i]!, hours[i]!, {for (final s in allSources) s: values[s]![i]}));
  }
  if (bad > 0) rep.warn('$bad satır okunamadı — atlanacak');
  if (rowsT.isEmpty) {
    rep.err('Okunabilir satır yok.');
    return GridCheck(rep);
  }
  final byDay = <String, List<GridRow>>{};
  for (final r in rowsT) {
    byDay.putIfAbsent(r.date, () => []).add(r);
  }
  final daysSorted = byDay.keys.toList()..sort();
  final skipped = <String>[], usable = <String>[];
  for (final day in daysSorted) {
    final g = byDay[day]!;
    final hrs = [for (final r in g) r.hour]..sort();
    final full = hrs.join(',') == List.generate(24, (i) => i).join(',');
    final positive = g.every((r) => allSources.fold(0.0, (a, s) => a + r.mwh[s]!) > 0);
    (full && positive ? usable : skipped).add(day);
  }
  if (skipped.isNotEmpty) {
    rep.warn('${skipped.length} gün eksik/tekrarlı saatli — atlanacak (ör. ${_fmtDate(skipped.first)})');
  }
  if (usable.isEmpty) {
    rep.err('Tam 24 saati olan gün yok.');
    return GridCheck(rep);
  }
  final usableSet = usable.toSet();
  rowsT = [for (final r in rowsT) if (usableSet.contains(r.date)) r]
    ..sort((a, b) {
      final c = a.date.compareTo(b.date);
      return c != 0 ? c : a.hour.compareTo(b.hour);
    });
  final grid = computeGrid(rowsT, factors);
  final years = {for (final d in usable) int.parse(d.substring(0, 4))}.toList()..sort();
  rep.ok('${_fmtInt(usable.length)} tam gün · ${_fmtInt(rowsT.length)} saat · '
      '${_fmtDate(usable.first)} – ${_fmtDate(usable.last)}');
  final ci = [for (final g in grid) g.ciT];
  final mean = ci.fold(0.0, (a, b) => a + b) / ci.length;
  rep.ok('Karbon yoğunluğu (tCO2/MWh): en düşük ${ci.reduce(math.min).toStringAsFixed(3)} · '
          'ortalama ${mean.toStringAsFixed(3)} · en yüksek ${ci.reduce(math.max).toStringAsFixed(3)}'
      .replaceAll('.', ','));
  final overlap = usable.where(existingDates.contains).toList();
  if (overlap.isNotEmpty) {
    rep.warn('${overlap.length} gün mevcut veriyle çakışıyor; bu paket etkinken yeni veri kullanılır.');
  }
  return GridCheck(rep, frame: grid, days: usable, years: years);
}

Future<Package> addGridPackage(GridCheck check, String name) async {
  assert(check.frame != null && !check.report.hasErrors);
  final meta = {
    'years': check.years,
    'first_day': check.days.first,
    'last_day': check.days.last,
    'days': check.days.length,
    'hours': check.frame!.length,
  };
  final (path, manifest) = await _newPackage(kindGrid, name, meta);
  final header = [
    'Tarih', 'Saat_No', 'Karbon_Yogunlugu_tCO2_MWh', 'Karbon_Yogunlugu_tCO2esd_MWh',
    'Yenilenebilir_Payi_Yuzde', 'Fosil_Payi_Yuzde', 'Baskin_Kaynak',
    for (final s in allSources) '${s}_Pay_Yuzde',
  ];
  final b = StringBuffer('${header.join(',')}\n');
  for (final g in check.frame!) {
    b.write([
      g.date, g.hour, _repr(g.ciT), _repr(g.ciE), _repr(g.ren), _repr(g.fos), g.dom,
      for (final s in allSources) _repr(g.shares[s]!),
    ].join(','));
    b.write('\n');
  }
  await File('${path.path}${Platform.pathSeparator}epias.csv').writeAsString(b.toString());
  await _writeManifest(path, manifest);
  return Package(
      id: manifest['id'] as String, kind: kindGrid, name: name, enabled: true,
      createdAt: manifest['created_at'] as String, meta: meta, path: path);
}

// ---------------- katsayı paketi ----------------

class FactorsCheck {
  FactorsCheck(this.report, [Map<String, (double, double)>? factors]) : factors = factors ?? {};
  final Report report;
  final Map<String, (double, double)> factors;
}

Future<FactorsCheck> checkFactorsFile(String path, Map<String, (double, double)> current) async {
  final rep = Report();
  Table df;
  try {
    df = await readTable(path);
  } catch (e) {
    rep.err('Dosya okunamadı: $e');
    return FactorsCheck(rep);
  }
  final tcol = findCol(df, const ['emisyonfaktorutco2', 'tco2', 'co2']);
  var ecol = findCol(df, const ['emisyonfaktorutco2esd', 'tco2esd', 'tco2eşd', 'co2esd', 'esdeger']);
  if (ecol == tcol) ecol = null;
  if (tcol == null) {
    rep.err('tCO2/MWh sütunu bulunamadı (ör. Kaynak; tCO2/MWh; tCO2-eşd/MWh).');
    return FactorsCheck(rep);
  }
  final nameCols = [for (final c in df.columns) if (c != tcol && c != ecol) c];
  final factors = <String, (double, double)>{};
  final unknown = <String>[];
  final ti = df.columns.indexOf(tcol);
  final ei = ecol == null ? -1 : df.columns.indexOf(ecol);
  for (final row in df.rows) {
    String? key;
    for (final c in nameCols) {
      key = sourceKey(row[df.columns.indexOf(c)]);
      if (key != null) break;
    }
    final t = parseNum(row[ti]);
    final e = ei >= 0 ? parseNum(row[ei]) : t;
    if (key == null) {
      var label = '?';
      for (final c in nameCols) {
        final v = row[df.columns.indexOf(c)];
        if (v.trim().isNotEmpty) {
          label = v;
          break;
        }
      }
      unknown.add(label);
      continue;
    }
    if (t.isNaN || t < 0 || e.isNaN || e < 0) {
      rep.err('${sourceNames[key]} için geçersiz katsayı.');
      continue;
    }
    factors[key] = (t, e);
  }
  if (unknown.isNotEmpty) {
    rep.warn('Tanınmayan satırlar atlandı: ${unknown.take(5).join(', ')}');
  }
  final missing = [for (final s in requiredFossil) if (!factors.containsKey(s)) sourceNames[s]!];
  if (missing.isNotEmpty) rep.err('Eksik fosil kaynak katsayısı: ${missing.join(', ')}');
  for (final s in allSources) {
    factors.putIfAbsent(s, () => renewable.contains(s) ? (0.0, 0.0) : (current[s] ?? (0.0, 0.0)));
  }
  final changed = [
    for (final s in allSources)
      if ((factors[s]!.$1 - (current[s] ?? (0.0, 0.0)).$1).abs() > 1e-12) s,
  ];
  rep.ok('${allSources.where(factors.containsKey).length} kaynak katsayısı okundu');
  if (changed.isNotEmpty) {
    rep.ok('Değişen: ${changed.map((s) => '${sourceNames[s]} ${fmtG((current[s] ?? (0.0, 0.0)).$1)} → ${fmtG(factors[s]!.$1)}'.replaceAll('.', ',')).join(', ')}');
  } else {
    rep.warn('Katsayılar mevcut değerlerle aynı; sonuçlar değişmez.');
  }
  return FactorsCheck(rep, factors);
}

Future<Package> addFactorsPackage(FactorsCheck check, String name) async {
  assert(!check.report.hasErrors);
  final meta = {'label': name};
  final (path, manifest) = await _newPackage(kindFactors, name, meta);
  final rows = ['Kaynak;Emisyon_Faktoru_tCO2_MWh;Emisyon_Faktoru_tCO2esd_MWh;Kategori'];
  for (final s in allSources) {
    final (t, e) = check.factors[s]!;
    final cat = renewable.contains(s) ? 'Yenilenebilir / Sıfır Doğrudan Yakıt Emisyonu' : 'Fosil';
    rows.add('${sourceNames[s]};${_repr(t)};${_repr(e)};$cat');
  }
  await File('${path.path}${Platform.pathSeparator}factors.csv').writeAsString('${rows.join('\n')}\n');
  await _writeManifest(path, manifest);
  for (final q in await listPackages()) {
    if (q.kind == kindFactors && q.id != manifest['id'] && q.enabled) {
      await setEnabled(q.id, false);
    }
  }
  return Package(
      id: manifest['id'] as String, kind: kindFactors, name: name, enabled: true,
      createdAt: manifest['created_at'] as String, meta: meta, path: path);
}

Future<Map<String, (double, double)>> readFactorsCsv(File file) async {
  final df = await readTable(file.path);
  final out = <String, (double, double)>{};
  for (final row in df.rows) {
    if (row.length < 3) continue;
    final k = sourceKey(row[0]);
    if (k != null) out[k] = (parseNum(row[1]), parseNum(row[2]));
  }
  return out;
}
