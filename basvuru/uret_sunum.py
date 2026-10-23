"""Proje Pazarı sunum taslağı (10 dk, 16:9) ve 50×70 cm poster taslağını üretir.

Çıktılar: basvuru/CarbonDelta_Sunum_Taslak.pptx, basvuru/CarbonDelta_Poster_50x70_Taslak.pptx
Rakamlar sonuclar.json'dan gelir. Çalıştırma: basvuru\\.araclar\\Scripts\\python basvuru\\uret_sunum.py
"""
import json
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Cm, Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "sonuclar.json").read_text(encoding="utf-8"))
IMG = HERE / "gorseller"

DARK = RGBColor(0x0B, 0x3B, 0x30)     # koyu orman yeşili (kapak/kapanış zemini)
GREEN = RGBColor(0x16, 0x78, 0x5C)    # ana renk
MINT = RGBColor(0x5F, 0xE0, 0xB0)     # koyu zeminde vurgu
SOFT = RGBColor(0xE7, 0xF3, 0xEF)     # kart zemini
CORAL = RGBColor(0xD0, 0x3C, 0x3C)    # "kirli saat" vurgusu
TEXT = RGBColor(0x1D, 0x27, 0x33)
MUTED = RGBColor(0x5B, 0x67, 0x76)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Calibri"


def num(v, d=2):
    s = f"{abs(v):,.{d}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return ("−" if round(v, d) < 0 else "") + s


def pct(v, d=2):
    return f"%{num(v, d)}" if v >= 0 else f"−%{num(-v, d)}"


prof, dh, ch = R["profile"], R["dirtiest_h"], R["cleanest_h"]
spread = (prof[dh] - prof[ch]) / prof[dh] * 100
ref, tot = R["ref_day"], R["total"]
comp = next(m for m in R["machines"] if m["id"] == "comp_b")
shiftable = [m for m in R["machines"] if m["shiftable"]]


# ----------------------------------------------------------------- yardımcılar
def box(slide, x, y, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE, name=None):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.08
    if name:
        s.name = name
    return s


