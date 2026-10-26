// Tesis Planı sekmesi: seçilen günde her kaydırılabilir makine için en temiz hedef pencere, tesis yük profili ve
// isteğe bağlı saatlik tepe yük sınırı (desktop/plan_tab.py). Masaüstündeki tablo yerine makine başına kart.

// ignore_for_file: non_constant_identifier_names

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../engine/data.dart';
import '../engine/packages.dart' show parseNum;
import '../engine/plan.dart' as pl;
import '../report/plan_export.dart';
import '../state/app_state.dart';
import '../ui/csv.dart';
import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;
import '../widgets/inputs.dart';
import '../widgets/plan_chart.dart';
import '../widgets/rich.dart';
import '../widgets/stat_grid.dart';

const Map<String, Color> statusColor = {
  pl.planned: th.good,
  pl.keep: th.muted,
  pl.planNonShiftable: th.muted,
  pl.noData: th.muted,
  pl.excluded: th.muted,
  pl.planNoLoad: th.warn,
};

class _RowSetting {
  _RowSetting(this.include, this.s, this.L);
  bool include;
  int s;
  int L;
}

class PlanScreen extends StatefulWidget {
  const PlanScreen({super.key, required this.app, required this.onApplied});

  final AppState app;

  /// Bir makine Senaryo'da açıldıktan sonra Senaryo sekmesine geçilir.
  final VoidCallback onApplied;

  @override
  State<PlanScreen> createState() => _PlanScreenState();
}

