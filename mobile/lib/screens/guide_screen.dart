// Kullanma kılavuzu (desktop/guide_tab.py). Klavye kısayolları yerine telefonda
// dokunmatik karşılıkları anlatılır.

import 'package:flutter/material.dart';

import '../ui/theme.dart' as th;
import '../widgets/rich.dart';

/// (anahtar, başlık, paragraflar) — '• ' ile başlayan satır madde işaretidir.
const List<(String, String, List<String>)> sections = [
  ('start', 'Başlarken', [
    '**CarbonDelta**, bir makinenin elektrik yükünü günün başka saatine kaydırdığınızda şebeke karbon emisyonunun '
        '**yüzde kaç** değişeceğini hesaplar. Hesap internetsiz ve yapay zekâsız yapılır; aynı girdiler her zaman aynı '
        'sonucu verir. Uygulama hiçbir makineye müdahale etmez, **karar her zaman sizindir**.',
    "Yük verisi İrlanda'daki bir tesisten alınmış **örnek** veridir (Balıkesir tesisi değildir); karbon yoğunluğu "
        'EPİAŞ 2025 saatlik üretim verisi ve ETKB 2023 emisyon faktörleriyle hesaplanır.',
    '**Hızlı başlangıç:** Ana sayfada _Yeni senaryo_ya dokunun, makineyi ve günü seçin, standart ve hedef saatleri '
        'girin; sonuç kartı anında güncellenir.',
  ]),
  ('home', 'Ana sayfa', [
    'Uygulama ana sayfayla açılır. Arkadaki eğri, örnek bir günün 24 saatlik şebeke karbon yoğunluğudur (en kirli ve '
        'en temiz saatler işaretlidir).',
    '• **Son senaryo / Demo senaryo kartı:** En son kaydettiğiniz senaryoyu (yoksa demo senaryoyu) tek adımda açar.',
    '• **Yeni senaryo:** Senaryo ekranını temiz bir başlangıçla açar (kısıtlı saatler temizlenir, oran %100).',
    '• **En temiz saat:** Seçtiğiniz yük için günün tüm hedef saatlerini emisyona göre sıralar.',
    "• **Delti'ye sor:** Ne yapmak istediğinizi günlük dille yazarsınız.",
    '• **Geçmiş**, **Hesap dökümü**, **Veri yönetimi**, **Kullanma kılavuzu**, **Kaynaklar**, **İletişim**: ilgili '
        'ekranları açar.',
    'Bir satıra dokunarak açın. Uygulamanın her yerinden sol üstteki ⌂ düğmesi ya da telefonun geri tuşu ana sayfaya '
        'döndürür.',
  ]),
  ('scenario', 'Senaryo ekranı', [
    "**Delti'ye yazın:** Ekranın üstündeki kutuya cümleyle yazabilirsiniz (ör. _Kompresörü 3'ten 18'e al_).",
    '**Makine ve gün:** Makineyi ve günü seçin. Takvimde yalnızca verisi olan günler seçilebilir. _Havalandırma_ ve '
        '_Pres ısıtma_ sürekli/kısıtlı süreçtir; bunlar seçildiğinde kaydırma alanları pasifleşir ve öneri üretilmez.',
    '**Emisyon tipi:** tCO2 (yalnızca CO2) veya tCO2-eşd (diğer sera gazlarının CO2 eşdeğeri dahil). '
        '**Parametrik mod:** Ölçülen yük yerine her saat için aynı kWh değerini kullanır (ör. yeni bir makineyi denemek için).',
    '**Zaman penceresi:**',
    '• **Standart başlangıç:** Yükün normalde çalıştığı saat.',
    '• **Pencere uzunluğu:** Kaç saatlik yükün taşınacağı (1–12).',
    '• **Hedef başlangıç:** Yükün taşınacağı saat. Pencere gece yarısını aşamaz (başlangıç + uzunluk ≤ 24).',
    '• **Kaydırma oranı:** Yükün ne kadarının taşınacağı (%0–100).',
    '• **En iyi saati bul:** Aynı yük için en düşük emisyonlu hedef saati seçer.',
    '**Kısıtlı saatler:** İşaretlediğiniz saatler hedef pencereye giremez (ör. vardiya, gürültü, bakım). Çiplere '
        'dokunarak işaretleyin.',
    '**Grafik:** Çizgi saatlik karbon yoğunluğu, soluk çubuklar makinenin yüküdür. Gri bant standart pencere, yeşil bant '
        '(emisyon düşüyorsa) ya da kırmızı bant (artıyorsa) seçilen penceredir. Bir saate dokununca değerler görünür.',
    '**Sonuç kartı:** Büyük yüzde, taşınan enerjinin emisyonundaki değişimdir; eksi değer daha düşük emisyon demektir. '
        'Altında bunun ne anlama geldiği, standart/seçilen pencere emisyonları, taşınan enerji ve makinenin günlük toplam '
        'emisyonuna etkisi yazar. **Senaryoyu kaydet** geçmişe ekler.',
  ]),
  ('results', 'Durum mesajları', [
    '• **Daha düşük emisyon potansiyeli** (yeşil): Seçilen saatlerde şebeke daha temiz.',
    '• **Bu kaydırma emisyonu ARTIRIR** (kırmızı): Seçilen saatlerde şebeke daha kirli.',
    '• **Bu yük kaydırılamaz:** Makine sürekli/kısıtlı süreç; öneri üretilmez.',
    '• **Aralık dışı:** Pencere aynı gün içinde kalmıyor; başlangıç veya uzunluğu küçültün.',
    '• **Kısıtlı saatlerle çakışıyor:** Hedef pencere işaretli bir saati kapsıyor; hedefi değiştirin ya da _En iyi saati '
        "bul_'u kullanın.",
    '• **Aynı pencere:** Standart ve hedef aynı; emisyon değişmez.',
    '• **Yük yok:** Standart pencerede makine çalışmıyor (0 kWh); yüzde hesaplanamaz.',
    '**Neden oranı değiştirince yüzde değişmiyor?** Ana yüzde, taşınan enerjinin _kendi_ emisyonundaki oransal '
        'değişimdir; oran yarıya inince hem standart hem seçilen emisyon yarıya iner, oran aynı kalır. Oranın etkisi kg '
        'değerlerinde ve **günlük etki**de görünür.',
  ]),
  ('best', 'En Temiz Saat', [
    'Makine, gün, standart başlangıç, uzunluk ve oranı seçin; günün tüm geçerli hedef pencereleri emisyona göre '
        'sıralanır (en üstte en temiz). Senaryo ekranındaki kısıtlı saatler burada da uygulanır. Alttaki grafik her hedef '
        'saatteki değişimi gösterir; çerçeveli çubuk en temiz penceredir.',
    'Listede bir satıra dokunup seçin; _Seçili saati senaryoya uygula_ ile (ya da satıra iki kez dokunarak) o saati '
        'senaryoya uygularsınız.',
  ]),
  ('delti', "Delti'ye Sor", [
    "**Delti**, CarbonDelta'nın yapay zekâ (AI) yardımcısıdır. Hesap yapmaz; motorun hesapladığı sonuçları açıklar ve "
        'günlük dille yazdıklarınızı senaryoya çevirir.',
    "Örnekler: _“Kompresörü 3'ten 18'e al”_, _“Presi %50 ile 2 saat 21'e kaydır”_. Cümle anlaşılınca Senaryo ekranına "
        'hemen uygulanır ve sonucun önizlemesi gösterilir. Oran yazmazsanız %100 kabul edilir; yazmadığınız diğer '
        'değerler (gün, kısıtlı saatler) korunur.',
    "Yazıp _Sor_'a basın; cevap gelince _Senaryoya git_. Senaryo ekranının üstündeki kutu da aynı işi yapar.",
  ]),
  ('explain', "Delti'nin açıklamaları", [
    'Senaryo ekranındaki **Delti açıklıyor** kartı, her hesaptan sonra sonucu sade bir dille anlatır: ne taşındı, emisyon '
        'neden değişti (o saatlerdeki yenilenebilir payı, baskın kaynak) ve günlük etkisi.',
    '• **Neden bu saat?** İki penceredeki üretim karışımını kıyaslar.',
    '• **Karşılaştır:** Mevcut senaryoyu en son kaydedilenle kıyaslar.',
    '• **Daha fazla:** Günlük etki yorumu, mevsim notu (aynı saatlerin 12 aylık davranışı), rapor cümlesi, terim '
        'açıklayıcı, veri kaynakları ve metni kopyala.',
    "**Güvenlik:** Delti'nin metnindeki her sayı hesaplanan değerlerle karşılaştırılır; veride olmayan bir sayı yazarsa "
        'metin gösterilmez, yerine şablon metin gelir. Etikette _AI_, _Düşünüyor…_, _Çevrimdışı · şablon_ veya _Şablon · '
        'doğrulanamadı_ yazar.',
    '**İnternet ya da anahtar yoksa** Delti uyur: “Delti (AI) şu an çevrimdışı; hesap sonucu geçerlidir.” Yüzde ve tüm '
        'hesaplar çalışmaya devam eder.',
    "**Delti'yi uyandırmak (API anahtarı):** Delti'ye Sor sekmesindeki _Delti'yi uyandır_ / ⚙ düğmesi, ana sayfanın "
        'altındaki _uyandır_ bağlantısı ya da Delti kartındaki _Daha fazla › Delti ayarları…_ ile **Delti ayarları** '
        'açılır. Sağlayıcıyı (Google Gemini veya Anthropic Claude) seçin, anahtarı yapıştırın, _Bağlantıyı dene_ ile '
        "kontrol edip _Kaydet_'e basın. Anahtar bu telefonda, Android'in güvenli deposunda şifrelenerek saklanır; "
        'uygulama güncellense de silinmez. _Anahtarı kaldır_ ile silinir.',
  ]),
  ('calc', 'Hesap dökümü', [
    'Hesabın saat saat dökümünü gösterir: her standart saatten taşınan enerji, o saatin ve hedef saatin karbon '
        'yoğunluğu, emisyonlar. Üstteki kartlarda B (standart emisyon), S (seçilen emisyon), değişim ve günlük etki yer '
        'alır. Altta formül ve ETKB 2023 emisyon faktörleri tablosu bulunur.',
    '**Formül:** E = oran × saatlik tüketim; B = Σ E × CI(standart saat); S = Σ E × CI(hedef saat); değişim = (S − B) / '
        'B × 100; günlük etki = (S − B) / günlük toplam emisyon × 100.',
    "**CSV olarak dışa aktar**, dökümü Türkçe Excel'de açılabilen bir dosyaya tam hassasiyetle yazar ve paylaşma "
        'menüsüyle gönderir.',
  ]),
  ('history', 'Geçmiş', [
    'Kaydettiğiniz senaryolar burada listelenir (telefonda, uygulamanın kendi veritabanında).',
    '• Bir kayda dokunarak senaryoyu geri yükleyin.',
    '• Çöp kutusu seçili kaydı siler (onay sorulur).',
    '• **Özetle:** Delti son 10 kaydı özetler; en iyi ve en kötü senaryoyu söyler.',
  ]),
  ('data', 'Veri yönetimi', [
    'Yeni makine, yeni yıl ya da yeni emisyon katsayıları **Veri** sekmesinden eklenir; uygulamayı yeniden kurmak '
        'gerekmez. Varsayılan 2025 verisi her zaman yerinde kalır. Eklenen her şey ayrı bir **veri paketi** olarak '
        'uygulamanın kendi klasöründe tutulur.',
    '• **Makine ekle:** Saatlik kWh dosyası seçin (CSV ya da Excel; sütunlar _Tarih, Saat, kWh_; ondalık virgül '
        'olabilir). Makine adını, türünü, kaydırılabilir olup olmadığını ve veri türünü (_örnek yük_ ya da _tesis '
        'ölçümü_) girin. Uygulama her günün 24 tekrarsız saati olup olmadığını, boş/negatif değerleri ve o gün için '
        'şebeke verisi bulunup bulunmadığını kontrol eder; eksik günleri atlar ve raporlar. _Şablon dosyayı kaydet_ ile '
        'örnek bir dosya alabilirsiniz.',
    '• **Yıl ekle:** EPİAŞ Şeffaflık Platformu › Üretim › Gerçek Zamanlı Üretim sayfasından istediğiniz dönemi dışa '
        'aktarıp seçin. Eksik sıfırlı ondalıklar düzeltilir, negatif gece güneş değerleri 0 yapılır, karbon yoğunluğu '
        'varsayılan veriyle aynı yöntemle hesaplanır. O yılın yükü için ayrıca makine verisi eklenmelidir.',
    '• **Emisyon katsayıları:** ETKB yeni faktörleri yayımladığında yakıt türü başına tCO2/MWh ve tCO2-eşd/MWh '
        'değerlerini içeren dosyayı seçin. Etkin olduğunda tüm yıllar yeni katsayılarla yeniden hesaplanır. Aynı anda '
        'tek katsayı paketi etkin olur.',
    'Paket listesinde anahtarla açıp kapatabilir, çöp kutusuyla silebilirsiniz. Kapatılan paketin makineleri ve günleri '
        'listelerden çıkar; silinen paketle kaydedilmiş geçmiş senaryolar açılamaz.',
    '**Etiket:** Tesis ölçümü olarak eklenen bir makine seçildiğinde alt bilgide _“Tesis ölçümü (Balıkesir)”_, örnek '
        'veride _“Örnek yük, Balıkesir tesisi değil”_ yazar; kaynakta kullanılan şebeke yılı ve katsayı paketi gösterilir.',
    '**Formül** bu ekrandan değiştirilmez: masaüstü, mobil ve Excel aynı formülü kullanmalıdır. Formül değişikliği '
        '_shared/FORMUL.md_ sürüm süreciyle geliştiriciler tarafından yapılır.',
  ]),
  ('contact', 'İletişim', [
    '**İletişim** sekmesinde geliştiricilerin ve danışmanın telefon ve e-posta bilgileri bulunur. _E-posta gönder_ '
        'e-posta uygulamanızı, telefon numarası arama ekranını açar; _Kopyala_ bilgileri panoya alır.',
  ]),
  ('keys', 'Dokunmatik kullanım', [
    'Masaüstü sürümdeki klavye kısayollarının telefondaki karşılıkları:',
    '• **Ana sayfa (Esc):** Sol üstteki ⌂ düğmesi ya da telefonun geri tuşu.',
    '• **Kılavuz (F1):** Diğer › Kılavuz.',
    "• **Delti ayarları (Ctrl+,):** Delti'ye Sor › ⚙ ya da Delti kartı › Daha fazla › Delti ayarları…",
    "• **Sekmeler (Ctrl+1…9):** Alttaki çubuk: Senaryo · En temiz saat · Delti'ye sor · Geçmiş · Diğer (Hesabı Göster, "
        'Veri, Kılavuz, Kaynaklar, İletişim).',
    '• **Senaryoyu kaydet (Ctrl+S):** Sonuç kartındaki _Senaryoyu kaydet_.',
    '• **En iyi saati bul (Ctrl+B):** Zaman penceresi kartındaki _En iyi saati bul_.',
    "• **Geçmiş'te sil (Delete):** Kaydın yanındaki çöp kutusu.",
    '• **Değer değiştirme (↑ ↓):** Açılır listeye dokunup seçin; kaydırıcıyı parmakla sürükleyin.',
  ]),
  ('sources', 'Veri ve sınırlılıklar', [
    '• **EPİAŞ 2025:** 8.760 saatlik kaynak bazında üretim; her saatin karbon yoğunluğu buradan hesaplanır.',
    '• **ETKB 2023:** Yakıt türü başına resmî emisyon faktörleri.',
    '• **Zenodo:** Bir imalat tesisindeki makinelerin temizlenmiş enerji ölçümleri (7 makine).',
    '**Sınırlılıklar:** Yük örnek veridir; kaydırma aynı gün içindedir; hesap saatlik ortalamayla yapılır; Delti\'nin '
        'açıklamaları için internet ve API anahtarı gerekir. Para/TL kazancı, CBAM hesabı, sensör bağlantısı ve otomatik '
        'makine kontrolü kapsam dışıdır.',
  ]),
];

