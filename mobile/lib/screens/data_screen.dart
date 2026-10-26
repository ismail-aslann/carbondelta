// Veri yönetimi sekmesi: makine, yıl (EPİAŞ) ve emisyon katsayısı paketleri
// (desktop/data_tab.py).

import 'dart:io';
import 'dart:math' as math;

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../engine/data.dart';
import '../engine/packages.dart' as pk;
import '../state/app_state.dart';
import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;

const Map<String, String> kindLabel = {pk.kindMachine: 'Makine', pk.kindGrid: 'Şebeke', pk.kindFactors: 'Katsayı'};

/// Kontrol raporu satırları (✓ ! ✕).
class ReportView extends StatelessWidget {
  const ReportView({super.key, required this.rep});
  final pk.Report rep;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final (level, text) in rep.lines)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 18,
                  child: Text(
                    {'ok': '✓', 'warn': '!', 'err': '✕'}[level]!,
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: {'ok': th.good, 'warn': th.warn, 'err': th.bad}[level],
                    ),
                  ),
                ),
                Expanded(child: Text(text, style: const TextStyle(fontSize: 13.5))),
              ],
            ),
          ),
      ],
    );
  }
}

/// 24 saatlik ortalama yük önizlemesi.
class ProfileBars extends StatelessWidget {
  const ProfileBars({super.key, required this.values});
  final List<double> values;

  @override
  Widget build(BuildContext context) =>
      SizedBox(height: 90, child: CustomPaint(size: Size.infinite, painter: _BarsPainter(values)));
}

class _BarsPainter extends CustomPainter {
  _BarsPainter(this.values);
  final List<double> values;

  @override
  void paint(Canvas canvas, Size size) {
    if (values.isEmpty) return;
    final vals = [for (final v in values) v.isNaN ? 0.0 : v];
    final w = size.width, h = size.height - 16;
    final top = vals.reduce(math.max) == 0 ? 1.0 : vals.reduce(math.max);
    final bw = w / 24;
    final paint = Paint()..color = const Color(0xFFA9BFD3);
    for (var i = 0; i < vals.length; i++) {
      final bh = vals[i] / top * (h - 4);
      canvas.drawRRect(
          RRect.fromRectAndRadius(Rect.fromLTWH(i * bw + 1.5, h - bh, bw - 3, bh), const Radius.circular(2)), paint);
    }
    for (final i in const [0, 6, 12, 18, 23]) {
      final tp = TextPainter(
        text: TextSpan(text: i.toString().padLeft(2, '0'), style: const TextStyle(fontSize: 10, color: th.muted)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(i * bw + bw / 2 - tp.width / 2, h + 2));
    }
  }

  @override
  bool shouldRepaint(covariant _BarsPainter old) => old.values != values;
}

Future<String?> _pickFile() async {
  const group = XTypeGroup(
    label: 'Veri dosyaları (CSV, TXT, Excel)',
    extensions: ['csv', 'txt', 'xlsx', 'xls'],
    mimeTypes: [
      'text/csv',
      'text/comma-separated-values',
      'text/plain',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
      'application/octet-stream',
    ],
  );
  final f = await openFile(acceptedTypeGroups: [group]);
  return f?.path;
}

class _FileRow extends StatelessWidget {
  const _FileRow({required this.title, required this.path, required this.onPick});
  final String title;
  final String? path;
  final VoidCallback onPick;

  @override
  Widget build(BuildContext context) {
    final name = path == null ? 'Dosya seçilmedi' : path!.split(RegExp(r'[\\/]')).last;
    return Row(
      children: [
        Expanded(
          child: Text(name,
              overflow: TextOverflow.ellipsis, style: TextStyle(color: path == null ? th.muted : th.text)),
        ),
        const SizedBox(width: 8),
        OutlinedButton(onPressed: onPick, child: const Text('Dosya seç…')),
      ],
    );
  }
}

class _Steps extends StatelessWidget {
  const _Steps({required this.steps, required this.current});
  final List<String> steps;
  final int current;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 4,
      runSpacing: 4,
      children: [
        for (var i = 0; i < steps.length; i++)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: i < current ? th.primarySoft : (i == current ? th.primary : const Color(0xFFEEF1F4)),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              steps[i],
              style: TextStyle(
                fontSize: 12,
                color: i < current ? th.primaryDark : (i == current ? Colors.white : th.muted),
                fontWeight: i == current ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
          ),
      ],
    );
  }
}

