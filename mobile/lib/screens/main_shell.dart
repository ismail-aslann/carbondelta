// Ana çerçeve: başlangıç ekranı ↔ uygulama sekmeleri (desktop/main_window.py
// MainWindow: pages, tabs, footer, _on_start_action).

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../ai/ai_context.dart' as ctx;
import '../engine/core.dart' as core;
import '../state/ai_state.dart';
import '../state/app_state.dart';
import '../ui/fmt.dart' as fmt;
import '../ui/theme.dart' as th;
import '../widgets/delti_box.dart';
import '../widgets/nl_bar.dart';
import '../widgets/summary_card.dart';
import 'annual_screen.dart';
import 'best_window_screen.dart';
import 'calc_screen.dart';
import 'contact_screen.dart';
import 'data_screen.dart';
import 'guide_screen.dart';
import 'delti_settings_screen.dart';
import 'history_screen.dart';
import 'nl_screen.dart';
import 'plan_screen.dart';
import 'scenario_screen.dart';
import 'sources_screen.dart';
import 'start_screen.dart';

/// Masaüstündeki sekme sırası.
enum AppTab { scenario, best, annual, plan, nl, calc, history, data, guide, sources, contact }

const Map<AppTab, String> tabTitles = {
  AppTab.scenario: 'Senaryo',
  AppTab.best: 'En Temiz Saat',
  AppTab.annual: 'Yıllık Etki',
  AppTab.plan: 'Tesis Planı',
  AppTab.nl: "Delti'ye Sor",
  AppTab.calc: 'Hesabı Göster',
  AppTab.history: 'Geçmiş',
  AppTab.data: 'Veri',
  AppTab.guide: 'Kılavuz',
  AppTab.sources: 'Kaynaklar',
  AppTab.contact: 'İletişim',
};

class MainShell extends StatefulWidget {
  const MainShell({super.key, required this.app, required this.ai});
  final AppState app;
  final AiState ai;

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  bool _home = true;
  AppTab _tab = AppTab.scenario;

  // Ana sayfa "son senaryo" kartı
  String _resumeSmall = 'Demo senaryo';
  String _resumeText = '';
  String _resumeDelta = '';
  bool _resumeGood = true;

  AppState get app => widget.app;
  AiState get ai => widget.ai;

  @override
  void initState() {
    super.initState();
    _refreshStart();
  }

  /// Başlangıç ekranındaki eğriyi ve son senaryo kartını günceller.
  Future<void> _refreshStart() async {
    final latest = await app.db.latest();
    if (latest != null && latest.deltaPct != null && app.data.hasMachine(latest.assetId)) {
      final name = app.data.machine(latest.assetId).name;
      setState(() {
        _resumeSmall = 'Son senaryo';
        _resumeText = '$name · ${fmt.hour(latest.s)} → ${fmt.hour(latest.t)}';
        _resumeDelta = fmt.pct(latest.deltaPct);
        _resumeGood = latest.deltaPct! <= 0;
      });
      return;
    }
    final demo = app.demoInputs();
    final (load, ci) = app.series(demo);
    final r = core.simulate(load, ci, demo.s, demo.L, demo.t, demo.p);
    final name = app.data.machine(demo.assetId).name;
    setState(() {
      _resumeSmall = 'Demo senaryo';
      _resumeText = '$name · ${fmt.hour(demo.s)} → ${fmt.hour(demo.t)}';
      _resumeDelta = fmt.pct(r.deltaPct);
      _resumeGood = (r.deltaPct ?? 0) <= 0;
    });
  }

  bool _fullscreen = false;

  void _open(AppTab t) {
    app.tabFooter.value = null; // Yıllık Etki / Tesis Planı açılınca kendi etiketini yazar
    setState(() {
      _home = false;
      _tab = t;
    });
  }

  /// Sunum modu (masaüstünde F11): durum ve gezinme çubukları gizlenir.
  Future<void> _toggleFullscreen() async {
    _fullscreen = !_fullscreen;
    await SystemChrome.setEnabledSystemUIMode(_fullscreen ? SystemUiMode.immersiveSticky : SystemUiMode.edgeToEdge);
    if (mounted) setState(() {});
  }

  void goHome() {
    _refreshStart();
    setState(() => _home = true);
  }

  Future<void> _onStartAction(String key) async {
    switch (key) {
      case 'resume':
        final latest = await app.db.latest();
        if (latest != null && latest.deltaPct != null && app.data.hasMachine(latest.assetId)) {
          app.restoreHistory(latest);
        } else {
          app.setInputs(app.demoInputs());
        }
        _open(AppTab.scenario);
      case 'new':
        app.newScenario();
        _open(AppTab.scenario);
      case 'best':
        _open(AppTab.best);
      case 'annual':
        _open(AppTab.annual);
      case 'plan':
        _open(AppTab.plan);
      case 'nl':
        _open(AppTab.nl);
      case 'history':
        _open(AppTab.history);
      case 'calc':
        _open(AppTab.calc);
      case 'guide':
        _open(AppTab.guide);
      case 'data':
        _open(AppTab.data);
      case 'contact':
        _open(AppTab.contact);
      case 'sources':
        _open(AppTab.sources);
      case 'delti_settings':
        _openDeltiSettings();
    }
  }