class GuideScreen extends StatefulWidget {
  const GuideScreen({super.key, this.section});
  final String? section;

  @override
  State<GuideScreen> createState() => _GuideScreenState();
}

class _GuideScreenState extends State<GuideScreen> {
  final Map<String, GlobalKey> _keys = {for (final s in sections) s.$1: GlobalKey()};

  void _go(String key) {
    final ctx = _keys[key]!.currentContext;
    if (ctx != null) Scrollable.ensureVisible(ctx, duration: const Duration(milliseconds: 300));
  }

  @override
  void initState() {
    super.initState();
    if (widget.section != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _go(widget.section!));
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          th.SectionCard(
            title: 'İçindekiler',
            child: Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final s in sections)
                  ActionChip(
                    label: Text(s.$2, style: const TextStyle(color: th.primaryDark, fontSize: 12.5)),
                    backgroundColor: th.primarySoft,
                    side: BorderSide.none,
                    onPressed: () => _go(s.$1),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          for (final (key, title, paras) in sections) ...[
            Container(
              key: _keys[key],
              child: th.SectionCard(
                titleWidget: Text(title,
                    style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: th.primaryDark)),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (final p in paras)
                      p.startsWith('• ') ? RichPara(p.substring(2), bullet: true) : RichPara(p),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
          ],
          const th.Muted('Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo', size: 12),
        ],
      ),
    );
  }
}
