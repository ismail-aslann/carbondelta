// AI açıklama katmanı: LLM yalnızca motorun ürettiği sayıları metne çevirir
// (desktop/ai_client.py).
//
// - Ayarlar: uygulamadaki "Delti ayarları" (ai_settings.dart) veya derleme
//   ayarı (--dart-define=LLM_PROVIDER/LLM_API_KEY/LLM_MODEL).
// - İstekler arka planda, 15 sn zaman aşımı; arayüz donmaz.
// - Metindeki her sayı girdilerdeki sayılarla doğrulanır; uymazsa şablon metin.
// - Anahtar/internet yoksa veya hata olursa: çevrimdışı mesajı + şablon metin.

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart' show rootBundle;
import 'package:http/http.dart' as http;

import 'ai_settings.dart' as ai_settings;

const Duration timeout = Duration(seconds: 15);
const Map<String, String> defaultModels = {
  'gemini': 'gemini-flash-lite-latest',
  'claude': 'claude-opus-5-5',
};
const Set<String> claudeFallbackModels = {
  'claude-fable-5-1', 'claude-opus-5', 'claude-sonnet-5-5', 'claude-opus-5-5',
};
final Set<double> _allowedHours = {for (var h = 0; h < 25; h++) h.toDouble()};

class AIConfig {
  const AIConfig({required this.provider, required this.apiKey, required this.model, this.source = ''});
  final String provider;
  final String apiKey;
  final String model;

  /// 'uygulama' | 'ortam' | ''
  final String source;

  bool get enabled => apiKey.isNotEmpty && defaultModels.containsKey(provider);
}

const _envProvider = String.fromEnvironment('LLM_PROVIDER');
const _envKey = String.fromEnvironment('LLM_API_KEY');
const _envModel = String.fromEnvironment('LLM_MODEL');

/// Öncelik: derleme ayarı (ortam) > uygulamadaki Delti ayarları.
Future<AIConfig> loadConfig() async {
  var vals = <String, String>{};
  var source = '';
  final saved = await ai_settings.load();
  if ((saved['api_key'] ?? '').isNotEmpty) {
    vals = {
      'LLM_PROVIDER': saved['provider'] ?? '',
      'LLM_API_KEY': saved['api_key'] ?? '',
      'LLM_MODEL': saved['model'] ?? '',
    };
    source = 'uygulama';
  }
  if (_envKey.trim().isNotEmpty) source = 'ortam';
  String get(String key, String env) => env.trim().isNotEmpty ? env.trim() : (vals[key] ?? '').trim();
  final provider = (get('LLM_PROVIDER', _envProvider).isEmpty ? 'gemini' : get('LLM_PROVIDER', _envProvider))
      .toLowerCase();
  final apiKey = get('LLM_API_KEY', _envKey);
  final model = get('LLM_MODEL', _envModel);
  return AIConfig(
    provider: provider,
    apiKey: apiKey,
    model: model.isNotEmpty ? model : (defaultModels[provider] ?? ''),
    source: apiKey.isNotEmpty ? source : '',
  );
}

Map<String, dynamic>? _prompts;

Map<String, dynamic> prompts() => _prompts!;

Future<void> loadPrompts() async {
  if (_prompts != null) return;
  final doc = jsonDecode(await rootBundle.loadString('assets/shared/prompts/ai_functions.json'))
      as Map<String, dynamic>;
  doc['by_id'] = {
    for (final fn in doc['functions'] as List) (fn as Map)['id'] as String: Map<String, dynamic>.from(fn),
  };
  _prompts = doc;
}

final RegExp _placeholder = RegExp(r'\{(\w+)\}');

/// {anahtar} yer tutucularını doldurur; bilinmeyen anahtarlara dokunmaz.
String render(String template, Map<String, Object?> values) => template.replaceAllMapped(
    _placeholder, (m) => values.containsKey(m.group(1)) ? '${values[m.group(1)] ?? 'None'}' : m.group(0)!);

