// CSV yardımcıları (desktop/tabs.py _raw ve csv.writer ';' ayraç, UTF-8 BOM).

import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

/// CSV için tam hassasiyet, Türkçe Excel uyumlu ondalık virgül; null → boş.
String rawNum(double? v) => v == null ? '' : v.toString().replaceAll('.', ',');

String csvField(Object? v) {
  final s = (v ?? '').toString();
  if (s.contains(';') || s.contains('"') || s.contains('\n') || s.contains('\r')) {
    return '"${s.replaceAll('"', '""')}"';
  }
  return s;
}

String csvText(List<List<Object?>> rows) =>
    '﻿${rows.map((r) => r.map(csvField).join(';')).join('\r\n')}\r\n';

/// Dosyayı geçici klasöre yazar (varsa üzerine) ve paylaşma menüsünü açar.
Future<void> shareFile(String name, List<int> bytes) async {
  final dir = await getTemporaryDirectory();
  final f = File('${dir.path}${Platform.pathSeparator}$name');
  if (await f.exists()) await f.delete();
  await f.writeAsBytes(bytes, flush: true);
  await SharePlus.instance.share(ShareParams(files: [XFile(f.path)], subject: name));
}
