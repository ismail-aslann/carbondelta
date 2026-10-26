# CarbonDelta — Mobil (Android APK)

EXE 1.1.0'ın (ismail-aslann/carbondelta) mobil karşılığı. Endüstriyel bir makinenin elektrik yükünü
günün başka saatine kaydırmanın şebeke karbon emisyonuna etkisini **yüzde olarak** hesaplar.

- Hesap deterministik ve internetsiz; formül `shared/FORMUL.md` ile birebir (lib/engine/core.dart).
- Yapay zekâ (Delti) yalnızca hesaplanmış sayıları açıklar; metindeki her sayı doğrulanır.
- **Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo**

Demo: Kompresör (comp_b), 15.07.2025, 03:00–06:00 → 18:00–21:00, %100 → **−15,62 %**.

## Telefona kurulum (jüri)
1. `CarbonDelta_1.1.0.apk` dosyasını telefona aktarın (kablo, e-posta, mesajlaşma).
2. Dosyaya dokunun; "Bilinmeyen kaynaklardan yükleme" izni istenirse verin.
3. **CarbonDelta** ikonuyla açın. İnternet gerekmez; Delti açıklamaları için Delti'ye Sor › ⚙ ile
   Gemini veya Claude API anahtarı girilebilir (anahtar Android Keystore'da şifreli saklanır).

## Geliştirme
```powershell
flutter pub get
flutter analyze
flutter test                 # 48 test: motor, 30 golden senaryo (EXE ile 1e-9), AI doğrulayıcı, veri paketleri
flutter run                  # emülatör veya USB'li telefon
flutter build apk --release  # build\app\outputs\flutter-apk\app-release.apk
```

## Yapı
- `lib/engine/` — core, best_window, explain, insights, data, packages (Python engine/*.py'nin çevirisi)
- `lib/ai/` — ai_client (Gemini/Claude, sayı doğrulayıcı), ai_context (15 işlev, kural çözümleyici), ai_settings
- `lib/screens/` — Ana sayfa, Senaryo, En Temiz Saat, Delti'ye Sor, Hesabı Göster, Geçmiş, Veri, Kılavuz,
  Kaynaklar, İletişim, Delti ayarları
- `assets/shared/` — EXE'nin shared/assets ve shared/prompts dosyalarının birebir kopyası
- `test/golden/vectors.json` — EXE'nin engine/make_golden.py çıktısı

## Sınırlılıklar
Yük örnek veridir; kaydırma aynı gün içindedir; hesap saatlik ortalamayla yapılır; Delti için internet ve API
anahtarı gerekir. APK hata ayıklama anahtarıyla imzalıdır (ders demosu). Para/TL kazancı, CBAM, sensör bağlantısı
ve otomatik makine kontrolü kapsam dışıdır.
