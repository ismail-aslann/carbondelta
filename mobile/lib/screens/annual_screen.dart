// Yıllık Etki sekmesi: senaryo yılın tüm günlerinde (bir makinede ya da tesis genelinde) uygulanırsa toplam
// emisyon değişimi, aylık kırılım, yenilenebilir pay, Delti yorumu, PDF rapor ve CSV (desktop/annual_tab.py).

// ignore_for_file: non_constant_identifier_names

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../ai/ai_context.dart' as ctx;
import '../engine/annual.dart' as annual;
import '../engine/data.dart';
import '../report/annual_export.dart';
import '../state/ai_state.dart';
import '../state/app_state.dart';
import '../ui/csv.dart';
import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;
import '../widgets/delti.dart';
import '../widgets/delti_box.dart' show SourceChip;
import '../widgets/inputs.dart';
import '../widgets/month_chart.dart';
import '../widgets/rich.dart';
import '../widgets/stat_grid.dart';

class AnnualScreen extends StatefulWidget {
  const AnnualScreen({super.key, required this.app, required this.ai, required this.onApplied});

  final AppState app;
  final AiState ai;

  /// "Senaryoya uygula" sonrası Senaryo sekmesine geçilir.
  final VoidCallback onApplied;

  @override
  State<AnnualScreen> createState() => _AnnualScreenState();
}

class _AnnualScreenState extends State<AnnualScreen> {
  /// Tesis geneli seçildiyse sekme yeniden açılınca kapsam korunur (masaüstündeki gibi).
  static bool _facilityChosen = false;

  late String _asset;
  int? _year;
  late int _s, _L, _t;
  late double _p;
  late Set<int> _restricted;
  late String _date;
  late String _kind;
  double? _param;

  final Map<String, List<annual.DaySeries>> _seriesCache = {};
  Timer? _timer;

  annual.AnnualResult? _result;
  List<annual.AnnualResult> _best = [];
  String _message = '';

  // Delti yorumu
  String _aiText = '';
  String _aiSource = '';
  String? _aiKey;
  bool _busy = false;

  AppState get app => widget.app;
  DataStore get data => app.data;