// ---------------- makine sihirbazı ----------------

class MachineWizard extends StatefulWidget {
  const MachineWizard({super.key, required this.data, required this.onAdded});
  final DataStore data;
  final ValueChanged<String> onAdded;

  @override
  State<MachineWizard> createState() => _MachineWizardState();
}

class _MachineWizardState extends State<MachineWizard> {
  String? _path;
  pk.MachineCheck? _check;
  final _name = TextEditingController();
  final _type = TextEditingController();
  bool _shiftable = true;
  bool _real = true;
  int _step = 0;
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    _type.dispose();
    super.dispose();
  }

  bool get _ok => _check != null && !_check!.report.hasErrors && _name.text.trim().isNotEmpty;

  void _updateStep() {
    if (_check == null) _step = _name.text.trim().isNotEmpty ? 1 : 0;
  }

  Future<void> _runCheck() async {
    if (_path == null) return;
    setState(() => _busy = true);
    final c = await pk.checkMachineFile(_path!, widget.data.allDates().toSet());
    if (!mounted) return;
    setState(() {
      _check = c;
      _step = 2;
      _busy = false;
    });
  }

  Future<void> _saveTemplate() async {
    final dir = await getTemporaryDirectory();
    final f = File('${dir.path}${Platform.pathSeparator}makine_sablonu.csv');
    await pk.writeMachineTemplate(f.path);
    await SharePlus.instance.share(ShareParams(files: [XFile(f.path)], subject: 'makine_sablonu.csv'));
  }

  Future<void> _add() async {
    if (!_ok) return;
    final name = _name.text.trim();
    setState(() => _busy = true);
    await pk.addMachinePackage(_check!, name, _type.text.trim(), _shiftable, _real ? 'real' : 'sample');
    setState(() {
      _step = 3;
      _check = null;
      _path = null;
      _name.clear();
      _type.clear();
      _busy = false;
    });
    widget.onAdded(name);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _Steps(steps: const ['1 · Dosya', '2 · Bilgiler', '3 · Kontrol ve önizleme', '4 · Ekle'], current: _step),
        const SizedBox(height: 12),
        const Text('Makine bilgileri', style: TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        _FileRow(
          title: 'Makine yük dosyası seç',
          path: _path,
          onPick: () async {
            final p = await _pickFile();
            if (p != null) {
              setState(() => _path = p);
              await _runCheck();
            }
          },
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _name,
          onChanged: (_) => setState(_updateStep),
          decoration: const InputDecoration(
              labelText: 'Makine adı', hintText: 'Ör. Kompresör (Hat 2)', border: OutlineInputBorder(), isDense: true),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _type,
          decoration: const InputDecoration(
              labelText: 'Tür', hintText: 'Ör. Basınçlı hava', border: OutlineInputBorder(), isDense: true),
        ),
        const SizedBox(height: 8),
        const Text('Kaydırılabilir mi?'),
        RadioGroup<bool>(
          groupValue: _shiftable,
          onChanged: (v) => setState(() => _shiftable = v ?? true),
          child: const Column(children: [
            RadioListTile<bool>(value: true, title: Text('Evet'), dense: true, contentPadding: EdgeInsets.zero),
            RadioListTile<bool>(
                value: false, title: Text('Hayır (sürekli / kısıtlı süreç)'), dense: true, contentPadding: EdgeInsets.zero),
          ]),
        ),
        const Text('Veri türü'),
        RadioGroup<bool>(
          groupValue: _real,
          onChanged: (v) => setState(() => _real = v ?? true),
          child: const Column(children: [
            RadioListTile<bool>(value: false, title: Text('Örnek yük'), dense: true, contentPadding: EdgeInsets.zero),
            RadioListTile<bool>(
                value: true, title: Text('Tesis ölçümü (Balıkesir)'), dense: true, contentPadding: EdgeInsets.zero),
          ]),
        ),
        const th.Muted('Beklenen biçim (ayraç ; veya ,  — ondalık virgül olabilir):'),
        const SizedBox(height: 4),
        Container(
          padding: const EdgeInsets.fromLTRB(8, 6, 8, 6),
          decoration: BoxDecoration(
            color: const Color(0xFFF6F8FA),
            border: Border.all(color: th.border),
            borderRadius: BorderRadius.circular(6),
          ),
          child: const Text('Tarih;Saat;kWh\n2026-01-01;0;12,40\n2026-01-01;1;11,85\n…',
              style: TextStyle(fontFamily: 'monospace', fontSize: 12.5)),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: _saveTemplate,
            icon: const Icon(Icons.ios_share, size: 18),
            label: const Text('Şablon dosyayı kaydet…'),
          ),
        ),
        const Divider(),
        const Text('Otomatik kontrol', style: TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        if (_busy) const LinearProgressIndicator(),
        if (_check == null && !_busy) const th.Muted('Dosya seçince kontrol otomatik yapılır.'),
        if (_check != null) ReportView(rep: _check!.report),
        const SizedBox(height: 10),
        const Text('Önizleme · ortalama günlük profil', style: TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        ProfileBars(values: _check?.profile ?? const []),
        const SizedBox(height: 10),
        // Dar ekranda iki düğme yan yana sığmazsa alt satıra iner.
        Wrap(
          alignment: WrapAlignment.spaceBetween,
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton(onPressed: _path == null || _busy ? null : _runCheck, child: const Text('Yeniden kontrol et')),
            FilledButton(
              onPressed: _ok && !_busy ? _add : null,
              child: Text(_check != null && !_check!.report.hasErrors
                  ? '${fmt.num(_check!.days.length.toDouble(), 0)} günü ekle →'
                  : 'Ekle'),
            ),
          ],
        ),
      ],
    );
  }
}