final RegExp _number = RegExp(r'(?<![\w.,])[-−+]?\d+(?:[.,]\d+)?');
final RegExp _date = RegExp(r'(?<![\w.,])(\d{1,2})[./](\d{1,2})[./](\d{4})(?![\w])');

/// Metindeki sayılar: (mutlak değer, ondalık basamak sayısı).
List<(double, int)> extractNumbers(String text) {
  final out = <(double, int)>[];
  text = text.replaceAllMapped(_date, (m) => '${m.group(1)} ${m.group(2)} ${m.group(3)}');
  for (final m in _number.allMatches(text)) {
    var tok = m.group(0)!;
    tok = tok.replaceFirst(RegExp(r'^[+\-−]+'), '').replaceAll(',', '.');
    final decimals = tok.contains('.') ? tok.split('.')[1].length : 0;
    out.add((double.parse(tok).abs(), decimals));
  }
  return out;
}

/// JSON benzeri yapıdaki tüm sayılar (metinlerdeki tarih/saat rakamları dahil).
List<double> collectNumbers(Object? obj) {
  final nums = <double>[];
  if (obj == null || obj is bool) return nums;
  if (obj is num) {
    nums.add(obj.toDouble());
  } else if (obj is String) {
    nums.addAll(extractNumbers(obj).map((e) => e.$1));
  } else if (obj is Map) {
    for (final v in obj.values) {
      nums.addAll(collectNumbers(v));
    }
  } else if (obj is Iterable) {
    for (final v in obj) {
      nums.addAll(collectNumbers(v));
    }
  }
  return nums;
}

/// Python round(x, n) (eşitlikte çift sayıya yuvarlama).
double pyRound(double v, int digits) {
  final scale = [1.0, 10.0, 100.0, 1000.0][digits];
  final m = v * scale;
  final fl = m.floorToDouble();
  if (m - fl == 0.5) {
    final even = (fl % 2 == 0) ? fl : fl + 1;
    return even / scale;
  }
  return double.parse(v.toStringAsFixed(digits));
}

/// Girdilerdeki sayıların 0, 1 ve 2 ondalıklı yuvarlanmış halleri + saatler (0–24).
Set<double> allowedNumbers(Object? payload) {
  final allowed = {..._allowedHours};
  for (final v in collectNumbers(payload)) {
    for (final d in const [0, 1, 2]) {
      allowed.add(pyRound(v.abs(), d));
    }
  }
  return allowed;
}

bool validateNumbers(String text, Set<double> allowed) {
  for (final (value, decimals) in extractNumbers(text)) {
    if (decimals > 2) return false;
    if (!allowed.contains(pyRound(value, decimals))) return false;
  }
  return true;
}

class AIError implements Exception {
  AIError(this.message);
  final String message;
  @override
  String toString() => message;
}

Future<Map<String, dynamic>> _postJson(String url, Map<String, String> headers, Map<String, Object?> body) async {
  http.Response resp;
  try {
    resp = await http
        .post(Uri.parse(url), headers: {'content-type': 'application/json', ...headers}, body: jsonEncode(body))
        .timeout(timeout);
  } on TimeoutException catch (e) {
    throw AIError('Bağlantı hatası: $e');
  } on SocketException catch (e) {
    throw AIError('Bağlantı hatası: $e');
  } on http.ClientException catch (e) {
    throw AIError('Bağlantı hatası: $e');
  }
  final text = utf8.decode(resp.bodyBytes, allowMalformed: true);
  if (resp.statusCode >= 400) {
    throw AIError('HTTP ${resp.statusCode}: ${text.length > 300 ? text.substring(0, 300) : text}');
  }
  return jsonDecode(text) as Map<String, dynamic>;
}

