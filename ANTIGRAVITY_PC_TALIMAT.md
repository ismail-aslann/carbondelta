# CarbonDelta — PC (Windows EXE) Yapım Talimatı

> Bu dosyanın tamamını Antigravity'ye ver ve şunu yaz:
> **"Bu dosyayı baştan sona oku. Görevleri sırayla yap. Her görevin sonundaki KONTROL maddeleri geçmeden bir sonraki göreve geçme. Formülü değiştirme."**

---

## 0. Proje bağlamı (ajan için)

CarbonDelta, endüstriyel bir makinenin elektrik yükünü günün başka saatine kaydırmanın şebeke karbon emisyonuna etkisini **yüzde olarak** hesaplayan bir masaüstü karar destek uygulamasıdır.

- Hesap **deterministik**, internetsiz çalışır. Hesapta yapay zekâ YOK.
- Yapay zekâ (LLM API) yalnızca hesaplanmış sayıları Türkçe açıklama metnine çevirir.
- Uygulama hiçbir makineye müdahale etmez; karar her zaman kullanıcıdadır.
- Ekranda her zaman şu etiket görünür: **"Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo"**
- Kapsam dışı: para/TL kazanç vaadi, CBAM hesabı, IoT/sensör bağlantısı, otomatik makine kontrolü.

**Ortam:** Windows 10/11, Python 3.11, proje klasörü `C:\Users\ISMO\carbondelta`, sanal ortam `.venv` (zaten var). Komutları Windows cmd sözdizimiyle çalıştır.

**Teknoloji:** Python 3.11 · pandas (yalnızca veri yükleme/hazırlık) · PySide6-Essentials (arayüz) · matplotlib QtAgg (grafik) · sqlite3 (standart kütüphane) · pytest · openpyxl · python-dotenv · PyInstaller.

Bağımlılıklar kurulu değilse:
```bat
.venv\Scripts\activate
pip install --timeout 120 --retries 10 PySide6-Essentials matplotlib pandas pytest openpyxl pyinstaller python-dotenv
```
`PySide6` (tam paket) KURMA; WebEngine gereksiz ve çok büyük.

---

## 1. Değişmez kurallar

1. Hesap formülü Bölüm 3'te kilitli. Değiştirme, "iyileştirme", yuvarlama ekleme.
2. Hesap kodu yalnızca `engine/` içinde. Arayüz (`desktop/`) formül içermez, `engine` fonksiyonlarını çağırır.
3. `engine/core.py` pandas KULLANMAZ; düz Python listeleri ve float ile çalışır (mobil Dart sürümü buna satır satır kopyalanacak).
4. Ham veri `data_raw/` altında kalır, git'e girmez. Uygulama yalnızca `shared/assets/` okur.
5. Ham veri SQLite'a yazılmaz. SQLite yalnızca kullanıcının hesap özetlerini tutar.
6. API anahtarı `.env` dosyasında; koda gömülmez, commit edilmez.
7. UI metinleri Türkçe; kod, değişken ve fonksiyon adları İngilizce.
8. Her görev sonunda testleri çalıştır ve git commit at.

---

## 2. Hedef klasör yapısı

```
carbondelta/
  .gitignore
  CLAUDE.md                  (varsa dokunma)
  data_raw/
    karbondeltaveri/         (ham CSV'ler, git'e girmez)
  data_build/
    build_assets.py
  shared/
    FORMUL.md
    assets/
      epias_2025.csv
      loads_hourly.csv
      machines.json
    golden/
      vectors.json
    prompts/
      ai_functions.json
  engine/
    __init__.py
    core.py                  (saf hesap)
    data.py                  (asset yükleme)
    best_window.py
    make_golden.py
    tests/
      test_core.py
      test_reference.py
      test_golden.py
      test_ai_validator.py
  desktop/
    __main__.py
    app.py
    main_window.py
    chart_widget.py
    history_db.py
    ai_client.py
    resources.py
  excel/
    dogrulama.xlsx
  carbondelta.spec
  build.bat
  requirements.txt
  .env.example
  README.md
```

