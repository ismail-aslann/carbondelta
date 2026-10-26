// Kaynak adları ve sınıfları (engine/packages.py ve desktop/ai_context.py sabitleri).

const List<String> sources = [
  'Dogal_Gaz', 'Barajli', 'Linyit', 'Akarsu', 'Ithal_Komur', 'Ruzgar', 'Gunes',
  'Fuel_Oil', 'Jeotermal', 'Asfaltit_Komur', 'Tas_Komur', 'Biyokutle', 'Atik_Isi',
];
const List<String> extraSources = ['Nafta', 'LNG'];
const List<String> allSources = [...sources, ...extraSources];

const Set<String> renewable = {
  'Ruzgar', 'Biyokutle', 'Atik_Isi', 'Gunes', 'Barajli', 'Akarsu', 'Jeotermal',
};

/// Tablo/rapor adları (packages.SOURCE_NAMES).
const Map<String, String> sourceNames = {
  'Dogal_Gaz': 'Doğal gaz', 'Barajli': 'Barajlı hidro', 'Linyit': 'Linyit',
  'Akarsu': 'Akarsu hidro', 'Ithal_Komur': 'İthal kömür', 'Ruzgar': 'Rüzgâr',
  'Gunes': 'Güneş', 'Fuel_Oil': 'Fuel oil', 'Jeotermal': 'Jeotermal',
  'Asfaltit_Komur': 'Asfaltit', 'Tas_Komur': 'Taş kömürü', 'Biyokutle': 'Biyokütle',
  'Atik_Isi': 'Atık ısı', 'Nafta': 'Nafta', 'LNG': 'LNG',
};

/// AI metinlerinde kullanılan küçük harfli adlar (ai_context.SOURCE_NAMES).
const Map<String, String> sourceNamesLower = {
  'Dogal_Gaz': 'doğal gaz', 'Barajli': 'barajlı hidro', 'Linyit': 'linyit',
  'Akarsu': 'akarsu hidro', 'Ithal_Komur': 'ithal kömür', 'Ruzgar': 'rüzgâr',
  'Gunes': 'güneş', 'Fuel_Oil': 'fuel oil', 'Jeotermal': 'jeotermal',
  'Asfaltit_Komur': 'asfaltit', 'Tas_Komur': 'taş kömürü', 'Biyokutle': 'biyokütle',
  'Atik_Isi': 'atık ısı',
};

const List<String> requiredFossil = [
  'Dogal_Gaz', 'Linyit', 'Ithal_Komur', 'Fuel_Oil', 'Asfaltit_Komur', 'Tas_Komur',
];

/// Karşılaştırma için sadeleştirme: 'Doğal Gaz (MWh)' → 'dogalgaz' (packages.norm).
String norm(String text) {
  var t = text.replaceAll('ı', 'i').replaceAll('İ', 'i');
  const from = 'çğöşüâîûÇĞÖŞÜÂÎÛéèêáàäëïíóòôúùÉÈÁÀÓÒÚÙ';
  const to = 'cgosuaiuCGOSUAIUeeeaaaeiiooouuEEAAOOUU';
  final b = StringBuffer();
  for (final ch in t.runes) {
    final c = String.fromCharCode(ch);
    final i = from.indexOf(c);
    b.write(i >= 0 ? to[i] : c);
  }
  t = b.toString().toLowerCase();
  t = t.replaceAll(RegExp(r'\(.*?\)'), '');
  t = t.replaceAll(RegExp(r'[^a-z0-9]'), '');
  for (final suffix in const ['mwh', 'yuzde', 'pay']) {
    if (t.endsWith(suffix) && t.length > suffix.length) {
      t = t.substring(0, t.length - suffix.length);
    }
  }
  return t;
}

const Map<String, String> sourceKeys = {
  'dogalgaz': 'Dogal_Gaz', 'barajli': 'Barajli', 'hidrolikbarajli': 'Barajli',
  'linyit': 'Linyit', 'akarsu': 'Akarsu', 'hidrolikakarsu': 'Akarsu',
  'ithalkomur': 'Ithal_Komur', 'ruzgar': 'Ruzgar', 'gunes': 'Gunes',
  'fueloil': 'Fuel_Oil', 'jeotermal': 'Jeotermal', 'asfaltitkomur': 'Asfaltit_Komur',
  'asfaltit': 'Asfaltit_Komur', 'taskomur': 'Tas_Komur', 'taskomuru': 'Tas_Komur',
  'biyokutle': 'Biyokutle', 'atikisi': 'Atik_Isi', 'nafta': 'Nafta', 'lng': 'LNG',
  'dogalgazlng': 'LNG',
};

String? sourceKey(String name) {
  final n = norm(name);
  if (sourceKeys.containsKey(n)) return sourceKeys[n];
  for (final e in sourceKeys.entries) {
    if (n.startsWith(e.key) && e.key.length >= 5) return e.value;
  }
  return null;
}