Future<String> _callGemini(AIConfig cfg, String system, String user, bool jsonMode) async {
  final url = 'https://generativelanguage.googleapis.com/v1beta/models/${cfg.model}:generateContent';
  final gen = <String, Object?>{'temperature': 0, 'maxOutputTokens': 1024};
  if (jsonMode) gen['responseMimeType'] = 'application/json';
  final body = {
    'systemInstruction': {
      'parts': [
        {'text': system}
      ]
    },
    'contents': [
      {
        'role': 'user',
        'parts': [
          {'text': user}
        ]
      }
    ],
    'generationConfig': gen,
  };
  final data = await _postJson(url, {'x-goog-api-key': cfg.apiKey}, body);
  List parts;
  try {
    parts = ((data['candidates'] as List)[0]['content'] as Map)['parts'] as List;
  } catch (_) {
    final s = data.toString();
    throw AIError('Beklenmeyen Gemini yanıtı: ${s.length > 200 ? s.substring(0, 200) : s}');
  }
  return parts.map((p) => ((p as Map)['text'] ?? '').toString()).join().trim();
}

Future<String> _callClaude(AIConfig cfg, String system, String user, bool jsonMode) async {
  final body = <String, Object?>{
    'model': cfg.model,
    'max_tokens': 2048,
    'system': system,
    'messages': [
      {'role': 'user', 'content': user}
    ],
    'output_config': {'effort': 'low'},
  };
  final headers = {'x-api-key': cfg.apiKey, 'anthropic-version': '2023-06-01'};
  if (claudeFallbackModels.contains(cfg.model)) {
    body['fallbacks'] = 'default';
    headers['anthropic-beta'] = 'server-side-fallback-2026-07-01';
  }
  final data = await _postJson('https://api.anthropic.com/v1/messages', headers, body);
  if (data['stop_reason'] == 'refusal') throw AIError('Model isteği reddetti.');
  final text = [
    for (final b in (data['content'] ?? const []) as List)
      if ((b as Map)['type'] == 'text') (b['text'] ?? '').toString(),
  ].join();
  if (text.trim().isEmpty) throw AIError('Boş yanıt.');
  return text.trim();
}

Future<String> callLlm(AIConfig cfg, String system, String user, {bool jsonMode = false}) {
  if (!cfg.enabled) throw AIError('AI yapılandırılmamış.');
  if (cfg.provider == 'claude') return _callClaude(cfg, system, user, jsonMode);
  return _callGemini(cfg, system, user, jsonMode);
}

/// AIError metnini kullanıcıya gösterilecek kısa Türkçe açıklamaya çevirir.
String friendlyError(String err) {
  final m = RegExp(r'HTTP (\d+)').firstMatch(err);
  final code = m != null ? int.parse(m.group(1)!) : 0;
  if (code == 401 || code == 403 ||
      (code == 400 && RegExp('API_KEY|api key|apikey', caseSensitive: false).hasMatch(err))) {
    return 'Anahtar geçersiz ya da bu sağlayıcıya ait değil.';
  }
  if (code == 404) return 'Model bulunamadı. Model alanını boş bırakıp tekrar deneyin.';
  if (code == 429) return 'Anahtar çalışıyor ama kullanım sınırı doldu; biraz sonra tekrar deneyin.';
  if (code >= 500) return 'Sağlayıcı şu an yanıt veremiyor; biraz sonra tekrar deneyin.';
  if (err.startsWith('Bağlantı hatası')) {
    return 'İnternete bağlanılamadı. Bağlantıyı veya güvenlik duvarını kontrol edin.';
  }
  return err.length > 160 ? err.substring(0, 160) : err;
}

/// Kısa bir istekle anahtarı dener.
Future<(bool, String)> checkConnection(AIConfig cfg) async {
  if (cfg.apiKey.isEmpty) return (false, 'Önce API anahtarını girin.');
  try {
    await callLlm(cfg, 'Kısa yanıt ver.', "Yalnızca 'tamam' yaz.");
  } on AIError catch (e) {
    return (false, friendlyError(e.message));
  } catch (e) {
    return (false, friendlyError(e.toString()));
  }
  return (true, 'Bağlantı başarılı. Delti uyanık.');
}

