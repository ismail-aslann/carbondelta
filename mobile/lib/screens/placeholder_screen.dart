import 'package:flutter/material.dart';

import '../ui/theme.dart' as th;

/// Henüz taşınmamış bölümler için geçici ekran.
class PlaceholderScreen extends StatelessWidget {
  const PlaceholderScreen({super.key, required this.title});
  final String title;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: th.Muted('$title bölümü bir sonraki sürümde eklenecek.', align: TextAlign.center),
        ),
      );
}