  Future<void> _openDeltiSettings() async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => DeltiSettingsScreen(cfg: ai.service.cfg)),
    );
    if (changed == true) {
      await ai.reloadConfig();
      if (mounted) setState(() {});
    }
  }

  Widget _page(AppTab t) {
    switch (t) {
      case AppTab.scenario:
        return ScenarioScreen(
          app: app,
          header: NlBar(ai: ai),
          deltiBox: DeltiBox(ai: ai, onOpenSettings: _openDeltiSettings),
          onBestApplied: () => ai.requestManual(ctx.bestWindowExplain),
        );
      case AppTab.best:
        return BestWindowScreen(key: ValueKey('best${app.dataVersion}'), app: app, onApplied: () => _open(AppTab.scenario));
      case AppTab.annual:
        return AnnualScreen(
            key: ValueKey('annual${app.dataVersion}'), app: app, ai: ai, onApplied: () => _open(AppTab.scenario));
      case AppTab.plan:
        return PlanScreen(key: ValueKey('plan${app.dataVersion}'), app: app, onApplied: () => _open(AppTab.scenario));
      case AppTab.nl:
        return NlScreen(
          ai: ai,
          onOpenScenario: () => _open(AppTab.scenario),
          onOpenSettings: _openDeltiSettings,
        );
      case AppTab.calc:
        return CalcScreen(app: app);
      case AppTab.history:
        return HistoryScreen(
          app: app,
          onRestored: () => _open(AppTab.scenario),
          onSummarize: () => ai.summarizeHistory(),
          summary: SummaryCard(ai: ai),
        );
      case AppTab.sources:
        return const SourcesScreen();
      case AppTab.data:
        return DataScreen(app: app);
      case AppTab.guide:
        return const GuideScreen();
      case AppTab.contact:
        return const ContactScreen();
    }
  }

  static const _bottom = [AppTab.scenario, AppTab.best, AppTab.nl, AppTab.history];

  Future<void> _more() async {
    final t = await showModalBottomSheet<AppTab>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true, // liste uzadı: küçük ekranda kaydırılabilir
      builder: (ctx) => SafeArea(
        child: SingleChildScrollView(
          child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final (tab, icon) in const [
              (AppTab.annual, Icons.calendar_month_outlined),
              (AppTab.plan, Icons.factory_outlined),
              (AppTab.calc, Icons.description_outlined),
              (AppTab.data, Icons.storage),
              (AppTab.guide, Icons.menu_book_outlined),
              (AppTab.sources, Icons.dataset_outlined),
              (AppTab.contact, Icons.mail_outline),
            ])
              ListTile(
                leading: Icon(icon, color: th.primary),
                title: Text(tabTitles[tab]!),
                selected: _tab == tab,
                onTap: () => Navigator.pop(ctx, tab),
              ),
            ListTile(
              leading: Icon(_fullscreen ? Icons.fullscreen_exit : Icons.fullscreen, color: th.primary),
              title: Text(_fullscreen ? 'Tam ekrandan çık' : 'Tam ekran (sunum modu)'),
              onTap: () {
                Navigator.pop(ctx);
                _toggleFullscreen();
              },
            ),
            ListTile(
              leading: const Icon(Icons.home_outlined, color: th.primary),
              title: const Text('Ana sayfa'),
              onTap: () {
                Navigator.pop(ctx);
                goHome();
              },
            ),
          ],
        ),
        ),
      ),
    );
    if (t != null) {
      _open(t);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_home) {
      return PopScope(
        canPop: true,
        child: StartScreen(
          curve: app.data.ci24(demoDate),
          resumeSmall: _resumeSmall,
          resumeText: _resumeText,
          resumeDelta: _resumeDelta,
          resumeGood: _resumeGood,
          aiOnline: ai.online,
          machineCount: app.data.machines().length,
          onAction: _onStartAction,
        ),
      );
    }
    final navIndex = _bottom.contains(_tab) ? _bottom.indexOf(_tab) : 4;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) goHome();
      },
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            tooltip: 'Ana sayfa',
            icon: const Icon(Icons.home_outlined),
            onPressed: goHome,
          ),
          titleSpacing: 0,
          title: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('CarbonDelta', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              Text(tabTitles[_tab]!, style: const TextStyle(fontSize: 12.5, color: Color(0xFFCFE9DF))),
            ],
          ),
        ),
        body: _page(_tab),
        bottomNavigationBar: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListenableBuilder(
              listenable: Listenable.merge([app, app.tabFooter]),
              builder: (context, _) {
                final i = app.inputs;
                // Yıllık Etki / Tesis Planı kendi kapsamlarının kaynak etiketini gösterir (yalnızca açıkken).
                final own = (_tab == AppTab.annual || _tab == AppTab.plan) ? app.tabFooter.value : null;
                final real = own?.$2 ?? app.data.isReal(i.assetId);
                return Container(
                  width: double.infinity,
                  color: th.bg,
                  padding: const EdgeInsets.fromLTRB(10, 4, 10, 4),
                  child: Text(
                    own?.$1 ?? app.data.sourceLabel(i.assetId, i.date),
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: real ? th.primaryDark : th.muted,
                      fontSize: 11,
                      fontWeight: real ? FontWeight.w600 : FontWeight.normal,
                    ),
                  ),
                );
              },
            ),
            NavigationBar(
              selectedIndex: navIndex,
              height: 64,
              labelTextStyle: const WidgetStatePropertyAll(
                TextStyle(fontSize: 11.5, fontWeight: FontWeight.w500, letterSpacing: 0, overflow: TextOverflow.ellipsis),
              ),
              onDestinationSelected: (k) {
                if (k < _bottom.length) {
                  _open(_bottom[k]);
                } else {
                  _more();
                }
              },
              destinations: const [
                NavigationDestination(icon: Icon(Icons.tune), label: 'Senaryo'),
                NavigationDestination(icon: Icon(Icons.search), label: 'Temiz saat', tooltip: 'En temiz saat'),
                NavigationDestination(icon: Icon(Icons.chat_bubble_outline), label: "Delti'ye sor"),
                NavigationDestination(icon: Icon(Icons.schedule), label: 'Geçmiş'),
                NavigationDestination(icon: Icon(Icons.more_horiz), label: 'Diğer'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
