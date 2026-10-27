// ignore_for_file: non_constant_identifier_names
// Ana pencerenin durum ve davranışı (desktop/main_window.py: ScenarioInputs,
// Computation, status_message, result_explanation, recompute, kaydet, geri yükle...).

import 'package:flutter/foundation.dart';

import '../data/history_db.dart';
import '../engine/best_window.dart';
import '../engine/core.dart' as core;
import '../engine/data.dart';
import '../ui/fmt.dart' as fmt;

const String appTitle = 'CarbonDelta — Emisyon Potansiyeli Karar Destek';
const String footerText = 'Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo';
const String nonShiftableText = 'Bu yük kaydırılamaz (sürekli/kısıtlı süreç). Öneri üretilmez.';
const Map<String, String> ciLabels = {'tCO2': 'tCO2', 'tCO2esd': 'tCO2-eşd'};
const String demoDate = '2025-07-15';

String machineLabel(Machine m) => m.shiftable ? m.name : '${m.name} — kaydırılamaz';

class ScenarioInputs {
  const ScenarioInputs({
    required this.assetId,
    required this.date,
    required this.s,
    required this.L,
    required this.t,
    required this.p,
    this.restricted = const [],
    this.ciKind = 'tCO2',
    this.parametric = false,
    this.paramKwh = 50.0,
  });

  final String assetId;
  final String date;
  final int s;
  final int L;
  final int t;
  final double p;
  final List<int> restricted;
  final String ciKind;
  final bool parametric;
  final double paramKwh;

  String get mode => parametric ? 'parametric' : 'data';

  ScenarioInputs copyWith({
    String? assetId,
    String? date,
    int? s,
    int? L,
    int? t,
    double? p,
    List<int>? restricted,
    String? ciKind,
    bool? parametric,
    double? paramKwh,
  }) =>
      ScenarioInputs(
        assetId: assetId ?? this.assetId,
        date: date ?? this.date,
        s: s ?? this.s,
        L: L ?? this.L,
        t: t ?? this.t,
        p: p ?? this.p,
        restricted: restricted ?? this.restricted,
        ciKind: ciKind ?? this.ciKind,
        parametric: parametric ?? this.parametric,
        paramKwh: paramKwh ?? this.paramKwh,
      );
}

class Computation {
  const Computation(this.inputs, this.machine, this.load, this.ci, this.result);
  final ScenarioInputs inputs;
  final Machine machine;
  final List<double> load;
  final List<double> ci;
  final core.Result result;
}

/// ok dışındaki durumlar için kullanıcıya gösterilen Türkçe açıklama.
String statusMessage(core.Result r, Set<int> restricted, [double? p]) {
  switch (r.status) {
    case core.nonShiftable:
      return nonShiftableText;
    case core.outOfRange:
      return 'Aralık dışı: pencere aynı gün içinde kalmalı (başlangıç saati + uzunluk en fazla 24 olabilir).';
    case core.restrictedConflict:
      final hours = [for (final h in r.targetHours) if (restricted.contains(h)) fmt.hour(h)].join(', ');
      return 'Seçilen pencere kısıtlı saatlerle çakışıyor ($hours). Hesap yapılmadı.';
    case core.sameWindow:
      return 'Standart ve seçilen pencere aynı; emisyon değişmez.';
    case core.noLoad:
      if (p == 0) return 'Kaydırma oranı %0: taşınacak enerji yok; yüzde hesaplanamaz. Oranı artırın.';
      return 'Standart pencerede yük yok (0 kWh); yüzde hesaplanamaz.';
  }
  return '';
}