// ---------------- yıl (şebeke) sihirbazı ----------------

class GridWizard extends StatefulWidget {
  const GridWizard({super.key, required this.data, required this.onAdded});
  final DataStore data;
  final ValueChanged<String> onAdded;

  @override
  State<GridWizard> createState() => _GridWizardState();
}

class _GridWizardState extends State<GridWizard> {
  String? _path;
  pk.GridCheck? _check;
  final _name = TextEditingController();
  int _step = 0;
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  bool get _ok => _check != null && !_check!.report.hasErrors && _name.text.trim().isNotEmpty;

  Future<void> _runCheck() async {
    if (_path == null) return;
    setState(() => _busy = true);
    final c = await pk.checkGridFile(_path!, widget.data.factors(), widget.data.allDates().toSet());
    if (!mounted) return;
    setState(() {
      _check = c;
      if (c.years.isNotEmpty && _name.text.trim().isEmpty) {
        _name.text = c.years.length > 1 ? 'EPİAŞ ${c.years.first}–${c.years.last}' : 'EPİAŞ ${c.years.first}';
      }
      _step = 1;
      _busy = false;
    });
  }

  Future<void> _add() async {
    if (!_ok) return;
    final name = _name.text.trim();
    setState(() => _busy = true);
    await pk.addGridPackage(_check!, name);
    setState(() {
      _step = 2;
      _check = null;
      _path = null;
      _name.clear();
      _busy = false;
    });
    widget.onAdded(name);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _Steps(steps: const ['1 · Dosya', '2 · Kontrol', '3 · Ekle'], current: _step),
        const SizedBox(height: 10),
        Text.rich(TextSpan(style: const TextStyle(color: th.muted), children: [
          const TextSpan(text: 'EPİAŞ Şeffaflık Platformu › Üretim › '),
          const TextSpan(text: 'Gerçek Zamanlı Üretim', style: TextStyle(fontWeight: FontWeight.w700)),
          TextSpan(
              text: ' sayfasından istediğiniz tarih aralığını Excel/CSV olarak dışa aktarın. Ondalık yazımları '
                  'düzeltilir, negatif gece güneş değerleri 0 yapılır ve karbon yoğunluğu varsayılan veriyle aynı '
                  'yöntemle (kaynak üretimi × ${widget.data.factorsLabel()} katsayıları) hesaplanır.'),
        ])),
        const SizedBox(height: 10),
        _FileRow(
          title: 'EPİAŞ üretim dosyası seç',
          path: _path,
          onPick: () async {
            final p = await _pickFile();
            if (p != null) {
              setState(() => _path = p);
              await _runCheck();
            }
          },
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _name,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(
              labelText: 'Paket adı', hintText: 'Ör. EPİAŞ 2026', border: OutlineInputBorder(), isDense: true),
        ),
        const Divider(),
        const Text('Otomatik kontrol', style: TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        if (_busy) const LinearProgressIndicator(),
        if (_check != null) ReportView(rep: _check!.report),
        const SizedBox(height: 10),
        Align(
          alignment: Alignment.centerRight,
          child: FilledButton(
            onPressed: _ok && !_busy ? _add : null,
            child: Text(_ok ? '${fmt.num(_check!.days.length.toDouble(), 0)} günü ekle →' : 'Ekle'),
          ),
        ),
      ],
    );
  }
}

