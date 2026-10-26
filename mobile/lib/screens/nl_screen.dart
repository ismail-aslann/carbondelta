// Delti'ye Sor sekmesi: cümle → anlaşılan senaryo (Senaryo sekmesine uygulanır)
// → önizleme (desktop/tools_tabs.py NLTab).

import 'package:flutter/material.dart';

import '../state/ai_state.dart';
import '../ui/theme.dart' as th;
import '../widgets/delti.dart';

const List<String> examples = [
  "Kompresörü 3'ten 18'e al",
  "Presi %50 ile 21'e kaydır",
  "Karıştırıcıyı 10'dan 19'a al",
];

class NlScreen extends StatefulWidget {
  const NlScreen({super.key, required this.ai, required this.onOpenScenario, required this.onOpenSettings});

  final AiState ai;
  final VoidCallback onOpenScenario;
  final VoidCallback onOpenSettings;

  @override
  State<NlScreen> createState() => _NlScreenState();
}

class _NlScreenState extends State<NlScreen> {
  final _edit = TextEditingController();

  @override
  void dispose() {
    _edit.dispose();
    super.dispose();
  }

  void _submit() {
    final text = _edit.text.trim();
    if (text.isEmpty) return;
    FocusScope.of(context).unfocus();
    widget.ai.submitNlPage(text);
  }

  @override
  Widget build(BuildContext context) {
    final ai = widget.ai;
    return ListenableBuilder(
      listenable: ai,
      builder: (context, _) {
        final a = ai.nlAnswer;
        final avatarState = a == null ? (ai.online ? 'ready' : 'sleep') : a.state;
        return ListView(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
          children: [
            th.SectionCard(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Delti(state: avatarState, size: 56),
                      const SizedBox(width: 10),
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text("Delti'ye sor", style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
                            th.Muted('Ne yapmak istediğinizi günlük dille yazın.'),
                          ],
                        ),
                      ),
                      Tooltip(
                        message: 'Delti bir yapay zekâ yardımcısıdır; hesap yapmaz, karar sizindir.',
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
                          decoration:
                              BoxDecoration(color: th.primarySoft, borderRadius: BorderRadius.circular(9)),
                          child: const Text('AI',
                              style: TextStyle(color: th.primary, fontWeight: FontWeight.w600, fontSize: 11.5)),
                        ),
                      ),
                      IconButton(
                        tooltip: 'Delti ayarları: API anahtarı',
                        onPressed: widget.onOpenSettings,
                        icon: const Icon(Icons.settings_outlined),
                      ),
                    ],
                  ),
                  if (!ai.online) ...[
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
                      decoration: BoxDecoration(
                        color: th.warnSoft,
                        border: Border.all(color: const Color(0xFFF0D9A8)),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          const Text.rich(TextSpan(style: TextStyle(color: th.warn), children: [
                            TextSpan(text: 'Delti uyuyor. ', style: TextStyle(fontWeight: FontWeight.w700)),
                            TextSpan(
                                text: 'AI anahtarı girilmemiş; cümleler yine de basit kurallarla çözülür. '
                                    "Delti'yi uyandırmak için anahtarınızı girin."),
                          ])),
                          Align(
                            alignment: Alignment.centerRight,
                            child: TextButton(
                                onPressed: widget.onOpenSettings, child: const Text("Delti'yi uyandır")),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 10),
                  Container(
                    margin: const EdgeInsets.only(left: 40),
                    padding: const EdgeInsets.fromLTRB(12, 9, 12, 9),
                    decoration: BoxDecoration(
                      color: th.primarySoft,
                      border: Border.all(color: const Color(0xFFCFE5DC)),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Text(
                      'Hangi makineyi hangi saatten hangi saate almak istersiniz? İsterseniz kaydırma oranını da söyleyin.',
                      style: TextStyle(color: th.primaryDark),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _edit,
                          textInputAction: TextInputAction.send,
                          onSubmitted: (_) => _submit(),
                          decoration: const InputDecoration(
                            hintText: "Örn. Kompresörü 3'ten 18'e al",
                            border: OutlineInputBorder(),
                            isDense: true,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      FilledButton(onPressed: _submit, child: const Text('Sor')),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      const th.Muted('Örnekler:'),
                      for (final ex in examples)
                        ActionChip(
                          label: Text(ex, style: const TextStyle(fontSize: 12, color: th.primaryDark)),
                          backgroundColor: th.primarySoft,
                          side: const BorderSide(color: Color(0xFFCFE5DC)),
                          onPressed: () {
                            _edit.text = ex;
                            _submit();
                          },
                        ),
                    ],
                  ),
                  if (a != null) ...[
                    const Divider(height: 24, color: th.border),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Delti(state: a.state, size: 32),
                        const SizedBox(width: 8),
                        Expanded(child: _answerText(a)),
                      ],
                    ),
                    if (a.explain.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      th.Muted(a.explain),
                    ],
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Expanded(child: th.Muted(a.via, size: 12)),
                        TextButton(
                          onPressed: () {
                            _edit.clear();
                            ai.clearNlAnswer();
                          },
                          child: const Text('Temizle'),
                        ),
                        if (a.canOpen)
                          FilledButton(onPressed: widget.onOpenScenario, child: const Text('Senaryoya git')),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _answerText(NlAnswer a) {
    const b = TextStyle(fontWeight: FontWeight.w700);
    if (a.error != null) {
      return Text.rich(TextSpan(style: const TextStyle(fontSize: 15), children: [
        const TextSpan(text: 'Bunu tam anlayamadım. ', style: b),
        TextSpan(text: '${a.error} Örneklerden birini deneyebilir misiniz?'),
      ]));
    }
    if (a.state == 'think') return Text(a.title, style: const TextStyle(fontSize: 15));
    return Text.rich(TextSpan(style: const TextStyle(fontSize: 15), children: [
      TextSpan(text: '${a.title} ', style: b),
      TextSpan(text: '${a.what}\n'),
      TextSpan(text: a.effect),
      if (a.effectDelta != null) ...[
        const TextSpan(text: ' '),
        TextSpan(text: a.effectDelta, style: TextStyle(fontWeight: FontWeight.w700, color: a.effectGood ? th.good : th.bad)),
        const TextSpan(text: ' değişiyor.'),
      ],
    ]));
  }
}
