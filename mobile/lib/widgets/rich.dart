import 'package:flutter/material.dart';

/// **kalın** ve _italik_ işaretli basit metni TextSpan'e çevirir.
TextSpan richText(String s, {TextStyle? base}) {
  final spans = <InlineSpan>[];
  final re = RegExp(r'\*\*(.+?)\*\*|_(.+?)_');
  var last = 0;
  for (final m in re.allMatches(s)) {
    if (m.start > last) spans.add(TextSpan(text: s.substring(last, m.start)));
    if (m.group(1) != null) {
      spans.add(TextSpan(text: m.group(1), style: const TextStyle(fontWeight: FontWeight.w700)));
    } else {
      spans.add(TextSpan(text: m.group(2), style: const TextStyle(fontStyle: FontStyle.italic)));
    }
    last = m.end;
  }
  if (last < s.length) spans.add(TextSpan(text: s.substring(last)));
  return TextSpan(style: base, children: spans);
}

class RichPara extends StatelessWidget {
  const RichPara(this.text, {super.key, this.bullet = false});
  final String text;
  final bool bullet;

  @override
  Widget build(BuildContext context) {
    final t = Text.rich(richText(text, base: const TextStyle(height: 1.45, fontSize: 14)));
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: bullet
          ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Padding(padding: EdgeInsets.only(right: 6), child: Text('•', style: TextStyle(height: 1.45))),
              Expanded(child: t),
            ])
          : t,
    );
  }
}
