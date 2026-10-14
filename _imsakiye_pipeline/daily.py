"""Daily content for @imsakiye.social.

Renders into ../imsakiye/ (published by GitHub Pages):
  story/<YYYY-MM-DD>.jpg   today's prayer times for 8 cities (Diyanet, cross-checked)
  reels/esma-<YYYY-MM-DD>.mp4   Esmâ-ül Hüsnâ series, one name per day
  daily/<YYYY-MM-DD>.json  manifest the Supabase publisher reads (captions, urls)

Nothing is published here; Supabase posts the files at the scheduled times.
If the prayer-time sources disagree, no story is produced for that day.
"""
import datetime as dt, json, re, shutil, subprocess, sys, urllib.request
import religious
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "imsakiye"
BASE_URL = "https://yagia.github.io/imsakiye"
TZ = ZoneInfo("Europe/Istanbul")
CITIES = [("İstanbul", 9541, "Istanbul"), ("Ankara", 9206, "Ankara"), ("İzmir", 9560, "Izmir"), ("Antalya", 9225, "Antalya"),
          ("Samsun", 9819, "Samsun"), ("Erzurum", 9451, "Erzurum"), ("Diyarbakır", 9402, "Diyarbakir"), ("Adana", 9146, "Adana")]
MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
ESMA_START = dt.date(2026, 10, 14)       # day 1 of the series
KEYS = ["imsak", "gunes", "ogle", "ikindi", "aksam", "yatsi"]


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "imsakiye-social/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def prayer_times(day):
    """Diyanet's timetable (imsakiyem mirror), cross-checked against Aladhan's Diyanet method."""
    stamp = day.isoformat()
    out, hijri = [], None
    for name, cid, en in CITIES:
        d = get(f"https://ezanvakti.imsakiyem.com/api/prayer-times/{cid}/range?startDate={stamp}&endDate={stamp}")
        row = d["data"][0]
        t = row["times"]
        hijri = hijri or row["hijri_date"]["full_date"]
        a = get(f"https://api.aladhan.com/v1/timingsByCity/{day.strftime('%d-%m-%Y')}?city={en}&country=Turkey&method=13")["data"]["timings"]
        ref = {"imsak": a["Fajr"], "gunes": a["Sunrise"], "ogle": a["Dhuhr"], "ikindi": a["Asr"], "aksam": a["Maghrib"], "yatsi": a["Isha"]}
        for k in KEYS:
            if abs(minutes(t[k]) - minutes(ref[k][:5])) > 4:
                raise SystemExit(f"Prayer-time sources disagree for {name} {k}: {t[k]} vs {ref[k]} – no story today.")
        out.append({"name": name, **{k: t[k] for k in KEYS}})
    return {"date": f"{day.day} {MONTHS[day.month - 1]} {day.year}", "weekday": DAYS[day.weekday()],
            "hijri": hijri.replace("Cemaziyelevvel", "Cemâziyelevvel").replace("Cemaziyelahir", "Cemâziyelâhir"), "cities": out}


def shoot(page_file, data, out_png, times=None):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.add_init_script(f"window.__DATA__ = {json.dumps(data, ensure_ascii=False)};")
        pg.goto((HERE / page_file).as_uri())
        pg.wait_for_timeout(800)
        if times is None:
            pg.screenshot(path=str(out_png))
        else:
            for i, t in enumerate(times):
                pg.evaluate(f"render({t})")
                pg.screenshot(path=str(out_png / f"{i:05d}.jpg"), type="jpeg", quality=92)
        b.close()


def story(day):
    from PIL import Image
    data = prayer_times(day)
    png = HERE / "story.png"
    shoot("story.html", data, png)
    dst = SITE / "story" / f"{day.isoformat()}.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.open(png).convert("RGB").save(dst, "JPEG", quality=92)
    return f"{BASE_URL}/story/{day.isoformat()}.jpg"


