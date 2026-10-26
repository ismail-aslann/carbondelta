// Kaynaklar sekmesi (desktop/tabs.py SourcesTab).

import 'package:flutter/material.dart';

import '../ui/theme.dart' as th;

const List<(String, String, String)> sourceCards = [
  (
    'EPİAŞ 2025',
    '8.760 saat',
    'Şeffaflık Platformu saatlik gerçek zamanlı üretim verisi. Doğal gaz, linyit, ithal kömür, rüzgâr, '
        'güneş, hidro gibi kaynakların her saatteki üretimi. Her saatin karbon yoğunluğu, kaynak '
        'üretimlerinin ETKB katsayılarıyla çarpılıp yurtiçi toplam üretime bölünmesiyle bulunur.'
  ),
  (
    'ETKB 2023',
    '15 yakıt katsayısı',
    "Enerji ve Tabii Kaynaklar Bakanlığı'nın yakıt türü başına resmî tCO2/MWh ve tCO2-eşd/MWh emisyon "
        'faktörleri. Yenilenebilir kaynaklar için doğrudan yakıt emisyonu sıfır kabul edilir. Tablo '
        '"Hesabı Göster" sekmesindedir.'
  ),
  (
    'Zenodo',
    '7 makine · 1.839 gün',
    'Bir imalat tesisindeki makinelerin 15 dakikalık enerji ölçümleri. Faz tekrarları, sensör hatalı '
        'cihazlar ve eksik günler temizlenmiş, saatlik toplama çevrilmiştir. Havalandırma ve pres ısıtma '
        'sürekli/kısıtlı süreç olduğu için kaydırılamaz.'
  ),
];

class SourcesScreen extends StatelessWidget {
  const SourcesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
      children: [
        for (final (title, stat, body) in sourceCards) ...[
          th.SectionCard(
            title: title,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
                  decoration: BoxDecoration(color: th.primarySoft, borderRadius: BorderRadius.circular(9)),
                  child: Text(stat,
                      style: const TextStyle(color: th.primaryDark, fontWeight: FontWeight.w600, fontSize: 12.5)),
                ),
                const SizedBox(height: 8),
                Text(body, style: const TextStyle(height: 1.35)),
              ],
            ),
          ),
          const SizedBox(height: 10),
        ],
        Container(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
          decoration: BoxDecoration(
            color: th.warnSoft,
            border: Border.all(color: const Color(0xFFF0D9A8)),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Text.rich(
            TextSpan(style: TextStyle(color: Color(0xFF5C3D07), height: 1.35), children: [
              TextSpan(text: 'Önemli not: örnek yük\n', style: TextStyle(fontWeight: FontWeight.w700)),
              TextSpan(text: "Yük verisi İrlanda'daki bir tesisten alınmış ve saat numarasıyla Türkiye şebekesine eşlenmiş "),
              TextSpan(text: 'örnek', style: TextStyle(fontWeight: FontWeight.w700)),
              TextSpan(text: ' veridir; Balıkesir tesisinin ölçümü değildir. Sonuçlar yöntemi ve büyüklük mertebesini gösterir.'),
            ]),
          ),
        ),
        const SizedBox(height: 10),
        const th.SectionCard(
          child: Text.rich(TextSpan(children: [
            TextSpan(text: 'Kapsam\n', style: TextStyle(fontWeight: FontWeight.w700)),
            TextSpan(
              text: 'Uygulama karar destek amaçlıdır; hiçbir makineye müdahale etmez ve karar her zaman '
                  'kullanıcıdadır. Para/TL kazanç vaadi, CBAM hesabı, IoT/sensör bağlantısı ve otomatik makine '
                  'kontrolü kapsam dışıdır. Yapay zekâ yalnızca hesaplanmış sayıları açıklama metnine çevirir; '
                  'internet yoksa hesap yine çalışır.',
              style: TextStyle(color: th.muted, height: 1.35),
            ),
          ])),
        ),
      ],
    );
  }
}
