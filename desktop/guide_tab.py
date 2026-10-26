"""Kullanma kılavuzu sekmesi: solda içindekiler, sağda anlatım (klavyeyle gezilebilir)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QTextBrowser, QWidget

from desktop import theme

K = "background:#eef1f4; border:1px solid #d6dde4; border-radius:4px; padding:1px 6px; font-family:Consolas; font-size:9pt;"


def _k(*keys: str) -> str:
    return " + ".join(f"<span style='{K}'>{k}</span>" for k in keys)


SECTIONS: list[tuple[str, str, str]] = [
    ("start", "Başlarken", f"""
<p><b>CarbonDelta</b>, bir makinenin elektrik yükünü günün başka saatine kaydırdığınızda şebeke karbon
emisyonunun <b>yüzde kaç</b> değişeceğini hesaplar. Hesap internetsiz ve yapay zekâsız yapılır; aynı
girdiler her zaman aynı sonucu verir. Uygulama hiçbir makineye müdahale etmez, <b>karar her zaman sizindir</b>.</p>
<p>Yük verisi İrlanda'daki bir tesisten alınmış <b>örnek</b> veridir (Balıkesir tesisi değildir); karbon
yoğunluğu EPİAŞ 2025 saatlik üretim verisi ve ETKB 2023 emisyon faktörleriyle hesaplanır.</p>
<p><b>Hızlı başlangıç:</b> Ana sayfada {_k('Enter')} ile <i>Yeni senaryo</i>yu açın, makineyi ve günü seçin,
standart ve hedef saatleri girin; sonuç kartı anında güncellenir.</p>"""),

    ("home", "Ana sayfa", f"""
<p>Uygulama ana sayfayla açılır. Arkadaki eğri, örnek bir günün 24 saatlik şebeke karbon yoğunluğudur
(en kirli ve en temiz saatler işaretlidir).</p>
<ul>
<li><b>Son senaryo / Demo senaryo kartı:</b> En son kaydettiğiniz senaryoyu (yoksa demo senaryoyu) tek adımda açar.</li>
<li><b>Yeni senaryo:</b> Senaryo ekranını temiz bir başlangıçla açar (kısıtlı saatler temizlenir, oran %100).</li>
<li><b>En temiz saat:</b> Seçtiğiniz yük için günün tüm hedef saatlerini emisyona göre sıralar.</li>
<li><b>Delti'ye sor:</b> Ne yapmak istediğinizi günlük dille yazarsınız.</li>
<li><b>Geçmiş</b>, <b>Hesap dökümü</b>, <b>Veri yönetimi</b>, <b>Kullanma kılavuzu</b>, <b>Kaynaklar</b>,
<b>İletişim</b>: ilgili ekranları açar.</li>
</ul>
<p>{_k('↑')} {_k('↓')} ile seçin, {_k('Enter')} ile açın; {_k('1')}…{_k('9')} rakamları satırı doğrudan açar.
Uygulamanın her yerinden {_k('Esc')} ile ana sayfaya dönersiniz.</p>"""),

    ("scenario", "Senaryo ekranı", f"""
<p><b>Makine ve gün:</b> Makineyi ve günü seçin. Takvimde yalnızca verisi olan günler seçilebilir; geçersiz bir gün
yazarsanız en yakın geçerli güne atlanır. <i>Havalandırma</i> ve <i>Pres ısıtma</i> sürekli/kısıtlı süreçtir;
bunlar seçildiğinde kaydırma alanları pasifleşir ve öneri üretilmez.</p>
<p><b>Emisyon tipi:</b> tCO2 (yalnızca CO2) veya tCO2-eşd (diğer sera gazlarının CO2 eşdeğeri dahil).<br>
<b>Parametrik mod:</b> Ölçülen yük yerine her saat için aynı kWh değerini kullanır (ör. yeni bir makineyi denemek için).</p>
<p><b>Zaman penceresi:</b></p>
<ul>
<li><b>Standart başlangıç:</b> Yükün normalde çalıştığı saat.</li>
<li><b>Pencere uzunluğu:</b> Kaç saatlik yükün taşınacağı (1–12).</li>
<li><b>Hedef başlangıç:</b> Yükün taşınacağı saat. Pencere gece yarısını aşamaz (başlangıç + uzunluk ≤ 24).</li>
<li><b>Kaydırma oranı:</b> Yükün ne kadarının taşınacağı (%0–100).</li>
<li><b>En iyi saati bul</b> ({_k('Ctrl', 'B')}): Aynı yük için en düşük emisyonlu hedef saati seçer.</li>
</ul>
<p><b>Kısıtlı saatler:</b> İşaretlediğiniz saatler hedef pencereye giremez (ör. vardiya, gürültü, bakım).
Çiplerde {_k('←')} {_k('→')} {_k('↑')} {_k('↓')} ile gezip {_k('Enter')} ile işaretleyin.</p>
<p><b>Grafik:</b> Çizgi saatlik karbon yoğunluğu, soluk çubuklar makinenin yüküdür. Gri bant standart pencere,
yeşil bant (emisyon düşüyorsa) ya da kırmızı bant (artıyorsa) seçilen penceredir. Fareyle bir saatin üzerine
gelince değerler görünür.</p>
<p><b>Sonuç kartı:</b> Büyük yüzde, taşınan enerjinin emisyonundaki değişimdir; eksi değer daha düşük emisyon
demektir. Altında bunun ne anlama geldiği, standart/seçilen pencere emisyonları, taşınan enerji ve makinenin
günlük toplam emisyonuna etkisi yazar. <b>Senaryoyu kaydet</b> ({_k('Ctrl', 'S')}) geçmişe ekler.</p>"""),

    ("results", "Durum mesajları", """
