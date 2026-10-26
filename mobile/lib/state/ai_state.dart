// Delti (AI) durum ve davranışı (MainWindow: _start_batch, _render_ai,
// _submit_batch, _schedule_auto_ai, request_manual, compare_with_saved,
// explain_term, summarize_history, submit_nl, _apply_nl, _apply_nl_page).

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../ai/ai_client.dart';
import '../ai/ai_context.dart' as ctx;
import '../engine/core.dart' as core;
import '../ui/fmt.dart' as fmt;
import 'app_state.dart';

class AiSlot {
  const AiSlot(this.title, this.text, this.source);
  final String title;
  final String text;

  /// 'ai' | 'pending' | 'fallback_offline' | 'fallback_invalid' | 'local'
  final String source;
}

/// (yazı, renk anahtarı) — etiket.
const Map<String, String> sourceChips = {
  'ai': 'AI',
  'pending': 'Düşünüyor…',
  'fallback_offline': 'Çevrimdışı · şablon',
  'fallback_invalid': 'Şablon · doğrulanamadı',
  'local': 'Uygulama',
};

/// Delti'ye Sor sayfasının cevabı.
class NlAnswer {
  const NlAnswer({
    required this.state,
    this.title = '',
    this.what = '',
    this.effect = '',
    this.effectDelta,
    this.effectGood = true,
    this.explain = '',
    this.via = '',
    this.canOpen = false,
    this.error,
  });

  /// 'think' | 'ready'
  final String state;
  final String title;
  final String what;
  final String effect;
  final String? effectDelta;
  final bool effectGood;
  final String explain;
  final String via;
  final bool canOpen;
  final String? error;
}

class AiState extends ChangeNotifier {
  AiState(this.app, this.service) {
    app.addListener(_onApp);
    _last = app.current;
    _scheduleAuto();
  }

  final AppState app;
  final AIService service;

  Computation? _last;
  int _gen = 0;
  List<AiSlot> slots = [];
  Timer? _aiDebounce;

  // Üst bant doğal dil durumu
  String nlStatus = '';
  String nlStatusKind = 'info';

  // Geçmiş özeti
  String? summaryText;
  String summarySource = 'local';

  // Delti'ye Sor sayfası
  NlAnswer? nlAnswer;

  bool get online => service.online;

  void _onApp() {
    if (!identical(app.current, _last)) {
      _last = app.current;
      if (app.lastAutoAi) _scheduleAuto();
    }
  }

  @override
  void dispose() {
    app.removeListener(_onApp);
    _aiDebounce?.cancel();
    super.dispose();
  }

  /// Açıklama kartında yeni bir metin grubu başlatır; eski yanıtlar yok sayılır.
  int _startBatch(List<AiSlot> items) {
    _gen++;
    slots = List.of(items);
    notifyListeners();
    return _gen;
  }

  void showLocal(String title, String text) {
    _aiDebounce?.cancel();
    _startBatch([AiSlot(title, text, 'local')]);
  }

  void _submitBatch(List<AIRequest> reqs) {
    final pending = online ? 'pending' : 'fallback_offline';
    final gen = _startBatch([for (final r in reqs) AiSlot(r.title, r.fallback(), pending)]);
    for (var idx = 0; idx < reqs.length; idx++) {
      final req = reqs[idx];
      service.submit(req).then((reply) {
        if (gen != _gen || idx >= slots.length) return;
        slots[idx] = AiSlot(slots[idx].title, reply.text, reply.source);
        notifyListeners();
      });
    }
  }

  void _scheduleAuto() {
    final c = app.current;
    final reqs = ctx.autoRequests(c);
    if (reqs.isEmpty) {
      showLocal('Durum', statusMessage(c.result, c.inputs.restricted.toSet()));
      return;
    }
    if (!online) {
      _aiDebounce?.cancel();
      _submitBatch(reqs);
      return;
    }
    _startBatch([for (final r in reqs) AiSlot(r.title, r.fallback(), 'pending')]);
    _aiDebounce?.cancel();
    _aiDebounce = Timer(const Duration(milliseconds: 700), () {
      final again = ctx.autoRequests(app.current);
      if (again.isNotEmpty) _submitBatch(again);
    });
  }

  void requestManual(AIRequest? Function(Computation) builder) {
    _aiDebounce?.cancel();
    final c = app.current;
    final req = builder(c);
    if (req == null) {
      final msg = statusMessage(c.result, c.inputs.restricted.toSet());
      showLocal('Açıklama',
          'Bu işlev mevcut senaryo durumunda kullanılamaz (${msg.isEmpty ? 'hesap yok' : msg}).');
      return;
    }
    _submitBatch([req]);
  }

  Future<void> compareWithSaved() async {
    final saved = await app.db.latest();
    if (saved == null) {
      showLocal('Senaryo kıyası',
          'Karşılaştırmak için önce bir senaryoyu "Senaryoyu kaydet" ile geçmişe ekleyin.');
      return;
    }
    requestManual((c) => ctx.scenarioCompare(saved, c));
  }

  void explainTerm(String term) => requestManual((_) => ctx.termExplain(term.trim()));

  Future<void> summarizeHistory() async {
    final req = ctx.historySummary(await app.db.list(10));
    if (req == null) {
      summaryText = 'Özetlenecek kayıt yok.';
      summarySource = 'local';
      notifyListeners();
      return;
    }
    summaryText = req.fallback();
    summarySource = online ? 'pending' : 'fallback_offline';
    notifyListeners();
    final reply = await service.submit(req);
    summaryText = reply.text;
    summarySource = reply.source;
    notifyListeners();
  }