/// Sonuç kartında büyük yüzdenin ne anlama geldiğini anlatan cümle (hesaptan, AI'sız).
String resultExplanation(Computation c) {
  final r = c.result;
  final i = c.inputs;
  final unit = i.ciKind == 'tCO2' ? 'kgCO2' : 'kgCO2-eşd';
  final src = fmt.window(i.s, i.L);
  final tgt = fmt.window(i.t, i.L);
  final moved = '${fmt.num(r.shiftedKwh)} kWh enerji (yükün %${fmt.num(i.p * 100, 0)} kadarı)';
  if (r.status == core.ok) {
    String what;
    if (r.deltaPct! <= 0) {
      what = 'Bu yüzde, $src aralığındaki $moved $tgt aralığında kullanılırsa bu enerjinin emisyonunun '
          '${fmt.num(r.baselineKg)} $unit yerine ${fmt.num(r.scenarioKg)} $unit olacağını gösterir.';
    } else {
      what = 'Bu yüzde, $src aralığındaki $moved $tgt aralığına alınırsa emisyonun '
          '${fmt.num(r.baselineKg)} $unit yerine ${fmt.num(r.scenarioKg)} $unit olacağını, '
          'yani seçilen saatlerde şebekenin daha kirli olduğunu gösterir.';
    }
    return '$what Makinenin o günkü toplam emisyonu açısından etkisi ${fmt.pct(r.dailyDeltaPct)}.';
  }
  if (r.status == core.sameWindow) return 'Yük aynı saatlerde kaldığı için emisyon değişmez.';
  return '';
}

