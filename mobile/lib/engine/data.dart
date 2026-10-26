// shared/assets (varsayılan 2025 verisi) + etkin veri paketleri (engine/data.py).
//
// Hesap için düz listeler sunar; formül burada değil, engine/core.dart'tadır.
// Katsayı paketi etkinse karbon yoğunluğu kaynak payları × yeni katsayılarla
// yeniden hesaplanır.

import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;

import 'packages.dart' as pk;
import 'sources.dart';

const String baseGridLabel = 'EPİAŞ 2025';
const String baseFactorsLabel = 'ETKB 2023';
const String sampleSource = 'Zenodo';

const Map<String, String> ciColumns = {
  'tCO2': 'Karbon_Yogunlugu_tCO2_MWh',
  'tCO2esd': 'Karbon_Yogunlugu_tCO2esd_MWh',
};

class GridHour {
  GridHour({
    required this.date,
    required this.hour,
    required this.ciT,
    required this.ciE,
    required this.renewablePct,
    required this.fossilPct,
    required this.dominant,
    required this.shares,
    required this.src,
  });

  final String date;
  final int hour;
  double ciT;
  double ciE;
  final double renewablePct;
  final double fossilPct;
  final String dominant;

  /// Kaynak → yüzde pay (yalnızca dosyada olan kaynaklar).
  final Map<String, double> shares;
  String src;
}

class Machine {
  Machine({
    required this.id,
    required this.name,
    required this.type,
    required this.role,
    required this.shiftable,
    required this.firstDay,
    required this.lastDay,
    required this.days,
    required this.source,
    required this.package,
  });

  final String id;
  final String name;
  final String type;
  final String role;
  final bool shiftable;
  String firstDay;
  String lastDay;
  List<String> days;

  /// 'sample' | 'real'
  final String source;
  final String? package;

  factory Machine.fromJson(Map<String, dynamic> m, {String? package}) => Machine(
        id: m['id'] as String,
        name: m['name'] as String,
        type: (m['type'] ?? '') as String,
        role: (m['role'] ?? '') as String,
        shiftable: m['shiftable'] as bool,
        firstDay: (m['first_day'] ?? '') as String,
        lastDay: (m['last_day'] ?? '') as String,
        days: [for (final d in m['days'] as List) d as String],
        source: (m['source'] ?? 'sample') as String,
        package: package,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'type': type,
        'shiftable': shiftable,
      };
}

class EtkbRow {
  const EtkbRow(this.name, this.tco2, this.tco2esd, this.category);
  final String name;
  final String tco2; // ekranda ham metin olarak gösterilir
  final String tco2esd;
  final String category;
}

class _Parsed {
  _Parsed(this.grid, this.loads);
  final Map<String, List<GridHour>> grid;
  final Map<String, List<double>> loads;
}

List<String> _splitLine(String line) => line.split(',');

List<String> _lines(String text) {
  final out = <String>[];
  for (final l in const LineSplitter().convert(text)) {
    if (l.trim().isNotEmpty) out.add(l);
  }
  return out;
}

double _num(String v) => double.parse(v.trim());

/// epias CSV metnini Tarih → 24 saatlik kayıt listesine çevirir.
Map<String, List<GridHour>> parseGridCsv(String text, String srcLabel) {
  final lines = _lines(text);
  var header = _splitLine(lines.first);
  if (header.isNotEmpty && header.first.startsWith('﻿')) {
    header = [header.first.substring(1), ...header.skip(1)];
  }
  int col(String n) => header.indexOf(n);
  final cDate = col('Tarih'), cHour = col('Saat_No');
  final cT = col('Karbon_Yogunlugu_tCO2_MWh'), cE = col('Karbon_Yogunlugu_tCO2esd_MWh');
  final cRen = col('Yenilenebilir_Payi_Yuzde'), cFos = col('Fosil_Payi_Yuzde');
  final cDom = col('Baskin_Kaynak');
  final shareCols = <String, int>{};
  for (final s in allSources) {
    final i = col('${s}_Pay_Yuzde');
    if (i >= 0) shareCols[s] = i;
  }
  final out = <String, List<GridHour>>{};
  for (final line in lines.skip(1)) {
    final f = _splitLine(line);
    final shares = <String, double>{};
    shareCols.forEach((s, i) {
      if (i < f.length && f[i].trim().isNotEmpty) shares[s] = _num(f[i]);
    });
    final g = GridHour(
      date: f[cDate].trim(),
      hour: int.parse(f[cHour].trim()),
      ciT: _num(f[cT]),
      ciE: _num(f[cE]),
      renewablePct: _num(f[cRen]),
      fossilPct: _num(f[cFos]),
      dominant: f[cDom].trim(),
      shares: shares,
      src: srcLabel,
    );
    out.putIfAbsent(g.date, () => []).add(g);
  }
  for (final v in out.values) {
    v.sort((a, b) => a.hour.compareTo(b.hour));
  }
  return out;
}

