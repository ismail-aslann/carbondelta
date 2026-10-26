# Mobile (Flutter) — CarbonDelta EXE 1.1.0'ın mobil karşılığı
- Hedef: EXE 1.1.0'daki her özellik mobilde de olacak; hiçbir şey çıkarılmaz.
- lib/engine/ Python engine/*.py dosyalarının satır satır çevirisidir. Formülü değiştirme.
- double kullan, toplama sırası i=0..L-1. Yuvarlama sadece UI'da (lib/ui/fmt.dart).
- Asset'ler EXE'nin shared/ klasöründen birebir kopyadır (assets/shared), elle düzenlenmez.
- Referans: comp_b, 2025-07-15, 03:00→18:00, %100 → −15,62 %.
- UI Türkçe; alt bilgi kaynak etiketi her ekranda.