class _PlanScreenState extends State<PlanScreen> {
  late String _date;
  late int _s, _L;
  late double _p;
  late Set<int> _restricted;
  late String _kind;
  bool _auto = true;
  double? _limit;
  final _limitCtrl = TextEditingController();
  final Map<String, _RowSetting> _rows = {};
  Timer? _timer;
  pl.FacilityPlan? _plan;
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
    _limitCtrl.dispose();
    super.dispose();
  }

  /// Senaryo sekmesindeki gün, saatler, oran ve kısıtlarla başlar.
  void _loadInputs() {
    final i = app.inputs;
    final days = data.allDates();
    _date = days.contains(i.date) ? i.date : days.last;
    _s = i.s;
    _L = i.L;
    _p = i.p;
    _restricted = i.restricted.toSet();
    _kind = i.ciKind;
    _rows.clear();
    for (final m in data.machines()) {
      _rows[m.id] = _RowSetting(m.shiftable, _s, _L);
    }
  }

  /// Üstteki standart saat/uzunluk değişince bütün satırlar ona eşitlenir.
  void _syncRows() {
    for (final r in _rows.values) {
      r.s = _s;
      r.L = _L;
    }
  }

  void _schedule() {
    _timer?.cancel();
    _timer = Timer(const Duration(milliseconds: 80), () {
      if (mounted) setState(_recompute);
    });
  }

  Map<String, pl.MachineSetting> _settings() => {
        for (final m in data.machines())
          if (m.shiftable)
            m.id: pl.MachineSetting(_auto ? null : _rows[m.id]!.s, _rows[m.id]!.L, _p, _rows[m.id]!.include),
      };

  void _recompute() {
    if (!data.allDates().contains(_date)) return;
    final p = pl.facilityPlan(data, _date, _settings(), restricted: _restricted, kind: _kind, peakLimit: _limit);
    _plan = p;
    if (_auto) {
      // Otomatik modda her makinenin bulunan standart saati satırına yazılır (Elle'ye geçince başlangıç olur).
      for (final r in p.rows) {
        if (r.status == pl.planned || r.status == pl.keep) _rows[r.assetId]?.s = r.s;
      }
    }
    final src = planSource(data, p);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) app.tabFooter.value = src;
    });
  }

  Future<void> _pickDate() async {
    final days = data.allDates();
    final valid = days.toSet();
    String iso(DateTime d) =>
        '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
    final picked = await showDatePicker(
      context: context,
      initialDate: DateTime.parse(_date),
      firstDate: DateTime.parse(days.first),
      lastDate: DateTime.parse(days.last),
      selectableDayPredicate: (d) => valid.contains(iso(d)),
      helpText: 'Gün seç (yalnızca verisi olan günler)',
    );
    if (picked != null) {
      setState(() {
        _date = iso(picked);
        _recompute();
      });
    }
  }

  void _openRow(pl.PlanRow r) {
    final p = _plan;
    if (p == null || r.result == null || r.t == null) return;
    final cur = app.inputs;
    app.setInputs(ScenarioInputs(
      assetId: r.assetId, date: p.date, s: r.s, L: r.L, t: r.t!, p: r.p,
      restricted: cur.restricted, ciKind: cur.ciKind,
    ));
    widget.onApplied();
  }

  Future<void> _csv() async {
    final p = _plan;
    if (p == null) return;
    setState(() => _busy = true);
    try {
      await shareFile('CarbonDelta_tesis_plani_${p.date}.csv', utf8.encode(planCsv(data, p, _restricted)));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Dosya oluşturulamadı:\n$e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  // ------------------------------------------------------------------ ekran
  @override
  Widget build(BuildContext context) {
    final p = _plan;
    final unit = _kind == 'tCO2' ? 'kg CO2' : 'kg CO2-eşd';
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
      children: [
        th.SectionCard(
          title: 'Tesis günlük planı',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              OutlinedButton.icon(
                onPressed: _pickDate,
                icon: const Icon(Icons.calendar_today, size: 18),
                label: Text('Gün: ${fmt.date(_date)}'),
              ),
              const SizedBox(height: 10),
              const Text('Standart pencere', style: TextStyle(color: th.muted, fontSize: 12.5)),
              const SizedBox(height: 4),
              Tooltip(
                message: 'Otomatik: her makine için o gün en çok emisyon ürettiği pencere standart kabul edilir. '
                    'Elle: aşağıdaki saat (makine başına değiştirilebilir) kullanılır.',
                child: SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(value: true, label: Text('Otomatik')),
                    ButtonSegment(value: false, label: Text('Elle')),
                  ],
                  selected: {_auto},
                  showSelectedIcon: false,
                  onSelectionChanged: (v) => setState(() {
                    _auto = v.first;
                    if (!_auto) _syncRows();
                    _recompute();
                  }),
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: HourDropdown(
                      label: 'Standart',
                      value: _s,
                      onChanged: _auto
                          ? null
                          : (v) => setState(() {
                                _s = v;
                                _syncRows();
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
                        _syncRows();
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
              Tooltip(
                message: 'Tesisin herhangi bir saatteki toplam yükü bu değeri aşmasın (boş ya da 0 = sınır yok). '
                    'Sınır aşılıyorsa planlayıcı makineyi sınırı aşmayan en temiz pencereye alır.',
                child: TextField(
                  controller: _limitCtrl,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    labelText: 'Tepe sınırı',
                    hintText: 'sınır yok',
                    suffixText: 'kWh',
                    isDense: true,
                    border: OutlineInputBorder(),
                  ),
                  onChanged: (v) {
                    final n = parseNum(v);
                    _limit = (n.isNaN || n <= 0) ? null : n.roundToDouble();
                    _schedule();
                  },
                ),
              ),
              const SizedBox(height: 8),
              th.Muted(
                [
                  _restricted.isNotEmpty
                      ? 'Kısıtlı saatler (Senaryo sekmesinden): ${(_restricted.toList()..sort()).map(fmt.hour).join(', ')}'
                      : 'Kısıtlı saat yok; Senaryo sekmesinden işaretlenebilir.',
                  if (_kind != 'tCO2') 'Emisyon tipi: tCO2-eşd.',
                ].join(' · '),
                size: 12,
              ),
              Align(
                alignment: Alignment.centerRight,
                child: Tooltip(
                  message: 'Planı CSV olarak paylaşır',
                  child: OutlinedButton.icon(
                    onPressed: p == null || _busy ? null : _csv,
                    icon: const Icon(Icons.ios_share, size: 18),
                    label: const Text('CSV'),
                  ),
                ),
              ),
            ],
          ),
        ),
        if (p != null) ...[
          const SizedBox(height: 10),
          StatGrid(_stats(p, unit)),
          const SizedBox(height: 10),
          th.SectionCard(child: Text.rich(richText(_summary(p, unit), base: const TextStyle(height: 1.4)))),
          const SizedBox(height: 10),
          th.SectionCard(
            title: 'Makine bazlı plan',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                th.Muted(
                    _auto
                        ? 'Otomatik modda standart pencere her makine için ayrı bulunur. Elle moduna geçince makine '
                            'başına standart saat ve uzunluk değiştirilebilir.'
                        : 'Makine başına standart saat ve uzunluk değiştirilebilir.',
                    size: 12),
                const SizedBox(height: 8),
                for (final r in p.rows) ...[_machineCard(r), const SizedBox(height: 8)],
              ],
            ),
          ),
          const SizedBox(height: 10),
          th.SectionCard(
            title: 'Tesis saatlik yükü',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                PlanChart(facility: p, ciLabel: _kind == 'tCO2' ? 'tCO2' : 'tCO2-eşd'),
                const SizedBox(height: 4),
                const th.Muted(
                    'Gri: plan öncesi, yeşil: plan sonrası tesis yükü. Mavi çizgi şebekenin saatlik karbon yoğunluğudur. '
                    'Yüklerin aynı saate toplanması tepe yükü artırabilir.',
                    size: 12),
              ],
            ),
          ),
        ],
      ],
    );
  }

  List<Stat> _stats(pl.FacilityPlan p, String unit) {
    final any = p.plannedCount > 0;
    final color = p.deltaKg <= 0 ? th.good : th.bad;
    final rise = p.peakAfter > p.peakBefore + 1e-9;
    return [
      Stat('Tesis emisyon değişimi', any ? '${fmt.num(p.deltaKg, 1)} $unit' : '—', any ? color : null),
      Stat('Kaydırılan yükte değişim', any ? fmt.pct(p.deltaPct) : '—', any ? color : null),
      Stat('Tesisin günlük emisyonunda', any ? fmt.pct(p.dailyDeltaPct) : '—'),
      Stat('Tepe yük (önce → sonra)', '${fmt.num(p.peakBefore, 1)} → ${fmt.num(p.peakAfter, 1)} kWh',
          rise ? th.warn : null),
    ];
  }

  String _summary(pl.FacilityPlan p, String unit) {
    if (p.plannedCount > 0) {
      var text = '**${fmt.date(p.date)}** için ${p.plannedCount} makine daha temiz saatlere alınabilir: kaydırılan '
          '${fmt.num(p.shiftedKwh, 1)} kWh enerjinin emisyonu ${fmt.num(p.baselineKg, 1)} yerine '
          '${fmt.num(p.scenarioKg, 1)} $unit olur (${fmt.pct(p.deltaPct)}).';
      if (p.fossilDeltaPct != null) text += ' Fosil marjinal varsayımla: ${fmt.pct(p.fossilDeltaPct)}.';
      if (p.peakAfter > p.peakBefore + 1e-9) {
        text += ' **Dikkat:** yükler aynı saatlere toplandığı için tesis tepe yükü ${fmt.num(p.peakBefore, 1)}\'den '
            '${fmt.num(p.peakAfter, 1)} kWh\'e çıkıyor; sözleşme gücü veya trafo sınırı varsa _Tepe sınırı_ girin.';
      }
      return text;
    }
    final reasons = pl.reasonCounts(p);
    final why = reasons.isEmpty
        ? 'plana dahil makine yok'
        : reasons.entries.map((e) => '${e.value} makinede: ${e.key.toLowerCase()}').join('; ');
    final hint = !_auto
        ? "Standart pencereyi makinelerin çalıştığı saatlere çekin ya da _Otomatik_'i seçin."
        : 'Bu gün için daha temiz bir saat bulunmuyor.';
    return '**${fmt.date(p.date)}** için plan değişiklik önermedi, iki çubuk bu yüzden aynı ($why). $hint';
  }

  Widget _machineCard(pl.PlanRow r) {
    final m = data.machine(r.assetId);
    final st = _rows[r.assetId]!;
    final res = r.result;
    final active = r.status == pl.planned || r.status == pl.keep;
    var target = r.t != null && active ? fmt.window(r.t!, r.L) : '—';
    if (r.status == pl.keep && r.t == r.s) target += ' (standart)';
    final color = statusColor[r.status] ?? th.text;
    final rows = <(String, String, Color?)>[
      ('Önerilen pencere', target, color),
      ('Kaydırılan', res != null ? '${fmt.num(res.shiftedKwh, 1)} kWh' : '—', null),
      ('Değişim', res != null ? '${fmt.num(r.deltaKg, 2)} kg' : '—', color),
      ('Değişim (%)', res != null ? (r.status == pl.planned ? fmt.pct(res.deltaPct) : '%0,00') : '—', color),
      (
        'Yenilenebilir payı',
        r.renewable != null ? '%${fmt.num(r.renewable!.$1, 1)} → %${fmt.num(r.renewable!.$2, 1)}' : '—',
        null
      ),
    ];
    return Container(
      padding: const EdgeInsets.fromLTRB(4, 4, 10, 8),
      decoration: BoxDecoration(
        border: Border.all(color: r.status == pl.planned ? const Color(0xFFB7DCC9) : th.border),
        borderRadius: BorderRadius.circular(8),
        color: r.status == pl.planned ? const Color(0xFFF6FBF8) : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Tooltip(
                message: 'Dahil: makine plana alınsın mı',
                child: Checkbox(
                  value: m.shiftable && st.include,
                  onChanged: m.shiftable
                      ? (v) => setState(() {
                            st.include = v ?? false;
                            _recompute();
                          })
                      : null,
                ),
              ),
              Expanded(child: Text(m.name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15))),
              if (res != null && r.t != null)
                TextButton(onPressed: () => _openRow(r), child: const Text('Senaryoda aç')),
            ],
          ),
          if (m.shiftable && st.include && r.status != pl.noData)
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 0, 0, 8),
              child: Row(
                children: [
                  Expanded(
                    child: HourDropdown(
                      label: _auto ? 'Standart (otomatik)' : 'Standart',
                      value: st.s,
                      onChanged: _auto
                          ? null
                          : (v) => setState(() {
                                st.s = v;
                                _recompute();
                              }),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: LabeledDropdown<int>(
                      label: 'Uzunluk',
                      value: st.L,
                      items: List.generate(12, (k) => k + 1),
                      itemLabel: (l) => '$l saat',
                      onChanged: (v) => setState(() {
                        st.L = v;
                        _recompute();
                      }),
                    ),
                  ),
                ],
              ),
            ),
          if (active || res != null)
            for (final (k, v, c) in rows)
              Padding(
                padding: const EdgeInsets.fromLTRB(10, 1, 0, 1),
                child: Row(
                  children: [
                    Expanded(flex: 5, child: th.Muted(k, size: 12.5)),
                    const SizedBox(width: 8),
                    Flexible(
                      flex: 5,
                      child: Text(v,
                          textAlign: TextAlign.right,
                          style: TextStyle(
                              fontSize: 13,
                              color: c,
                              fontWeight: k == 'Önerilen pencere' && r.status == pl.planned
                                  ? FontWeight.w700
                                  : FontWeight.w500)),
                    ),
                  ],
                ),
              ),
          if (r.note.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 4, 0, 0),
              child: Text(r.note,
                  style: TextStyle(fontSize: 12.5, color: r.status == pl.planNoLoad ? th.warn : th.muted)),
            ),
        ],
      ),
    );
  }
}
