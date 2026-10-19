# CarbonDelta – ortak kurallar
- Hesap formülü shared/FORMUL.md'de kilitli. Formülü değiştirme; şüphe varsa dur ve sor.
- Hesap katmanında AI/LLM yok. LLM yalnızca engine çıktısını metne çevirir.
- Her hesap değişikliğinden sonra golden testleri çalıştır: Python `pytest engine`, mobil `flutter test`.
- Ham veri data_raw/ altında, asla commit etme. Uygulamalar sadece shared/assets/ okur.
- Ekranda her zaman "Örnek yük, Balıkesir tesisi değil" etiketi görünür.
- Kayamayan yükler (ex_a, php_c) için kaydırma önerisi üretme.
- Finansal vaat, CBAM, otonom makine kontrolü kapsam dışı.
- UI metinleri Türkçe. Kod ve değişken adları İngilizce.
- Ortam: Windows, Python 3.11, sanal ortam .venv. Komutları Windows cmd sözdizimiyle öner.
