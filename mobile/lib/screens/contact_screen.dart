// İletişim sekmesi: geliştiriciler ve danışman (desktop/contact_tab.py).

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../ui/theme.dart' as th;

const String appVersion = '1.1.0';

class Person {
  const Person(this.role, this.name, this.phone, this.email, [this.org]);
  final String role, name, phone, email;
  final String? org;
}

const List<Person> people = [
  Person('Geliştirici', 'İsmail Ali ASLAN', '05527987865', 'ismailaliaslan11@gmail.com'),
  Person('Geliştirici', 'Emin Burak ÖZTÜRK', '05550392314', 'eminburak1410@gmail.com'),
  Person('Danışman', 'Öğr. Gör. Ali ERFİDAN', '05414597933', 'ali.erfidan@balikesir.edu.tr', 'Balıkesir Üniversitesi'),
];

/// 05527987865 → 0552 798 78 65
String fmtPhone(String p) {
  final d = p.replaceAll(RegExp(r'\D'), '');
  return d.length == 11 ? '${d.substring(0, 4)} ${d.substring(4, 7)} ${d.substring(7, 9)} ${d.substring(9, 11)}' : p;
}

String initials(String name) {
  final parts = name.replaceAll('Öğr.', '').replaceAll('Gör.', '').split(' ').where((w) => w.isNotEmpty).toList();
  return parts.length > 1
      ? (parts.first[0] + parts.last[0]).toUpperCase()
      : (parts.first.length > 2 ? parts.first.substring(0, 2) : parts.first).toUpperCase();
}

class ContactScreen extends StatelessWidget {
  const ContactScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 16, 12, 24),
      children: [
        const Text('İletişim', textAlign: TextAlign.center, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
        const th.Muted('CarbonDelta hakkında soru, öneri ve geri bildirimleriniz için bize ulaşın.', align: TextAlign.center),
        const SizedBox(height: 12),
        for (final p in people) ...[_card(context, p), const SizedBox(height: 10)],
        const th.SectionCard(
          child: Text.rich(TextSpan(children: [
            TextSpan(text: 'CarbonDelta', style: TextStyle(fontWeight: FontWeight.w700)),
            TextSpan(
                text: ' · Sürüm $appVersion · Emisyon Potansiyeli Karar Destek. Endüstriyel yükleri daha temiz saatlere '
                    'kaydırmanın şebeke emisyonuna etkisini hesaplar; karar her zaman kullanıcıdadır.'),
          ])),
        ),
      ],
    );
  }

  Widget _card(BuildContext context, Person p) {
    final color = p.role == 'Geliştirici' ? th.primary : const Color(0xFF1F4E79);
    final role = {'Geliştirici': 'GELİŞTİRİCİ', 'Danışman': 'DANIŞMAN'}[p.role] ?? p.role;
    return th.SectionCard(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 23,
                backgroundColor: color,
                child: Text(initials(p.name),
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 16)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(role,
                        style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1)),
                    Text(p.name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                    if (p.org != null) th.Muted(p.org!),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          InkWell(
            onTap: () => launchUrl(Uri.parse('tel:${p.phone}')),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Text('☎  ${fmtPhone(p.phone)}'),
            ),
          ),
          InkWell(
            onTap: () => launchUrl(Uri.parse('mailto:${p.email}')),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Text('✉  ${p.email}', style: const TextStyle(color: th.primary)),
            ),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              FilledButton(
                onPressed: () => launchUrl(Uri.parse('mailto:${p.email}')),
                child: const Text('E-posta gönder'),
              ),
              const SizedBox(width: 8),
              Tooltip(
                message: 'E-posta ve telefonu panoya kopyalar',
                child: OutlinedButton(
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: '${p.name} · ${fmtPhone(p.phone)} · ${p.email}'));
                  ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('✓ ${p.name} iletişim bilgileri panoya kopyalandı')));
                },
                child: const Text('Kopyala'),
              ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