// ---------------- katsayı sihirbazı ----------------

class FactorsWizard extends StatefulWidget {
  const FactorsWizard({super.key, required this.data, required this.onAdded});
  final DataStore data;
  final ValueChanged<String> onAdded;

  @override
  State<FactorsWizard> createState() => _FactorsWizardState();
}

class _FactorsWizardState extends State<FactorsWizard> {
  String? _path;
  pk.FactorsCheck? _check;
  final _name = TextEditingController();
  int _step = 0;
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  bool get _ok => _check != null && !_check!.report.hasErrors && _name.text.trim().isNotEmpty;

  Future<void> _runCheck() async {
    if (_path == null) return;
    setState(() => _busy = true);
    final c = await pk.checkFactorsFile(_path!, widget.data.factors());
    if (!mounted) return;
    setState(() {
      _check = c;
      _step = 1;
      _busy = false;
    });
  }

  Future<void> _add() async {
    if (!_ok) return;
    final name = _name.text.trim();
    setState(() => _busy = true);
    await pk.addFactorsPackage(_check!, name);
    setState(() {
      _step = 2;
      _check = null;
      _path = null;
      _name.clear();
      _busy = false;
    });
    widget.onAdded(name);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _Steps(steps: const ['1 · Dosya', '2 · Kontrol', '3 · Ekle'], current: _step),
        const SizedBox(height: 10),
        const Text.rich(TextSpan(style: TextStyle(color: th.muted), children: [
          TextSpan(
              text: 'ETKB yeni emisyon faktörlerini yayımladığında yakıt türü başına tCO2/MWh ve tCO2-eşd/MWh '
                  'değerlerini içeren bir dosya seçin (ör. '),
          TextSpan(text: 'Kaynak;tCO2/MWh;tCO2-eşd/MWh', style: TextStyle(fontStyle: FontStyle.italic)),
          TextSpan(
              text: '). Etkin olduğunda tüm yılların karbon yoğunluğu yeni katsayılarla yeniden hesaplanır; '
                  'formül değişmez.'),
        ])),
        const SizedBox(height: 10),
        _FileRow(
          title: 'Emisyon katsayısı dosyası seç',
          path: _path,
          onPick: () async {
            final p = await _pickFile();
            if (p != null) {
              setState(() => _path = p);
              await _runCheck();
            }
          },
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _name,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(
              labelText: 'Paket adı', hintText: 'Ör. ETKB 2025', border: OutlineInputBorder(), isDense: true),
        ),
        const Divider(),
        const Text('Otomatik kontrol', style: TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        if (_busy) const LinearProgressIndicator(),
        if (_check != null) ReportView(rep: _check!.report),
        const SizedBox(height: 10),
        Align(
          alignment: Alignment.centerRight,
          child: FilledButton(onPressed: _ok && !_busy ? _add : null, child: const Text('Katsayıları etkinleştir')),
        ),
      ],
    );
  }
}