SURAHS = ("Fâtiha Bakara Âl-i_İmrân Nisâ Mâide En'âm A'râf Enfâl Tevbe Yûnus Hûd Yûsuf Ra'd İbrâhîm Hicr Nahl İsrâ Kehf "
          "Meryem Tâhâ Enbiyâ Hac Mü'minûn Nûr Furkân Şuarâ Neml Kasas Ankebût Rûm Lokmân Secde Ahzâb Sebe' Fâtır Yâsîn "
          "Sâffât Sâd Zümer Mü'min Fussilet Şûrâ Zuhruf Duhân Câsiye Ahkâf Muhammed Fetih Hucurât Kâf Zâriyât Tûr Necm Kamer "
          "Rahmân Vâkıa Hadîd Mücâdele Haşr Mümtehine Saf Cuma Münâfikûn Teğâbün Talâk Tahrîm Mülk Kalem Hâkka Meâric Nûh Cin "
          "Müzzemmil Müddessir Kıyâme İnsân Mürselât Nebe' Nâziât Abese Tekvîr İnfitâr Mutaffifîn İnşikâk Bürûc Târık A'lâ "
          "Gâşiye Fecr Beled Şems Leyl Duhâ İnşirâh Tîn Alak Kadir Beyyine Zilzâl Âdiyât Kâria Tekâsür Asr Hümeze Fîl Kureyş "
          "Mâûn Kevser Kâfirûn Nasr Tebbet İhlâs Felak Nâs").split()
SURAHS = [x.replace("_", " ") for x in SURAHS]
assert len(SURAHS) == 114
NARRATORS = {"Bukhari": "Buhârî", "Muslim": "Müslim", "Tirmidhi": "Tirmizî", "Abu Dawud": "Ebû Dâvûd",
             "Ibn Majah": "İbn Mâce", "Hakim": "Hâkim", "Nasai": "Nesâî", "Ahmad": "Ahmed b. Hanbel"}


def frames_dir():
    frames = HERE / "frames"
    shutil.rmtree(frames, ignore_errors=True); frames.mkdir()
    return frames


def encode_reel(frames, fps, dur, dst):
    subprocess.run([sys.executable, str(HERE / "music.py"), str(dur), str(HERE / "music.wav"), str(dur + 5), "calm"], check=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames / "%05d.jpg"),
                    "-i", str(HERE / "music.wav"), "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
                    "-crf", "20", "-preset", "slow", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest",
                    "-movflags", "+faststart", str(dst)], check=True)


def still(page_file, data, dst, size):
    from PIL import Image
    from playwright.sync_api import sync_playwright
    png = HERE / "story.png"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": size[0], "height": size[1]})
        pg.add_init_script(f"window.__DATA__ = {json.dumps(data, ensure_ascii=False)};")
        pg.goto((HERE / page_file).as_uri()); pg.wait_for_timeout(800)
        pg.screenshot(path=str(png)); b.close()
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.open(png).convert("RGB").save(dst, "JPEG", quality=92)


def esma_reel(day):
    names = json.loads((HERE / "esma.json").read_text())
    n = ((day - ESMA_START).days % 99) + 1
    item = names[n - 1]
    frames = frames_dir(); fps, dur = 30, 12
    shoot("esma.html", item, frames, [i / fps for i in range(fps * dur)])
    encode_reel(frames, fps, dur, SITE / "reels" / f"esma-{day.isoformat()}.mp4")
    caption = (f"Esmâ-ül Hüsnâ · {n}/99\n{item['transliteration']} ✨\n\n"
               "Her gün Allah'ın güzel isimlerinden birini paylaşıyoruz. Takipte kal, serinin tamamını kaçırma.\n\n"
               "📲 99 ismin tamamı İmsakiye uygulamasında, App Store'da ücretsiz.\n\n"
               "#esmaülhüsna #allahın99ismi #imsakiye #dua #zikir #islam")
    return f"{BASE_URL}/reels/esma-{day.isoformat()}.mp4", caption


def verse_reel(day):
    """The app's verse of the day (same list and order), Diyanet Vakfı translation."""
    refs = json.loads((HERE / "verses.json").read_text())
    s, a = refs[(day - dt.date(2026, 1, 1)).days % len(refs)]
    text = get(f"https://api.alquran.cloud/v1/ayah/{s}:{a}/tr.vakfi")["data"]["text"].strip()
    if len(text) < 10:
        raise SystemExit("verse text missing")
    ref = f"{SURAHS[s - 1]} Sûresi, {a}. ayet"
    words = len(text.split())
    dur = int(min(30, max(12, 6.5 + words * 0.32)))
    frames = frames_dir(); fps = 30
    shoot("verse.html", {"ref": ref, "text": text, "duration": dur}, frames, [i / fps for i in range(fps * dur)])
    encode_reel(frames, fps, dur, SITE / "reels" / f"ayet-{day.isoformat()}.mp4")
    caption = (f"Günün Ayeti 📖\n\n“{text}”\n({ref})\n\nMeal: Diyanet Vakfı\n\n"
               "📲 Her gün bir ayet, Arapça metni ve tefsiriyle İmsakiye uygulamasında.\n\n"
               "#gününayeti #kuranıkerim #ayet #meal #imsakiye #islam")
    return f"{BASE_URL}/reels/ayet-{day.isoformat()}.mp4", caption


