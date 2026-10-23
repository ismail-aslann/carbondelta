# BAÜN TTO III. İnovatif Fikirler Proje Pazarı — başvuru taslakları

Son başvuru: **6 Kasım 2026** · Ön değerlendirme ilanı: 11 Kasım 2026 · Etkinlik: 26 Kasım 2026
Başvuru e-postası: projepazari@balikesir.edu.tr · Tema: **Yeşil Teknolojiler ve Döngüsel Ekonomi**

## Dosyalar

| Dosya | Ne işe yarar |
|---|---|
| `CarbonDelta_Tam_Metin_Taslak.docx` | Tam metin içeriği. Resmî **TAM METİN** şablonuna bölüm bölüm aktarılır. |
| `CarbonDelta_Sunum_Taslak.pptx` | 10 dakikalık sunum (9 slayt, konuşmacı notlarında süre ve ne söyleneceği). Resmî **SUNUM ŞABLONU**na aktarılır. |
| `CarbonDelta_Poster_50x70_Taslak.pptx` | 50 × 70 cm dikey poster taslağı (organizatör basar). |
| `gorseller/` | Uygulama ekran görüntüleri ve grafikler (belgelerde kullanılanlar). |
| `sonuclar.json` | Belgelerdeki tüm rakamlar; motordan üretilir. |

Belgeleri yeniden üretmek (rakamlar veya metin değişirse):

```bat
.venv\Scripts\python basvuru\sonuclari_hesapla.py
basvuru\.araclar\Scripts\python basvuru\uret_tam_metin.py
basvuru\.araclar\Scripts\python basvuru\uret_sunum.py
```

`.araclar` klasörü yalnızca belge üretimi için ayrı bir Python ortamıdır (python-docx, python-pptx); git'e girmez.

## Gönderimden önce yapılacaklar

1. **Daha önce sunulmama şartı.** Proje daha önce bir kongre, yarışma vb. etkinlikte sunulmuş ya da ödül/patent
   almış olmamalı. Kaynak verilerde bir *“Ön Tasarım Raporu”* geçiyor: bu rapor bir ders/bitirme projesi
   kapsamında bir jüriye sunulduysa TTO'ya (projepazari@balikesir.edu.tr) sorun.
2. **Resmî şablonlar.** Siteden dört dosyayı indirin: Katılımcı Taahhütnamesi, Tam Metin, Sunum Şablonu,
   Başvuru Formu. Taslaklardaki içeriği bu şablonlara aktarın. Form veya taahhütname eksikse başvuru geçersiz.
3. **Sarı yer tutucular.** Tam metinde ve posterde: sunumu yapacak kişinin adı (ilk sırada olmalı), fakülte/bölüm,
   e-posta, EPİAŞ erişim tarihi, Zenodo DOI.
4. **Doğrulanacak künyeler.** 7552 sayılı İklim Kanunu'nun Resmî Gazete tarihi; ETKB 2023 faktör raporunun yayım
   yılı; Zenodo veri setinin DOI'si (veri setinin sayfasından).
5. **Benzerlik (%30 sınırı, Turnitin).** Metin özgün yazıldı; şablona aktarırken README, talimat veya kaynak
   sitelerden metin kopyalamayın. Bir projenin tek başvuru hakkı var.
6. **Gerçek veri (çok güçlendirir).** Balıkesir'deki bir tesisten bir haftalık saatlik kWh verisi alınabilirse
   Veri sekmesinden eklenir, “Tesis ölçümü (Balıkesir)” etiketiyle sonuçlar belgelere eklenir.

## Demo akışı (3 dakika)

Hazırlık: uygulama açık, **F11** tam ekran, internet olmasa da hesaplar çalışır (Delti şablon metin gösterir).

1. Ana ekran → **Son senaryo** kartı (Kompresör 03:00 → 18:00): “−%15,62”.
2. Senaryo: hedef saati 11:00'e çekin, sonucun değiştiğini gösterin; tekrar 18:00.
3. **Ctrl+B**: günün en temiz penceresi.
4. **Yıllık etki** sekmesi: 2025 toplamı, aylık grafik, “yıl boyu en temiz hedef”.
5. Delti'ye yazın: *Presi %50 ile 21'e kaydır* → **Senaryoya git**.
6. **Veri** sekmesini gösterin: “Tesisinizin kendi ölçümü buradan eklenir.”

## Jürinin sorabileceği sorular

- **“Yük kaydırınca gerçekten o kadar azalır mı?”** — Hesap ortalama saatlik yoğunlukla yapılıyor; gerçek etki
  o saatteki marjinal santrale bağlı. Sonuçlar karşılaştırma ve önceliklendirme için gösterge; marjinal faktör yol
  haritamızda.
- **“Veriniz Balıkesir'den mi?”** — Hayır, açık bir imalat veri seti; yöntemi göstermek için. Uygulama tesisin
  kendi ölçümünü doğrudan alıyor; pilot için Balıkesir'deki tesislerle çalışmak istiyoruz.
- **“Yapay zekâ yanlış sayı söylerse?”** — Söyleyemez: metindeki her sayı hesapla karşılaştırılıyor, uymazsa metin
  gösterilmiyor. Hesabı yapay zekâ değil, test edilmiş formül yapıyor.
- **“Para kazandırır mı?”** — Bu sürüm emisyona odaklanıyor; piyasa fiyatıyla maliyet etkisi yol haritasında.
  Ayrıca SKDM ve ETS ile emisyonun kendisi bir maliyet kalemine dönüşüyor.
- **“Rakip ürünlerden farkı?”** — Karbon muhasebesi yazılımları yıllık toplamı raporlar; CarbonDelta makine ve saat
  düzeyinde zamanlama kararına odaklanır, internetsiz çalışır, tesis verisiyle büyür.
