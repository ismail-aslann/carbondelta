import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'ai/ai_client.dart';
import 'data/history_db.dart';
import 'engine/data.dart';
import 'screens/main_shell.dart';
import 'state/ai_state.dart';
import 'state/app_state.dart';
import 'ui/theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const CarbonDeltaApp());
}

class CarbonDeltaApp extends StatelessWidget {
  const CarbonDeltaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CarbonDelta',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      locale: const Locale('tr'),
      supportedLocales: const [Locale('tr'), Locale('en')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: const _Loader(),
    );
  }
}

class _Loader extends StatefulWidget {
  const _Loader();

  @override
  State<_Loader> createState() => _LoaderState();
}

class _LoaderState extends State<_Loader> {
  late final Future<(AppState, AiState)> _future = _init();

  /// Uygulama açılışında tüm veriyi bir kez belleğe al.
  Future<(AppState, AiState)> _init() async {
    final sw = Stopwatch()..start();
    await DataStore.instance.load();
    await loadPrompts();
    final db = await HistoryDB.open();
    final cfg = await loadConfig();
    debugPrint('CarbonDelta veri yükleme: ${sw.elapsedMilliseconds} ms');
    final app = AppState(DataStore.instance, db);
    return (app, AiState(app, AIService(cfg)));
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<(AppState, AiState)>(
      future: _future,
      builder: (context, snap) {
        if (snap.hasError) {
          return Scaffold(
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text('Veri yüklenemedi:\n${snap.error}'),
              ),
            ),
          );
        }
        if (!snap.hasData) {
          return const Scaffold(
            body: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [CircularProgressIndicator(), SizedBox(height: 12), Text('Veri yükleniyor…')],
              ),
            ),
          );
        }
        return MainShell(app: snap.data!.$1, ai: snap.data!.$2);
      },
    );
  }
}