---

## 3. Kilitli formül (shared/FORMUL.md ile aynı)

**Veri**
- `CI(D, h)`: `epias_2025.csv` → `Karbon_Yogunlugu_tCO2_MWh` (varsayılan) veya `Karbon_Yogunlugu_tCO2esd_MWh`. Birim tCO2/MWh = kgCO2/kWh.
- `kWh(M, D, h)`: `loads_hourly.csv` → `Saatlik_Tuketim_kWh`. `h = 0..23`.

**Girdiler:** makine `M`, gün `D`, kaynak başlangıç saati `s`, pencere uzunluğu `L` (saat), hedef başlangıç saati `t`, kaydırma oranı `p` (0–1), `restricted` (kullanıcının kısıtlı saatleri kümesi).
Parametrik mod: `kWh(M,D,h)` yerine kullanıcının girdiği sabit kWh/saat değeri kullanılır, formül aynıdır.

**Hesap** (toplama sırası her zaman i = 0'dan L-1'e):
```
E_i            = p × kWh(M, D, s+i)
B              = Σ E_i × CI(D, s+i)          # standart saat emisyonu (kgCO2)
S              = Σ E_i × CI(D, t+i)          # seçilen saat emisyonu (kgCO2)
delta_pct      = (S − B) / B × 100           # ANA YÜZDE, eksi = daha düşük emisyon
daily_kg       = Σ_{h=0..23} kWh(M,D,h) × CI(D,h)
daily_delta_pct= (S − B) / daily_kg × 100
```

**Durum (status) kuralları** — öncelik sırasıyla kontrol et:
| status | koşul | sonuç |
|---|---|---|
| `non_shiftable` | makinenin rolü `Kayamayan_Kisitli_Yuk` (ex_a, php_c) | hesap yok |
| `out_of_range` | `s+L > 24` veya `t+L > 24` veya `L < 1` veya `p` 0–1 dışında | hesap yok |
| `restricted_conflict` | `{t..t+L-1}` ∩ `restricted` boş değil | hesap yok |
| `same_window` | `s == t` | delta = 0 |
| `no_load` | `B == 0` | yüzde yok |
| `ok` | diğer | tam sonuç |

**Sayısal:** iç hesap tam double; yuvarlama SADECE ekranda (2 ondalık).

**best_window:** aynı `M, D, s, L, p, restricted` için `t = 0..24-L` aralığındaki tüm geçerli değerleri dene; en düşük `S` olanı seç; eşitlikte en küçük `t`. Deterministik; AI yalnızca açıklar.

**Referans sonuçlar (testte sabit olmalı):**
1. El hesabı: kWh=[10,20], kaynak CI=[0.5,0.4], hedef CI=[0.4,0.3], p=1 → B=13, S=10, delta_pct = −23.076923…
2. Gerçek veri: `comp_b`, `2025-07-15`, s=3, L=3, t=18, p=1, tCO2 →
   B = 42.613384, S = 35.957618, delta_pct = −15.6190, daily_delta_pct = −2.1542 (4 ondalık tolerans)

---

## 4. Ham veri şeması (data_raw/karbondeltaveri/)

**`1_EPIAS_2025_Saatlik_Karbon_Yogunlugu_Temiz.csv`** — 8.760 satır, virgül ayraçlı, ondalık nokta.
Sütunlar: `Tarih_Saat_Anahtari, Tarih, Saat, Saat_No, Yurtici_Toplam_Uretim_MWh, EPIAS_Net_Toplam_MWh, Dogal_Gaz_MWh, Barajli_MWh, Linyit_MWh, Akarsu_MWh, Ithal_Komur_MWh, Ruzgar_MWh, Gunes_MWh, Fuel_Oil_MWh, Jeotermal_MWh, Asfaltit_Komur_MWh, Tas_Komur_MWh, Biyokutle_MWh, Atik_Isi_MWh, Uluslararasi_Net_MWh, Toplam_Emisyon_tCO2, Toplam_Emisyon_tCO2esd, Karbon_Yogunlugu_tCO2_MWh, Karbon_Yogunlugu_tCO2esd_MWh, Yenilenebilir_Payi_Yuzde, Fosil_Payi_Yuzde, Baskin_Kaynak`