<ul>
<li><b>Daha düşük emisyon potansiyeli</b> (yeşil): Seçilen saatlerde şebeke daha temiz.</li>
<li><b>Bu kaydırma emisyonu ARTIRIR</b> (kırmızı): Seçilen saatlerde şebeke daha kirli.</li>
<li><b>Bu yük kaydırılamaz:</b> Makine sürekli/kısıtlı süreç; öneri üretilmez.</li>
<li><b>Aralık dışı:</b> Pencere aynı gün içinde kalmıyor; başlangıç veya uzunluğu küçültün.</li>
<li><b>Kısıtlı saatlerle çakışıyor:</b> Hedef pencere işaretli bir saati kapsıyor; hedefi değiştirin ya da
<i>En iyi saati bul</i>'u kullanın.</li>
<li><b>Aynı pencere:</b> Standart ve hedef aynı; emisyon değişmez.</li>
<li><b>Yük yok:</b> Standart pencerede makine çalışmıyor (0 kWh); yüzde hesaplanamaz.</li>
</ul>
<p><b>Neden oranı değiştirince yüzde değişmiyor?</b> Ana yüzde, taşınan enerjinin <i>kendi</i> emisyonundaki
oransal değişimdir; oran yarıya inince hem standart hem seçilen emisyon yarıya iner, oran aynı kalır.
Oranın etkisi kg değerlerinde ve <b>günlük etki</b>de görünür.</p>
<p><b>Yenilenebilir payı:</b> Sonuç kartındaki bu satır, kaydırılan enerjinin tüketildiği saatlerde şebekedeki
yenilenebilir (rüzgâr, güneş, hidro, jeotermal, biyokütle) üretim payını gösterir: standart pencere → seçilen
pencere. Yeşilse kaydırma, enerjiyi daha temiz kaynakların ağırlıklı olduğu saatlere taşıyor demektir.</p>
<p><b>Fosil marjinal varsayımla:</b> Ana sonuç şebekenin saatlik <i>ortalama</i> yoğunluğuyla hesaplanır. Oysa bir yük
kaydırıldığında üretimini değiştiren santral çoğunlukla fosil bir santraldir. Bu satır, kaydırılan yükü o saatlerde
yalnızca fosil santrallerin karşıladığı varsayımıyla aynı hesabı gösterir (CI_fosil = CI / fosil payı). Genellikle
daha küçük bir azalma çıkar; gerçek etki büyük olasılıkla iki değer arasındadır.</p>"""),

    ("best", "En Temiz Saat", f"""
<p>Makine, gün, standart başlangıç, uzunluk ve oranı seçin; günün tüm geçerli hedef pencereleri emisyona göre
sıralanır (en üstte en temiz). Senaryo ekranındaki kısıtlı saatler burada da uygulanır. Sağdaki grafik her hedef
saatteki değişimi gösterir; çerçeveli çubuk en temiz penceredir.</p>
<p>Tabloda {_k('↑')} {_k('↓')} ile satır seçip {_k('Enter')} ile o saati senaryoya uygularsınız.</p>"""),

    ("annual", "Yıllık Etki", """