def text(slide, x, y, w, h, paras, size=16, color=TEXT, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, margin=0, spacing=6):
    """paras: str | list[str | (str, {size,color,bold,italic})] — her öğe bir paragraf."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, Emu(margin))
    if isinstance(paras, str):
        paras = [paras]
    for i, item in enumerate(paras):
        t, o = (item, {}) if isinstance(item, str) else item
        par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        par.alignment = o.get("align", align)
        par.space_after = Pt(o.get("after", spacing))
        r = par.add_run()
        r.text = t
        f = r.font
        f.name = FONT
        f.size = Pt(o.get("size", size))
        f.bold = o.get("bold", bold)
        f.italic = o.get("italic", False)
        f.color.rgb = o.get("color", color)
    return tb


def bullets(slide, x, y, w, h, items, size=16, color=TEXT):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        par.space_after = Pt(8)
        pPr = par._p.get_or_add_pPr()
        pPr.set("marL", str(Emu(Inches(0.28))))
        pPr.set("indent", str(-Emu(Inches(0.28))))
        bu = pPr.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}buChar", {"char": "•"})
        pPr.append(bu)
        head, _, rest = it.partition("|")
        r = par.add_run()
        r.text = head if rest else it
        r.font.name, r.font.size, r.font.color.rgb = FONT, Pt(size), color
        r.font.bold = bool(rest)
        if rest:
            r2 = par.add_run()
            r2.text = " " + rest
            r2.font.name, r2.font.size, r2.font.color.rgb = FONT, Pt(size), color
    return tb


def title(slide, t, color=TEXT):
    text(slide, Inches(0.6), Inches(0.4), Inches(12.1), Inches(0.9), t, size=34, bold=True, color=color,
         anchor=MSO_ANCHOR.MIDDLE)


def stat(slide, x, y, w, value, label, vcolor=GREEN, lcolor=MUTED, vsize=44, h=Inches(1.6)):
    text(slide, x, y, w, Inches(0.85), value, size=vsize, bold=True, color=vcolor)
    text(slide, x, y + Inches(0.85), w, h - Inches(0.85), label, size=14, color=lcolor)


def picture(slide, name, x, y, w=None, h=None, border=True):
    pic = slide.shapes.add_picture(str(IMG / name), x, y, w, h)
    if border:
        pic.line.color.rgb = RGBColor(0xD5, 0xDD, 0xE4)
        pic.line.width = Pt(0.75)
    return pic


def page_no(slide, n, dark=False):
    text(slide, Inches(12.2), Inches(7.0), Inches(0.8), Inches(0.3), str(n), size=11,
         color=MINT if dark else MUTED, align=PP_ALIGN.RIGHT)


def bg(slide, color):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = color


# =================================================================== SUNUM
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W = prs.slide_width
n = 0


def new(dark=False):
    global n
    n += 1
    s = prs.slides.add_slide(BLANK)
    bg(s, DARK if dark else WHITE)
    if n > 1:
        page_no(s, n, dark)
    return s


# 1 — Kapak
s = new(dark=True)
picture(s, "../../desktop/icon.png", Inches(0.9), Inches(1.2), h=Inches(1.3), border=False)
text(s, Inches(0.9), Inches(2.75), Inches(9), Inches(1.2), [("Carbon", {"size": 66, "bold": True, "color": WHITE})])
tb = s.shapes[-1].text_frame.paragraphs[0]
r = tb.add_run()
r.text = "Delta"
r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(66), True, MINT
text(s, Inches(0.9), Inches(3.95), Inches(8.5), Inches(1.6), [
    ("Aynı iş, daha temiz saat.", {"size": 28, "color": WHITE, "italic": True}),
    ("Endüstriyel yükleri daha düşük karbonlu saatlere kaydırmak için yapay zekâ destekli karar destek yazılımı",
     {"size": 18, "color": RGBColor(0xC9, 0xE6, 0xDC)})])
text(s, Inches(0.9), Inches(5.9), Inches(8.5), Inches(1.0), [
    ("İsmail Ali ASLAN · Emin Burak ÖZTÜRK · Danışman: Öğr. Gör. Ali ERFİDAN", {"size": 15, "color": WHITE}),
    ("Balıkesir Üniversitesi · Tema: Yeşil Teknolojiler ve Döngüsel Ekonomi", {"size": 13, "color": MINT})])
picture(s, "01_ana_ekran.png", Inches(8.4), Inches(1.0), w=Inches(4.4))
s.notes_slide.notes_text_frame.text = (
    "(0:00–0:30) Kendinizi ve ekibi tanıtın. Tek cümle: CarbonDelta, fabrikadaki esnek yüklerin hangi saatte "
    "çalıştırılırsa daha az emisyon oluşacağını hesaplayan bir karar destek yazılımı.")

# 2 — Problem
s = new()
title(s, "Aynı elektrik, saate göre farklı karbon")
picture(s, "07_saatlik_profil.png", Inches(0.6), Inches(1.5), w=Inches(7.6))
stat(s, Inches(8.7), Inches(1.6), Inches(4.2), f"%{num(spread, 1)}",
     f"2025'te en kirli ({dh:02d}:00) ve en temiz ({ch:02d}:00) saat arasındaki karbon yoğunluğu farkı")
stat(s, Inches(8.7), Inches(3.4), Inches(4.2), f"{num(prof[dh], 3)} → {num(prof[ch], 3)}",
     "tCO2/MWh, yıllık ortalama (EPİAŞ üretimi × ETKB faktörleri)", vsize=32)
text(s, Inches(8.7), Inches(5.0), Inches(4.2), Inches(1.6), [
    ("Kurumsal karbon hesabı çoğunlukla yıllık ortalama faktör kullanır; bu saatlik fark görünmez.",
     {"size": 15, "color": TEXT})])
text(s, Inches(0.6), Inches(5.6), Inches(7.6), Inches(1.4), [
    ("Neden şimdi?", {"size": 15, "bold": True, "color": GREEN, "after": 2}),
    ("İklim Kanunu (2025) ile Türkiye ETS pilot dönemde · AB SKDM (CBAM) 1 Ocak 2026'dan beri mali yükümlülük "
     "içeriyor · İhracatçılar ürün başına emisyonu ölçmek ve azaltmak zorunda", {"size": 14, "color": TEXT})])
s.notes_slide.notes_text_frame.text = (
    "(0:30–1:45) Şebekede gece kömürün payı yüksek, akşam yenilenebilir ve doğal gaz payı artıyor. Aynı 1 kWh "
    f"saate göre %{num(spread, 1)}'e kadar farklı karbon taşıyor. Fabrikalarda kompresör, pres, karıştırıcı gibi "
    "yükler birkaç saat kaydırılabilir; ama yöneticinin 'ne kadar etki eder?' sorusuna hızlı ve güvenilir cevap "
    "verecek aracı yok. Düzenlemeler (ETS, SKDM) bu soruyu her geçen gün daha önemli hale getiriyor.")

# 3 — Çözüm
s = new()
title(s, "CarbonDelta: zamanlama kararını sayıya döker")
picture(s, "02_senaryo.png", Inches(0.6), Inches(1.45), w=Inches(7.4))
cards = [("Senaryo", "Makine, gün, standart ve hedef saat seçilir; emisyon değişimi anında hesaplanır."),
         ("En temiz saat", "Günün tüm geçerli pencereleri taranır, en temizi önerilir."),
         ("Yıllık etki", "Aynı kaydırma yılın her gününde: ton CO2 ve aylık kırılım."),
         ("Delti (AI)", "Sonucu sade Türkçe ile açıklar; her sayı otomatik doğrulanır.")]
y = Inches(1.45)
for head, body in cards:
    box(s, Inches(8.3), y, Inches(4.45), Inches(1.22), fill=SOFT, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(8.5), y + Inches(0.12), Inches(4.1), Inches(1.0), [
        (head, {"size": 17, "bold": True, "color": GREEN, "after": 2}), (body, {"size": 14})])
    y += Inches(1.36)
s.notes_slide.notes_text_frame.text = (
    "(1:45–2:45) Dört işlev: senaryo hesabı, en temiz saati bulma, yıllık etki ve Delti. İnternetsiz çalışır, "
    "tek dosyayla kurulur. Karar her zaman kullanıcıda; yazılım makineye müdahale etmez.")

# 4 — Yöntem
s = new()
title(s, "Resmî veri, kilitli formül, doğrulanmış sonuç")
steps = [("EPİAŞ 2025", "8.760 saat kaynak bazında üretim"), ("ETKB 2023", "15 yakıt emisyon faktörü"),
         ("CI(h)", "Her saatin şebeke karbon yoğunluğu"), ("Makine yükü", "Saatlik kWh (örnek veya tesis ölçümü)"),
         ("B ve S", "Standart ve hedef pencere emisyonu")]
x = Inches(0.6)
for i, (head, body) in enumerate(steps):
    box(s, x, Inches(1.7), Inches(2.2), Inches(1.7), fill=SOFT if i != 2 else GREEN,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x + Inches(0.15), Inches(1.85), Inches(1.9), Inches(1.5), [
        (head, {"size": 19, "bold": True, "color": WHITE if i == 2 else GREEN, "align": PP_ALIGN.CENTER}),
        (body, {"size": 13, "color": WHITE if i == 2 else TEXT, "align": PP_ALIGN.CENTER})],
        anchor=MSO_ANCHOR.MIDDLE)
    if i < len(steps) - 1:
        a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x + Inches(2.25), Inches(2.4), Inches(0.28), Inches(0.3))
        a.fill.solid()
        a.fill.fore_color.rgb = MUTED
        a.line.fill.background()
    x += Inches(2.5)
box(s, Inches(0.6), Inches(3.85), Inches(12.1), Inches(1.35), fill=None, line=RGBColor(0xCF, 0xD6, 0xDE),
    shape=MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, Inches(0.8), Inches(3.95), Inches(11.7), Inches(1.2), [
    ("Eᵢ = p × kWh(s+i)     B = Σ Eᵢ × CI(s+i)     S = Σ Eᵢ × CI(t+i)", {"size": 22, "bold": True,
                                                                     "align": PP_ALIGN.CENTER}),
    ("Değişim = (S − B) / B × 100     ·     Yıllık değişim = (ΣS − ΣB) / ΣB × 100",
     {"size": 18, "color": GREEN, "align": PP_ALIGN.CENTER})], anchor=MSO_ANCHOR.MIDDLE)
bullets(s, Inches(0.6), Inches(5.45), Inches(12.1), Inches(1.6), [
    "Tekrarlanabilir:|Aynı formül masaüstünde, Excel doğrulama dosyasında ve test vektörlerinde birebir aynı sonucu verir; 138 otomatik test.",
    "Güvenli yapay zekâ:|Dil modeli hesap yapmaz; metindeki veride olmayan bir sayı, metni otomatik olarak devre dışı bırakır.",
], size=15)
s.notes_slide.notes_text_frame.text = (
    "(2:45–3:45) Her saatin karbon yoğunluğu: kaynak üretimleri × resmî faktör / toplam üretim. Kaydırılan "
    "enerjinin standart ve hedef penceredeki emisyonu karşılaştırılır. Formül kilitli; Excel ve testlerle "
    "doğrulanıyor. Yapay zekâ yalnızca anlatır, sayı uyduramaz.")

# 5 — Canlı demo
s = new(dark=True)
text(s, Inches(0.9), Inches(0.9), Inches(11.5), Inches(1.0), "Canlı demo · 3 dakika", size=40, bold=True,
     color=WHITE)
demo = ["1|Ana ekran → Son senaryo kartı: Kompresör 03:00 → 18:00",
        "2|Senaryo: hedef saati değiştir, sonucun anında değiştiğini göster",
        "3|En temiz saat: Ctrl+B ile günün en temiz penceresi",
        "4|Yıllık etki: aynı kaydırmanın 2025 toplamı ve aylık grafik",
        "5|Delti: “Presi %50 ile 21'e kaydır” yaz → senaryo kurulur",
        "6|Veri: tesisin kendi ölçümünü eklemek (sadece ekranı göster)"]
y = Inches(2.15)
for item in demo:
    k, _, t = item.partition("|")
    c = box(s, Inches(0.9), y, Inches(0.6), Inches(0.6), fill=MINT, shape=MSO_SHAPE.OVAL)
    text(s, Inches(0.9), y, Inches(0.6), Inches(0.6), k, size=18, bold=True, color=DARK, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(1.75), y, Inches(10.5), Inches(0.6), t, size=20, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
    y += Inches(0.78)
text(s, Inches(0.9), Inches(6.85), Inches(11.5), Inches(0.4),
     "İnternet yoksa da çalışır · F11 tam ekran · Esc ana sayfa", size=13, color=MINT)
s.notes_slide.notes_text_frame.text = (
    "(3:45–6:45) Demodan önce: uygulamayı açık bırakın, F11 ile tam ekran yapın. Salonda internet olmayabilir; "
    "Delti çevrimdışıysa şablon metin çıkar, hesaplar etkilenmez. Her adımda tek cümle söyleyin, fareyle değil "
    "klavyeyle ilerlemek akıcı görünür.")

# 6 — Bulgular
s = new()
title(s, "Bulgular: basit bir zamanlama değişikliği, belirgin azalma")
stat(s, Inches(0.6), Inches(1.5), Inches(3.6), pct(ref["delta_pct"]),
     "Örnek gün (15.07.2025), Kompresör 03:00→18:00, kaydırılan enerjinin emisyonu")
stat(s, Inches(0.6), Inches(3.3), Inches(3.6), pct(comp["delta_pct"]),
     f"Aynı kaydırma 2025'te verisi olan {comp['days_ok']} günde; emisyon her gün düştü")
stat(s, Inches(0.6), Inches(5.1), Inches(3.6), f"≈{num((prof[dh] - prof[ch]) * 1000, 0)} kg",
     f"{dh:02d}:00'dan {ch:02d}:00'a kaydırılan her 1 MWh için daha az CO2 (yıllık ortalama)")
cd = CategoryChartData()
cd.categories = [m["name"] for m in shiftable]
cd.add_series("Yıllık azalma (%)", [round(-m["delta_pct"], 2) for m in shiftable])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(4.6), Inches(1.45), Inches(8.1), Inches(5.0), cd)
chart = gf.chart
chart.has_legend = False
chart.has_title = True
chart.chart_title.text_frame.text = "2025 yıllık emisyon azalması (kaydırılan yükte)"
tp = chart.chart_title.text_frame.paragraphs[0]
tp.runs[0].font.size, tp.runs[0].font.bold, tp.runs[0].font.color.rgb = Pt(14), True, TEXT
plot = chart.plots[0]
plot.gap_width = 60
plot.has_data_labels = True
dl = plot.data_labels
dl.number_format, dl.number_format_is_linked = '"%"0.0', False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size, dl.font.color.rgb = Pt(12), TEXT
ser = plot.series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = GREEN
ser.invert_if_negative = False
va = chart.value_axis
va.minimum_scale = 0
_sc = va._element.find("{http://schemas.openxmlformats.org/drawingml/2006/chart}scaling")
if _sc.find("{http://schemas.openxmlformats.org/drawingml/2006/chart}orientation") is None:
    _o = _sc.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/chart}orientation", {"val": "minMax"})
    _sc.insert(0, _o)  # PowerPoint, orientation olmayan eksen ölçeğini bozuk sayar
va.has_major_gridlines = True
va.major_gridlines.format.line.color.rgb = RGBColor(0xE5, 0xE9, 0xEE)
va.tick_labels.font.size, va.tick_labels.font.color.rgb = Pt(11), MUTED
va.format.line.fill.background()
ca = chart.category_axis
ca.tick_labels.font.size, ca.tick_labels.font.color.rgb = Pt(12), TEXT
ca.reverse_order = True
ca.format.line.color.rgb = RGBColor(0xCF, 0xD6, 0xDE)
text(s, Inches(4.6), Inches(6.55), Inches(8.1), Inches(0.5),
     "Örnek yük (açık veri seti), Balıkesir tesisi değil · Kaynak: EPİAŞ 2025, ETKB 2023, Zenodo", size=11,
     color=MUTED)
s.notes_slide.notes_text_frame.text = (
    f"(6:45–7:45) Örnek günde {pct(ref['delta_pct'])}, yıl genelinde {pct(comp['delta_pct'])}. Beş kaydırılabilir "
    f"makinenin hepsinde azalma var. Mutlak değerler küçük, çünkü örnek makineler küçük; her 1 MWh kaydırma "
    f"yaklaşık {num((prof[dh] - prof[ch]) * 1000, 0)} kg CO2 demek. Günde 1 MWh esnek yükü olan bir tesis için "
    f"yılda ~{num((prof[dh] - prof[ch]) * 300, 1)} ton (300 iş günü).")

# 7 — Yenilik + Pazar
s = new()
title(s, "Neden farklı, kimin için")
left = ["Saatlik ve makine bazlı:|yıllık ortalama değil, her saatin gerçek üretim karışımı",
        "Doğrulanmış yapay zekâ:|anlaşılır anlatım, sayı uydurma riski yok",
        "Çevrim dışı ve tek dosya kurulum:|sahada, internetsiz çalışır",
        "Kendi verisiyle büyür:|yeni makine, yıl ve faktörler kod değişmeden eklenir"]
right = ["Hedef kitle:|enerji yoğun KOBİ'ler, OSB üreticileri, AB'ye ihracatçılar, enerji ve sürdürülebilirlik "
         "danışmanları",
         "İş modeli:|yıllık lisans + tesis verisi aktarım ve ilk analiz hizmeti + danışman firmalara çoklu tesis lisansı",
         "İlk adım:|Balıkesir'de TTO aracılığıyla 1–2 tesiste pilot uygulama ve saha doğrulaması"]
box(s, Inches(0.6), Inches(1.5), Inches(5.9), Inches(5.3), fill=SOFT, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, Inches(0.9), Inches(1.7), Inches(5.4), Inches(0.5), "Yenilikçi yönler", size=20, bold=True, color=GREEN)
bullets(s, Inches(0.9), Inches(2.35), Inches(5.4), Inches(4.3), left, size=16)
box(s, Inches(6.8), Inches(1.5), Inches(5.9), Inches(5.3), fill=None, line=RGBColor(0xCF, 0xD6, 0xDE),
    shape=MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, Inches(7.1), Inches(1.7), Inches(5.4), Inches(0.5), "Ticarileşme", size=20, bold=True, color=GREEN)
bullets(s, Inches(7.1), Inches(2.35), Inches(5.4), Inches(4.3), right, size=16)
s.notes_slide.notes_text_frame.text = (
    "(7:45–8:30) Genel karbon muhasebesi yazılımları yıllık toplamı raporlar; CarbonDelta zamanlama kararına "
    "odaklanır ve onları tamamlar. Pilot için Balıkesir'deki sanayiyle çalışmak istiyoruz.")

# 8 — Sınırlılıklar ve yol haritası
s = new()
title(s, "Sınırlılıklar ve yol haritası")
bullets(s, Inches(0.6), Inches(1.5), Inches(5.6), Inches(5.2), [
    "Ortalama yoğunluk:|gerçek etki o saatteki marjinal santrale bağlıdır; sonuçlar gösterge niteliğindedir",
    "Örnek yük:|makine verisi açık veri setinden; saha ölçümüyle doğrulanacak",
    "Kapsam:|ETKB 2023 faktörleri 2025 üretimine uygulanır; ithalat/ihracat hesapta yok",
    "Varsayım:|kaydırılan enerji aynı kalır, yük aynı gün içinde taşınır"], size=16)
road = [("Şimdi", "Masaüstü uygulama, yıllık etki, veri ekleme, Delti"),
        ("0–6 ay", "Balıkesir pilotu, tesis ölçümüyle doğrulama"),
        ("6–12 ay", "Marjinal faktör, maliyet etkisi, çoklu makine planı"),
        ("12+ ay", "Otomatik EPİAŞ güncellemesi, mobil, enerji izleme entegrasyonu")]
y = Inches(1.5)
for i, (head, body) in enumerate(road):
    box(s, Inches(6.8), y, Inches(5.9), Inches(1.15), fill=GREEN if i == 0 else SOFT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(7.05), y, Inches(1.4), Inches(1.15), head, size=17, bold=True,
         color=WHITE if i == 0 else GREEN, anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(8.5), y, Inches(4.0), Inches(1.15), body, size=15, color=WHITE if i == 0 else TEXT,
         anchor=MSO_ANCHOR.MIDDLE)
    y += Inches(1.3)
s.notes_slide.notes_text_frame.text = (
    "(8:30–9:15) Sınırlılıkları jüri sormadan söyleyin; bu güven verir. Özellikle ortalama/marjinal ayrımı: "
    "'Sonuçlarımız karşılaştırma ve önceliklendirme için bir gösterge; marjinal faktör yol haritamızda.'")

# 9 — Kapanış
s = new(dark=True)
text(s, Inches(0.9), Inches(1.6), Inches(11.5), Inches(2.4), [
    ("Yatırım yok, ekipman yok:", {"size": 40, "bold": True, "color": WHITE, "after": 0}),
    ("sadece daha temiz bir saat.", {"size": 40, "bold": True, "color": MINT})])
text(s, Inches(0.9), Inches(3.9), Inches(11.5), Inches(1.2),
     "CarbonDelta, şebekenin saatlik karbon farkını sanayicinin uygulayabileceği bir karara dönüştürür: "
     "dijital araçlarla yeşil dönüşüm.", size=20, color=RGBColor(0xC9, 0xE6, 0xDC))
text(s, Inches(0.9), Inches(5.5), Inches(11.5), Inches(1.2), [
    ("İsmail Ali ASLAN · ismailaliaslan11@gmail.com", {"size": 16, "color": WHITE, "after": 2}),
    ("Emin Burak ÖZTÜRK · eminburak1410@gmail.com", {"size": 16, "color": WHITE, "after": 2}),
    ("Danışman: Öğr. Gör. Ali ERFİDAN · ali.erfidan@balikesir.edu.tr", {"size": 16, "color": MINT})])
s.notes_slide.notes_text_frame.text = (
    "(9:15–9:30) Tek cümleyle kapatın ve soruları alın. Toplam süre soru-cevap dahil 10 dakika; konuşmayı "
    "yaklaşık 7–7,5 dakikada bitirmeyi hedefleyin.")

prs.save(HERE / "CarbonDelta_Sunum_Taslak.pptx")


# =================================================================== POSTER
ps = Presentation()
ps.slide_width, ps.slide_height = Cm(50), Cm(70)
s = ps.slides.add_slide(ps.slide_layouts[6])
bg(s, WHITE)
M = Cm(2)
CW = Cm(46)
box(s, 0, 0, ps.slide_width, Cm(12.5), fill=DARK)
s.shapes.add_picture(str(HERE.parent / "desktop" / "icon.png"), M, Cm(2.2), height=Cm(5))
text(s, Cm(8.2), Cm(1.8), Cm(40), Cm(3), [("CarbonDelta", {"size": 96, "bold": True, "color": WHITE})])
text(s, Cm(8.2), Cm(5.2), Cm(40), Cm(4.5), [
    ("Endüstriyel elektrik yüklerini daha düşük karbonlu saatlere kaydırmak için yapay zekâ destekli karar "
     "destek yazılımı", {"size": 36, "color": RGBColor(0xC9, 0xE6, 0xDC)})])
text(s, M, Cm(9.6), CW, Cm(2.6), [
    ("[Sunumu yapacak kişi], İsmail Ali ASLAN, Emin Burak ÖZTÜRK · Danışman: Öğr. Gör. Ali ERFİDAN",
     {"size": 26, "color": WHITE, "after": 2}),
    ("Balıkesir Üniversitesi · Tema: Yeşil Teknolojiler ve Döngüsel Ekonomi", {"size": 22, "color": MINT})])

# Büyük rakamlar
stats = [(f"%{num(spread, 1)}", "en kirli ve en temiz saat\narasındaki karbon farkı (2025)"),
         (pct(ref["delta_pct"]), "örnek gün, kaydırılan\nyükün emisyonu"),
         (pct(comp["delta_pct"]), "aynı kaydırma,\n2025 yıl geneli"),
         (f"≈{num((prof[dh] - prof[ch]) * 1000, 0)} kg", "kaydırılan her 1 MWh\niçin daha az CO2")]
sw = Emu(int((CW - Cm(3)) / 4))
x = M
for v, l in stats:
    box(s, x, Cm(13.6), sw, Cm(6.4), fill=SOFT, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x, Cm(14.2), sw, Cm(3), v, size=66, bold=True, color=GREEN, align=PP_ALIGN.CENTER)
    text(s, x + Cm(0.6), Cm(17.3), sw - Cm(1.2), Cm(2.6), l, size=22, color=TEXT, align=PP_ALIGN.CENTER)
    x += sw + Cm(1)


def section(x, y, w, head):
    text(s, x, y, w, Cm(1.6), head, size=34, bold=True, color=GREEN)


COL = Emu(int((CW - Cm(1.5)) / 2))
X1, X2 = M, M + COL + Cm(1.5)
section(X1, Cm(21.2), COL, "Problem")
text(s, X1, Cm(23.0), COL, Cm(7), [
    ("Şebekedeki üretim karışımı saat saat değişir; aynı 1 kWh elektrik tüketildiği saate göre farklı miktarda "
     "CO2 taşır. Fabrikalardaki kompresör, pres ve karıştırıcı gibi yükler birkaç saat kaydırılabilir, ancak "
     "bunun etkisini hızlı ve güvenilir hesaplayan bir araç yoktur. İklim Kanunu ile kurulan Türkiye ETS ve AB "
     "SKDM (CBAM), ürün başına emisyonu bir rekabet koşuluna dönüştürmektedir.", {"size": 22})])
section(X2, Cm(21.2), COL, "Yöntem")
text(s, X2, Cm(23.0), COL, Cm(3.4), [
    ("EPİAŞ 2025 saatlik üretimi × ETKB 2023 emisyon faktörleri → her saatin karbon yoğunluğu CI(h). Kaydırılan "
     "enerjinin standart (B) ve hedef (S) penceredeki emisyonu karşılaştırılır.", {"size": 22})])
box(s, X2, Cm(26.6), COL, Cm(4.0), fill=SOFT, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, X2, Cm(26.8), COL, Cm(3.6), [
    ("B = Σ p·kWh(s+i)·CI(s+i)    S = Σ p·kWh(s+i)·CI(t+i)", {"size": 22, "bold": True, "align": PP_ALIGN.CENTER}),
    ("Değişim = (S − B) / B × 100", {"size": 24, "bold": True, "color": GREEN, "align": PP_ALIGN.CENTER})],
    anchor=MSO_ANCHOR.MIDDLE)

section(X1, Cm(31.4), CW, "Bulgular")
C3 = Emu(int((CW - Cm(2)) / 3))
s.shapes.add_picture(str(IMG / "07_saatlik_profil.png"), X1, Cm(33.2), width=C3)
s.shapes.add_picture(str(IMG / "08_aylik_etki.png"), X1 + C3 + Cm(1), Cm(33.2), width=C3)
rows = [("Makine", "Gün", "Değişim", "Yükte")]
rows += [(m["name"], str(m["days_ok"]), f"{num(m['delta_kg'], 0)} kg", pct(m["delta_pct"], 1)) for m in shiftable]
rows.append(("Toplam", "", f"{num(tot['delta_kg'], 0)} kg", pct(tot["delta_pct"], 1)))
TX = X1 + 2 * (C3 + Cm(1))
tbl = s.shapes.add_table(len(rows), 4, TX, Cm(33.2), C3, Cm(0.95 * len(rows))).table
for i, wv in enumerate([Cm(5.6), Cm(2.0), Cm(3.6), Cm(3.46)]):
    tbl.columns[i].width = wv
for ri, row in enumerate(rows):
    tbl.rows[ri].height = Cm(0.95)
    for ci, v in enumerate(row):
        c = tbl.cell(ri, ci)
        c.margin_left = c.margin_right = Cm(0.2)
        c.fill.solid()
        c.fill.fore_color.rgb = GREEN if ri == 0 else (SOFT if ri % 2 == 0 else WHITE)
        tf = c.text_frame
        r0 = tf.paragraphs[0].add_run()
        r0.text = v
        r0.font.size, r0.font.name = Pt(15), FONT
        r0.font.bold = ri in (0, len(rows) - 1)
        r0.font.color.rgb = WHITE if ri == 0 else TEXT
        tf.paragraphs[0].alignment = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER
text(s, X1, Cm(40.4), CW, Cm(1.0),
     "Örnek yükler (açık veri seti), 03:00–06:00 → 18:00–21:00, 2025 · Balıkesir tesisi değildir.", size=18,
     color=MUTED)

section(X1, Cm(41.8), CW, "Uygulama")
from PIL import Image
iw, ih = Image.open(IMG / "02_senaryo.png").size
sh_w = Emu(int((CW - Cm(1.5)) / 2))
s.shapes.add_picture(str(IMG / "02_senaryo.png"), X1, Cm(43.6), width=sh_w)
s.shapes.add_picture(str(IMG / "04_yillik_etki.png"), X1 + sh_w + Cm(1.5), Cm(43.6), width=sh_w)

y0 = Cm(43.6) + int(sh_w * ih / iw) + Cm(1.2)
third = Emu(int((CW - Cm(2)) / 3))
blocks = [("Yenilik", "Saatlik ve makine bazlı hesap · sayıları otomatik doğrulanan yapay zekâ (Delti) · "
                      "internetsiz çalışma · kullanıcının kendi verisini eklemesi"),
          ("Ticarileşme", "Enerji yoğun KOBİ'ler, OSB'ler, ihracatçılar ve danışmanlar · yıllık lisans + kurulum "
                          "hizmeti · Balıkesir'de pilot"),
          ("Sınırlılık", "Ortalama karbon yoğunluğu (gösterge niteliğinde) · örnek yük · marjinal faktör ve saha "
                         "doğrulaması yol haritasında")]
x = M
for head, body in blocks:
    box(s, x, y0, third, Cm(8.4), fill=SOFT, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x + Cm(0.8), y0 + Cm(0.6), third - Cm(1.6), Cm(1.5), head, size=28, bold=True, color=GREEN)
    text(s, x + Cm(0.8), y0 + Cm(2.3), third - Cm(1.6), Cm(5.8), body, size=20)
    x += third + Cm(1)
text(s, M, Cm(68.2), CW, Cm(1.2),
     "Kaynak: EPİAŞ Şeffaflık Platformu 2025 · ETKB 2023 Emisyon Faktörleri · Zenodo imalat yük verisi   "
     "·   İletişim: ismailaliaslan11@gmail.com", size=16, color=MUTED, align=PP_ALIGN.CENTER)
ps.save(HERE / "CarbonDelta_Poster_50x70_Taslak.pptx")
print("ok")