/// loads CSV metni (AssetId, Tarih, Saat_No, Saatlik_Tuketim_kWh) → 'id|tarih' → 24 değer.
Map<String, List<double>> parseLoadsCsv(String text) {
  final lines = _lines(text);
  var header = _splitLine(lines.first);
  if (header.isNotEmpty && header.first.startsWith('﻿')) {
    header = [header.first.substring(1), ...header.skip(1)];
  }
  final cA = header.indexOf('AssetId'), cD = header.indexOf('Tarih');
  final cH = header.indexOf('Saat_No'), cK = header.indexOf('Saatlik_Tuketim_kWh');
  final tmp = <String, List<(int, double)>>{};
  for (final line in lines.skip(1)) {
    final f = _splitLine(line);
    final key = '${f[cA].trim()}|${f[cD].trim()}';
    tmp.putIfAbsent(key, () => []).add((int.parse(f[cH].trim()), _num(f[cK])));
  }
  final out = <String, List<double>>{};
  tmp.forEach((k, v) {
    v.sort((a, b) => a.$1.compareTo(b.$1));
    out[k] = [for (final x in v) x.$2];
  });
  return out;
}

_Parsed _parseBase(List<String> texts) =>
    _Parsed(parseGridCsv(texts[0], baseGridLabel), parseLoadsCsv(texts[1]));

/// Uygulama verisi. [DataStore.load] ile bir kez okunur; paket değişince [reload].
class DataStore {
  DataStore._();

  static final DataStore instance = DataStore._();

  late String _baseEpiasText;
  late String _baseLoadsText;
  late List<Map<String, dynamic>> _baseMachinesJson;
  late List<Map<String, String>> _baseEtkbRaw;

  Map<String, List<GridHour>> _baseGrid = {};
  Map<String, List<double>> _baseLoads = {};

  Map<String, List<GridHour>> _grid = {};
  Map<String, List<double>> _loads = {};
  List<Machine> _machines = [];
  Map<String, (double, double)> _factors = {};
  String _factorsLabel = baseFactorsLabel;
  List<EtkbRow> _etkbRows = [];

  /// Okunamayan paketler: paket id → hata metni.
  final Map<String, String> _errors = {};

  bool _loaded = false;
  bool get loaded => _loaded;

  Future<void> load() async {
    if (_loaded) return;
    _baseEpiasText = await rootBundle.loadString('assets/shared/epias_2025.csv');
    _baseLoadsText = await rootBundle.loadString('assets/shared/loads_hourly.csv');
    _baseMachinesJson = [
      for (final m in jsonDecode(
              await rootBundle.loadString('assets/shared/machines.json')) as List)
        Map<String, dynamic>.from(m as Map),
    ];
    _baseEtkbRaw = _parseSimpleCsv(
        await rootBundle.loadString('assets/shared/etkb_2023.csv'));
    final parsed = await compute(_parseBase, [_baseEpiasText, _baseLoadsText]);
    _baseGrid = parsed.grid;
    _baseLoads = parsed.loads;
    await reload();
    _loaded = true;
  }

  static List<Map<String, String>> _parseSimpleCsv(String text) {
    final lines = _lines(text);
    var header = _splitLine(lines.first);
    if (header.first.startsWith('﻿')) {
      header = [header.first.substring(1), ...header.skip(1)];
    }
    return [
      for (final l in lines.skip(1))
        {
          for (var i = 0; i < header.length; i++)
            header[i]: i < _splitLine(l).length ? _splitLine(l)[i] : '',
        },
    ];
  }

  // ---------------- katsayılar ----------------