<p>Senaryo ekranındaki kaydırma (makine, standart saat, hedef saat, uzunluk, oran ve kısıtlı saatler) seçilen
yılın verisi olan <b>her gününde</b> aynı formülle hesaplanır ve toplanır. Sonuç: yılda kaç kg/ton CO2
azalacağı, kaydırılan yükteki yüzde değişim ve makinenin toplam emisyonu içindeki payı.</p>
<p><b>Yıllık değişim</b> = (ΣS − ΣB) / ΣB × 100. Standart pencerede yükün olmadığı ya da hedefin kısıtlı
olduğu günler toplama girmez ve <i>Hesaba giren gün</i> kutusunda görünür. Makine verisi yılın tamamını
kapsamıyorsa sonuç yalnızca verisi olan günlerin toplamıdır; yıla tamamlama yapılmaz.</p>
<p>Ekran ayrıca yıl boyunca sabit tutulabilecek <b>en temiz hedef saati</b> gösterir. <i>Bu hedefi dene</i>
onu seçer, <i>Senaryoya uygula</i> saatleri Senaryo sekmesine aktarır. Aylık tablo ve grafik mevsim
farklarını gösterir.</p>
<p><b>Kapsam:</b> Tek bir makine ya da <b>Tesis geneli</b> seçilebilir. Tesis genelinde aynı kaydırma bütün
kaydırılabilir makinelere uygulanır; toplam emisyon değişimi, makinelerin katkıları ve aylık toplam gösterilir
(gün sayısı makine-gün olarak toplanır).</p>
<p><b>Yenilenebilir payı</b> kutusu, kaydırılan enerjinin yıl boyunca şebekedeki yenilenebilir üretimden karşılanan
payını (enerji ağırlıklı) standart ve hedef pencere için karşılaştırır. Senaryoda <i>tCO2-eşd</i> seçiliyse birimler
CO2-eşd, <i>parametrik mod</i> açıksa her saat sabit yük kullanılır; ekranın üstündeki not bunu belirtir.</p>
<p><b>Delti yorumlasın</b> yıllık sonucu sade bir dille açıklar (internet yoksa şablon metin). <b>PDF rapor</b>
özet göstergeleri, Delti yorumunu, aylık grafik ve tabloyu, makine katkılarını ve yöntem notlarını içeren bir rapor
kaydeder; <b>CSV</b> aynı verileri tam hassasiyetle dışa aktarır.</p>"""),

    ("plan", "Tesis Planı", """
