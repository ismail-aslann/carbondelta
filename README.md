# CarbonDelta — Emisyon Potansiyeli Karar Destek (PC)

Endüstriyel bir makinenin elektrik yükünü günün başka saatine kaydırmanın şebeke karbon
emisyonuna etkisini **yüzde olarak** hesaplayan Windows masaüstü uygulaması.

- Hesap **deterministik** ve internetsiz çalışır; hesapta yapay zekâ yoktur (formül: [shared/FORMUL.md](shared/FORMUL.md)).
- Yapay zekâ (LLM) yalnızca hesaplanmış sayıları Türkçe açıklama metnine çevirir; metindeki her sayı doğrulanır.
- Uygulama hiçbir makineye müdahale etmez; karar her zaman kullanıcıdadır.
- **Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo**

## Kurulum

Windows 10/11, Python 3.11.

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`PySide6` tam paketini kurmayın; `PySide6-Essentials` yeterlidir (WebEngine gerekmez).

## Çalıştırma

```bat
.venv\Scripts\activate
python -m desktop
```

Uygulama fare olmadan tamamen klavyeyle kullanılabilir: **Esc** ana sayfa, **F1** kullanma kılavuzu,
**Ctrl+1…7** sekmeler, **Tab** alanlar, **↑ ↓** değer/seçim, **Enter** düğme/satır, **Ctrl+S** kaydet,
**Ctrl+B** en iyi saat. Tam liste uygulamadaki *Kılavuz* sekmesindedir.

Uygulama başlangıç ekranıyla açılır (logo, son/demo senaryo kartı ve bölüm listesi; ↑ ↓ ve Enter ile
gezilebilir). Üst banttaki "Ana sayfa" düğmesi bu ekrana döner. Tasarım örnekleri `mockups/` klasöründedir.

Demo senaryosu: Kompresör (comp_b), 15.07.2025, 03:00–06:00 → 18:00–21:00, %100 → **−15,62 %**.

Sekmeler: **Senaryo** (girdiler, grafik, sonuç, açıklama) · **En Temiz Saat** (günün tüm geçerli
hedef pencerelerinin emisyona göre sıralaması ve grafiği; seçileni senaryoya uygular) · **Doğal Dil**
(cümle anlaşılınca Senaryo sekmesine hemen uygulanır, önizlemesi gösterilir) · **Hesabı Göster** (formül, saat saat
döküm, ETKB tablosu, CSV dışa aktarma) · **Geçmiş** (kayıtlı senaryolar; çift tık = geri yükle,
Sil, Özetle) · **Kaynaklar**.

Geçmiş veritabanı: `%APPDATA%\CarbonDelta\history.db` (yalnızca hesap özetleri; ham veri yazılmaz).

## Test

```bat
python -m pytest engine -q
```

| Dosya | Kapsam |
|---|---|
| `engine/tests/test_core.py` | El hesabı referansı, tüm durumlar (status), p = 0,5, best_window |
| `engine/tests/test_reference.py` | Gerçek veri referansı: comp_b, 2025-07-15, 3 → 18 = −15,6190 % / günlük −2,1542 % |
| `engine/tests/test_golden.py` | `shared/golden/vectors.json` içindeki 30 senaryo, 1e-9 tolerans |
| `engine/tests/test_explain.py` | Hesabı Göster dökümünün B ve S'ye birebir eşitliği |
| `engine/tests/test_ai_validator.py` | AI sayı doğrulayıcı, Türkçe ondalık, kural tabanlı doğal dil çözümleyici |

Golden vektörleri ve Excel doğrulamasını yeniden üretmek için (seed = 42):

```bat
python -m engine.make_golden
```

`excel/dogrulama.xlsx` dosyasında B ve S, Excel formülüyle (SUMPRODUCT) hesaplanır; `fark` sütunları 0,00 olmalıdır.