  Map<String, (double, double)> _baseFactors() {
    final out = <String, (double, double)>{};
    for (final row in _baseEtkbRaw) {
      final k = sourceKey(row['Yakit_Turu_EPIAS_Sutunu'] ?? '');
      if (k != null) {
        out[k] = (
          double.parse(row['Emisyon_Faktoru_tCO2_MWh']!),
          double.parse(row['Emisyon_Faktoru_tCO2esd_MWh']!),
        );
      }
    }
    return out;
  }

  List<EtkbRow> _baseEtkbRows() => [
        for (final r in _baseEtkbRaw)
          EtkbRow(r['Yakit_Turu_EPIAS_Sutunu'] ?? '', r['Emisyon_Faktoru_tCO2_MWh'] ?? '',
              r['Emisyon_Faktoru_tCO2esd_MWh'] ?? '', r['Kategori'] ?? ''),
      ];

  /// (katsayılar, etiket, tablo satırları, paket mi?)
  Future<(Map<String, (double, double)>, String, List<EtkbRow>, bool)>
      _activeFactors(List<pk.Package> pkgs) async {
    final factorPkgs = [
      for (final p in pkgs)
        if (p.kind == pk.kindFactors && p.enabled) p,
    ]..sort((a, b) => a.createdAt.compareTo(b.createdAt));
    if (factorPkgs.isEmpty) {
      return (_baseFactors(), baseFactorsLabel, _baseEtkbRows(), false);
    }
    final p = factorPkgs.last;
    Map<String, (double, double)>? f;
    try {
      f = await pk.readFactorsCsv(p.file('factors.csv'));
    } catch (e) {
      _errors[p.id] = '${e.runtimeType}: $e';
    }
    if (f == null || !requiredFossil.every(f.containsKey)) {
      _errors.putIfAbsent(p.id, () => 'katsayı dosyası eksik ya da okunamadı');
      return (_baseFactors(), baseFactorsLabel, _baseEtkbRows(), false);
    }
    for (final s in allSources) {
      f.putIfAbsent(s, () => (0.0, 0.0));
    }
    final rows = [
      for (final s in allSources)
        if (f.containsKey(s))
          EtkbRow(sourceNames[s]!, _repr(f[s]!.$1), _repr(f[s]!.$2),
              renewable.contains(s) ? 'Yenilenebilir' : 'Fosil'),
    ];
    return (f, p.name, rows, true);
  }

  static String _repr(double v) {
    final s = v.toString();
    return s;
  }

  // ---------------- yeniden okuma ----------------

  /// Paket eklenince / açılıp kapatılınca veriyi yeniden okur.
  Future<void> reload() async {
    _errors.clear();
    final pkgs = await pk.listPackages();

    // Şebeke: varsayılan + etkin yıl paketleri (aynı gün varsa paket kazanır).
    final grid = <String, List<GridHour>>{};
    _baseGrid.forEach((d, rows) {
      grid[d] = [
        for (final r in rows)
          GridHour(
            date: r.date, hour: r.hour, ciT: r.ciT, ciE: r.ciE,
            renewablePct: r.renewablePct, fossilPct: r.fossilPct,
            dominant: r.dominant, shares: r.shares, src: r.src,
          ),
      ];
    });
    final gridPkgs = [
      for (final p in pkgs)
        if (p.kind == pk.kindGrid && p.enabled) p,
    ]..sort((a, b) => a.createdAt.compareTo(b.createdAt));
    for (final p in gridPkgs) {
      try {
        final text = await pk.readText(p.file('epias.csv'));
        final g = parseGridCsv(text, p.name);
        grid.addAll(g);
      } catch (e) {
        _errors[p.id] = '${e.runtimeType}: $e';
      }
    }

    final (f, label, rows, isPkg) = await _activeFactors(pkgs);
    _factors = f;
    _factorsLabel = label;
    _etkbRows = rows;
    if (isPkg) {
      for (final recs in grid.values) {
        for (final r in recs) {
          var t = 0.0, e = 0.0;
          for (final s in allSources) {
            final share = r.shares[s];
            if (share == null || share.isNaN) continue;
            t += share / 100 * f[s]!.$1;
            e += share / 100 * f[s]!.$2;
          }
          r.ciT = t;
          r.ciE = e;
        }
      }
    }
    _grid = grid;

    // Yükler: varsayılan + etkin makine paketleri.
    final loads = Map<String, List<double>>.from(_baseLoads);
    final extraMachines = <Machine>[];
    for (final p in pkgs) {
      if (p.kind != pk.kindMachine || !p.enabled) continue;
      try {
        loads.addAll(parseLoadsCsv(await pk.readText(p.file('loads.csv'))));
        final ms = jsonDecode(await pk.readText(p.file('machines.json'))) as List;
        for (final m in ms) {
          final mm = Map<String, dynamic>.from(m as Map);
          for (final k in const ['id', 'name', 'shiftable', 'days']) {
            if (!mm.containsKey(k)) throw FormatException("makine kaydında '$k' yok");
          }
          extraMachines.add(Machine.fromJson(mm, package: p.id));
        }
      } catch (e) {
        _errors[p.id] = '${e.runtimeType}: $e';
      }
    }
    _loads = loads;

    final out = <Machine>[];
    for (final m in [
      for (final j in _baseMachinesJson) Machine.fromJson(j),
      ...extraMachines,
    ]) {
      final days = [for (final d in m.days) if (_grid.containsKey(d)) d];
      if (days.isEmpty) continue;
      m.days = days;
      m.firstDay = days.first;
      m.lastDay = days.last;
      out.add(m);
    }
    _machines = out;
  }

