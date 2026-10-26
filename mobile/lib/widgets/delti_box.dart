// "Delti açıklıyor" kartı (MainWindow._build_ai_box / _render_ai).

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../ai/ai_client.dart';
import '../ai/ai_context.dart' as ctx;
import '../state/ai_state.dart';
import '../ui/theme.dart' as th;
import 'delti.dart';

(Color, Color) chipColors(String source) => switch (source) {
      'ai' => (th.primary, th.primarySoft),
      'fallback_invalid' => (th.warn, th.warnSoft),
      _ => (th.muted, const Color(0xFFEEF1F4)),
    };

class SourceChip extends StatelessWidget {
  const SourceChip(this.source, {super.key});
  final String source;

  @override
  Widget build(BuildContext context) {
    final (fg, bg) = chipColors(source);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(9)),
      child: Text(sourceChips[source] ?? source,
          style: TextStyle(color: fg, fontSize: 11.5, fontWeight: FontWeight.w600)),
    );
  }
}

/// Metin kaynaklarına göre öncelikli etiket.
String? leadSource(Iterable<String> sources) {
  for (final key in const ['fallback_invalid', 'fallback_offline', 'pending', 'local', 'ai']) {
    if (sources.contains(key)) return key;
  }
  return null;
}

/// Çevrimdışı / doğrulanamadı notları (italik).
List<String> aiNotes(Iterable<String> sources) => [
      if (sources.contains('fallback_offline')) prompts()['offline_message'] as String,
      if (sources.contains('fallback_invalid')) prompts()['invalid_message'] as String,
    ];

class DeltiBox extends StatelessWidget {
  const DeltiBox({super.key, required this.ai, required this.onOpenSettings});

  final AiState ai;
  final VoidCallback onOpenSettings;

  Future<void> _pickTerm(BuildContext context) async {
    final terms = (prompts()['glossary'] as Map).keys.cast<String>().toList();
    final term = await showDialog<String>(
      context: context,
      builder: (ctx2) => SimpleDialog(
        title: const Text('Terim açıkla'),
        children: [
          for (final t in terms)
            SimpleDialogOption(onPressed: () => Navigator.pop(ctx2, t), child: Text(t)),
        ],
      ),
    );
    if (term != null && term.trim().isNotEmpty) ai.explainTerm(term);
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: ai,
      builder: (context, _) {
        final sources = [for (final s in ai.slots) s.source];
        final lead = leadSource(sources);
        final notes = aiNotes(sources);
        final multi = ai.slots.length > 1;
        final plain = [
          for (final s in ai.slots) multi ? '${s.title}\n${s.text}' : s.text,
        ].join('\n\n');
        return th.SectionCard(
          titleWidget: Row(
            children: [
              Tooltip(
                message: "Delti, CarbonDelta'nın AI yardımcısı. Hesap yapmaz; sonuçları açıklar.",
                child: Delti(state: stateForSource[lead] ?? 'ready', size: 34),
              ),
              const SizedBox(width: 8),
              const Text('Delti açıklıyor',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: th.text)),
              const SizedBox(width: 8),
              if (lead != null) SourceChip(lead),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (notes.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Text(notes.join('\n'),
                      style: const TextStyle(color: th.muted, fontSize: 12, fontStyle: FontStyle.italic)),
                ),
              for (final s in ai.slots)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text.rich(TextSpan(children: [
                    if (multi)
                      TextSpan(
                        text: '${s.title}\n',
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: s.source == 'fallback_invalid' ? th.warn : th.primaryDark),
                      ),
                    TextSpan(text: s.text, style: const TextStyle(height: 1.4)),
                  ])),
                ),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  Tooltip(
                    message: 'Standart ve seçilen saatlerin şebeke üretim karışımını açıklar.',
                    child: OutlinedButton(
                      onPressed: () => ai.requestManual(ctx.hourReason),
                      child: const Text('Neden bu saat?'),
                    ),
                  ),
                  Tooltip(
                    message: 'Mevcut senaryoyu en son kaydedilen senaryoyla kıyaslar.',
                    child: OutlinedButton(
                      onPressed: () => ai.compareWithSaved(),
                      child: const Text('Karşılaştır'),
                    ),
                  ),
                  PopupMenuButton<String>(
                    onSelected: (k) {
                      switch (k) {
                        case 'daily':
                          ai.requestManual(ctx.dailyImpact);
                        case 'season':
                          ai.requestManual(ctx.seasonNote);
                        case 'report':
                          ai.requestManual(ctx.reportSentence);
                        case 'term':
                          _pickTerm(context);
                        case 'sources':
                          ai.requestManual((_) => ctx.dataSourceExplain());
                        case 'copy':
                          Clipboard.setData(ClipboardData(text: plain));
                          ScaffoldMessenger.of(context)
                              .showSnackBar(const SnackBar(content: Text('Metin kopyalandı.')));
                        case 'settings':
                          onOpenSettings();
                      }
                    },
                    itemBuilder: (_) => const [
                      PopupMenuItem(value: 'daily', child: Text('Günlük etki yorumu')),
                      PopupMenuItem(value: 'season', child: Text('Mevsim notu')),
                      PopupMenuItem(value: 'report', child: Text('Rapor cümlesi')),
                      PopupMenuDivider(),
                      PopupMenuItem(value: 'term', child: Text('Terim açıkla…')),
                      PopupMenuItem(value: 'sources', child: Text('Veri kaynakları')),
                      PopupMenuDivider(),
                      PopupMenuItem(value: 'copy', child: Text('Metni kopyala')),
                      PopupMenuDivider(),
                      PopupMenuItem(value: 'settings', child: Text('Delti ayarları…')),
                    ],
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        border: Border.all(color: th.fieldBorder),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Text('Daha fazla ▾', style: TextStyle(color: th.primary)),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}
