// CSV (; , veya sekme) ya da Excel dosyasını metin sütunlarıyla okur
// (packages.read_table karşılığı). Tüm hücreler metin olarak döner.

import 'dart:convert';
import 'dart:io';

import 'package:excel/excel.dart';

class Table {
  Table(this.columns, this.rows);
  final List<String> columns;
  final List<List<String>> rows;

  int get length => rows.length;

  List<String> column(String name) {
    final i = columns.indexOf(name);
    return [for (final r in rows) i < r.length ? r[i] : ''];
  }
}

const List<int> _cp1254High = [
  0x20AC, 0x81, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030,
  0x0160, 0x2039, 0x0152, 0x8D, 0x8E, 0x8F, 0x90, 0x2018, 0x2019, 0x201C, 0x201D,
  0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0x9D, 0x9E, 0x0178,
];

String _decodeCp1254(List<int> bytes) {
  final b = StringBuffer();
  for (final c in bytes) {
    if (c >= 0x80 && c <= 0x9F) {
      b.writeCharCode(_cp1254High[c - 0x80]);
    } else {
      switch (c) {
        case 0xD0: b.write('Ğ');
        case 0xDD: b.write('İ');
        case 0xDE: b.write('Ş');
        case 0xF0: b.write('ğ');
        case 0xFD: b.write('ı');
        case 0xFE: b.write('ş');
        default: b.writeCharCode(c);
      }
    }
  }
  return b.toString();
}

/// utf-8-sig → cp1254 → latin-1 sırasıyla çözer.
String decodeText(List<int> raw) {
  try {
    var s = utf8.decode(raw);
    if (s.startsWith('﻿')) s = s.substring(1);
    return s;
  } on FormatException {
    return _decodeCp1254(raw);
  }
}

/// Tırnaklı alanları destekleyen basit CSV ayrıştırıcı.
List<List<String>> parseCsv(String text, String sep) {
  final rows = <List<String>>[];
  var row = <String>[];
  final field = StringBuffer();
  var inQuotes = false;
  for (var i = 0; i < text.length; i++) {
    final ch = text[i];
    if (inQuotes) {
      if (ch == '"') {
        if (i + 1 < text.length && text[i + 1] == '"') {
          field.write('"');
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field.write(ch);
      }
    } else if (ch == '"') {
      inQuotes = true;
    } else if (ch == sep) {
      row.add(field.toString());
      field.clear();
    } else if (ch == '\n' || ch == '\r') {
      if (ch == '\r' && i + 1 < text.length && text[i + 1] == '\n') i++;
      row.add(field.toString());
      field.clear();
      if (!(row.length == 1 && row.first.isEmpty)) rows.add(row);
      row = <String>[];
    } else {
      field.write(ch);
    }
  }
  if (field.isNotEmpty || row.isNotEmpty) {
    row.add(field.toString());
    if (!(row.length == 1 && row.first.isEmpty)) rows.add(row);
  }
  return rows;
}

Table _fromRows(List<List<String>> all) {
  if (all.isEmpty) return Table([], []);
  final cols = [for (final c in all.first) c.trim()];
  final rows = [
    for (final r in all.skip(1))
      [for (var i = 0; i < cols.length; i++) i < r.length ? r[i] : ''],
  ];
  return Table(cols, rows);
}

String _two(int v) => v.toString().padLeft(2, '0');

String _cellText(CellValue? v) {
  if (v == null) return '';
  if (v is DateTimeCellValue) {
    return '${v.year}-${_two(v.month)}-${_two(v.day)} ${_two(v.hour)}:${_two(v.minute)}:${_two(v.second)}';
  }
  if (v is DateCellValue) {
    return '${v.year}-${_two(v.month)}-${_two(v.day)} 00:00:00';
  }
  if (v is TimeCellValue) {
    return '${_two(v.hour)}:${_two(v.minute)}:${_two(v.second)}';
  }
  return v.toString();
}

Future<Table> readTable(String path) async {
  final lower = path.toLowerCase();
  final raw = await File(path).readAsBytes();
  if (lower.endsWith('.xlsx') || lower.endsWith('.xlsm') || lower.endsWith('.xls')) {
    final book = Excel.decodeBytes(raw);
    if (book.tables.isEmpty) return Table([], []);
    final sheet = book.tables[book.tables.keys.first]!;
    final all = <List<String>>[
      for (final r in sheet.rows) [for (final c in r) _cellText(c?.value)],
    ];
    return _fromRows(all);
  }
  final text = decodeText(raw);
  final first = text.split(RegExp(r'\r?\n')).first;
  final semi = ';'.allMatches(first).length;
  final comma = ','.allMatches(first).length;
  final sep = (semi >= comma && first.contains(';'))
      ? ';'
      : (first.contains('\t') ? '\t' : ',');
  return _fromRows(parseCsv(text, sep));
}