**`3_CarbonDelta_Ana_Veri_Seti_Saatlik_Birlesik.csv`** — 44.136 satır (7 makine).
Sütunlar: `AssetId, AssetType, CarbonDelta_Role, Tarih_Saat_Anahtari, Tarih, Saat, Saat_No, Saatlik_Tuketim_kWh, Saatlik_Ortalama_Guc_kW, EPIAS_Karbon_Yogunlugu_tCO2_MWh, EPIAS_Karbon_Yogunlugu_tCO2esd_MWh, Standart_Saat_Emisyon_kgCO2, Standart_Saat_Emisyon_kgCO2esd, EPIAS_Yenilenebilir_Payi_Yuzde, EPIAS_Fosil_Payi_Yuzde, EPIAS_Baskin_Kaynak`

**`0_Makine_Envanteri_ve_Temizlik_Ozeti.csv`** — 13 makine, UTF-8 BOM'lu.
Sütunlar: `AssetId, AssetType, CarbonDelta_Role, Paket_Durumu, Tam_24_Saatlik_Gun_Sayisi, …, Ilk_Tam_Gun, Son_Tam_Gun`. Ana paket: `Paket_Durumu == "Evet (Ana Paket)"` → 7 makine: comp_b, ex_a, mh_a, mix_c, p_i, php_c, u_e.

**`2_ETKB_2023_Resmi_Emisyon_Faktorleri_Tablosu.csv`** — emisyon faktörleri (şeffaflık ekranında gösterilecek).

Not: Yük verisi İrlanda'daki bir tesisten, saat numarasıyla Türkiye şebekesine eşlenmiş örnek veridir. Bu yüzden ekrandaki "örnek yük" etiketi zorunludur.

---

## GÖREV 1 — Klasör düzeni ve git

1. `C:\Users\ISMO\carbondelta` içinde `data_raw` klasörü yoksa oluştur.
2. Kökte duran `karbondeltaveri` klasörünü ve kökteki tüm `.zip` dosyalarını `data_raw\` içine taşı. Klasör iç içe çıkmışsa (`karbondeltaveri\karbondeltaveri\`) düzelt.
3. `.gitignore` içeriği en az şu olsun: `.venv/`, `data_raw/`, `__pycache__/`, `*.pyc`, `.env`, `dist/`, `build/`, `.pytest_cache/`
4. `shared/FORMUL.md` yoksa Bölüm 3'ü içine yaz.
5. `requirements.txt` ve `.env.example` (`LLM_PROVIDER=gemini`, `LLM_API_KEY=`, `LLM_MODEL=`) oluştur.
6. Git yoksa `git init`. İlk commit.

**KONTROL**
- `data_raw\karbondeltaveri\1_EPIAS_2025_Saatlik_Karbon_Yogunlugu_Temiz.csv` mevcut.
- `git status` çıktısında `data_raw`, `.venv`, `.zip` YOK.

---

## GÖREV 2 — Asset paketleme (`data_build/build_assets.py`)

Script ham veriden küçük asset dosyaları üretir:

1. `shared/assets/epias_2025.csv`: `Tarih, Saat_No, Karbon_Yogunlugu_tCO2_MWh, Karbon_Yogunlugu_tCO2esd_MWh, Yenilenebilir_Payi_Yuzde, Fosil_Payi_Yuzde, Baskin_Kaynak` + her kaynak için yüzde pay sütunu (`<Kaynak>_Pay_Yuzde = <Kaynak>_MWh / Yurtici_Toplam_Uretim_MWh × 100`). Bu paylar AI'ın "saat nedeni" açıklaması içindir.
2. `shared/assets/loads_hourly.csv`: dosya 3'ten `AssetId, Tarih, Saat_No, Saatlik_Tuketim_kWh`.
3. `shared/assets/machines.json`: ana paketteki 7 makine, her biri `{id, type, role, shiftable (bool), first_day, last_day, days: [verisi olan günler listesi]}`.
4. Ondalıkları KIRPMA; ham değerleri olduğu gibi yaz.
5. Assert: EPİAŞ 8.760 satır ve tekil `(Tarih, Saat_No)`; her `(AssetId, Tarih)` için tam 24 saat (0..23).
6. Sonunda satır sayılarını yazdır.

Çalıştır: `python data_build\build_assets.py`

**KONTROL**
- Çıktı: EPİAŞ **8760**, yük **44136**, makine **7**.
- `machines.json` içinde ex_a ve php_c `shiftable: false`.
- Commit.

---

## GÖREV 3 — Hesap motoru (`engine/`)

**ÖNCE TESTLERİ YAZ, SONRA KODU.**

`engine/core.py` (pandas yok):
```python
@dataclass(frozen=True)
class Result:
    status: str               # ok | non_shiftable | out_of_range | restricted_conflict | same_window | no_load
    shifted_kwh: float
    baseline_kg: float        # B
    scenario_kg: float        # S
    delta_pct: float | None
    daily_kg: float
    daily_delta_pct: float | None
    source_hours: list[int]
    target_hours: list[int]