  @override
  void initState() {
    super.initState();
    _loadInputs();
    _recompute();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  List<Machine> get _machines => [for (final m in data.machines()) if (m.shiftable) m];

  /// Senaryo sekmesindeki değerlerle başlar (tesis geneli seçiliyse kapsam korunur).
  void _loadInputs() {
    final i = app.inputs;
    final ms = _machines;
    if (_facilityChosen) {
      _asset = annual.all;
    } else {
      _asset = ms.any((m) => m.id == i.assetId) ? i.assetId : (ms.isNotEmpty ? ms.first.id : annual.all);
    }
    _s = i.s;
    _L = i.L;
    _t = i.t;
    _p = i.p;
    _restricted = i.restricted.toSet();
    _date = i.date;
    _kind = i.ciKind;
    _param = i.parametric ? i.paramKwh : null;
    _fillYear(prefer: int.tryParse(i.date.length >= 4 ? i.date.substring(0, 4) : ''));
  }

  List<int> get _years => _machines.isEmpty ? const [] : annual.yearsFor(data, _asset);

  void _fillYear({int? prefer}) {
    final ys = _years;
    final cur = prefer ?? _year;
    _year = ys.contains(cur) ? cur : (ys.isEmpty ? null : ys.last);
  }

  void _schedule() {
    _timer?.cancel();
    _timer = Timer(const Duration(milliseconds: 80), () {
      if (mounted) setState(_recompute);
    });
  }

  List<annual.DaySeries> _series(String asset, int year) =>
      _seriesCache.putIfAbsent('$asset|$year', () => annual.yearSeries(data, asset, year, _kind, _param));

  annual.AnnualResult _compute(String asset, int year, int t) {
    if (asset == annual.all) {
      final series = {for (final a in annual.facilityMachines(data)) a: _series(a, year)};
      return annual.facilityImpact(data, year, _s, _L, t, _p,
          restricted: _restricted, kind: _kind, seriesByAsset: series, parametricKwh: _param);
    }
    return annual.annualImpact(data, asset, year, _s, _L, t, _p,
        restricted: _restricted, kind: _kind, series: _series(asset, year));
  }

  void _recompute() {
    _resetAi();
    final year = _year;
    if (_machines.isEmpty || year == null) {
      _result = null;
      _best = [];
      _message = 'Kaydırılabilir makine yok.';
      return;
    }
    final r = _compute(_asset, year, _t);
    _result = r;
    _best = annual.rankTargets([for (var tt = 0; tt < 25 - _L; tt++) _compute(_asset, year, tt)]);
    final src = sourceFor(data, r);
    // Alt bilgi çizim sırasında değiştirilmez; bir sonraki karede güncellenir.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) app.tabFooter.value = src.$1.isEmpty ? null : src;
    });
    if (r.daysOk == 0) {
      const reasons = {
        'restricted_conflict': 'hedef saat kısıtlı',
        'same_window': 'hedef standart pencereyle aynı',
        'no_load': 'standart pencerede yük yok',
        'out_of_range': 'pencere gün dışına taşıyor',
      };
      final why = r.statusCounts.keys.map((k) => reasons[k] ?? k).join(', ');
      _message = '${_what(r)}: ${r.year} yılında hesaba girebilen gün yok (${why.isEmpty ? 'veri yok' : why}).';
    } else {
      _message = '';
    }
  }

  String _what(annual.AnnualResult r) =>
      '${scopeName(data, r)} · ${fmt.window(r.s, r.L)} → ${fmt.window(r.t, r.L)} · %${fmt.num(r.p * 100, 0)}';

  // ------------------------------------------------------------------ Delti
  void _resetAi() {
    _aiText = '';
    _aiSource = '';
    _aiKey = null;
  }

  Future<void> _askDelti() async {
    final req = ctx.annualExplain(_result, _best.isEmpty ? null : _best.first, _kind, _param);
    if (req == null) return;
    final key = req.cacheKey();
    setState(() {
      _aiKey = key;
      _aiText = req.fallback();
      _aiSource = widget.ai.online ? 'pending' : 'fallback_offline';
    });
    final reply = await widget.ai.service.submit(req);
    if (!mounted || _aiKey != key) return; // eski bir sonuca ait yanıt yok sayılır
    setState(() {
      _aiText = reply.text;
      _aiSource = reply.source;
    });
  }

  // ------------------------------------------------------------------ işler
  void _apply() {
    final r = _result;
    if (r == null) return;
    var asset = r.assetId;
    if (r.isFacility) {
      // Senaryo tek makine çalışır: en çok katkı yapan makine.
      final parts = [for (final x in r.parts) if (x.daysOk > 0) x]..sort((a, b) => a.deltaKg.compareTo(b.deltaKg));
      asset = parts.isNotEmpty ? parts.first.assetId : annual.facilityMachines(data).first;
    }
    final days = data.daysFor(asset);
    final yearDays = [for (final d in days) if (d.startsWith('${r.year}')) d];
    final pool = yearDays.isEmpty ? days : yearDays;
    final date = pool.contains(_date) ? _date : pool.first;
    final cur = app.inputs;
    app.setInputs(ScenarioInputs(
      assetId: asset, date: date, s: r.s, L: r.L, t: r.t, p: r.p,
      restricted: cur.restricted, ciKind: cur.ciKind,
    ));
    widget.onApplied();
  }

  Future<void> _export(Future<void> Function() job) async {
    setState(() => _busy = true);
    try {
      await job();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Dosya oluşturulamadı:\n$e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _csv() => _export(() async {
        final r = _result!;
        final name = 'CarbonDelta_yillik_${r.isFacility ? 'tesis' : r.assetId}_${r.year}.csv';
        await shareFile(name, utf8.encode(annualCsv(data, r, _restricted, _kind)));
      });

  Future<void> _pdf() => _export(() async {
        final r = _result!;
        final name = 'CarbonDelta_rapor_${r.isFacility ? 'tesis' : r.assetId}_${r.year}.pdf';
        final bytes = await annualPdf(data, r, _best.isEmpty ? null : _best.first, _restricted, _kind, _param,
            aiText: _aiText, aiSource: _aiSource == 'pending' ? 'fallback_offline' : _aiSource);
        await shareFile(name, bytes);
      });

  // ------------------------------------------------------------------ ekran
  @override
  Widget build(BuildContext context) {
    final r = _result;
    final ok = r != null && r.daysOk > 0;
    final ms = _machines;
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
      children: [
        th.SectionCard(
          title: 'Yıllık etki',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              LabeledDropdown<String>(
                label: 'Kapsam',
                value: _asset,
                items: [annual.all, for (final m in ms) m.id],
                itemLabel: (id) => id == annual.all ? 'Tesis geneli (tümü)' : data.machine(id).name,
                onChanged: (id) => setState(() {
                  _asset = id;
                  _facilityChosen = id == annual.all;
                  _fillYear();
                  _recompute();
                }),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: LabeledDropdown<int>(
                      label: 'Yıl',
                      value: _year ?? 0,
                      items: _years,
                      itemLabel: (y) => '$y',
                      onChanged: _years.isEmpty
                          ? null
                          : (y) => setState(() {
                                _year = y;
                                _recompute();
                              }),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: LabeledDropdown<int>(
                      label: 'Uzunluk',
                      value: _L,
                      items: List.generate(12, (k) => k + 1),
                      itemLabel: (l) => '$l saat',
                      onChanged: (v) => setState(() {
                        _L = v;
                        _recompute();
                      }),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: HourDropdown(
                      label: 'Standart',
                      value: _s,
                      onChanged: (v) => setState(() {
                        _s = v;
                        _recompute();
                      }),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: HourDropdown(
                      label: 'Hedef',
                      value: _t,
                      onChanged: (v) => setState(() {
                        _t = v;
                        _recompute();
                      }),
                    ),
                  ),
                ],
              ),
              Row(
                children: [
                  const th.Muted('Oran'),
                  Expanded(
                    child: Slider(
                      value: (_p * 100).roundToDouble(),
                      min: 0,
                      max: 100,
                      divisions: 100,
                      label: '%${(_p * 100).round()}',
                      onChanged: (v) {
                        setState(() => _p = v.round() / 100);
                        _schedule();
                      },
                    ),
                  ),
                  SizedBox(width: 44, child: Text('%${(_p * 100).round()}', textAlign: TextAlign.right)),
                ],
              ),
              th.Muted(_note(), size: 12),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                alignment: WrapAlignment.end,
                children: [
                  Tooltip(
                    message: 'Yıllık sonucu, aylık dökümü, Delti yorumunu ve yöntemi tek raporda paylaşır',
                    child: OutlinedButton.icon(
                      onPressed: ok && !_busy ? _pdf : null,
                      icon: const Icon(Icons.picture_as_pdf_outlined, size: 18),
                      label: const Text('PDF rapor'),
                    ),
                  ),
                  Tooltip(
                    message: 'Özet ve aylık dökümü CSV olarak paylaşır',
                    child: OutlinedButton.icon(
                      onPressed: ok && !_busy ? _csv : null,
                      icon: const Icon(Icons.ios_share, size: 18),
                      label: const Text('CSV'),
                    ),
                  ),
                ],
              ),
              if (_busy) const Padding(padding: EdgeInsets.only(top: 6), child: LinearProgressIndicator()),
            ],
          ),
        ),
        const SizedBox(height: 10),
        StatGrid(_stats(r)),
        const SizedBox(height: 10),
        th.SectionCard(child: _summary(r)),
        if (ok) ...[
          const SizedBox(height: 10),
          th.SectionCard(title: 'Aylara göre', child: _monthTable(r)),
          const SizedBox(height: 10),
          th.SectionCard(
            title: 'Aylık emisyon değişimi',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                MonthChart(months: r.months, unit: unitFor(_kind)),
                const SizedBox(height: 4),
                const th.Muted(
                    'Yeşil çubuk o ay emisyonun düştüğünü, kırmızı arttığını gösterir. Verisi olmayan aylar boş kalır.',
                    size: 12),
              ],
            ),
          ),
        ],
      ],
    );
  }

  String _note() {
    final notes = <String>[
      _restricted.isNotEmpty
          ? 'Kısıtlı saatler (Senaryo sekmesinden): ${(_restricted.toList()..sort()).map(fmt.hour).join(', ')}'
          : 'Kısıtlı saat yok; Senaryo sekmesinden işaretlenebilir.',
      if (_param != null) 'Parametrik mod: her makinede her saat sabit ${fmt.num(_param!, 1)} kWh yük varsayılır.',
      if (_kind != 'tCO2') 'Emisyon tipi: tCO2-eşd.',
    ];
    return notes.join(' · ');
  }

  List<Stat> _stats(annual.AnnualResult? r) {
    final daysTitle = (r?.isFacility ?? false) ? 'Hesaba giren makine-gün' : 'Hesaba giren gün';
    if (r == null || r.daysOk == 0) {
      return [
        const Stat('Yıllık emisyon değişimi', '—'),
        const Stat('Kaydırılan yükte değişim', '—'),
        const Stat('Yenilenebilir payı (kaydırılan enerji)', '—'),
        Stat(daysTitle, r == null ? '—' : '0 / ${r.daysTotal}'),
      ];
    }
    final color = r.deltaKg <= 0 ? th.good : th.bad;
    final up = (r.renTargetPct ?? 0) >= (r.renSourcePct ?? 0);
    return [
      Stat('Yıllık emisyon değişimi', mass(r.deltaKg, _kind), color),
      Stat('Kaydırılan yükte değişim', fmt.pct(r.deltaPct), color),
      Stat('Yenilenebilir payı (kaydırılan enerji)', '${ren(r.renSourcePct)} → ${ren(r.renTargetPct)}',
          up ? th.good : th.bad),
      Stat(daysTitle, '${r.daysOk} / ${r.daysTotal}'),
    ];
  }

  Widget _summary(annual.AnnualResult? r) {
    if (r == null || r.daysOk == 0) return Text(_message);
    final kind = _kind;
    final good = r.deltaKg <= 0;
    final color = good ? th.good : th.bad;
    final verb = good ? 'azalırdı' : 'artardı';
    final unit = r.isFacility ? 'makine-gün' : 'gün';
    final loc = '${unit}de'; // gün → günde, makine-gün → makine-günde
    final skipped = r.daysTotal - r.daysOk;
    final skipTxt =
        skipped > 0 ? ' $skipped $unit standart pencerede yük olmadığı ya da kısıt nedeniyle hesaba girmedi.' : '';
    var tail = '';
    if (r.isFacility) {
      final parts = [for (final x in r.parts) if (x.daysOk > 0) x]..sort((a, b) => a.deltaKg.compareTo(b.deltaKg));
      tail = ' Katkılar: ${parts.map((x) => '${data.machine(x.assetId).name} ${mass(x.deltaKg, kind)}').join(', ')}.';
    } else if (r.bestDay != null && r.worstDay != null) {
      tail = ' En iyi gün ${fmt.date(r.bestDay!.$1)} (${fmt.pct(r.bestDay!.$2)}), '
          'en zayıf gün ${fmt.date(r.worstDay!.$1)} (${fmt.pct(r.worstDay!.$2)}).';
    }
    final b = _best.isEmpty ? null : _best.first;
    final aiState = switch (_aiSource) {
      'ai' => 'ready',
      'pending' => 'think',
      'fallback_offline' => 'sleep',
      _ => 'ready',
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text.rich(TextSpan(style: const TextStyle(height: 1.4), children: [
          TextSpan(text: '${_what(r)}\n', style: const TextStyle(fontWeight: FontWeight.w700)),
          TextSpan(
              text: 'Bu kaydırma ${r.year} yılında verisi olan ${r.daysOk} $loc uygulansaydı, kaydırılan yükün emisyonu '
                  '${mass(r.baselineKg, kind)} yerine ${mass(r.scenarioKg, kind)} olur; toplam emisyon '),
          TextSpan(
              text: '${mass(r.deltaKg.abs(), kind)} $verb',
              style: TextStyle(fontWeight: FontWeight.w700, color: color)),
          TextSpan(
              text: '. Kaydırılan enerjinin yenilenebilir kaynaklı payı ${ren(r.renSourcePct)} yerine '
                  '${ren(r.renTargetPct)} olur. ${r.betterDays} $loc emisyon düştü, ${r.worseDays} $loc arttı.$skipTxt'),
          TextSpan(text: tail),
        ])),
        if (r.fossilDeltaPct != null) ...[
          const SizedBox(height: 6),
          Text.rich(TextSpan(style: const TextStyle(color: th.muted, fontSize: 13, height: 1.35), children: [
            const TextSpan(
                text: 'Duyarlılık: kaydırılan yükü yalnızca fosil santrallerin karşıladığı varsayımıyla değişim '),
            TextSpan(text: fmt.pct(r.fossilDeltaPct), style: const TextStyle(fontWeight: FontWeight.w700)),
            TextSpan(
                text: ' (${mass(r.fossilDeltaKg, kind)}); gerçek etki büyük olasılıkla bu iki değer arasındadır.'),
          ])),
        ],
        if (b != null) ...[
          const Divider(height: 20, color: th.border),
          Text.rich(richText(b.t == r.t
              ? '✓ Seçtiğiniz hedef **${fmt.window(b.t, b.L)}**, yıl boyunca sabit tutulabilecek en temiz hedef pencere.'
              : 'Yıl boyunca sabit tutulacak en temiz hedef: **${fmt.window(b.t, b.L)}** → '
                  '${mass(b.deltaKg, kind)} (${fmt.pct(b.deltaPct)}).')),
          const SizedBox(height: 6),
          Wrap(
            alignment: WrapAlignment.end,
            spacing: 8,
            runSpacing: 6,
            children: [
              Tooltip(
                message: 'Yıl boyunca en düşük emisyonu veren hedef saati bu ekranda seçer',
                child: OutlinedButton(
                  onPressed: b.t != r.t
                      ? () => setState(() {
                            _t = b.t;
                            _recompute();
                          })
                      : null,
                  child: const Text('Bu hedefi dene'),
                ),
              ),
              Tooltip(
                message: 'Bu ekrandaki saatleri Senaryo sekmesine aktarır',
                child: FilledButton(onPressed: _apply, child: const Text('Senaryoya uygula')),
              ),
            ],
          ),
        ],
        const Divider(height: 20, color: th.border),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Delti(state: aiState, size: 30),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (_aiSource.isNotEmpty) ...[SourceChip(_aiSource), const SizedBox(height: 4)],
                  Text(
                    _aiText.isEmpty ? 'Delti bu yıllık sonucu sizin için yorumlayabilir.' : _aiText,
                    style: TextStyle(color: _aiSource == 'ai' ? th.text : th.muted, height: 1.4),
                  ),
                ],
              ),
            ),
          ],
        ),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton(
            onPressed: _aiSource == 'pending' ? null : _askDelti,
            child: const Text('Delti yorumlasın'),
          ),
        ),
      ],
    );
  }

  /// Aylık döküm: telefon genişliğine sığar (yana kaydırma yok); uzun sayılar hücrede küçülür.
  Widget _monthTable(annual.AnnualResult r) {
    final months = [for (final m in r.months) if (m.days > 0) m];
    Color? col(annual.MonthTotal m) => m.deltaKg == 0 ? null : (m.deltaKg < 0 ? th.good : th.bad);
    const head = TextStyle(color: th.muted, fontWeight: FontWeight.w600, fontSize: 11.5, height: 1.2);
    Widget cell(String t, {TextAlign align = TextAlign.right, TextStyle? style, bool header = false}) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 6),
          child: header
              ? Text(t, textAlign: align, style: head)
              : FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: align == TextAlign.left ? Alignment.centerLeft : Alignment.centerRight,
                  child: Text(t, maxLines: 1, style: (style ?? const TextStyle()).copyWith(fontSize: 13)),
                ),
        );
    return Table(
      columnWidths: const {
        0: FlexColumnWidth(1.25),
        1: FlexColumnWidth(0.6),
        2: FlexColumnWidth(1.15),
        3: FlexColumnWidth(1.15),
        4: FlexColumnWidth(1.1),
        5: FlexColumnWidth(1.25),
      },
      defaultVerticalAlignment: TableCellVerticalAlignment.middle,
      border: const TableBorder(horizontalInside: BorderSide(color: th.border)),
      children: [
        TableRow(children: [
          cell('Ay', align: TextAlign.left, header: true),
          cell('Gün', header: true),
          cell('Standart (kg)', header: true),
          cell('Seçilen (kg)', header: true),
          cell('Değişim (kg)', header: true),
          cell('Değişim', header: true),
        ]),
        for (final m in months)
          TableRow(children: [
            cell(ctx.monthNames[m.month - 1], align: TextAlign.left),
            cell('${m.days}'),
            cell(fmt.num(m.baselineKg, 1)),
            cell(fmt.num(m.scenarioKg, 1)),
            cell(fmt.num(m.deltaKg, 1), style: TextStyle(color: col(m))),
            cell(fmt.pct(m.deltaPct), style: TextStyle(color: col(m))),
          ]),
      ],
    );
  }
}
