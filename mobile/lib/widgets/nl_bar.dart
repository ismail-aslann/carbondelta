// Üst bant doğal dil kutusu (MainWindow._build_header: nl_edit, Sor, nl_status).

import 'package:flutter/material.dart';

import '../state/ai_state.dart';
import '../ui/theme.dart' as th;
import 'delti.dart';

class NlBar extends StatefulWidget {
  const NlBar({super.key, required this.ai});
  final AiState ai;

  @override
  State<NlBar> createState() => _NlBarState();
}

class _NlBarState extends State<NlBar> {
  final _edit = TextEditingController();

  @override
  void dispose() {
    _edit.dispose();
    super.dispose();
  }

  void _submit() {
    FocusScope.of(context).unfocus();
    widget.ai.submitNl(_edit.text);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [th.primaryDark, Color(0xFF16765B)]),
        borderRadius: BorderRadius.circular(10),
      ),
      child: ListenableBuilder(
        listenable: widget.ai,
        builder: (context, _) {
          final color = switch (widget.ai.nlStatusKind) {
            'ok' => const Color(0xFFB9F3D2),
            'error' => const Color(0xFFFFD0D0),
            _ => const Color(0xFFCFE9DF),
          };
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const Delti(size: 28),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: _edit,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _submit(),
                      style: const TextStyle(fontSize: 14),
                      decoration: InputDecoration(
                        hintText: "Delti'ye yazın: Kompresörü 3'ten 18'e al",
                        filled: true,
                        fillColor: Colors.white,
                        isDense: true,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.white,
                      side: const BorderSide(color: Color(0x73FFFFFF)),
                      backgroundColor: const Color(0x29FFFFFF),
                    ),
                    onPressed: _submit,
                    child: const Text('Sor'),
                  ),
                ],
              ),
              if (widget.ai.nlStatus.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4, left: 36),
                  child: Text(widget.ai.nlStatus, style: TextStyle(color: color, fontSize: 12)),
                ),
            ],
          );
        },
      ),
    );
  }
}