  /// Delti ayarları değişti: yeni yapılandırma, durum satırları ve açıklama tazelenir.
  Future<void> reloadConfig() async {
    service.setConfig(await loadConfig());
    _setNlStatus(online ? 'Delti uyanık.' : 'Delti uyuyor: Delti ayarlarından anahtar girin.',
        online ? 'ok' : 'info');
    _scheduleAuto();
  }

  void _setNlStatus(String text, [String kind = 'info']) {
    nlStatus = text;
    nlStatusKind = kind;
    notifyListeners();
  }

  // ---------------- doğal dil ----------------

  /// AI ve kural çözümleyiciyi birleştirir: cümlede açıkça yazan sayılar kural
  /// çözümleyiciden gelir, AI yalnızca boşlukları doldurur.
  (Map<String, Object?>?, String, String) _nlMerge(String sentence, AIReply reply) {
    final rule = ctx.parseNlRule(sentence);
    Map<String, Object?>? aiObj;
    if (reply.source == 'ai') {
      try {
        aiObj = parseJsonReply(reply.text);
      } catch (_) {
        aiObj = null;
      }
    }
    Map<String, Object?> obj;
    String via;
    if (aiObj == null) {
      obj = Map.of(rule);
      via = 'kural çözümleyici (Delti çevrimdışı)';
    } else {
      obj = {...aiObj, ...rule};
      via = 'Delti (AI)';
    }
    if (!const ['asset_id', 's', 'L', 't', 'p'].any(obj.containsKey)) {
      return (null, 'Cümleden senaryo bilgisi çıkarılamadı.', via);
    }
    obj.putIfAbsent('p', () => 1.0);
    final (merged, err) = ctx.validateNl(obj, app.inputs);
    return (merged, err, via);
  }

  /// Üst banttaki kutu: cümleyi uygular ve Senaryo sekmesine geçer.
  Future<bool> submitNl(String sentence) async {
    sentence = sentence.trim();
    if (sentence.isEmpty) return false;
    _setNlStatus(online ? 'Çözümleniyor…' : '');
    final reply = await service.submit(ctx.nlInput(sentence, app.inputs));
    final (merged, err, via) = _nlMerge(sentence, reply);
    if (merged == null) {
      _setNlStatus('Uygulanamadı: $err', 'error');
      showLocal('Doğal dil girişi',
          ((prompts()['by_id'] as Map)['nl_input'] as Map)['fallback_template'] as String);
      return false;
    }
    final cur = app.inputs;
    app.setInputs(ScenarioInputs(
      assetId: merged['asset_id'] as String,
      date: cur.date,
      s: merged['s'] as int,
      L: merged['L'] as int,
      t: merged['t'] as int,
      p: merged['p'] as double,
      restricted: cur.restricted,
      ciKind: cur.ciKind,
      parametric: cur.parametric,
      paramKwh: cur.paramKwh,
    ));
    _setNlStatus('✓ Uygulandı · $via', 'ok');
    return true;
  }

  /// Delti'ye Sor sayfası: cümle → anlaşılan senaryo (Senaryo'ya uygulanır) → önizleme.
  Future<void> submitNlPage(String sentence) async {
    sentence = sentence.trim();
    if (sentence.isEmpty) return;
    nlAnswer = const NlAnswer(state: 'think', title: 'Düşünüyorum…');
    notifyListeners();
    final reply = await service.submit(ctx.nlInput(sentence, app.inputs));
    final (merged, err, via) = _nlMerge(sentence, reply);
    if (merged == null) {
      nlAnswer = NlAnswer(state: 'ready', error: err);
      notifyListeners();
      return;
    }
    final cur = app.inputs;
    final mg = ScenarioInputs(
      assetId: merged['asset_id'] as String,
      date: cur.date,
      s: merged['s'] as int,
      L: merged['L'] as int,
      t: merged['t'] as int,
      p: merged['p'] as double,
      restricted: cur.restricted,
      ciKind: cur.ciKind,
    );
    app.setInputs(mg);
    // Önizleme motorla hesaplanır (kısıtsız, tCO2).
    final m = app.data.machine(mg.assetId);
    final (load, ci) = app.data.scenarioSeries(mg.assetId, mg.date);
    final r = core.simulate(load, ci, mg.s, mg.L, mg.t, mg.p, shiftable: m.shiftable);
    final c = Computation(
        ScenarioInputs(assetId: mg.assetId, date: mg.date, s: mg.s, L: mg.L, t: mg.t, p: mg.p), m, load, ci, r);
    final ex = resultExplanation(c);
    nlAnswer = NlAnswer(
      state: 'ready',
      title: 'Anladım:',
      what: '${m.name} · ${fmt.date(mg.date)} · ${fmt.window(mg.s, mg.L)} → ${fmt.window(mg.t, mg.L)} · '
          '%${fmt.num(mg.p * 100, 0)}',
      effect: r.status == core.ok
          ? 'Senaryo sekmesine uyguladım; emisyon'
          : 'Senaryo sekmesine uyguladım; bu girdilerle yüzde hesaplanamıyor.',
      effectDelta: r.status == core.ok ? fmt.pct(r.deltaPct) : null,
      effectGood: (r.deltaPct ?? 0) <= 0,
      explain: ex.isNotEmpty ? ex : statusMessage(r, const {}),
      via: 'Çözümleyen: $via',
      canOpen: true,
    );
    notifyListeners();
  }

  void clearNlAnswer() {
    nlAnswer = null;
    notifyListeners();
  }
}

