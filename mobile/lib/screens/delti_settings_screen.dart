// Delti ayarları: API anahtarı uygulama içinden girilir, denenir ve saklanır
// (desktop/delti_settings.py).

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../ai/ai_client.dart';
import '../ai/ai_settings.dart' as ai_settings;
import '../ui/theme.dart' as th;
import '../widgets/delti.dart';

const List<(String, String)> providers = [('gemini', 'Google Gemini'), ('claude', 'Anthropic Claude')];
const Map<String, String> keyPages = {
  'gemini': 'https://aistudio.google.com/apikey',
  'claude': 'https://console.anthropic.com/',
};
const Map<String, String> sourceText = {
  'uygulama': 'Anahtar bu ekrandan kaydedildi (bu telefonda şifreli saklanıyor).',
  'ortam': 'Anahtar derleme ayarından (LLM_API_KEY) okunuyor; buradaki ayardan önce gelir.',
};

/// Kaydet/Kaldır sonrası true döner; çağıran yapılandırmayı yeniden yükler.
class DeltiSettingsScreen extends StatefulWidget {
  const DeltiSettingsScreen({super.key, required this.cfg});
  final AIConfig cfg;

  @override
  State<DeltiSettingsScreen> createState() => _DeltiSettingsScreenState();
}

class _DeltiSettingsScreenState extends State<DeltiSettingsScreen> {
  late String _provider;
  late final TextEditingController _key;
  late final TextEditingController _model;
  bool _show = false;
  bool _busy = false;
  String _status = '';
  bool? _ok;
  bool _canRemove = false;
  late String _avatar;
  final _link = TapGestureRecognizer();

  @override
  void initState() {
    super.initState();
    final cfg = widget.cfg;
    _provider = defaultModels.containsKey(cfg.provider) ? cfg.provider : 'gemini';
    _key = TextEditingController(text: cfg.apiKey);
    _model = TextEditingController(text: cfg.model == defaultModels[cfg.provider] ? '' : cfg.model);
    _avatar = cfg.enabled ? 'ready' : 'sleep';
    ai_settings.load().then((s) {
      if (mounted) setState(() => _canRemove = (s['api_key'] ?? '').isNotEmpty);
    });
  }

  @override
  void dispose() {
    _link.dispose();
    _key.dispose();
    _model.dispose();
    super.dispose();
  }

  AIConfig _config() => AIConfig(
        provider: _provider,
        apiKey: _key.text.trim(),
        model: _model.text.trim().isNotEmpty ? _model.text.trim() : defaultModels[_provider]!,
        source: 'uygulama',
      );

  void _setStatus(String text, bool? ok) => setState(() {
        _status = text;
        _ok = ok;
      });

  Future<void> _test() async {
    final cfg = _config();
    if (cfg.apiKey.isEmpty) {
      _setStatus('Önce API anahtarını girin.', false);
      return;
    }
    _setStatus('Deneniyor… (en fazla 15 saniye)', null);
    setState(() {
      _avatar = 'think';
      _busy = true;
    });
    final (ok, msg) = await checkConnection(cfg);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _avatar = ok ? 'ready' : 'sleep';
    });
    _setStatus(msg, ok);
  }

  Future<void> _save() async {
    final cfg = _config();
    if (cfg.apiKey.isEmpty) {
      _setStatus("Kaydetmek için API anahtarını girin (anahtarı silmek için 'Anahtarı kaldır').", false);
      return;
    }
    try {
      await ai_settings.save(cfg.provider, cfg.apiKey, _model.text.trim());
    } catch (e) {
      _setStatus('Ayar kaydedilemedi: $e', false);
      return;
    }
    if (mounted) Navigator.pop(context, true);
  }

  Future<void> _remove() async {
    await ai_settings.clear();
    if (mounted) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    final (fg, bg) = _ok == null ? (th.muted, th.bg) : (_ok! ? (th.good, th.primarySoft) : (th.bad, th.badSoft));
    return Scaffold(
      appBar: AppBar(title: const Text('Delti ayarları')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Delti(state: _avatar, size: 48),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Delti ayarları', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                    th.Muted("Delti'nin çalışması için bir yapay zekâ API anahtarı gerekir. "
                        'Hesaplar anahtarsız da çalışır.'),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          InputDecorator(
            decoration: const InputDecoration(labelText: 'Sağlayıcı', border: OutlineInputBorder(), isDense: true),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: _provider,
                isDense: true,
                isExpanded: true,
                items: [for (final (k, l) in providers) DropdownMenuItem(value: k, child: Text(l))],
                onChanged: _busy
                    ? null
                    : (v) => setState(() {
                          _provider = v!;
                          _status = '';
                        }),
              ),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _key,
            enabled: !_busy,
            obscureText: !_show,
            onChanged: (_) => _setStatus('', null),
            decoration: InputDecoration(
              labelText: 'API anahtarı',
              hintText: 'API anahtarını buraya yapıştırın',
              border: const OutlineInputBorder(),
              suffixIcon: IconButton(
                tooltip: 'Göster',
                icon: Icon(_show ? Icons.visibility_off : Icons.visibility),
                onPressed: () => setState(() => _show = !_show),
              ),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _model,
            enabled: !_busy,
            decoration: InputDecoration(
              labelText: 'Model',
              hintText: 'Boş bırakın: ${defaultModels[_provider]}',
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 10),
          // Tek akan paragraf: bağlantı satır ortasında kopuk durmaz.
          Text.rich(TextSpan(children: [
            const TextSpan(text: 'Anahtarınız yoksa: '),
            TextSpan(
              text: keyPages[_provider]!,
              style: const TextStyle(color: th.primary, decoration: TextDecoration.underline),
              recognizer: _link
                ..onTap = () => launchUrl(Uri.parse(keyPages[_provider]!), mode: LaunchMode.externalApplication),
            ),
            const TextSpan(text: ' adresinden ücretsiz/ücretli anahtar alabilirsiniz.'),
          ])),
          if (widget.cfg.source.isNotEmpty) ...[
            const SizedBox(height: 8),
            th.Muted(sourceText[widget.cfg.source] ?? ''),
          ],
          if (_status.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
              decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(8)),
              child: Text(_status, style: TextStyle(color: fg)),
            ),
          ],
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            alignment: WrapAlignment.end,
            children: [
              TextButton(
                onPressed: _canRemove && !_busy ? _remove : null,
                child: const Text('Anahtarı kaldır'),
              ),
              OutlinedButton(onPressed: _busy ? null : _test, child: const Text('Bağlantıyı dene')),
              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Vazgeç')),
              FilledButton(onPressed: _busy ? null : _save, child: const Text('Kaydet')),
            ],
          ),
          const SizedBox(height: 16),
          const th.Muted(
            "Delti'ye yalnızca hesap sonuçlarındaki sayılar gider; tesis verisi gönderilmez. "
            'Anahtar bu telefonun güvenli deposunda (Android Keystore) şifreli saklanır.',
          ),
        ],
      ),
    );
  }
}
