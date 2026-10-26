// Geçmiş özeti kartı (HistoryTab.show_summary).

import 'package:flutter/material.dart';

import '../state/ai_state.dart';
import '../ui/theme.dart' as th;
import 'delti_box.dart';

class SummaryCard extends StatelessWidget {
  const SummaryCard({super.key, required this.ai});
  final AiState ai;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: ai,
      builder: (context, _) {
        final text = ai.summaryText;
        if (text == null) return const SizedBox.shrink();
        final notes = aiNotes([ai.summarySource]);
        return th.SectionCard(
          titleWidget: Row(children: [
            const Text('Geçmiş özeti', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            const SizedBox(width: 8),
            SourceChip(ai.summarySource),
          ]),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (notes.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(notes.join('\n'),
                      style: const TextStyle(color: th.muted, fontSize: 12, fontStyle: FontStyle.italic)),
                ),
              Text(text, style: const TextStyle(height: 1.4)),
            ],
          ),
        );
      },
    );
  }
}
