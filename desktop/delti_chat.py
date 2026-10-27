"""Delti sohbet beyni: niyet tanıma, ön izleme (senaryoyu değiştirmeden hesap), hazır cevaplar, AI isteği.

Hesap her zaman motorda yapılır; Delti yalnızca sonucu anlatır. Ön izleme Senaryo sekmesine dokunmaz,
kullanıcı isterse "Senaryoya uygula" der.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from desktop import fmt
from desktop.ai_client import AIRequest
from engine import annual, data
from engine.best_window import best_window
from engine.core import simulate
from engine.insights import fossil_sensitivity, shifted_renewable

GREETING = "greeting"
THANKS = "thanks"
SCENARIO = "scenario"
QUESTION = "question"

_GREET = re.compile(r"^\s*(merhaba|selam|selamlar|günaydın|iyi günler|iyi akşamlar|hey|hi|hello)\b[\s!.,]*$", re.I)
_THANKS = re.compile(r"^\s*(teşekkür|teşekkürler|sağ ?ol|sağolun|eyvallah|thanks|tşk)", re.I)
_HOURISH = re.compile(r"\d{1,2}\s*(:|'|’|\.|da|de|den|dan|te|ta|ten|tan|e|a|ye|ya)\b|\b\d{1,2}\s*(saat|:00)", re.I)
_SCENARIO_WORDS = ("kaydır", "kaydir", "taşı", "tasi", "al ", "alırsak", "alirsak", "alsak", "kaydırsak",
                   "çalıştır", "calistir", "başlat", "baslat", "geçir", "gecir")


def classify(sentence: str) -> str:
    """Mesajın türü: selam, teşekkür, senaryo (ön izleme) ya da genel soru."""
    from desktop.ai_context import parse_nl_rule
    s = sentence.strip()
    if _GREET.match(s):
        return GREETING
    if _THANKS.match(s) and len(s) < 40:
        return THANKS
    rule = parse_nl_rule(s)
    low = s.lower() + " "
    has_hours = "s" in rule or "t" in rule
    if has_hours and ("asset_id" in rule or any(w in low for w in _SCENARIO_WORDS)):
        return SCENARIO
    if "asset_id" in rule and has_hours:
        return SCENARIO
    return QUESTION


# ------------------------------------------------------------------ ön izleme
@dataclass
class Preview:
    merged: dict          # asset_id, date, s, L, t, p
    text: str             # kullanıcıya gösterilecek açıklama (HTML'siz düz metin, satırlarla)
    ok: bool


def _nearest_day(days: list[str], iso: str) -> str:
    if iso in days:
        return iso
    from desktop.tools_tabs import nearest_day
    return nearest_day(days, iso)


def preview(merged: dict, current, note: str = "") -> Preview:
    """Senaryoyu değiştirmeden motorla hesaplar; daha iyi saat ve yıllık etkiyi de ekler."""
    m = data.machine(merged["asset_id"])
    date = _nearest_day(m["days"], merged.get("date") or current.date)
    merged = {**merged, "date": date}
    s, L, t, p = merged["s"], merged["L"], merged["t"], merged["p"]
    kind = current.ci_kind
    param = current.param_kwh if current.parametric else None
    load, ci = data.scenario_series(m["id"], date, kind, param)
    restricted = set(current.restricted)
    r = simulate(load, ci, s, L, t, p, restricted, m["shiftable"])
    unit = "kgCO2" if kind == "tCO2" else "kgCO2-eşd"
    head = (f"{m['name']} · {fmt.date(date)} · {fmt.window(s, L)} → {fmt.window(t, L)} · "
            f"%{fmt.num(p * 100, 0)}")
    lines = [f"Ön izleme (Senaryo sekmesi değişmedi): {head}"]
    if r.status != "ok":
        from desktop.main_window import status_message
        lines.append(status_message(r, restricted, p) or "Bu girdilerle hesap yapılamadı.")
        if r.status == "restricted_conflict":
            lines.append("Kısıtlı saatleri Senaryo sekmesinden değiştirebilir ya da başka bir hedef saat deneyebilirsiniz.")
        if r.status == "no_load" and p > 0:
            lines.append("Bu makine o saatlerde çalışmıyor; makinenin çalıştığı bir standart saat deneyin.")
        return Preview(merged, "\n".join(lines), False)
    verb = "düşer" if r.delta_pct <= 0 else "artar"
    lines.append(f"Sonuç: {fmt.pct(r.delta_pct)}. Taşınan {fmt.num(r.shifted_kwh)} kWh enerjinin emisyonu "
                 f"{fmt.num(r.baseline_kg)} {unit} yerine {fmt.num(r.scenario_kg)} {unit} olur, yani emisyon {verb}. "
                 f"Makinenin o günkü toplam emisyonuna etkisi {fmt.pct(r.daily_delta_pct)}.")
    ren = shifted_renewable(date, load, s, L, t, p)
    fos = fossil_sensitivity(load, data.ci_fossil_24(date, kind), s, L, t, p)[2]
    extra = []
    if ren:
        extra.append(f"kaydırılan enerjinin yenilenebilir payı %{fmt.num(ren[0], 1)} → %{fmt.num(ren[1], 1)}")
    if fos is not None:
        extra.append(f"fosil marjinal varsayımla değişim {fmt.pct(fos)}")
    if extra:
        lines.append("Ayrıca " + "; ".join(extra) + ".")
    best = best_window(load, ci, s, L, p, restricted, True)
    if best is not None and best[0] != t and best[1].scenario_kg < r.scenario_kg - 1e-9:
        bt, br = best
        lines.append(f"Daha iyisi var: aynı gün {fmt.window(bt, L)} penceresi {fmt.pct(br.delta_pct)} verir.")
    elif best is not None and best[0] == t:
        lines.append("Bu, o gün için seçilebilecek en temiz hedef pencere.")
    try:
        year = int(date[:4])
        ar = annual.annual_impact(m["id"], year, s, L, t, p, restricted, kind,
                                  annual.year_series(m["id"], year, kind, param))
        if ar.days_ok:
            kg = abs(ar.delta_kg)
            amount = f"{fmt.num(kg / 1000)} t" if kg >= 1000 else f"{fmt.num(kg, 1)} kg"
            yverb = "azalır" if ar.delta_kg <= 0 else "artar"
            lines.append(f"Yıl boyunca her gün uygulanırsa ({ar.days_ok} gün): emisyon {amount} {yverb} "
                         f"({fmt.pct(ar.delta_pct)}).")
    except Exception:  # noqa: BLE001 — yıllık özet ek bilgidir; hata ön izlemeyi bozmasın
        pass
    if note:
        lines.append(note)
    lines.append("Uygun görürseniz “Senaryoya uygula” ile Senaryo sekmesine aktarabilirsiniz.")
    return Preview(merged, "\n".join(lines), True)


# ------------------------------------------------------------------ hazır cevaplar
FAQ: list[tuple[tuple[str, ...], str]] = [
    (("ne yapıyor", "ne işe yarıyor", "ne ise yariyor", "amacı", "amaci", "nedir bu", "bu program", "bu uygulama",
      "carbondelta nedir", "ne yapar"),
     "CarbonDelta, bir makinenin elektrik yükünü günün başka bir saatine kaydırdığınızda şebeke kaynaklı karbon "
     "emisyonunun ne kadar değişeceğini hesaplar. Şebekedeki üretim karışımı saat saat değiştiği için aynı elektrik "
     "her saatte aynı karbonu taşımaz; uygulama en temiz saati bulmanıza, bir kaydırmanın yıllık etkisini ve tüm "
     "tesisin günlük planını görmenize yardım eder. Karar her zaman sizdedir; uygulama makinelere müdahale etmez."),
    (("nasıl kullan", "nasil kullan", "nereden başla", "nereden basla", "ilk adım", "ilk adim", "kullanım", "kullanim"),
     "Senaryo sekmesinde makineyi ve günü seçin, standart başlangıç saatini, pencere uzunluğunu, hedef saati ve "
     "kaydırma oranını girin; sonuç anında görünür. ‘En iyi saati bul’ (Ctrl+B) en temiz hedefi seçer. Yıllık etki "
     "sekmesi aynı kaydırmanın bir yıllık toplamını, Tesis planı tüm makinelerin günlük planını gösterir. Bana da "
     "“Kompresörü 18'e alırsak ne olur?” gibi sorabilirsiniz."),
    (("delti", "sen kimsin", "sen nesin", "yapay zek", "ai ne"),
     "Ben Delti, CarbonDelta'nın yardımcısıyım. Sorularınızı yanıtlarım, “şöyle yaparsak ne olur?” sorularında "
     "senaryoyu değiştirmeden ön izleme yaparım ve sonuçları sade bir dille açıklarım. Hesabı ben yapmam; hesap "
     "kilitli formülle yapılır ve yazdığım her sayı bu hesapla karşılaştırılır."),
    (("veri", "kaynak", "epiaş", "epias", "etkb", "zenodo", "nereden al"),
     "Şebeke verisi EPİAŞ Şeffaflık Platformu'nun saatlik gerçek zamanlı üretim verisidir; emisyon katsayıları Enerji "
     "ve Tabii Kaynaklar Bakanlığı'nın (ETKB) resmî faktörleridir. Makine yükleri bir imalat tesisine ait açık bir "
     "veri setinden (Zenodo) alınmış örnek yüklerdir; Balıkesir tesisi değildir. Kendi ölçümlerinizi Veri sekmesinden "
     "ekleyebilirsiniz; ayrıntılar Kaynaklar sekmesindedir."),
    (("karbon yoğunluğu", "karbon yogunlugu", "yoğunluk nedir", "ci nedir"),
     "Karbon yoğunluğu, o saatte üretilen her megavatsaat elektriğin kaç ton CO2 salımına yol açtığıdır (tCO2/MWh). "
     "Her saatin değeri, kaynakların (doğal gaz, kömür, rüzgâr, güneş, hidro…) o saatteki üretim paylarının emisyon "
     "katsayılarıyla çarpılmasıyla bulunur. Yenilenebilirlerin payı yüksek olan saatlerde yoğunluk düşüktür."),
    (("formül", "formul", "nasıl hesap", "nasil hesap", "hesap nasıl", "hesap nasil"),
     "Taşınan enerji, standart penceredeki her saatin tüketiminin kaydırma oranıyla çarpılmasıdır. Bu enerjinin "
     "standart saatlerdeki emisyonu (B) ile hedef saatlerdeki emisyonu (S) karşılaştırılır: değişim = (S − B) / B × 100. "
     "Eksi değer daha düşük emisyon demektir. Saat saat döküm Hesabı Göster sekmesindedir."),
    (("yıllık", "yillik", "bir yıl", "bir yil", "yılda", "yilda"),
     "Yıllık etki, Senaryo'daki kaydırmanın seçilen yılın verisi olan her gününde uygulanmasıyla bulunan toplamdır: "
     "yılda kaç kg ya da ton CO2 değiştiği, yenilenebilir pay ve aylık kırılım. Tek makine ya da tesis geneli "
     "seçilebilir; PDF rapor ve CSV alınabilir. Verisi olmayan günler tahminle doldurulmaz."),
    (("tesis plan", "tüm makine", "tum makine", "tepe yük", "tepe yuk", "plan"),
     "Tesis planı, seçilen günde her makine için ayrı ayrı en temiz hedef saati bulur. Bütün yükler aynı saate "
     "toplanırsa tesisin tepe yükü artabilir; bu yüzden bir tepe sınırı girebilirsiniz. Planlayıcı sınırı aşan "
     "makineyi sınırı aşmayan bir sonraki en temiz saate alır."),
    (("en temiz", "en iyi saat", "hangi saat"),
     "Genel olarak gece ve sabahın erken saatleri (yaklaşık 03:00–06:00) en kirli, akşam saatleri (yaklaşık "
     "17:00–21:00) en temizdir. Belirli bir makine ve gün için kesin cevabı En Temiz Saat sekmesi verir; Senaryo'da "
     "‘En iyi saati bul’ (Ctrl+B) da kullanabilirsiniz."),
    (("neden akşam", "neden aksam", "neden gece", "niye"),
     "Gece talep düşükken üretimde kömür santrallerinin payı artar, bu da karbon yoğunluğunu yükseltir. Akşam "
     "saatlerinde ise üretimde doğal gaz ve yenilenebilir kaynakların payı daha yüksektir; bu yüzden aynı elektrik "
     "daha az karbon taşır."),
    (("oran", "yüzde neden değişmiyor", "yuzde neden degismiyor"),
     "Kaydırma oranı, standart penceredeki yükün ne kadarının taşınacağıdır. Yüzde değişim orandan bağımsızdır, "
     "çünkü oran hem standart hem hedef emisyonu aynı ölçüde değiştirir; oran taşınan kWh'ı, kg değerlerini ve "
     "günlük etkiyi değiştirir. Grafikte taşınan kısım kesikli, hedefe eklenen kısım yeşil görünür."),
    (("kısıtlı", "kisitli"),
     "Kısıtlı saatler, vardiya, gürültü ya da bakım gibi nedenlerle makinenin çalışamayacağı saatlerdir. Senaryo "
     "sekmesinde işaretlediğiniz saatler hedef olarak seçilemez; En Temiz Saat, Yıllık Etki ve Tesis Planı da bu "
     "saatleri dikkate alır."),
    (("fosil", "marjinal"),
     "Ana sonuç saatlik ortalama karbon yoğunluğuyla hesaplanır. Gerçekte bir yük kaydırıldığında üretimini değiştiren "
     "santral genellikle fosil bir santraldir; bu yüzden uygulama, kaydırılan yükü yalnızca fosil santrallerin "
     "karşıladığı varsayımıyla daha temkinli ikinci bir değer de gösterir. Gerçek etki büyük olasılıkla ikisinin arasındadır."),
    (("yenilenebilir",),
     "Yenilenebilir payı, kaydırılan enerjinin tüketildiği saatlerde şebekedeki rüzgâr, güneş, hidro, jeotermal ve "
     "biyokütle üretiminin payıdır. Standart pencereden hedef pencereye bu pay artıyorsa enerjiyi daha temiz "
     "kaynakların ağırlıklı olduğu saatlere taşıyorsunuz demektir."),
    (("veri ekle", "makine ekle", "yeni yıl", "yeni yil", "kendi veri"),
     "Veri sekmesinden yeni bir makine (saatlik ya da 15 dakikalık kWh ölçümü), EPİAŞ'tan indirilen yeni bir yıl ya da "
     "yeni emisyon katsayıları ekleyebilirsiniz. Dosya CSV ya da Excel olabilir; uygulama eksik saatleri ve hatalı "
     "değerleri denetler. Eklenenler Kaynaklar sekmesinde listelenir."),
    (("kısayol", "kisayol", "klavye"),
     "Esc ana sayfaya döner, F1 kılavuzu açar, F11 tam ekran yapar. Ctrl+1…0 sekmeler arasında geçer, Ctrl+B en iyi "
     "saati bulur, Ctrl+S senaryoyu kaydeder, Ctrl+virgül Delti ayarlarını açar."),
    (("internet", "çevrimdışı", "cevrimdisi", "api", "anahtar"),
     "Bütün hesaplar internetsiz çalışır. Benim (Delti) daha ayrıntılı cevap verebilmem için bir yapay zekâ API "
     "anahtarı gerekir; Ctrl+virgül ile ayarlardan Gemini, Claude, GPT ya da Grok anahtarı girebilirsiniz. Anahtar "
     "yoksa hazır cevaplarla ve ön izlemeyle yardımcı olmaya devam ederim."),
    (("sınırlı", "sinirli", "eksik", "doğru mu", "dogru mu", "güvenilir", "guvenilir"),
     "Sonuçlar ortalama karbon yoğunluğuyla hesaplanır, bu yüzden karşılaştırma ve önceliklendirme için bir göstergedir. "
     "Yük verisi örnek veridir; kaydırma aynı gün içinde yapılır; elektrik ithalatı ve ihracatı hesaba girmez. Temkinli "
     "bir alt sınır için fosil marjinal değerine bakabilirsiniz."),
    (("kim geliştir", "kim gelistir", "iletişim", "iletisim", "kim yaptı", "kim yapti"),
     "CarbonDelta'yı İsmail Ali Aslan ve Emin Burak Öztürk geliştirdi; danışman Öğr. Gör. Ali Erfidan (Balıkesir "
     "Üniversitesi). İletişim bilgileri İletişim sekmesindedir."),
]

HELP = ("Size şu konularda yardımcı olabilirim: uygulamanın ne yaptığı ve nasıl kullanıldığı, veri kaynakları, karbon "
        "yoğunluğu, yıllık etki ve tesis planı. Ayrıca “Kompresörü 3'ten 18'e alırsak ne olur?” gibi sorularda "
        "senaryoyu değiştirmeden ön izleme yapabilirim.")

SUGGESTIONS = ["Bu program ne yapıyor?", "Kompresörü 3'ten 18'e alırsak ne olur?", "En temiz saat hangisi?",
               "Yıllık etki nedir?", "Verileri nereden alıyorsunuz?"]


def faq(sentence: str) -> str | None:
    low = sentence.lower()
    for keys, answer in FAQ:
        if any(k in low for k in keys):
            return answer
    return None


def local_reply(kind: str) -> str:
    if kind == GREETING:
        return "Merhaba! " + HELP
    if kind == THANKS:
        return "Rica ederim! Başka bir sorunuz ya da denemek istediğiniz bir kaydırma olursa yazabilirsiniz."
    return HELP


# ------------------------------------------------------------------ AI sohbet isteği
KNOWLEDGE = (
    "CarbonDelta: endüstriyel elektrik yüklerini daha düşük karbonlu saatlere kaydırmanın şebeke emisyonuna etkisini "
    "hesaplayan, Windows masaüstü ve Android için karar destek uygulaması. Hesap kilitli formülle yapılır: taşınan enerji "
    "E = oran × saatlik tüketim; B = Σ E × CI(standart saat); S = Σ E × CI(hedef saat); değişim = (S − B) / B × 100; "
    "günlük etki = (S − B) / günlük toplam emisyon × 100. CI, saatin karbon yoğunluğudur (tCO2/MWh) ve EPİAŞ saatlik "
    "üretimi ile ETKB emisyon faktörlerinden hesaplanır. Varsayılan veri: EPİAŞ 2025 (8760 saat), ETKB 2023 (15 yakıt "
    "katsayısı), Zenodo imalat tesisi örnek yükleri (7 makine). Yük verisi örnektir, Balıkesir tesisi değildir. "
    "2025 yıllık ortalamada 03:00–06:00 en kirli, 17:00–21:00 en temiz saatlerdir. "
    "Sekmeler: Senaryo (kaydırma hesabı, kısıtlı saatler, kaydırma oranı, parametrik mod, tCO2/tCO2-eşd), En Temiz Saat "
    "(günün bütün hedef pencerelerinin sıralaması), Yıllık Etki (aynı kaydırmanın yıllık toplamı, tesis geneli, PDF/CSV), "
    "Tesis Planı (her makine için en temiz saat, tepe yük sınırı), Delti'ye Sor, Hesabı Göster (saat saat döküm), Geçmiş "
    "(kayıtlı senaryolar), Veri (yeni makine, yeni yıl, yeni katsayı), Kılavuz, Kaynaklar, İletişim. Yüzde değişim "
    "kaydırma oranından bağımsızdır; oran kg ve günlük etkiyi değiştirir. Ek göstergeler: kaydırılan enerjinin "
    "yenilenebilir payı ve fosil marjinal duyarlılık (yükü yalnızca fosil santrallerin karşıladığı varsayımı). "
    "Sınırlılıklar: ortalama yoğunluk, örnek yük, aynı gün içinde kaydırma, ithalat/ihracat yok. Para/TL kazancı ve "
    "CBAM hesabı kapsam dışıdır. Kısayollar: Esc ana sayfa, F1 kılavuz, F11 tam ekran, Ctrl+B en iyi saat, Ctrl+S kaydet, "
    "Ctrl+virgül Delti ayarları. Geliştiriciler: İsmail Ali Aslan, Emin Burak Öztürk; danışman Öğr. Gör. Ali Erfidan "
    "(Balıkesir Üniversitesi)."
)


def chat_request(question: str, current_comp, history: list[tuple[str, str]]) -> AIRequest:
    """Genel soru için AI isteği. Şablon metin (çevrimdışı/doğrulanamayan) hazır cevap ya da yardım metnidir."""
    ctx = {}
    if current_comp is not None:
        i, r, m = current_comp.inputs, current_comp.result, current_comp.machine
        ctx = {"makine": m["name"], "gun": fmt.date(i.date), "standart_pencere": fmt.window(i.s, i.L),
               "hedef_pencere": fmt.window(i.t, i.L), "oran_yuzde": i.p * 100, "durum": r.status}
        if r.status == "ok":
            ctx.update({"degisim_yuzde": r.delta_pct, "standart_emisyon_kg": r.baseline_kg,
                        "secilen_emisyon_kg": r.scenario_kg, "kaydirilan_enerji_kwh": r.shifted_kwh,
                        "gunluk_etki_yuzde": r.daily_delta_pct})
    sm = data.source_summary() if hasattr(data, "source_summary") else None
    payload = {"bilgi": KNOWLEDGE, "mevcut_senaryo": ctx,
               "yuklu_makineler": [x["name"] for x in data.machines()],
               "son_mesajlar": [{"kim": who, "metin": txt[:400]} for who, txt in history[-6:]]}
    if sm:
        payload["yuklu_veri"] = {"sebeke": [k for k, _ in sm["grids"]], "katsayi": sm["factors"]}
    return AIRequest("chat", payload, {"answer": faq(question) or HELP}, extra={"question": question})
