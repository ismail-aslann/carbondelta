// Delti ayarları: API anahtarı telefonun güvenli deposunda (Android Keystore)
// şifreli saklanır (desktop/ai_settings.py DPAPI karşılığı).

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _storage = FlutterSecureStorage();

/// {'provider', 'model', 'api_key'}; kayıt yoksa veya okunamazsa boş sözlük.
Future<Map<String, String>> load() async {
  try {
    final key = await _storage.read(key: 'api_key');
    if (key == null || key.isEmpty) return {};
    return {
      'provider': await _storage.read(key: 'provider') ?? 'gemini',
      'model': await _storage.read(key: 'model') ?? '',
      'api_key': key,
    };
  } catch (_) {
    // Çözülemeyen anahtar (bozuk depo vb.) boş sayılır.
    return {};
  }
}

Future<void> save(String provider, String apiKey, String model) async {
  await _storage.write(key: 'provider', value: provider);
  await _storage.write(key: 'api_key', value: apiKey);
  await _storage.write(key: 'model', value: model);
}

Future<void> clear() async {
  await _storage.delete(key: 'provider');
  await _storage.delete(key: 'api_key');
  await _storage.delete(key: 'model');
}