<p>Seçilen günde <b>her kaydırılabilir makine için ayrı ayrı</b> en temiz hedef pencereyi bulur. Üstteki standart
saat, uzunluk ve oran bütün satırlara uygulanır; tablodan her makinenin kendi standart saatini ve uzunluğunu
değiştirebilir, <i>Dahil</i> kutusuyla makineyi plandan çıkarabilirsiniz. Kaydırılamayan ve o gün verisi olmayan
makineler nedeniyle birlikte listelenir.</p>
<p>Özet kutularında tesisin toplam emisyon değişimi, kaydırılan yükteki yüzde, tesisin günlük emisyonundaki pay ve
<b>tepe yük</b> (plan öncesi → sonrası) görünür. Bütün yükleri en temiz saate toplamak tesisin saatlik tepe yükünü
artırabilir. Sözleşme gücü ya da trafo sınırı varsa <b>Tepe sınırı</b> girin: planlayıcı makineleri azaltım
potansiyeline göre sırayla yerleştirir, sınırı aşan pencereyi atlayıp sınırı aşmayan en temiz pencereyi seçer.</p>
<p>Grafik plan öncesi/sonrası tesis yükünü ve şebeke karbon yoğunluğunu gösterir. Bir satıra çift tıklamak o
makineyi Senaryo'da açar; <i>CSV</i> planı kaydeder.</p>"""),

    ("delti", "Delti'ye Sor", f"""
<p><b>Delti</b>, CarbonDelta'nın yapay zekâ (AI) yardımcısıdır. Hesap yapmaz; motorun hesapladığı sonuçları
açıklar ve günlük dille yazdıklarınızı senaryoya çevirir.</p>
<p>Örnekler: <i>“Kompresörü 3'ten 18'e al”</i>, <i>“Presi %50 ile 2 saat 21'e kaydır”</i>. Cümle anlaşılınca
Senaryo ekranına hemen uygulanır ve sonucun önizlemesi gösterilir. Oran yazmazsanız %100 kabul edilir;
yazmadığınız diğer değerler (gün, kısıtlı saatler) korunur.</p>
<p>Yazıp {_k('Enter')}'a basın; cevap gelince {_k('Enter')} ile <i>Senaryoya git</i>. Üst banttaki kutu da aynı işi yapar.</p>"""),

    ("explain", "Delti'nin açıklamaları", """
<p>Senaryo ekranındaki <b>Delti açıklıyor</b> kartı, her hesaptan sonra sonucu sade bir dille anlatır:
ne taşındı, emisyon neden değişti (o saatlerdeki yenilenebilir payı, baskın kaynak) ve günlük etkisi.</p>
<ul>
<li><b>Neden bu saat?</b> İki penceredeki üretim karışımını kıyaslar.</li>
<li><b>Karşılaştır:</b> Mevcut senaryoyu en son kaydedilenle kıyaslar.</li>
<li><b>Daha fazla:</b> Günlük etki yorumu, mevsim notu (aynı saatlerin 12 aylık davranışı), rapor cümlesi,
terim açıklayıcı, veri kaynakları ve metni kopyala.</li>
</ul>
<p><b>Güvenlik:</b> Delti'nin metnindeki her sayı hesaplanan değerlerle karşılaştırılır; veride olmayan bir sayı
yazarsa metin gösterilmez, yerine şablon metin gelir. Etikette <i>AI</i>, <i>Düşünüyor…</i>,
<i>Çevrimdışı · şablon</i> veya <i>Şablon · doğrulanamadı</i> yazar.</p>
<p><b>İnternet ya da anahtar yoksa</b> Delti uyur: “Delti (AI) şu an çevrimdışı; hesap sonucu geçerlidir.”
Yüzde ve tüm hesaplar çalışmaya devam eder.</p>
<p><b>Delti'yi uyandırmak (API anahtarı):</b> Delti'ye Sor sekmesindeki <i>Delti'yi uyandır</i> / <i>⚙ Ayarlar</i>
düğmesi, ana sayfanın altındaki <i>uyandır</i> bağlantısı ya da Ctrl+, ile <b>Delti ayarları</b> açılır.
Sağlayıcıyı (Google Gemini veya Anthropic Claude) seçin, anahtarı yapıştırın, <i>Bağlantıyı dene</i> ile
kontrol edip <i>Kaydet</i>'e basın. Anahtar bu bilgisayarda, yalnızca sizin Windows hesabınızın çözebileceği
şekilde şifrelenerek saklanır; program güncellense de silinmez. <i>Anahtarı kaldır</i> ile silinir.</p>"""),

    ("calc", "Hesap dökümü", """
<p>Hesabın saat saat dökümünü gösterir: her standart saatten taşınan enerji, o saatin ve hedef saatin karbon
yoğunluğu, emisyonlar. Üstteki kartlarda B (standart emisyon), S (seçilen emisyon), değişim ve günlük etki yer
alır. Sağda formül ve ETKB 2023 emisyon faktörleri tablosu bulunur.</p>
<p><b>Formül:</b> E = oran × saatlik tüketim; B = Σ E × CI(standart saat); S = Σ E × CI(hedef saat);
değişim = (S − B) / B × 100; günlük etki = (S − B) / günlük toplam emisyon × 100.</p>
<p><b>CSV olarak dışa aktar</b>, dökümü Türkçe Excel'de açılabilen bir dosyaya tam hassasiyetle yazar.</p>"""),

    ("history", "Geçmiş", f"""
<p>Kaydettiğiniz senaryolar burada listelenir (bilgisayarınızda, <i>%APPDATA%\\CarbonDelta\\history.db</i>).</p>
<ul>
<li>{_k('↑')} {_k('↓')} ile seçin, {_k('Enter')} ile senaryoyu geri yükleyin (çift tıklama da olur).</li>
<li>{_k('Delete')} seçili kaydı siler (onay sorulur).</li>
<li><b>Özetle:</b> Delti son 10 kaydı özetler; en iyi ve en kötü senaryoyu söyler.</li>
</ul>"""),

    ("data", "Veri yönetimi", f"""
<p>Yeni makine, yeni yıl ya da yeni emisyon katsayıları <b>Veri</b> sekmesinden eklenir; uygulamayı yeniden
kurmak gerekmez. Varsayılan 2025 verisi her zaman yerinde kalır. Eklenen her şey ayrı bir <b>veri paketi</b>
olarak <i>%APPDATA%\CarbonDelta\veri</i> klasöründe tutulur.</p>
<ul>
<li><b>Makine ekle:</b> Saatlik kWh dosyası seçin (CSV ya da Excel; sütunlar <i>Tarih, Saat, kWh</i>; ondalık
virgül olabilir). Makine adını, türünü, kaydırılabilir olup olmadığını ve veri türünü (<i>örnek yük</i> ya da
<i>tesis ölçümü</i>) girin. Uygulama her günün 24 tekrarsız saati olup olmadığını, boş/negatif değerleri ve
o gün için şebeke verisi bulunup bulunmadığını kontrol eder; eksik günleri atlar ve raporlar.
<i>Şablon dosyayı kaydet</i> ile örnek bir dosya alabilirsiniz.</li>
<li><b>Yıl ekle:</b> EPİAŞ Şeffaflık Platformu › Üretim › Gerçek Zamanlı Üretim sayfasından istediğiniz dönemi
dışa aktarıp seçin. Eksik sıfırlı ondalıklar düzeltilir, negatif gece güneş değerleri 0 yapılır, karbon
yoğunluğu varsayılan veriyle aynı yöntemle hesaplanır. O yılın yükü için ayrıca makine verisi eklenmelidir.</li>
<li><b>Emisyon katsayıları:</b> ETKB yeni faktörleri yayımladığında yakıt türü başına tCO2/MWh ve
tCO2-eşd/MWh değerlerini içeren dosyayı seçin. Etkin olduğunda tüm yıllar yeni katsayılarla yeniden
hesaplanır. Aynı anda tek katsayı paketi etkin olur.</li>
</ul>
<p>Paket listesinde {_k('↑')} {_k('↓')} ile seçip {_k('Boşluk')} ile açıp kapatabilir, {_k('Delete')} ile
silebilirsiniz. Kapatılan paketin makineleri ve günleri listelerden çıkar; silinen paketle kaydedilmiş geçmiş
senaryolar açılamaz.</p>
<p><b>Etiket:</b> Tesis ölçümü olarak eklenen bir makine seçildiğinde alt bilgide
<i>“Tesis ölçümü (Balıkesir)”</i>, örnek veride <i>“Örnek yük, Balıkesir tesisi değil”</i> yazar; kaynakta
kullanılan şebeke yılı ve katsayı paketi gösterilir.</p>
<p><b>Formül</b> bu ekrandan değiştirilmez: masaüstü, mobil ve Excel aynı formülü kullanmalıdır. Formül
değişikliği <i>shared/FORMUL.md</i> sürüm süreciyle geliştiriciler tarafından yapılır.</p>"""),

    ("contact", "İletişim", """
<p><b>İletişim</b> sekmesinde geliştiricilerin ve danışmanın telefon ve e-posta bilgileri bulunur.
<i>E-posta gönder</i> varsayılan e-posta uygulamanızı açar, <i>Kopyala</i> bilgileri panoya alır.</p>"""),

    ("keys", "Klavye kısayolları", f"""
<p>Uygulama fare olmadan tamamen klavyeyle kullanılabilir. Odaktaki öğe yeşil çerçeveyle gösterilir.</p>
<table cellspacing="0" cellpadding="5">
<tr><td>{_k('Esc')}</td><td>Ana sayfaya dön (açık bir liste/takvim varsa önce onu kapatır)</td></tr>
<tr><td>{_k('F1')}</td><td>Kullanma kılavuzu</td></tr>
<tr><td>{_k('F11')}</td><td>Tam ekran (sunum modu) aç/kapat</td></tr>
<tr><td>{_k('Ctrl', ',')}</td><td>Delti ayarları (API anahtarı)</td></tr>
<tr><td>{_k('Ctrl', '1')} … {_k('Ctrl', '0')}</td><td>Senaryo · En Temiz Saat · Yıllık Etki · Tesis Planı · Delti'ye Sor · Hesabı Göster · Geçmiş · Veri · Kılavuz · Kaynaklar (İletişim'e Ctrl+Tab ile geçilir)</td></tr>
<tr><td>{_k('Ctrl', 'Tab')} / {_k('Ctrl', 'Shift', 'Tab')}</td><td>Sonraki / önceki sekme</td></tr>
<tr><td>{_k('Tab')} / {_k('Shift', 'Tab')}</td><td>Alanlar arasında ileri / geri</td></tr>
<tr><td>{_k('↑')} {_k('↓')}</td><td>Sayı ve saat değerini değiştir, listede seç, kaydırıcıyı oynat</td></tr>
<tr><td>{_k('Enter')}</td><td>Odaktaki düğmeye bas, çipi işaretle, tablodaki satırı uygula / geri yükle</td></tr>
<tr><td>{_k('Boşluk')}</td><td>Onay kutusunu ve düğmeyi değiştir</td></tr>
<tr><td>{_k('Alt', '↓')}</td><td>Açılır listeyi / takvimi aç</td></tr>
<tr><td>{_k('Ctrl', 'S')}</td><td>Senaryoyu kaydet</td></tr>
<tr><td>{_k('Ctrl', 'B')}</td><td>En iyi saati bul</td></tr>
<tr><td>{_k('Delete')}</td><td>Geçmiş'te seçili kaydı sil</td></tr>
<tr><td>{_k('PgUp')} / {_k('PgDn')}</td><td>Kılavuz ve uzun metinlerde sayfa kaydır</td></tr>
</table>
<p><b>Ana sayfada:</b> {_k('↑')} {_k('↓')} seç, {_k('Enter')} aç, {_k('1')}…{_k('9')} doğrudan aç;
en üstte {_k('↑')} ile <i>Son senaryo</i> kartına çıkılır.</p>"""),

    ("sources", "Veri ve sınırlılıklar", """
<ul>
<li><b>EPİAŞ 2025:</b> 8.760 saatlik kaynak bazında üretim; her saatin karbon yoğunluğu buradan hesaplanır.</li>
<li><b>ETKB 2023:</b> Yakıt türü başına resmî emisyon faktörleri.</li>
<li><b>Zenodo:</b> Bir imalat tesisindeki makinelerin temizlenmiş enerji ölçümleri (7 makine).</li>
</ul>
<p><b>Sınırlılıklar:</b> Yük örnek veridir; kaydırma aynı gün içindedir; hesap saatlik <i>ortalama</i> karbon
yoğunluğuyla yapılır (gerçek etki o saatteki marjinal santrale bağlıdır, sonuçlar gösterge niteliğindedir);
ETKB 2023 faktörleri 2025 üretimine uygulanır; ithalat/ihracat hesaba girmez;
Delti'nin açıklamaları için internet ve API anahtarı gerekir. Para/TL kazancı, CBAM hesabı, sensör bağlantısı ve
otomatik makine kontrolü kapsam dışıdır.</p>"""),
]


class GuideTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)

        toc_card, tl = theme.card("İçindekiler", margins=(10, 12, 10, 10))
        toc_card.setFixedWidth(240)
        self.toc = QListWidget()
        self.toc.setStyleSheet(
            "QListWidget { border: none; background: transparent; outline: none; }"
            "QListWidget::item { padding: 7px 8px; border-radius: 6px; }"
            f"QListWidget::item:selected {{ background: {theme.PRIMARY_SOFT}; color: {theme.PRIMARY_DARK}; font-weight: 600; }}"
            "QListWidget::item:hover { background: #f2f6f4; }")
        for key, title, _ in SECTIONS:
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, key)
            self.toc.addItem(item)
        self.toc.currentRowChanged.connect(self._go)
        tl.addWidget(self.toc, 1)
        lay.addWidget(toc_card)

        body_card, bl = theme.card(margins=(18, 14, 18, 14))
        self.text = QTextBrowser()
        self.text.setOpenLinks(False)
        html = ["<div style='line-height:150%;'>"]
        for key, title, body in SECTIONS:
            html.append(f"<a name='{key}'></a><h2 style='color:{theme.PRIMARY_DARK}; margin:14px 0 6px 0;'>{title}</h2>{body}")
        html.append("<p style='color:#6b7785; margin-top:18px;'>Örnek yük, Balıkesir tesisi değil · "
                    "Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo</p></div>")
        self.text.setHtml("".join(html))
        bl.addWidget(self.text, 1)
        lay.addWidget(body_card, 1)
        self.toc.setCurrentRow(0)

    def _go(self, row: int) -> None:
        if row >= 0:
            self.text.scrollToAnchor(SECTIONS[row][0])

    def focus_default(self) -> None:
        self.toc.setFocus()

    def show_section(self, key: str) -> None:
        for i, (k, _t, _b) in enumerate(SECTIONS):
            if k == key:
                self.toc.setCurrentRow(i)
                self._go(i)
                return
