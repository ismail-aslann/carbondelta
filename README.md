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

Açılışta demo senaryosu yüklenir: comp_b, 15.07.2025, 03:00–06:00 → 18:00–21:00, %100 → **−15,62 %**.

Sekmeler: **Senaryo** (girdiler, grafik, sonuç, açıklama) · **Hesabı Göster** (formül, saat saat
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

## EXE üretme

```bat
build.bat
```

Önce testleri çalıştırır, sonra PyInstaller ile `dist\CarbonDelta\CarbonDelta.exe` (onedir, konsolsuz)
üretir. `dist\CarbonDelta` klasörünün tamamı kopyalanarak Python kurulu olmayan bir bilgisayarda
çalıştırılabilir. İlk açılışta matplotlib font önbelleği oluşturulduğu için açılış birkaç saniye uzun sürer.

## AI ayarı (.env)

`.env.example` dosyasını `.env` olarak kopyalayın:

```
LLM_PROVIDER=gemini        # veya claude
LLM_API_KEY=...
LLM_MODEL=                 # boş: gemini-2.5-flash / claude-opus-5-5
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

## Klasörler

```
data_build/   ham veriden asset üretimi
engine/       hesap motoru (core.py saf Python, pandas yok) + testler
desktop/      PySide6 arayüzü (formül içermez, engine'i çağırır)
shared/       FORMUL.md, assets/, golden/, prompts/ — mobil (Dart) sürüm de bunları kullanır
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