/// Verisi olan günler içinde en yakın gün (eşitlikte önceki gün).
String nearestDay(List<String> days, String iso) {
  int ord(String d) => DateTime.utc(int.parse(d.substring(0, 4)), int.parse(d.substring(5, 7)),
          int.parse(d.substring(8, 10)))
      .millisecondsSinceEpoch ~/
      86400000;
  int target;
  try {
    target = ord(iso);
  } catch (_) {
    return days.first;
  }
  final ords = [for (final d in days) ord(d)];
  var lo = 0, hi = ords.length;
  while (lo < hi) {
    final mid = (lo + hi) >> 1;
    if (ords[mid] < target) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  final cand = [for (final j in [lo - 1, lo]) if (j >= 0 && j < ords.length) j];
  cand.sort((a, b) {
    final c = (ords[a] - target).abs().compareTo((ords[b] - target).abs());
    return c != 0 ? c : a.compareTo(b);
  });
  return days[cand.first];
}

class AppState extends ChangeNotifier {
  AppState(this.data, this.db) {
    _inputs = _demoInputs();
    recompute();
  }

  final DataStore data;
  final HistoryDB db;

  late ScenarioInputs _inputs;
  late Computation current;

  /// "✓ Geçmişe kaydedildi" etiketi (2,5 sn).
  String savedLabel = '';

  /// Geçmiş listesi değişince artar (ekranlar yeniden okur).
  int historyVersion = 0;

  /// Veri paketleri değişince artar.
  int dataVersion = 0;

  /// Yıllık Etki / Tesis Planı açıkken alt bilgide kendi kapsamlarının kaynak etiketi (metin, tesis ölçümü mü).
  final ValueNotifier<(String, bool)?> tabFooter = ValueNotifier(null);

  /// Son hesap otomatik Delti açıklaması istesin mi (En iyi saat sonrası istemez).
  bool lastAutoAi = true;

  ScenarioInputs get inputs => _inputs;
  Machine get selectedMachine => data.machine(_inputs.assetId);

  static ScenarioInputs _demoInputs() => const ScenarioInputs(
      assetId: 'comp_b', date: demoDate, s: 3, L: 3, t: 18, p: 1.0);

  ScenarioInputs demoInputs() => _demoInputs();

  /// Girdileri değiştirir; makine değiştiyse gün en yakın geçerli güne çekilir.
  void update(ScenarioInputs Function(ScenarioInputs) change, {bool autoAi = true}) {
    var next = change(_inputs);
    if (!data.hasMachine(next.assetId)) {
      next = next.copyWith(assetId: data.machines().first.id);
    }
    final days = data.daysFor(next.assetId);
    final near = nearestDay(days, next.date);
    if (near != next.date) next = next.copyWith(date: near);
    _inputs = next;
    recompute(autoAi: autoAi);
  }

  /// Kaydedilmiş bir senaryoyu girdilere geri yükler.
  void setInputs(ScenarioInputs i) => update((_) => i);

  (List<double>, List<double>) series(ScenarioInputs i) => data.scenarioSeries(i.assetId, i.date,
      kind: i.ciKind, parametricKwh: i.parametric ? i.paramKwh : null);

  void recompute({bool autoAi = true}) {
    lastAutoAi = autoAi;
    final i = _inputs;
    final m = data.machine(i.assetId);
    final (load, ci) = series(i);
    final r = core.simulate(load, ci, i.s, i.L, i.t, i.p,
        restricted: i.restricted.toSet(), shiftable: m.shiftable);
    current = Computation(i, m, load, ci, r);
    notifyListeners();
  }

  Future<int?> saveCurrent() async {
    final i = current.inputs;
    final r = current.result;
    final id = await db.add(
      assetId: i.assetId, date: i.date, s: i.s, L: i.L, t: i.t, p: i.p,
      restricted: i.restricted, mode: i.mode, ciKind: i.ciKind, status: r.status,
      deltaPct: r.deltaPct, dailyDeltaPct: r.dailyDeltaPct,
      baselineKg: r.baselineKg, scenarioKg: r.scenarioKg,
      paramKwh: i.parametric ? i.paramKwh : null,
    );
    historyVersion++;
    savedLabel = '✓ Geçmişe kaydedildi';
    notifyListeners();
    Future.delayed(const Duration(milliseconds: 2500), () {
      savedLabel = '';
      notifyListeners();
    });
    return id;
  }

  /// Geçmiş kaydını geri yükler. Dönüş: (açıldı mı, kullanıcıya gösterilecek uyarı).
  (bool, String?) restoreHistory(HistoryRow h) {
    if (!data.hasMachine(h.assetId)) {
      return (
        false,
        'Bu kaydın makinesi artık yüklü değil (veri paketi kapatılmış ya da silinmiş). '
            'Veri sekmesinden paketi yeniden açabilirsiniz.'
      );
    }
    setInputs(ScenarioInputs(
      assetId: h.assetId, date: h.date, s: h.s, L: h.L, t: h.t, p: h.p,
      restricted: h.restricted, ciKind: h.ciKind, parametric: h.mode == 'parametric',
      paramKwh: h.paramKwh ?? 50.0,
    ));
    final opened = _inputs.date;
    if (opened != h.date) {
      return (
        true,
        'Kaydın günü (${fmt.date(h.date)}) artık veride yok (şebeke ya da makine paketi kapatılmış '
            'olabilir). En yakın gün olan ${fmt.date(opened)} açıldı; sonuç kayıttakinden farklı olabilir.'
      );
    }
    return (true, null);
  }

  /// "En iyi saati bul". Bulunamazsa false.
  bool applyBestWindow() {
    final i = _inputs;
    final m = data.machine(i.assetId);
    final (load, ci) = series(i);
    final found = bestWindow(load, ci, i.s, i.L, i.p,
        restricted: i.restricted.toSet(), shiftable: m.shiftable);
    if (found == null) return false;
    update((x) => x.copyWith(t: found.$1), autoAi: false);
    return true;
  }

  /// Temiz başlangıç: makine ve gün korunur; kısıtlar, oran ve mod sıfırlanır.
  void newScenario() {
    final cur = _inputs;
    setInputs(ScenarioInputs(assetId: cur.assetId, date: cur.date, s: 3, L: 3, t: 18, p: 1.0));
  }

  void notifyHistoryChanged() {
    historyVersion++;
    notifyListeners();
  }

  /// Veri paketi eklendi/açıldı/kapandı/silindi: her şeyi yeniden oku ve tazele.
  Future<void> applyDataChange() async {
    await data.reload();
    dataVersion++;
    update((i) => i);
  }
}
