// Senaryo sekmesi (MainWindow._build_scenario_tab).

import 'package:flutter/material.dart';

import '../engine/data.dart';
import '../engine/packages.dart' show parseNum;
import '../state/app_state.dart';
import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;
import '../widgets/inputs.dart';
import '../widgets/result_card.dart';
import '../widgets/scenario_chart.dart';

class ScenarioScreen extends StatefulWidget {
  const ScenarioScreen({super.key, required this.app, this.deltiBox, this.header, this.onBestApplied});

  final AppState app;

  /// Üst bant: Delti'ye yazın kutusu.
  final Widget? header;

  /// "En iyi saati bul" sonrası (Delti açıklaması ister).
  final VoidCallback? onBestApplied;

  /// Delti açıklama kartı (AI katmanı bağlanınca).
  final Widget? deltiBox;

  @override
  State<ScenarioScreen> createState() => _ScenarioScreenState();
}

class _ScenarioScreenState extends State<ScenarioScreen> {
  late final TextEditingController _paramCtrl;

  @override
  void initState() {
    super.initState();
    _paramCtrl = TextEditingController(text: fmt.num(widget.app.inputs.paramKwh));
  }

  @override
  void dispose() {
    _paramCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickDate(BuildContext context) async {
    final app = widget.app;
    final m = app.selectedMachine;
    final valid = m.days.toSet();
    DateTime parse(String iso) => DateTime.parse(iso);
    String iso(DateTime d) =>
        '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
    final picked = await showDatePicker(
      context: context,
      initialDate: parse(app.inputs.date),
      firstDate: parse(m.firstDay),
      lastDate: parse(m.lastDay),
      selectableDayPredicate: (d) => valid.contains(iso(d)),
      helpText: 'Gün seç (yalnızca verisi olan günler)',
    );
    if (picked != null) app.update((i) => i.copyWith(date: iso(picked)));
  }

  @override
  Widget build(BuildContext context) {
    final app = widget.app;
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        final i = app.inputs;
        final c = app.current;
        final m = c.machine;
        final shiftable = m.shiftable;
        final machines = app.data.machines();
        return ListView(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
          children: [
            if (widget.header != null) ...[widget.header!, const SizedBox(height: 10)],
            th.SectionCard(
              title: 'Makine ve gün',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  LabeledDropdown<String>(
                    label: 'Makine',
                    value: i.assetId,
                    items: [for (final x in machines) x.id],
                    itemLabel: (id) => machineLabel(machines.firstWhere((x) => x.id == id)),
                    onChanged: (id) => app.update((x) => x.copyWith(assetId: id)),
                  ),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    onPressed: () => _pickDate(context),
                    icon: const Icon(Icons.calendar_today, size: 18),
                    label: Text('Gün: ${fmt.date(i.date)}'),
                  ),
                  if (!shiftable) ...[
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
                      decoration: BoxDecoration(
                        color: th.badSoft,
                        border: Border.all(color: const Color(0xFFF3C3C3)),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Text(nonShiftableText,
                          style: TextStyle(color: th.bad, fontWeight: FontWeight.w600)),
                    ),
                  ],
                  const SizedBox(height: 8),
                  const Text('Emisyon tipi', style: TextStyle(color: th.muted, fontSize: 12.5)),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Expanded(
                        child: SegmentedButton<String>(
                          segments: const [
                            ButtonSegment(value: 'tCO2', label: Text('tCO2')),
                            ButtonSegment(value: 'tCO2esd', label: Text('tCO2-eşd')),
                          ],
                          selected: {i.ciKind},
                          showSelectedIcon: false,
                          onSelectionChanged: (v) => app.update((x) => x.copyWith(ciKind: v.first)),
                        ),
                      ),
                    ],
                  ),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    title: const Text('Parametrik mod (sabit yük)'),
                    subtitle: const Text('Ölçülen yük yerine her saat için aynı kWh değerini kullanır.'),
                    value: i.parametric,
                    onChanged: shiftable ? (v) => app.update((x) => x.copyWith(parametric: v ?? false)) : null,
                  ),
                  if (i.parametric)
                    Padding(
                      padding: const EdgeInsets.only(left: 22),
                      child: TextField(
                        controller: _paramCtrl,
                        enabled: shiftable,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(
                          labelText: 'Sabit yük',
                          suffixText: 'kWh/saat',
                          isDense: true,
                          border: OutlineInputBorder(),
                        ),
                        onChanged: (v) {
                          final n = parseNum(v);
                          if (!n.isNaN && n >= 0 && n <= 100000) {
                            app.update((x) => x.copyWith(paramKwh: double.parse(n.toStringAsFixed(2))));
                          }
                        },
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            th.SectionCard(
              title: 'Zaman penceresi',
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  HourDropdown(
                    label: 'Standart başlangıç',
                    value: i.s,
                    onChanged: shiftable ? (v) => app.update((x) => x.copyWith(s: v)) : null,
                  ),
                  const SizedBox(height: 10),
                  LabeledDropdown<int>(
                    label: 'Pencere uzunluğu',
                    value: i.L,
                    items: List.generate(12, (k) => k + 1),
                    itemLabel: (l) => '$l saat',
                    onChanged: shiftable ? (v) => app.update((x) => x.copyWith(L: v)) : null,
                  ),
                  const SizedBox(height: 10),
                  HourDropdown(
                    label: 'Hedef başlangıç',
                    value: i.t,
                    onChanged: shiftable ? (v) => app.update((x) => x.copyWith(t: v)) : null,
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      const Text('Kaydırma oranı'),
                      Expanded(
                        child: Slider(
                          value: (i.p * 100).roundToDouble(),
                          min: 0,
                          max: 100,
                          divisions: 100,
                          label: '%${(i.p * 100).round()}',
                          onChanged: shiftable ? (v) => app.update((x) => x.copyWith(p: v.round() / 100)) : null,
                        ),
                      ),
                      SizedBox(
                        width: 44,
                        child: Text('%${(i.p * 100).round()}', textAlign: TextAlign.right),
                      ),
                    ],
                  ),
                  Tooltip(
                    message: 'Aynı yük için en düşük emisyonlu hedef pencereyi seçer (kısıtlı saatler atlanır).',
                    child: FilledButton.icon(
                    onPressed: shiftable
                        ? () {
                            if (app.applyBestWindow()) {
                              widget.onBestApplied?.call();
                            } else {
                              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                                  content: Text('Bu girdilerle geçerli bir hedef pencere bulunamadı '
                                      '(yük yok, aralık dışı veya tüm saatler kısıtlı).')));
                            }
                          }
                        : null,
                    icon: const Icon(Icons.search),
                    label: const Text('En iyi saati bul'),
                  ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            th.SectionCard(
              titleWidget: const Text.rich(TextSpan(children: [
                TextSpan(
                    text: 'Kısıtlı saatler ',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: th.text)),
                TextSpan(text: '· hedef olamaz', style: TextStyle(fontSize: 13, color: th.muted)),
              ])),
              child: Tooltip(
                message: 'İşaretli saatler hedef pencereye giremez.',
                child: HourChips(
                selected: i.restricted.toSet(),
                onToggle: shiftable
                    ? (h) => app.update((x) {
                          final s = x.restricted.toSet();
                          if (!s.remove(h)) s.add(h);
                          return x.copyWith(restricted: s.toList()..sort());
                        })
                    : null,
              ),
              ),
            ),
            const SizedBox(height: 10),
            th.SectionCard(
              child: ScenarioChart(
                ci: c.ci,
                load: c.load,
                s: i.s,
                L: i.L,
                t: i.t,
                restricted: i.restricted.toSet(),
                status: c.result.status,
                deltaPct: c.result.deltaPct,
                ciLabel: ciLabels[i.ciKind]!,
              ),
            ),
            const SizedBox(height: 10),
            ResultCard(
              c: c,
              savedLabel: app.savedLabel,
              onSave: () => app.saveCurrent(),
            ),
            if (widget.deltiBox != null) ...[
              const SizedBox(height: 10),
              widget.deltiBox!,
            ],
          ],
        );
      },
    );
  }
}

/// Makine kimliğinden okunur ad (yardımcı).
String machineName(DataStore data, String id) => data.hasMachine(id) ? data.machine(id).name : id;
