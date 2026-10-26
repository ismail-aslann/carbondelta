// ignore_for_file: non_constant_identifier_names
// Kullanıcının hesap özetleri için SQLite geçmişi. Ham veri buraya yazılmaz.
// desktop/history_db.py ile aynı şema.

import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

const String schema = '''
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY,
    created_at TEXT,
    asset_id TEXT,
    date TEXT,
    s INT,
    L INT,
    t INT,
    p REAL,
    restricted TEXT,
    mode TEXT,
    ci_kind TEXT,
    status TEXT,
    delta_pct REAL,
    daily_delta_pct REAL,
    baseline_kg REAL,
    scenario_kg REAL,
    param_kwh REAL
)
''';

class HistoryRow {
  HistoryRow(this.raw)
      : restricted = [
          for (final h in ((raw['restricted'] ?? '') as String).split(','))
            if (h.isNotEmpty) int.parse(h),
        ];

  final Map<String, Object?> raw;
  final List<int> restricted;

  int get id => raw['id'] as int;
  String get createdAt => (raw['created_at'] ?? '') as String;
  String get assetId => raw['asset_id'] as String;
  String get date => raw['date'] as String;
  int get s => raw['s'] as int;
  int get L => raw['L'] as int;
  int get t => raw['t'] as int;
  double get p => (raw['p'] as num).toDouble();
  String get mode => (raw['mode'] ?? 'data') as String;
  String get ciKind => (raw['ci_kind'] ?? 'tCO2') as String;
  String get status => (raw['status'] ?? '') as String;
  double? get deltaPct => (raw['delta_pct'] as num?)?.toDouble();
  double? get dailyDeltaPct => (raw['daily_delta_pct'] as num?)?.toDouble();
  double get baselineKg => ((raw['baseline_kg'] ?? 0) as num).toDouble();
  double get scenarioKg => ((raw['scenario_kg'] ?? 0) as num).toDouble();
  double? get paramKwh => (raw['param_kwh'] as num?)?.toDouble();
}

String _two(int v) => v.toString().padLeft(2, '0');

String _nowIso() {
  final n = DateTime.now();
  return '${n.year}-${_two(n.month)}-${_two(n.day)}T${_two(n.hour)}:${_two(n.minute)}:${_two(n.second)}';
}

class HistoryDB {
  HistoryDB._(this._db);
  final Database _db;

  static Future<HistoryDB> open() async {
    final dir = await getDatabasesPath();
    final db = await openDatabase(p.join(dir, 'history.db'), version: 1,
        onCreate: (db, _) => db.execute(schema), onOpen: (db) => db.execute(schema));
    return HistoryDB._(db);
  }

  Future<int> add({
    required String assetId,
    required String date,
    required int s,
    required int L,
    required int t,
    required double p,
    required List<int> restricted,
    required String mode,
    required String ciKind,
    required String status,
    required double? deltaPct,
    required double? dailyDeltaPct,
    required double baselineKg,
    required double scenarioKg,
    double? paramKwh,
  }) {
    final sorted = [...restricted]..sort();
    return _db.insert('history', {
      'created_at': _nowIso(),
      'asset_id': assetId,
      'date': date,
      's': s,
      'L': L,
      't': t,
      'p': p,
      'restricted': sorted.join(','),
      'mode': mode,
      'ci_kind': ciKind,
      'status': status,
      'delta_pct': deltaPct,
      'daily_delta_pct': dailyDeltaPct,
      'baseline_kg': baselineKg,
      'scenario_kg': scenarioKg,
      'param_kwh': paramKwh,
    });
  }

  Future<List<HistoryRow>> list([int? limit]) async {
    final rows = await _db.query('history', orderBy: 'id DESC', limit: limit);
    return [for (final r in rows) HistoryRow(r)];
  }

  Future<HistoryRow?> get(int id) async {
    final rows = await _db.query('history', where: 'id = ?', whereArgs: [id]);
    return rows.isEmpty ? null : HistoryRow(rows.first);
  }

  Future<HistoryRow?> latest() async {
    final rows = await list(1);
    return rows.isEmpty ? null : rows.first;
  }

  Future<void> delete(int id) => _db.delete('history', where: 'id = ?', whereArgs: [id]);
}
