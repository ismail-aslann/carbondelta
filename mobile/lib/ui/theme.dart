import 'package:flutter/material.dart';

// desktop/theme.py renkleri.
const bg = Color(0xFFF3F5F8);
const surface = Color(0xFFFFFFFF);
const border = Color(0xFFE1E6EC);
const fieldBorder = Color(0xFFCFD6DE);
const text = Color(0xFF1D2733);
const muted = Color(0xFF6B7785);
const primary = Color(0xFF16785C);
const primaryDark = Color(0xFF0F5B46);
const primarySoft = Color(0xFFE7F3EF);
const good = Color(0xFF1F9254);
const bad = Color(0xFFD03C3C);
const badSoft = Color(0xFFFDECEC);
const warn = Color(0xFF9A6412);
const warnSoft = Color(0xFFFFF6E5);
const ciColor = Color(0xFF1F4E79);

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: primary, primary: primary, surface: surface);
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: bg,
    appBarTheme: const AppBarTheme(
      backgroundColor: primaryDark,
      foregroundColor: Colors.white,
      elevation: 0,
    ),
    cardTheme: const CardThemeData(
      color: surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.all(Radius.circular(10)),
        side: BorderSide(color: border),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(backgroundColor: primary, foregroundColor: Colors.white),
    ),
  );
}

/// Başlıklı beyaz kart (theme.card).
class SectionCard extends StatelessWidget {
  const SectionCard({super.key, this.title, this.titleWidget, required this.child, this.padding});

  final String? title;
  final Widget? titleWidget;
  final Widget child;
  final EdgeInsets? padding;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: padding ?? const EdgeInsets.fromLTRB(14, 12, 14, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ?titleWidget,
            if (title != null && titleWidget == null)
              Text(title!,
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: text)),
            if (title != null || titleWidget != null) const SizedBox(height: 8),
            child,
          ],
        ),
      ),
    );
  }
}

class Muted extends StatelessWidget {
  const Muted(this.data, {super.key, this.size = 13, this.align});
  final String data;
  final double size;
  final TextAlign? align;

  @override
  Widget build(BuildContext context) =>
      Text(data, textAlign: align, style: TextStyle(color: muted, fontSize: size));
}