def hadis_post(day):
    items = json.loads((HERE / "hadis.json").read_text())
    h = items[day.toordinal() % len(items)]
    src = NARRATORS.get(h["source"], h["source"])
    still("post.html", {"text": h["tr"], "source": f"— {src}"}, SITE / "post" / f"{day.isoformat()}.jpg", (1080, 1350))
    caption = (f"Günün Hadisi\n\n“{h['tr']}”\n— {src}\n\n💚 Kaydet, paylaş, hatırlat.\n\n"
               "#hadis #gününhadisi #sünnet #imsakiye #islam")
    return f"{BASE_URL}/post/{day.isoformat()}.jpg", caption


def dua_story(day):
    items = [d for d in json.loads((HERE / "dua.json").read_text()) if re.search(r"\b(\d+):(\d+)", d["source"]) and d.get("ar")]
    d = items[day.toordinal() % len(items)]
    s, a = map(int, re.search(r"\b(\d+):(\d+)", d["source"]).groups())
    still("dua.html", {"ar": d["ar"], "tr": d["tr"], "source": f"{SURAHS[s - 1]} Sûresi, {a}. ayet"},
          SITE / "story" / f"dua-{day.isoformat()}.jpg", (1080, 1920))
    return f"{BASE_URL}/story/dua-{day.isoformat()}.jpg"


GREETINGS = {
    "regaib":  ("Regaib Kandiliniz mübarek olsun", "Bu mübarek gecenin ailemize, ülkemize ve tüm İslam âlemine hayırlar getirmesini dileriz."),
    "mirac":   ("Miraç Kandiliniz mübarek olsun", "Bu mübarek gecenin ailemize, ülkemize ve tüm İslam âlemine hayırlar getirmesini dileriz."),
    "berat":   ("Berat Kandiliniz mübarek olsun", "Bu mübarek gecenin ailemize, ülkemize ve tüm İslam âlemine hayırlar getirmesini dileriz."),
    "mevlid":  ("Mevlid Kandiliniz mübarek olsun", "Bu mübarek gecenin ailemize, ülkemize ve tüm İslam âlemine hayırlar getirmesini dileriz."),
    "kadir":   ("Kadir Gecesi'niz mübarek olsun", "Bin aydan hayırlı bu gecenin hayırlara vesile olmasını dileriz."),
    "ramadanBegins": ("Hayırlı Ramazanlar", "Ramazan-ı Şerif'in sağlık, huzur ve bereketle geçmesini dileriz."),
    "ramadanFeast":  ("Ramazan Bayramınız mübarek olsun", "Bayramın sevdiklerinizle birlikte huzur ve bereket getirmesini dileriz."),
    "kurbanFeast":   ("Kurban Bayramınız mübarek olsun", "Bayramın sevdiklerinizle birlikte huzur ve bereket getirmesini dileriz."),
    "ramadanArefe":  ("Arefe gününüz hayırlı olsun", "Yarın Ramazan Bayramı."),
    "kurbanArefe":   ("Arefe gününüz hayırlı olsun", "Yarın Kurban Bayramı."),
    "hijriNewYear":  ("Hicri yeni yılınız mübarek olsun", "Yeni yılın hayırlara vesile olmasını dileriz."),
    "ashura":        ("Aşure Günü", "Bereketli ve hayırlı bir Aşure günü dileriz."),
    "threeMonthsBegin": ("Üç Aylar başladı", "Receb, Şaban ve Ramazan'ın hayırlara vesile olmasını dileriz."),
}
DATIVE = {"regaib": "Regaib Kandili'ne", "mirac": "Miraç Kandili'ne", "berat": "Berat Kandili'ne", "mevlid": "Mevlid Kandili'ne",
          "kadir": "Kadir Gecesi'ne", "ramadanBegins": "Ramazan'a"}