  // ---------------- sorgular ----------------

  Map<String, String> packageErrors(List<pk.Package> pkgs) {
    final errs = Map<String, String>.from(_errors);
    for (final p in pkgs) {
      if (p.kind == pk.kindBroken) {
        errs[p.id] = (p.meta['error'] ?? 'okunamadı').toString();
      }
    }
    return errs;
  }

  Map<String, (double, double)> factors() => Map.of(_factors);
  String factorsLabel() => _factorsLabel;
  List<EtkbRow> etkbFactors() => List.of(_etkbRows);

  List<String> allDates() => _grid.keys.toList()..sort();

  String gridLabel(String date) {
    final recs = _grid[date];
    return (recs != null && recs.isNotEmpty) ? recs.first.src : baseGridLabel;
  }

  List<double> ci24(String date, [String kind = 'tCO2']) => [
        for (final r in _grid[date]!) kind == 'tCO2esd' ? r.ciE : r.ciT,
      ];

  /// dominant, renewable_pct, fossil_pct, shares (13 kaynak)
  ({String dominant, double renewablePct, double fossilPct, Map<String, double> shares})
      mixAt(String date, int hour) {
    final row = _grid[date]![hour];
    return (
      dominant: row.dominant,
      renewablePct: row.renewablePct,
      fossilPct: row.fossilPct,
      shares: {for (final s in sources) s: row.shares[s] ?? 0.0},
    );
  }

  List<Machine> machines() => List.of(_machines);

  Machine machine(String assetId) {
    for (final m in _machines) {
      if (m.id == assetId) return m;
    }
    throw StateError('Bilinmeyen makine: $assetId');
  }

  bool hasMachine(String assetId) => _machines.any((m) => m.id == assetId);

  List<String> daysFor(String assetId) => List.of(machine(assetId).days);

  List<double> load24(String assetId, String date) =>
      List.of(_loads['$assetId|$date']!);

  /// simulate() için (load_kwh, ci). Parametrik modda yük sabit kWh/saat.
  (List<double>, List<double>) scenarioSeries(String assetId, String date,
      {String kind = 'tCO2', double? parametricKwh}) {
    final load = parametricKwh == null
        ? load24(assetId, date)
        : List<double>.filled(24, parametricKwh);
    return (load, ci24(date, kind));
  }

  bool isReal(String assetId) {
    if (!hasMachine(assetId)) return false;
    return machine(assetId).source == 'real';
  }

  /// Ekrandaki zorunlu kaynak etiketi; makinenin veri türüne göre değişir.
  String sourceLabel(String assetId, String date) {
    final grid = gridLabel(date);
    if (isReal(assetId)) {
      return 'Tesis ölçümü (Balıkesir) · Kaynak: $grid, ${factorsLabel()}';
    }
    return 'Örnek yük, Balıkesir tesisi değil · Kaynak: $grid, ${factorsLabel()}, $sampleSource';
  }
}