/// ```json ... ``` sarmalı olsa da ilk JSON nesnesini çıkarır.
Map<String, dynamic> parseJsonReply(String text) {
  final m = RegExp(r'\{.*\}', dotAll: true).firstMatch(text);
  if (m == null) throw AIError('Yanıtta JSON yok.');
  Object? obj;
  try {
    obj = jsonDecode(m.group(0)!);
  } on FormatException {
    throw AIError('Geçersiz JSON.');
  }
  if (obj is! Map) throw AIError('JSON nesne değil.');
  return Map<String, dynamic>.from(obj);
}

class AIRequest {
  AIRequest(this.funcId, this.payload, this.display, {this.extra, this.jsonMode = false});

  final String funcId;
  final Map<String, Object?> payload;
  final Map<String, Object?> display;
  final Map<String, Object?>? extra;
  final bool jsonMode;

  Map<String, dynamic> get _fn => (prompts()['by_id'] as Map)[funcId] as Map<String, dynamic>;

  String systemPrompt() => '${prompts()['common_system']}\n\n${_fn['system']}';

  String userPrompt() {
    final values = <String, Object?>{'payload_json': jsonEncode(payload)};
    values.addAll(extra ?? const {});
    return render(_fn['user_template'] as String, values);
  }

  String fallback() => render(_fn['fallback_template'] as String, display);

  String get title => _fn['title'] as String;

  String cacheKey() => jsonEncode([funcId, payload, extra]);
}

class AIReply {
  const AIReply(this.funcId, this.text, this.source, [this.error = '']);
  final String funcId;
  final String text;

  /// 'ai' | 'fallback_offline' | 'fallback_invalid'
  final String source;
  final String error;
}

final RegExp _intro = RegExp(
    r'^\s*(merhaba|selam|iyi günler|ben,?\s+delti|delti olarak|ben\s+carbondelta)\b[^.!?]*[.!?]+\s*',
    caseSensitive: false);

/// Model talimata rağmen kendini tanıtırsa baştaki tanıtım cümlelerini siler.
String stripIntro(String text) {
  String? prev;
  while (prev != text) {
    prev = text;
    text = text.replaceFirst(_intro, '');
  }
  return text.trim();
}

Future<AIReply> runRequest(AIConfig cfg, AIRequest req) async {
  if (!cfg.enabled) return AIReply(req.funcId, req.fallback(), 'fallback_offline', 'AI yapılandırılmamış.');
  String text;
  try {
    text = await callLlm(cfg, req.systemPrompt(), req.userPrompt(), jsonMode: req.jsonMode);
  } catch (e) {
    return AIReply(req.funcId, req.fallback(), 'fallback_offline', e.toString());
  }
  if (req.jsonMode) return AIReply(req.funcId, text, 'ai');
  text = stripIntro(text);
  if (text.isEmpty) {
    return AIReply(req.funcId, req.fallback(), 'fallback_invalid', 'Boş yanıt (yalnızca giriş cümlesi).');
  }
  if (!validateNumbers(text, allowedNumbers([req.payload, req.extra ?? const {}]))) {
    return AIReply(req.funcId, req.fallback(), 'fallback_invalid', text);
  }
  return AIReply(req.funcId, text, 'ai');
}

/// İstekleri arka planda çalıştırır; sonuçları önbelleğe alır.
class AIService {
  AIService(this.cfg);

  AIConfig cfg;
  final Map<String, AIReply> _cache = {};

  bool get online => cfg.enabled;

  /// Delti ayarları değişince: yeni anahtar/model, eski önbellek geçersiz.
  void setConfig(AIConfig c) {
    cfg = c;
    _cache.clear();
  }

  Future<AIReply> submit(AIRequest req) async {
    final key = req.cacheKey();
    final hit = _cache[key];
    if (hit != null) return hit;
    final rep = await runRequest(cfg, req);
    if (rep.source == 'ai') _cache[key] = rep;
    return rep;
  }
}