TAGS = "#imsakiye #hayırlıcumalar #kandil #bayram #ramazan #dua"


def quran_duas():
    return [d for d in json.loads((HERE / "dua.json").read_text()) if re.search(r"\b(\d+):(\d+)", d["source"]) and d.get("ar")]


def dua_of(day, shift=0):
    items = quran_duas()
    d = items[(day.toordinal() + shift) % len(items)]
    s, a = map(int, re.search(r"\b(\d+):(\d+)", d["source"]).groups())
    return {"ar": d["ar"], "tr": d["tr"], "source": f"{SURAHS[s - 1]} Sûresi, {a}. ayet"}


def special_card(day, name, data, size):
    folder = "post" if size == "post" else "story"
    dst = SITE / folder / f"{name}-{day.isoformat()}.jpg"
    still("special.html", {**data, "size": size}, dst, (1080, 1350 if size == "post" else 1920))
    return f"{BASE_URL}/{folder}/{name}-{day.isoformat()}.jpg"


def overrides(day):
    """Special-day content that takes the place of the noon post and/or the evening story."""
    out = {}
    occ = [k for k, _ in religious.on(day) if k in GREETINGS]
    if occ:
        k = occ[-1] if "regaib" not in occ else "regaib"     # Regaib shares its day with the three months
        title, sub = GREETINGS[k]
        kicker = religious.NAMES[k]
        card = {"kicker": kicker, "title": title, "sub": sub, "dua": dua_of(day)}
        out["noon_post"] = (special_card(day, "ozel", card, "post"),
                            f"{title} 🤲\n\n{sub}\n\n{card['dua']['tr']}\n({card['dua']['source']})\n\n{TAGS}")
        out["evening_story"] = special_card(day, "ozel", {"kicker": kicker, "title": title, "sub": sub}, "story")
        return out
    if day.weekday() == 4:                                       # Friday
        card = {"kicker": "Cuma", "title": "Hayırlı Cumalar", "sub": "Cumanız mübarek, dualarınız kabul olsun.", "dua": dua_of(day, 7)}
        out["noon_post"] = (special_card(day, "cuma", card, "post"),
                            f"Hayırlı Cumalar 🤲\n\n{card['dua']['tr']}\n({card['dua']['source']})\n\n"
                            "Sevdiklerinle paylaş, duaya ortak olsunlar.\n\n#hayırlıcumalar #cuma #dua #imsakiye")
    nxt = religious.next_after(day, set(DATIVE))
    if nxt:
        k, when = nxt
        left = (when - day).days
        if (k == "ramadanBegins" and left <= 30) or (k != "ramadanBegins" and left <= 3):
            card = {"kicker": "Geri sayım", "big": str(left), "title": f"{DATIVE[k]} {left} gün",
                    "sub": f"{when.day} {MONTHS[when.month - 1]} {DAYS[when.weekday()]}"
                           + (" gecesi" if k in religious.NIGHTS else ""), "dua": dua_of(day, 3)}
            out["evening_story"] = special_card(day, "sayac", card, "story")
    return out


def main():
    day = dt.datetime.now(TZ).date() if len(sys.argv) < 2 else dt.date.fromisoformat(sys.argv[1])
    manifest = {"date": day.isoformat(), "items": []}

    def add(slot, kind, fn):
        try:
            r = fn(day)
            url, caption = (r, None) if isinstance(r, str) else r
            manifest["items"].append({"slot": slot, "kind": kind, "url": url, "caption": caption})
        except BaseException as e:      # one failed piece must not stop the others
            print(f"{slot}: skipped ({e})")

    special = {}
    try:
        special = overrides(day)
    except BaseException as e:
        print(f"special: skipped ({e})")
    add("morning_story", "story_image", story)
    add("morning_reel", "reel", verse_reel)
    add("noon_post", "image", (lambda d: special["noon_post"]) if "noon_post" in special else hadis_post)
    add("evening_story", "story_image", (lambda d: special["evening_story"]) if "evening_story" in special else dua_story)
    add("evening_reel", "reel", esma_reel)
    out = SITE / "daily" / f"{day.isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