def simulate(load_kwh: list[float], ci: list[float], s: int, L: int, t: int, p: float,
             restricted: set[int] = frozenset(), shiftable: bool = True) -> Result
```
- `load_kwh` ve `ci` 24 elemanlı listeler.
- Bölüm 3'teki formül ve status kuralları birebir.

`engine/best_window.py`: `best_window(load_kwh, ci, s, L, p, restricted, shiftable) -> (t, Result) | None`

`engine/data.py`: asset dosyalarını bir kez okur (pandas kullanabilir), şu fonksiyonları sağlar:
- `machines() -> list[dict]`
- `days_for(asset_id) -> list[str]`
- `load_24(asset_id, date) -> list[float]`
- `ci_24(date, kind="tCO2") -> list[float]`
- `mix_at(date, hour) -> dict` (kaynak payları, baskın kaynak, yenilenebilir %)
- Asset klasörünü `desktop/resources.py` içindeki `resource_path()` ile bulsun (PyInstaller uyumu).

Testler (`engine/tests/`):
- `test_core.py`: el hesabı referansı; her status durumu için en az bir test; p=0.5 yarı yük; `same_window` → delta 0.
- `test_reference.py`: gerçek veri referansı (comp_b, 2025-07-15, s=3, L=3, t=18, p=1) → Bölüm 3'teki değerler, 4 ondalık.
- best_window için: dönen t gerçekten minimum S'ye sahip; kısıtlı saatleri atlıyor.

Çalıştır: `python -m pytest engine -q`

**KONTROL**
- Tüm testler yeşil.
- comp_b referansı: delta_pct ≈ −15.6190, daily_delta_pct ≈ −2.1542.
- Commit.

---

## GÖREV 4 — Golden vektörler ve Excel doğrulaması

`engine/make_golden.py` (sabit seed = 42):
1. 30 senaryo üret: 7 makineden, farklı aylardan. En az 3 `non_shiftable`, 3 `restricted_conflict`, 2 parametrik mod, 2 `no_load` (yükün 0 olduğu saatler), 2 `same_window`, geri kalanı `ok`.
2. Her senaryo için girdileri (24 kWh, 24 CI, s, L, t, p, restricted, shiftable) ve beklenen tüm `Result` alanlarını `shared/golden/vectors.json`'a yaz. Float'ları `repr()` hassasiyetinde yaz.
3. `openpyxl` ile `excel/dogrulama.xlsx` üret: her `ok` senaryosu bir satır; B ve S'yi **Excel formülüyle** (SUMPRODUCT) hesapla; yanında Python sonucu ve `fark` sütunu.
4. `engine/tests/test_golden.py`: vectors.json'daki her senaryoyu `simulate` ile çalıştırıp 1e-9 toleransla karşılaştırır.

**KONTROL**
- `python -m pytest engine -q` yeşil.
- `dogrulama.xlsx` Excel'de açıldığında fark sütunu 2 ondalıkta her satırda 0,00.
- Commit + push. (Mobil taraf bu dosyalara bağlı.)

---

## GÖREV 5 — Masaüstü ana ekran (`desktop/`)

Çalıştırma: `python -m desktop`

`desktop/resources.py`:
```python
def resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel
```

**Pencere düzeni** (başlık: "CarbonDelta — Emisyon Potansiyeli Karar Destek"):

Sol panel (girdiler):
- Makine seçici (machines.json; ad + tür). Kayamayan makine seçilince kaydırma kontrolleri pasif ve altında: "Bu yük kaydırılamaz (sürekli/kısıtlı süreç). Öneri üretilmez."
- Gün seçici (QDateEdit/takvim; yalnızca o makinenin `days` listesindeki günler seçilebilir; geçersiz günde en yakın geçerli güne atla).
- Kaynak başlangıç saati (0–23), pencere uzunluğu (1–12), hedef başlangıç saati (0–23).
- Kaydırma oranı kaydırıcısı (%0–100, varsayılan %100).
- Kısıtlı saatler: 24 adet işaretlenebilir düğme (saat çipleri).
- Emisyon tipi: tCO2 / tCO2-eşd.
- Parametrik mod anahtarı + sabit kWh/saat girişi.
- "En iyi saati bul" düğmesi → `best_window` sonucunu hedef saate uygular.

Sağ üst: matplotlib grafik (QtAgg)
- 24 saatlik karbon yoğunluğu çizgisi (sol eksen, tCO2/MWh).
- Makinenin saatlik yükü çubuk grafik (sağ eksen, kWh), soluk renk.
- Kaynak pencere gri gölge, hedef pencere yeşil (veya senaryo kötüyse kırmızı) gölge.
- Kısıtlı saatler taralı.

Sağ orta: sonuç kartı
- Büyük yazı: `delta_pct` (2 ondalık, işaretiyle). Eksi → yeşil "daha düşük emisyon potansiyeli"; artı → kırmızı "bu kaydırma emisyonu ARTIRIR".
- Küçük: standart ve senaryo kgCO2, kaydırılan kWh, günlük etki %.
- status `ok` değilse ilgili Türkçe açıklama.

Alt: AI açıklama kutusu (Görev 7'ye kadar şablon metin göstersin).

Alt bilgi (her zaman görünür): **"Örnek yük, Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo"**

Davranış:
- Her girdi değişiminde 50 ms debounce ile `engine.simulate` çağrılır, grafik ve kart güncellenir.
- Uygulama açılışında asset'ler bir kez yüklenir.

**KONTROL**
- comp_b, 2025-07-15, kaynak 3, uzunluk 3, hedef 18, %100 → kartta **−15,62 %**.
- ex_a seçilince kaydırma kontrolleri pasif.
- Hedef saati 21+ ve uzunluk 4 → "aralık dışı" mesajı, çökme yok.
- Commit.

---

## GÖREV 6 — Şeffaflık sekmesi ve geçmiş (SQLite)

Sekmeler: **Senaryo** · **Hesabı Göster** · **Geçmiş** · **Kaynaklar**

Hesabı Göster:
- Kullanılan formül (Bölüm 3, okunur Türkçe).
- Tablo: kaynak ve hedef saatlerin her biri için saat, kWh, CI, emisyon.
- ETKB emisyon faktörü tablosu.
- "CSV olarak dışa aktar" düğmesi.

Geçmiş (`desktop/history_db.py`):
- DB yolu: `%APPDATA%\CarbonDelta\history.db` (klasör yoksa oluştur).
- Tablo `history`: `id INTEGER PK, created_at TEXT, asset_id TEXT, date TEXT, s INT, L INT, t INT, p REAL, restricted TEXT, mode TEXT, ci_kind TEXT, status TEXT, delta_pct REAL, daily_delta_pct REAL, baseline_kg REAL, scenario_kg REAL`
- Ana ekranda "Kaydet" düğmesi; Geçmiş sekmesinde liste; çift tıkla → senaryoyu geri yükle; "Sil" düğmesi.

Kaynaklar: EPİAŞ, ETKB, Zenodo açıklamaları ve "örnek yük" notu.

**KONTROL**
- Uygulamayı kapatıp açınca geçmiş kayıtlar duruyor.
- CSV dışa aktarma çalışıyor.
- Commit.

---

## GÖREV 7 — AI açıklama katmanı

`shared/prompts/ai_functions.json`: aşağıdaki 15 işlevin her biri için `id`, `title`, `system`, `user_template`, `fallback_template`.

| id | İşlev | Girdi | Çıktı |
|---|---|---|---|
| nl_input | Doğal dil girişi | kullanıcı cümlesi + makine listesi | JSON `{asset_id, s, L, t, p}` — motor doğrular |
| scenario_summary | Senaryo özeti | Result + girdiler | 2 cümle |
| hour_reason | Saat nedeni | kaynak/hedef saatlerin kaynak payları | neden düşük/yüksek |
| scenario_compare | Senaryo kıyası | iki Result | hangisi daha iyi, kaç puan |
| best_window_explain | Otomatik pencere açıklaması | best_window sonucu | neden bu saat |
| non_shiftable_warn | Kayamayan yük uyarısı | makine rolü | neden öneri yok |
| restricted_warn | Kısıtlı saat uyarısı | çakışan saatler | ne yapılabilir |
| no_load_warn | Sıfır yük uyarısı | B=0 | açıklama |
| reverse_effect_warn | Ters etki uyarısı | delta_pct > 0 | bu kaydırma emisyonu artırır |
| daily_impact | Günlük etki yorumu | daily_delta_pct | tesis-gün ölçeği |
| season_note | Mevsim notu | aynı saatlerin aylık ortalaması | sonuç mevsime özgü mü |
| history_summary | Geçmiş özeti | son 10 kayıt | en iyi/kötü senaryolar |
| term_explain | Terim açıklayıcı | terim | sade tanım |
| data_source_explain | Veri kaynağı açıklaması | sabit | EPİAŞ/ETKB/Zenodo |
| report_sentence | Rapor cümlesi | Result | sunuma kopyalanacak tek cümle |

`desktop/ai_client.py`:
- `.env`'den `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` okur (python-dotenv). Gemini veya Claude, ikisi için basit HTTP istemcisi; `temperature = 0`.
- İstek **QThread** içinde; arayüz donmaz; 15 sn zaman aşımı.
- LLM'e yalnızca motorun ürettiği sayılar JSON olarak gider. Sistem talimatı: "Yalnızca verilen sayıları kullan, yeni sayı yazma, Türkçe yaz, en fazla 3 cümle."
- **Sayı doğrulayıcı** (`validate_numbers(text, allowed) -> bool`): metindeki tüm sayıları regex ile çek (Türkçe virgül ve nokta ondalığı, eksi işareti, yüzde dahil); izin verilen küme = girdilerdeki tüm sayıların 0, 1 ve 2 ondalıklı yuvarlanmış halleri + saatler (0–24). Kümede olmayan bir sayı varsa metni ATMA, yerine `fallback_template` göster.
- İnternet/anahtar yoksa veya hata olursa: AI kutusunda "AI metni çevrimdışı; hesap sonucu geçerlidir." + fallback metni. Yüzde ekranda görünmeye devam eder.
- `engine/tests/test_ai_validator.py`: izinli sayı geçer, uydurma sayı reddedilir, Türkçe ondalık ("−15,62") doğru okunur.

Arayüze bağla:
- Her hesapta otomatik: status'a göre uygun uyarı işlevi veya `scenario_summary` (+ delta>0 ise `reverse_effect_warn`).
- "Neden bu saat?" düğmesi → `hour_reason`.
- "En iyi saati bul" sonrası → `best_window_explain`.
- Üstte doğal dil kutusu: "Kompresörü 3'ten 18'e al" → `nl_input` → dönen JSON motor kurallarıyla doğrulanır, geçerliyse girdilere uygulanır.
- "Senaryoyu karşılaştır": son kaydedilen ile mevcut → `scenario_compare`.
- Geçmiş sekmesinde "Özetle" → `history_summary`.

**KONTROL**
- `python -m pytest engine -q` yeşil.
- Wi-Fi kapalıyken uygulama açılıyor, yüzde görünüyor, AI kutusu çevrimdışı mesajı veriyor.
- `.env` git'e girmiyor.
- Commit.

---

## GÖREV 8 — EXE paketleme

`carbondelta.spec` (PyInstaller):
- Giriş: `desktop/__main__.py`, `--windowed` (konsol yok), ad `CarbonDelta`.
- `datas`: `shared/assets`, `shared/prompts`.
- matplotlib backend QtAgg; gereksiz Qt modüllerini hariç tut (WebEngine, Multimedia vb.).
- Önce **onedir** üret (hızlı açılış). İstenirse ikinci bir onefile hedefi.
- İkon varsa ekle.

`build.bat`:
```bat
call .venv\Scripts\activate
python -m pytest engine -q || exit /b 1
pyinstaller carbondelta.spec --noconfirm --clean
```

`.env` EXE'ye GÖMÜLMEZ. Uygulama `.env`'i EXE'nin yanındaki klasörden okur; yoksa AI kapalı çalışır.

`README.md`: kurulum, çalıştırma, test, EXE üretme, `.env` ayarı, bilinen sınırlılıklar (örnek yük, aynı gün içinde kaydırma, AI internet gerektirir).

**KONTROL**
- `build.bat` hatasız biter, `dist\CarbonDelta\CarbonDelta.exe` oluşur.
- EXE'ye çift tıklayınca açılıyor; comp_b referans senaryosu −15,62 % veriyor.
- `dist\CarbonDelta` klasörü **Python kurulu olmayan** başka bir bilgisayarda açılıyor.
- Commit + push.

---

## Son kabul listesi

- [ ] pytest tamamı yeşil (core, referans, golden, AI doğrulayıcı)
- [ ] Excel fark sütunu 0,00
- [ ] comp_b referansı ekranda −15,62 %
- [ ] Kayamayan makinede öneri yok
- [ ] Ters yönde kaydırmada kırmızı "emisyon artar" uyarısı
- [ ] İnternetsiz açılıyor, yüzde görünüyor
- [ ] AI metninde uydurma sayı yok (doğrulayıcı devrede)
- [ ] Alt bilgi etiketi her ekranda
- [ ] EXE temiz Windows'ta açılıyor
- [ ] `shared/assets`, `shared/golden/vectors.json`, `shared/FORMUL.md`, `shared/prompts/ai_functions.json` push edildi (mobil taraf bunları kullanıyor)

## Önemli veri bulgusu (rapor/sunum için)

2025 EPİAŞ verisinde yıllık ortalamada 03:00–06:00 en kirli, 17:00–21:00 en temiz saatlerdir. Raporun "14:00 → 03:00 kaydırma %20 daha düşük" örneği veriyle ters düşer (ortalamada ~%10,5 artış). Demo ve raporda örnek olarak "03:00 → 18:00" kullanın (comp_b, 2025-07-15: −15,62 %).