// ---------------- sekme ----------------

class DataScreen extends StatefulWidget {
  const DataScreen({super.key, required this.app});
  final AppState app;

  @override
  State<DataScreen> createState() => _DataScreenState();
}

class _DataScreenState extends State<DataScreen> {
  List<pk.Package> _pkgs = [];
  Map<String, String> _errors = {};
  int _action = 0;
  String _msg = '';

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final pkgs = await pk.listPackages();
    if (!mounted) return;
    setState(() {
      _pkgs = pkgs;
      _errors = widget.app.data.packageErrors(pkgs);
    });
  }

  /// Veri paketi eklendi/açıldı/kapandı/silindi: her şeyi yeniden oku ve tazele.
  Future<void> _changed(String message) async {
    await widget.app.applyDataChange();
    await _refresh();
    if (mounted) setState(() => _msg = '✓ $message  Makine listeleri ve hesaplar güncellendi.');
  }

  String _describe(pk.Package p) {
    final m = p.meta;
    if (p.kind == pk.kindMachine) {
      final src = m['source'] == 'real' ? 'Tesis ölçümü' : 'Örnek yük';
      return '${m['days'] ?? 0} gün · ${fmt.date('${m['first_day']}')} – ${fmt.date('${m['last_day']}')}\nMakine · $src';
    }
    if (p.kind == pk.kindGrid) {
      return '${fmt.num(((m['hours'] ?? 0) as num).toDouble(), 0)} saat · ${fmt.date('${m['first_day']}')} – '
          '${fmt.date('${m['last_day']}')}\nŞebeke verisi';
    }
    return 'Emisyon faktörleri\nKatsayı · tüm yıllar bununla hesaplanır';
  }

  Future<void> _delete(pk.Package p) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Paketi sil'),
        content: Text('“${p.name}” paketi kalıcı olarak silinsin mi?\n'
            'Bu paketle kaydedilmiş geçmiş senaryolar artık açılamaz.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Vazgeç')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: th.bad),
            child: const Text('Sil'),
          ),
        ],
      ),
    );
    if (ok == true) {
      await pk.deletePackage(p.id);
      await _changed('“${p.name}” silindi.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = widget.app.data;
    const titles = [
      ('Makine ekle', 'Saatlik kWh dosyası (CSV / Excel)'),
      ('Yıl ekle', 'EPİAŞ gerçek zamanlı üretim dışa aktarımı'),
      ('Emisyon katsayıları', 'Yeni ETKB yakıt faktörleri'),
    ];
    void added(String name) => _changed('“$name” eklendi.');
    final wizard = switch (_action) {
      0 => MachineWizard(data: data, onAdded: added),
      1 => GridWizard(data: data, onAdded: added),
      _ => FactorsWizard(data: data, onAdded: added),
    };
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
      children: [
        th.SectionCard(
          title: 'Yüklü veri paketleri',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _PkgTile(
                title: 'Varsayılan veri (2025)',
                subtitle: '$baseGridLabel · 8.760 saat · 7 makine · $baseFactorsLabel\nYerleşik · Örnek yük',
              ),
              for (final p in _pkgs)
                if (_errors.containsKey(p.id))
                  _PkgTile(
                    title: p.name,
                    subtitle: '⚠ Okunamadı — paket atlandı\n'
                        'Dosyaları eksik ya da bozuk; silip yeniden ekleyin.',
                    error: true,
                    tooltip: 'Ayrıntı: ${_errors[p.id]}',
                    onDelete: () => _delete(p),
                  )
                else
                  _PkgTile(
                    title: p.name,
                    subtitle: _describe(p),
                    tooltip: p.createdAt.isNotEmpty ? 'Eklendi: ${fmt.datetime(p.createdAt)}' : null,
                    enabled: p.enabled,
                    onToggle: (v) async {
                      try {
                        await pk.setEnabled(p.id, v);
                        await _changed('Veri paketi ${v ? 'açıldı.' : 'kapatıldı.'}');
                      } catch (e) {
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
                        }
                      }
                    },
                    onDelete: () => _delete(p),
                  ),
              const SizedBox(height: 6),
              const th.Muted('Anahtarla aç/kapat · çöp kutusuyla sil. Paketler uygulamanın kendi klasöründe tutulur.',
                  size: 12),
            ],
          ),
        ),
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
          decoration: BoxDecoration(
            color: th.warnSoft,
            border: Border.all(color: const Color(0xFFF0D9A8)),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Text.rich(TextSpan(style: TextStyle(color: Color(0xFF5C3D07)), children: [
            TextSpan(text: 'Formül bu ekrandan değiştirilmez. ', style: TextStyle(fontWeight: FontWeight.w700)),
            TextSpan(
                text: "Hesap formülü masaüstü, mobil ve Excel'de aynı kalmalıdır; değişiklik FORMUL.md sürüm "
                    'süreciyle yapılır. Emisyon katsayıları ise veri olarak güncellenebilir.'),
          ])),
        ),
        const SizedBox(height: 10),
        for (var i = 0; i < titles.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: OutlinedButton(
              style: OutlinedButton.styleFrom(
                alignment: Alignment.centerLeft,
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
                backgroundColor: _action == i ? th.primarySoft : null,
                side: BorderSide(color: _action == i ? th.primary : th.fieldBorder, width: _action == i ? 2 : 1),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              onPressed: () => setState(() => _action = i),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(titles[i].$1, style: const TextStyle(fontWeight: FontWeight.w600, color: th.text)),
                  Text(titles[i].$2, style: const TextStyle(fontSize: 12, color: th.muted)),
                ],
              ),
            ),
          ),
        if (_msg.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Text(_msg, style: const TextStyle(color: th.good, fontWeight: FontWeight.w600)),
          ),
        th.SectionCard(child: KeyedSubtree(key: ValueKey(_action), child: wizard)),
      ],
    );
  }
}

class _PkgTile extends StatelessWidget {
  const _PkgTile({
    required this.title,
    required this.subtitle,
    this.enabled,
    this.onToggle,
    this.onDelete,
    this.error = false,
    this.tooltip,
  });

  final String title;
  final String subtitle;
  final bool? enabled;
  final ValueChanged<bool>? onToggle;
  final VoidCallback? onDelete;
  final bool error;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final color = error ? th.bad : (enabled == false ? th.muted : th.text);
    final tile = Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.fromLTRB(10, 8, 4, 8),
      decoration: BoxDecoration(border: Border.all(color: th.border), borderRadius: BorderRadius.circular(8)),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: TextStyle(fontWeight: FontWeight.w600, color: color)),
                Text(subtitle, style: TextStyle(fontSize: 12.5, color: error ? th.bad : th.muted)),
              ],
            ),
          ),
          if (onToggle != null) Switch(value: enabled ?? false, onChanged: onToggle),
          if (onDelete != null)
            IconButton(onPressed: onDelete, icon: const Icon(Icons.delete_outline, color: th.bad), tooltip: 'Sil'),
        ],
      ),
    );
    return tooltip == null ? tile : Tooltip(message: tooltip!, child: tile);
  }
}