Asset dosyalarını ham veriden (`data_raw/karbondeltaveri/`, git'e girmez) yeniden üretmek için:

```bat
python data_build\build_assets.py
```

Uygulama ikonunu ve arayüz ok simgelerini yeniden üretmek için:

```bat
python data_build\make_icon.py
```

## EXE üretme

```bat
build.bat
```

Önce testleri çalıştırır, sonra PyInstaller ile `dist\CarbonDelta\CarbonDelta.exe` (onedir, konsolsuz)
üretir. `dist\CarbonDelta` klasörünün tamamı kopyalanarak Python kurulu olmayan bir bilgisayarda
çalıştırılabilir. İlk açılışta matplotlib font önbelleği oluşturulduğu için açılış birkaç saniye uzun sürer.

## Veri ekleme (yeni makine, yeni yıl, yeni katsayılar)

Uygulamadaki **Veri** sekmesinden (ana sayfada *Veri yönetimi*) eklenir; EXE'yi yeniden üretmek gerekmez.
Varsayılan 2025 verisi EXE içinde kalır; eklenenler `%APPDATA%\CarbonDelta\veri\<paket>\` altında
ayrı paketler olarak tutulur (açılıp kapatılabilir, silinebilir). Kod: `engine/packages.py`.

- **Makine:** `Tarih;Saat;kWh` (CSV/Excel). Her gün 24 tekrarsız saat ve o gün için şebeke verisi gerekir;
  eksik günler atlanır. Veri türü *örnek yük* ya da *tesis ölçümü* seçilir; alt bilgi etiketi buna göre değişir.
- **Yıl:** EPİAŞ Şeffaflık › Gerçek Zamanlı Üretim dışa aktarımı. Ondalık yazımları düzeltilir, negatif
  değerler 0 yapılır, karbon yoğunluğu varsayılan veriyle aynı yöntemle (kaynak üretimi × katsayı) hesaplanır.
- **Emisyon katsayıları:** Yeni ETKB faktörleri; etkin olunca tüm yıllar yeniden hesaplanır.
- **Formül** uygulamadan değiştirilmez (FORMUL.md sürüm süreci).

Testler kullanıcı paketlerinden etkilenmez (`conftest.py` boş geçici veri klasörü kullanır).

## Kurulum dosyası (başka bilgisayar için)

```bat
kurulum.bat
```

Testleri çalıştırır, EXE'yi üretir ve [Inno Setup 6](https://jrsoftware.org/isinfo.php) ile tek dosyalık
`dist_installer\CarbonDelta_Kurulum_<sürüm>.exe` sihirbazını oluşturur (Inno Setup yoksa:
`winget install JRSoftware.InnoSetup`). Sürüm numarası `desktop/version.py` içindedir; kurulum betiği
`installer/carbondelta.iss`.

Kullanıcı tarafında: dosyaya çift tıkla → İleri → Kur. Yönetici izni istemez;
`%LOCALAPPDATA%\Programs\CarbonDelta` içine kurulur, Başlat menüsüne ve (isteğe bağlı) masaüstüne kısayol
ekler, *Ayarlar › Uygulamalar*'da görünür ve kaldırıcısı vardır. Yeni sürüm aynı dosyayla üzerine kurulur.
Kaldırma, geçmişi ve eklenen veri paketlerini (`%APPDATA%\CarbonDelta`) silmez.

`.env` kurulum dosyasına **girmez**. AI anahtarı kurulumdan sonra uygulamadaki **Delti ayarları**
ekranından (`Ctrl+,`) girilir; anahtar yoksa uygulama AI'sız çalışır.
Sessiz kurulum: `CarbonDelta_Kurulum_<sürüm>.exe /VERYSILENT /TASKS=desktopicon`.

## Bilgisayara kurma (masaüstü uygulaması)

```bat
kur.bat
```

`dist\CarbonDelta` klasörünü `%LOCALAPPDATA%\Programs\CarbonDelta` içine kopyalar, masaüstüne ve
Başlat menüsüne **CarbonDelta** kısayolu ekler. Proje kökünde `.env` varsa kurulum klasörüne de
kopyalanır (AI açık olur). Kodu güncelledikten sonra `build.bat` ve ardından `kur.bat` çalıştırmak
yeterlidir; uygulama açıksa önce kapatın.

## AI ayarı (.env)

Uygulamadaki AI yardımcısının adı **Delti**'dir (maskot: logodaki delta üçgeninden türetildi,
`desktop/delti.py`). Delti hesap yapmaz; motorun sonuçlarını açıklar ve "Delti'ye Sor" sekmesinde
cümleleri senaryoya çevirir. Yanında her zaman "AI" etiketi durur; karar kullanıcıdadır.

**Uygulama içinden (önerilen):** Delti'ye Sor › *Delti'yi uyandır* / *⚙ Ayarlar*, ana sayfadaki *uyandır*
bağlantısı ya da `Ctrl+,` ile **Delti ayarları** açılır: sağlayıcı seçilir, anahtar yapıştırılır, *Bağlantıyı dene*
ile kontrol edilip kaydedilir. Anahtar `%APPDATA%\CarbonDelta\delti_ayarlar.json` içinde Windows DPAPI ile
şifreli durur (yalnızca aynı bilgisayardaki aynı kullanıcı çözebilir; güncelleme/kaldırma silmez). Kod:
`desktop/ai_settings.py`, `desktop/delti_settings.py`. Öncelik: ortam değişkeni > uygulama ayarı > `.env`.

**Dosyayla:** `.env.example` dosyasını `.env` olarak kopyalayın:

```
LLM_PROVIDER=gemini        # veya claude
LLM_API_KEY=...
LLM_MODEL=                 # boş: gemini-flash-lite-latest / claude-opus-5-5
```

- Geliştirmede `.env` repo kökünde, EXE ile kullanırken **EXE'nin yanında** (`dist\CarbonDelta\.env`) durur. EXE'ye gömülmez, git'e girmez.
- `.env` yoksa, anahtar boşsa veya internet yoksa uygulama AI'sız çalışır: açıklama kutusunda
  "AI metni çevrimdışı; hesap sonucu geçerlidir." ve şablon metin görünür; yüzde her zaman görünür.
- LLM'e yalnızca motorun ürettiği sayılar JSON olarak gider. Yanıttaki her sayı girdilerle
  karşılaştırılır (0, 1, 2 ondalık yuvarlama + saatler); veride olmayan bir sayı varsa AI metni
  gösterilmez, şablon metin gösterilir.
- Gemini isteği `temperature = 0` ile gider. Güncel Claude modelleri `temperature` parametresini kabul
  etmediği için Claude isteği `temperature` göndermez; bunun yerine `effort: low` kullanılır.
- 15 AI işlevinin istem ve şablonları: [shared/prompts/ai_functions.json](shared/prompts/ai_functions.json).

## Mobil (Android APK)

`mobile/` klasörü, bu masaüstü uygulamasının (EXE 1.1.0) Flutter/Dart ile yazılmış Android karşılığıdır.
Hiçbir özellik çıkarılmadan taşındı: Ana sayfa, Senaryo, En Temiz Saat, Delti'ye Sor, Hesabı Göster,
Geçmiş, Veri yönetimi, Kılavuz, Kaynaklar, İletişim ve Delti ayarları.

- Hesap motoru (`mobile/lib/engine/`) `engine/*.py` dosyalarının satır satır çevirisidir; formül `shared/FORMUL.md`.
- Veri ve AI şablonları `shared/assets` ve `shared/prompts` ile birebir aynıdır (`mobile/assets/shared`).
- **Golden test:** `shared/golden/vectors.json` içindeki 30 senaryo Dart motorunda 1e-9 toleransla
  aynı sonucu verir (`mobile/test/golden_test.dart`). Toplam 48 test.
- Demo: comp_b, 15.07.2025, 03:00 → 18:00, %100 → **−15,62 %** (EXE ile aynı).
- Delti anahtarı telefonda Android Keystore'da şifreli saklanır.

```powershell
cd mobile
flutter pub get
flutter test                  # 48 test (30 golden senaryo dahil)
flutter build apk --release   # build\app\outputs\flutter-apk\app-release.apk
```

Kurulabilir APK: GitHub **Releases** sayfasında `CarbonDelta_1.1.0.apk`. Ayrıntılar: [mobile/README.md](mobile/README.md).

## Klasörler

```
data_build/   ham veriden asset üretimi
engine/       hesap motoru (core.py saf Python, pandas yok) + testler
desktop/      PySide6 arayüzü (formül içermez, engine'i çağırır)
shared/       FORMUL.md, assets/, golden/, prompts/ — mobil (Dart) sürüm de bunları kullanır
mobile/       Flutter/Dart Android uygulaması (APK); hesap motoru engine/ ile birebir
excel/        dogrulama.xlsx
```

## Bilinen sınırlılıklar

- **Örnek yük:** Makine yükleri İrlanda'daki bir imalat tesisinden (Zenodo) alınmış ve saat
  numarasıyla Türkiye şebekesine eşlenmiş örnek veridir; Balıkesir tesisinin ölçümü değildir.
- **Aynı gün içinde kaydırma:** Pencere gece yarısını aşamaz (başlangıç + uzunluk ≤ 24); yük başka güne taşınmaz.
- **Saatlik çözünürlük:** Hesap saatlik ortalama karbon yoğunluğuyla yapılır; saat içi değişim yoktur.
- **AI internet gerektirir:** Açıklama metni için API anahtarı ve internet gerekir; hesap gerektirmez.
- **Kapsam dışı:** Para/TL kazanç vaadi, CBAM hesabı, IoT/sensör bağlantısı, otomatik makine kontrolü.
- 2025 EPİAŞ verisinde yıllık ortalamada 03:00–06:00 en kirli, 17:00–21:00 en temiz saatlerdir;
  demo ve raporda örnek olarak 03:00 → 18:00 kullanılmalıdır.
