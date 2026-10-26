// Geçmiş sekmesi (desktop/tabs.py HistoryTab).

import 'package:flutter/material.dart';

import '../data/history_db.dart';
import '../state/app_state.dart';
import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;
import 'calc_screen.dart' show statusLabels;

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({
    super.key,
    required this.app,
    required this.onRestored,
    this.onSummarize,
    this.summary,
  });

  final AppState app;
  final VoidCallback onRestored;

  /// "Özetle" (Delti son 10 kaydı özetler).
  final VoidCallback? onSummarize;

  /// Özet kartı (AI katmanı doldurur).
  final Widget? summary;

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<HistoryRow> _rows = [];
  int _version = -1;

  Future<void> _load() async {
    final rows = await widget.app.db.list();
    if (mounted) setState(() => _rows = rows);
  }

  Future<void> _delete(HistoryRow h) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Kaydı sil'),
        content: const Text('Seçili kayıt geçmişten silinsin mi?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Vazgeç')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: th.bad),
            child: const Text('Sil'),
          ),
        ],
      ),
    );
    if (ok == true) {
      await widget.app.db.delete(h.id);
      widget.app.notifyHistoryChanged();
    }
  }

  void _restore(HistoryRow h) {
    final (opened, msg) = widget.app.restoreHistory(h);
    if (opened) widget.onRestored();
    if (msg != null) {
      showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(opened ? 'Gün değişti' : 'Senaryo açılamadı'),
          content: Text(msg),
          actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Tamam'))],
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final app = widget.app;
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        if (_version != app.historyVersion + app.dataVersion * 100000) {
          _version = app.historyVersion + app.dataVersion * 100000;
          _load();
        }
        final names = {for (final m in app.data.machines()) m.id: m.name};
        return ListView(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text('Kayıtlı senaryolar',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                ),
                OutlinedButton(
                  onPressed: _rows.isEmpty ? null : widget.onSummarize,
                  child: const Text('Özetle'),
                ),
              ],
            ),
            const th.Muted('Dokun: geri yükle · çöp kutusu: sil', size: 12),
            const SizedBox(height: 8),
            if (widget.summary != null) ...[widget.summary!, const SizedBox(height: 8)],
            if (_rows.isEmpty)
              const Padding(
                padding: EdgeInsets.all(32),
                child: th.Muted(
                  'Henüz kayıt yok.\nSenaryo sekmesinde “Senaryoyu kaydet” ile ekleyebilirsiniz.',
                  align: TextAlign.center,
                ),
              ),
            for (final h in _rows) ...[
              _HistoryCard(
                h: h,
                machineName: names[h.assetId] ?? 'Silinmiş makine',
                onTap: () => _restore(h),
                onDelete: () => _delete(h),
              ),
              const SizedBox(height: 8),
            ],
          ],
        );
      },
    );
  }
}

class _HistoryCard extends StatelessWidget {
  const _HistoryCard({required this.h, required this.machineName, required this.onTap, required this.onDelete});

  final HistoryRow h;
  final String machineName;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final mode = h.mode == 'parametric' ? 'Parametrik' : 'Ölçülen';
    final kind = h.ciKind == 'tCO2esd' ? 'tCO2-eşd' : 'tCO2';
    final deltaColor = h.deltaPct == null ? th.text : (h.deltaPct! <= 0 ? th.good : th.bad);
    Widget kv(String k, String v, {Color? color}) => Padding(
          padding: const EdgeInsets.only(right: 14, bottom: 2),
          child: Text.rich(TextSpan(children: [
            TextSpan(text: '$k ', style: const TextStyle(color: th.muted, fontSize: 12)),
            TextSpan(text: v, style: TextStyle(fontSize: 13, color: color ?? th.text, fontWeight: FontWeight.w600)),
          ])),
        );
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 4, 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('$machineName · ${fmt.date(h.date)}',
                        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                    th.Muted('Kayıt zamanı: ${fmt.datetime(h.createdAt)}', size: 12),
                    const SizedBox(height: 4),
                    Wrap(children: [
                      kv('Standart', fmt.window(h.s, h.L)),
                      kv('Seçilen', fmt.window(h.t, h.L)),
                      kv('Oran', '%${fmt.num(h.p * 100, 0)}'),
                      kv('Tip', kind),
                      kv('Mod', mode),
                      kv('Durum', statusLabels[h.status] ?? h.status),
                      kv('Değişim', fmt.pct(h.deltaPct), color: deltaColor),
                      kv('Günlük etki', fmt.pct(h.dailyDeltaPct)),
                    ]),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'Seçili kaydı sil',
                onPressed: onDelete,
                icon: const Icon(Icons.delete_outline, color: th.bad),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
