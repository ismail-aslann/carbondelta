# Desktop (PySide6)
- Hesap yalnızca engine/ paketinden çağrılır; desktop/ içinde formül yazma.
- Qt bağlaması: PySide6-Essentials (WebEngine yok, kullanma). matplotlib backend: QtAgg.
- Asset yolu: PyInstaller altında sys._MEIPASS, geliştirmede repo kökü. Tek bir resource_path() fonksiyonu kullan.
- SQLite: %APPDATA%/CarbonDelta/history.db. Ham veri SQLite'a yazılmaz, yalnızca hesap özeti.
- AI çağrısı ayrı QThread'de; internet yoksa arayüz donmaz, yüzde görünmeye devam eder.
- API anahtarı .env / ortam değişkeni; koda gömme, commit etme.
