# CarbonDelta – Kilitli Hesap Formülü (v1)

Bu dosya iki platformun (Python EXE, Dart APK) ve Excel doğrulamasının tek doğruluk kaynağıdır.
Değişiklik yalnızca iki ekip üyesinin onayıyla yapılır; değişince golden vektörler yeniden üretilir.

## Veri
- CI(D, h): `epias_2025.csv` içindeki `Karbon_Yogunlugu_tCO2_MWh` (varsayılan) veya `Karbon_Yogunlugu_tCO2esd_MWh`.
  Birim: tCO2/MWh ≡ kgCO2/kWh.
- kWh(M, D, h): `loads_hourly.csv` içindeki `Saatlik_Tuketim_kWh`. h = 0..23 (Saat_No).

## Girdiler
- M: makine, D: gün (YYYY-MM-DD), s: kaynak başlangıç saati, L: pencere uzunluğu (saat),
  t: hedef başlangıç saati, p: kaydırma oranı (0–1), restricted: kullanıcının kısıtlı saatleri (küme).
- Parametrik mod: kWh(M, D, h) yerine kullanıcının girdiği sabit kWh/saat kullanılır; formül aynıdır.

## Hesap
Her i = 0..L-1 için (toplama sırası daima i küçükten büyüğe):
- E_i = p × kWh(M, D, s+i)
- B = Σ E_i × CI(D, s+i)            (standart saatlerdeki emisyon, kgCO2)
- S = Σ E_i × CI(D, t+i)            (seçilen saatlerdeki emisyon, kgCO2)
- delta_pct = (S − B) / B × 100     (ANA YÜZDE; eksi = daha düşük emisyon potansiyeli)
- daily_kg = Σ_{h=0..23} kWh(M, D, h) × CI(D, h)
- daily_delta_pct = (S − B) / daily_kg × 100

## Kurallar (status alanı)
- `ok`: hesap geçerli.
- `non_shiftable`: CarbonDelta_Role == Kayamayan_Kisitli_Yuk (ex_a, php_c). Hesap yapılmaz.
- `out_of_range`: s+L > 24 veya t+L > 24 (gece yarısı sarması yok, aynı takvim günü).
- `restricted_conflict`: t..t+L-1 aralığı restricted ile kesişiyor.
- `no_load`: B == 0 (kaydırılacak yük yok). Yüzde gösterilmez.
- `same_window`: s == t. delta 0, kullanıcıya bilgi verilir.

## Sayısal kurallar
- İç hesap tam double (IEEE 754). Yuvarlama yalnızca ekranda, 2 ondalık.
- Golden test toleransı: 1e-9 (Python ↔ Dart). Excel kontrolü: 2 ondalıkta eşitlik.

## Otomatik pencere önerisi (best_window)
- Verilen M, D, s, L, p, restricted için t = 0..24-L arasındaki tüm geçerli değerler denenir,
  en düşük S seçilir. Eşitlikte en küçük t. Bu tamamen deterministiktir; AI yalnızca açıklar.

## Referans senaryolar (testlerde sabit)
1. El hesabı: kWh=[10,20], CI kaynak=[0.5,0.4], CI hedef=[0.4,0.3], p=1 → B=13, S=10, delta=−23.0769…%
2. Gerçek veri: comp_b, 2025-07-15, s=3, L=3, t=18, p=1 →
   B=42.613384 kg, S=35.957618 kg, delta=−15.6190 %, daily_delta=−2.1542 %
