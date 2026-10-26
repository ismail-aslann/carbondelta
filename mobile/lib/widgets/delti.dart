// Delti: CarbonDelta'nın AI yardımcısı maskotu (desktop/delti.py SVG'si).
// Halleri: "ready" (hazır), "think" (AI metni hazırlanıyor), "sleep" (çevrimdışı).

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

const String deltiName = 'Delti';

const String _defs = '''
<defs>
  <linearGradient id="body" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#7cf0c4"/><stop offset="1" stop-color="#2fb487"/>
  </linearGradient>
</defs>
''';

const String _body = '''
<path d="M53 6 C60 2 70 3 74 9 C66 9 60 12 56 18 Z" fill="#2fb487"/>
<path d="M53 18 C53 12 53 8 53 6" stroke="#1e8f69" stroke-width="2.4" stroke-linecap="round" fill="none"/>
<path d="M50 16 C53 16 55 17.5 56.8 20.6 L91 81 C93.6 85.6 90.6 91 85.4 91 H14.6 C9.4 91 6.4 85.6 9 81 L43.2 20.6 C45 17.5 47 16 50 16 Z" fill="url(#body)"/>
<path d="M50 16 C53 16 55 17.5 56.8 20.6 L91 81 C93.6 85.6 90.6 91 85.4 91 H14.6 C9.4 91 6.4 85.6 9 81 L43.2 20.6 C45 17.5 47 16 50 16 Z" fill="none" stroke="#0f5b46" stroke-opacity=".25" stroke-width="2"/>
<ellipse cx="31" cy="72" rx="4.5" ry="2.6" fill="#ff9a8a" opacity=".55"/>
<ellipse cx="69" cy="72" rx="4.5" ry="2.6" fill="#ff9a8a" opacity=".55"/>
''';

const String _eyesOpen = '''
<ellipse cx="40" cy="60" rx="5.2" ry="6.4" fill="#0b3d33"/>
<ellipse cx="60" cy="60" rx="5.2" ry="6.4" fill="#0b3d33"/>
<circle cx="41.6" cy="57.8" r="1.7" fill="#fff"/><circle cx="61.6" cy="57.8" r="1.7" fill="#fff"/>
''';

const Map<String, String> _faces = {
  'ready': '$_eyesOpen<path d="M42 72 Q50 79 58 72" stroke="#0b3d33" stroke-width="3.4" stroke-linecap="round" fill="none"/>',
  'think': '$_eyesOpen<path d="M44 74 H56" stroke="#0b3d33" stroke-width="3.4" stroke-linecap="round"/><circle cx="80" cy="32" r="3" fill="#9fc4b7"/><circle cx="88" cy="22" r="4" fill="#9fc4b7"/>',
  'sleep': '<path d="M35 61 Q40 64 45 61 M55 61 Q60 64 65 61" stroke="#0b3d33" stroke-width="3" stroke-linecap="round" fill="none"/><path d="M44 74 Q50 77 56 74" stroke="#0b3d33" stroke-width="3" stroke-linecap="round" fill="none"/><text x="72" y="40" font-size="14" font-weight="700" fill="#8aa39a">z</text><text x="81" y="29" font-size="10" font-weight="700" fill="#8aa39a">z</text>',
};

/// AI yanıt kaynağına göre Delti hali.
const Map<String, String> stateForSource = {
  'ai': 'ready',
  'local': 'ready',
  'pending': 'think',
  'fallback_offline': 'sleep',
  'fallback_invalid': 'ready',
};

String deltiSvg([String state = 'ready']) =>
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">$_defs$_body${_faces[state] ?? _faces['ready']}</svg>';

class Delti extends StatelessWidget {
  const Delti({super.key, this.state = 'ready', this.size = 34});
  final String state;
  final double size;

  @override
  Widget build(BuildContext context) =>
      SvgPicture.string(deltiSvg(state), width: size, height: size);
}
