"""Daily content for @imsakiye.social.

Renders into ../imsakiye/ (published by GitHub Pages):
  story/<YYYY-MM-DD>.jpg   today's prayer times for 8 cities (Diyanet, cross-checked)
  reels/ayet-, ayet2-, dua-<YYYY-MM-DD>.mp4   story reels: hook → verse/dua → note → CTA → app end card
  story/esma-<YYYY-MM-DD>.jpg   Esmâ-ül Hüsnâ series, one name per day (evening story)
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


def encode_reel(frames, fps, dur, dst, vo=None):
    subprocess.run([sys.executable, str(HERE / "music.py"), str(dur), str(HERE / "music.wav"), str(dur + 5), "calm"], check=True)
    audio = HERE / "music.wav"
    if vo:     # music sits under the narration and dips while it speaks
        audio = HERE / "mix.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(HERE / "music.wav"), "-i", str(vo), "-filter_complex",
                        "[1:a]aformat=channel_layouts=stereo,asplit=2[v1][v2];[0:a]volume=0.2[m];"
                        "[m][v1]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=450[md];"
                        "[md][v2]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", "48000", "-ac", "2", str(audio)], check=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames / "%05d.jpg"),
                    "-i", str(audio), "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
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



# ---------------------------------------------------------------- story reels (hook → verse → note → CTA → app)
import reels_content as RC

REEL_EPOCH = dt.date(2026, 10, 15)
APP_SHOTS = [("times", "Namaz vakitleri ve 30 günlük imsakiye"), ("quran", "Kur'an-ı Kerim: meal, tefsir ve dinleme"),
             ("qibla", "Kıble pusulası ve yakındaki camiler"), ("tracker", "Namaz takibi ve akşam hatırlatması"),
             ("hatim", "Hatim planı: her gün biraz")]
CTA = {"amin": ("Yorumlara “Âmin” yaz.", "Duana ortak olalım.", "comment", "🤲 Yorumlara “Âmin” yaz."),
       "share": ("İhtiyacı olan birine\ngönder.", "Bir paylaşım, bir hatırlatma.", "share", "📩 İhtiyacı olan birine gönder."),
       "save": ("Kaydet,\ntekrar oku.", "Gün içinde dönüp bakmak için.", "save", "🔖 Kaydet, gün içinde tekrar oku."),
       "salavat": ("Yorumlara bir\nsalavat bırak.", "Allâhümme salli alâ Muhammed.", "comment", "🤍 Yorumlara bir salavat bırak."),
       "hamd": ("Yorumlara bir\n“Elhamdülillah” bırak.", "Bugün neye şükrettin?", "comment", "🤲 Yorumlara bir “Elhamdülillah” bırak.")}
BISMILLAH = "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ "


def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def ref_name(ref):
    s, a = ref.split(":")
    return SURAHS[int(s) - 1], a


def quran_text(ref):
    """Diyanet Vakfı translation + simple Arabic; the cached copy is only a fallback when the API is down."""
    try:
        tr = get(f"https://api.alquran.cloud/v1/ayah/{ref}/tr.vakfi")["data"]["text"]
        ar = get(f"https://api.alquran.cloud/v1/ayah/{ref}/quran-simple")["data"]["text"]
        return tr.strip(), ar.strip()
    except Exception as e:
        print(f"quran api: {e} – using cache for {ref}")
        return tuple(json.loads((HERE / "quran_cache.json").read_text())[ref])


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def ayet_entry(day, which):
    """which: 0 = morning, 1 = evening (odd days only). Fridays' morning reel comes from the Cuma set."""
    n = (day - REEL_EPOCH).days
    if which == 0 and day.weekday() == 4:
        pool, start = RC.CUMA, (n // 7) % len(RC.CUMA)
    else:
        pool, start = RC.AYET, (n + n // 2 + which) % len(RC.AYET)
    for k in range(len(pool)):                          # an entry whose excerpt no longer matches is skipped
        e = pool[(start + k) % len(pool)]
        tr, ar = quran_text(e["ref"])
        if norm(e["ex"]) in norm(tr) and e["hl"] in e["ex"]:
            return e, tr, ar
        print(f"reel: excerpt mismatch for {e['ref']}, skipped")
    raise SystemExit("no valid verse entry")


def shoot_reel(data, frames, fps=30, page="reel.html"):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.add_init_script(f"window.__DATA__ = {json.dumps(data, ensure_ascii=False)};")
        pg.goto((HERE / page).as_uri())
        dur = float(pg.evaluate("window.READY"))
        starts = pg.evaluate("window.VO_AT || {}")
        pg.wait_for_timeout(500)
        for i in range(int(dur * fps)):
            pg.evaluate(f"render({i / fps})")
            pg.screenshot(path=str(frames / f"{i:05d}.jpg"), type="jpeg", quality=92)
        b.close()
    return dur, starts


def app_shot(day, which):
    name, line = APP_SHOTS[((day - REEL_EPOCH).days * 2 + which) % len(APP_SHOTS)]
    return {"img": f"app/{name}.jpg", "line": line}


def render_reel(day, data, stem):
    frames = frames_dir()
    say = data.pop("say", {})
    clips = vo_clips(say)
    data["vo"] = {k: v[1] for k, v in clips.items()}
    pre = data.pop("vo_prefix", "")
    data["vo_pre"] = round(clips["s2"][1] * len(pre) / len(say["s2"]), 3) if pre and "s2" in clips else 0
    dur, starts = shoot_reel(data, frames)
    vo = None
    if clips:
        vo = HERE / "vo_tmp" / "track.wav"
        ins, fl = [], []
        for i, (sc, (wav, _)) in enumerate(clips.items()):
            ins += ["-i", str(wav)]; ms = int(starts[sc] * 1000)
            fl.append(f"[{i}:a]adelay={ms}|{ms}[c{i}]")
        fc = ";".join(fl) + ";" + "".join(f"[c{i}]" for i in range(len(clips))) + \
            f"amix=inputs={len(clips)}:normalize=0,apad=whole_dur={dur},atrim=0:{dur},highpass=f=70," \
            "equalizer=f=3200:t=q:w=1.2:g=1.5,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120,loudnorm=I=-16:TP=-2:LRA=7[v]"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", fc, "-map", "[v]", "-ar", "48000", "-ac", "1", str(vo)], check=True)
    dst = SITE / "reels" / f"{stem}-{day.isoformat()}.mp4"
    encode_reel(frames, 30, int(dur + 0.999), dst, vo)
    return f"{BASE_URL}/reels/{stem}-{day.isoformat()}.mp4"


FOLLOW = ("Her gün bir ayet ve dua için @imsakiye.social'ı takip et.\n"
          "📲 İmsakiye uygulaması App Store'da ücretsiz: namaz vakitleri, Kur'an, kıble ve dualar. Profildeki bağlantıdan indir.")


# ---- narration (Azure, en-US-RyanMultilingualNeural speaking Turkish; best fluency in our tests).
# Clips are generated ahead of time and kept in vo/ (named by a hash of voice+rate+text), so the
# renderer needs no credentials. A clip that is missing simply leaves that scene without narration.
VO_VOICE, VO_RATE = "en-US-RyanMultilingualNeural", "-6%"
SPOKEN_CTA = {"amin": "Yorumlara âmin yaz.", "share": "İhtiyacı olan birine gönder.", "save": "Kaydet, tekrar oku.",
              "salavat": "Yorumlara bir salavat bırak.", "hamd": "Yorumlara bir elhamdülillah bırak."}


# The voice mispronounces circumflex vowels (âmin -> "emin") and some loanwords, so the spoken text is
# normalised; on-screen text and captions keep the proper spelling. Checked with Azure pronunciation assessment.
SAY_FIX = {r"\bwidget": "vicit", r"\bWidget": "Vicit", r"\bmeal\b": "meali", r"\bMeal\b": "Meali"}


SAY_ABBR = {"(s.a.v.)": "sallallahu aleyhi ve sellem", "Hz.": "Hazreti", "Âl-i": "Ali", "Al-i": "Ali"}
_ONES = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
_TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
_ORD = {"bir": "birinci", "iki": "ikinci", "üç": "üçüncü", "dört": "dördüncü", "beş": "beşinci", "altı": "altıncı",
        "yedi": "yedinci", "sekiz": "sekizinci", "dokuz": "dokuzuncu", "on": "onuncu", "yirmi": "yirminci",
        "otuz": "otuzuncu", "kırk": "kırkıncı", "elli": "ellinci", "altmış": "altmışıncı", "yetmiş": "yetmişinci",
        "seksen": "sekseninci", "doksan": "doksanıncı", "yüz": "yüzüncü"}


def tr_number(n, ordinal=False):
    """Turkish words for 1–999 (ordinal with ordinal=True): 128 -> yüz yirmi sekiz(inci)."""
    h, r = divmod(n, 100)
    words = ([] if h == 0 else (["yüz"] if h == 1 else [_ONES[h], "yüz"])) + ([_TENS[r // 10]] if r >= 10 else []) + ([_ONES[r % 10]] if r % 10 else [])
    if ordinal:
        words[-1] = _ORD[words[-1]]
    return " ".join(words)


def speakable(t):
    t = t.replace("\n", " ").replace("…", "").replace("“", "").replace("”", "").replace('"', "")
    for k, v in SAY_ABBR.items():
        t = t.replace(k, v)
    t = t.translate(str.maketrans("âîûÂÎÛ", "aiuAIU"))
    for k, v in SAY_FIX.items():
        t = re.sub(k, v, t)
    t = re.sub(r"(\d+)-(\d+)\. ", lambda m: f"{tr_number(int(m[1]))} ve {tr_number(int(m[2]), True)} ", t)
    t = re.sub(r"(\d+)\. ", lambda m: f"{tr_number(int(m[1]), True)} ", t)
    t = re.sub(r"\d+", lambda m: tr_number(int(m[0])), t)
    return re.sub(r"\s+", " ", t).strip()


def vo_name(text):
    import hashlib
    return hashlib.sha1(f"{VO_VOICE}|{VO_RATE}|{text}".encode()).hexdigest()[:16]


# ElevenLabs narration (Seyfullah Kartal, eleven_v3 with delivery cues) replaces the Azure clips wherever a clip exists.
EL_VOICE, EL_MODEL = "mF7tIc9VLrznhGooGjaT", "eleven_v3"
EL_TAGS = {"s1": "[softly] [curious] ", "s2": "[reverent] [slowly] ", "s3": "[warmly] [thoughtful] ", "s4": "[gently] ", "s5": "[warmly] "}


def el_text(scene, text):
    return EL_TAGS.get(scene, "") + text


def el_name(tagged):
    import hashlib
    return "el_" + hashlib.sha1(f"{EL_VOICE}|{EL_MODEL}|{tagged}".encode()).hexdigest()[:16]


def say_ayet(e, sura, a, line):
    return {"s1": speakable(e["hook"]), "s2": speakable(f"{sura} Sûresi, {a}. ayet. {e['ex']}"), "s3": speakable(e["note"]),
            "s4": SPOKEN_CTA.get(e["cta"]) or speakable(e["cta"]), "s5": speakable(f"İmsakiye. {line}. App Store'da ücretsiz.")}


def say_dua(e, d, line):
    return {"s1": speakable(e["hook"]), "s2": speakable(d["tr"]), "s3": speakable(e["note"]),
            "s4": SPOKEN_CTA["amin"], "s5": speakable(f"İmsakiye. {line}. App Store'da ücretsiz.")}


def vo_clips(say):
    """{scene: (wav path, seconds)} for the clips we have; silence is trimmed at both ends."""
    out = {}
    tmp = HERE / "vo_tmp"; tmp.mkdir(exist_ok=True)
    for sc, text in say.items():
        src = HERE / "vo" / f"{el_name(el_text(sc, text))}.mp3"
        if not src.exists():
            src = HERE / "vo" / f"{vo_name(text)}.mp3"
        if not src.exists():
            print(f"narration missing for {sc}: {text[:40]}"); continue
        wav = tmp / f"{sc}.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                        "-ar", "48000", "-ac", "1", str(wav)], check=True)
        d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)]))
        out[sc] = (wav, round(d, 3))
    return out


def ayet_reel(day, which=0):
    e, tr, ar = ayet_entry(day, which)
    sura, a = ref_name(e["ref"])
    ex = e["ex"]
    shown = ("…" if ex[0].islower() else "") + ex + ("" if ex[-1] in ".!?”\"" else "…")
    full = norm(ex) == norm(tr)
    if ar.startswith(BISMILLAH) and not e["ref"].startswith("1:"):
        ar = ar[len(BISMILLAH):]
    ar = ar.replace("۞", "").strip()
    big, small, icon, cap = CTA.get(e["cta"], (e["cta"], "", "comment", "💬 " + e["cta"].replace("\n", " ")))
    data = {"kind": "ayet", "seed": day.toordinal() * 2 + which,
            "kicker1": "BİR SORU" if e["hook"].rstrip().endswith("?") else "BİR HATIRLATMA",
            "hook": e["hook"], "kicker2": f"{tr_upper(sura)} SÛRESİ · {a}. AYET",
            "ar": ar if full and len(ar) <= 110 else "", "text": shown, "hl": e["hl"], "src": "Meal: Diyanet Vakfı",
            "note": e["note"], "ctaBig": big, "ctaSmall": small, "ctaIcon": icon, "app": app_shot(day, which)}
    data["say"] = say_ayet(e, sura, a, data["app"]["line"])
    data["vo_prefix"] = f"{sura} Sûresi, {a}. ayet. "
    url = render_reel(day, data, "ayet" if which == 0 else "ayet2")
    extra = [l for k, l in (("share", CTA["share"][3]), ("save", CTA["save"][3])) if e["cta"] != k]
    caption = (f"{e['hook'].replace(chr(10), ' ')}\n\n“{shown}”\n({sura} Sûresi, {a}. ayet · Meal: Diyanet Vakfı)\n\n"
               f"{e['note'].replace(chr(10), ' ')}\n\n{cap}\n" + "\n".join(extra) + f"\n\n{FOLLOW}\n\n"
               "#ayet #kuranıkerim #huzur #namazvakitleri #imsakiye")
    return url, caption


def dua_reel(day):
    n = (day - REEL_EPOCH).days
    e = RC.DUA[(n // 2) % len(RC.DUA)]
    d = next(x for x in json.loads((HERE / "dua.json").read_text()) if x["id"] == e["id"])
    s, a = re.search(r"\b(\d+):([\d-]+)", d["source"]).groups()
    sura = SURAHS[int(s) - 1]
    unit = "ayetler" if "-" in a else "ayet"
    big, small, icon, cap = CTA["amin"]
    data = {"kind": "dua", "seed": day.toordinal() * 2 + 1, "kicker1": e["who"], "hook": e["hook"],
            "kicker2": f"{tr_upper(sura)} SÛRESİ · {a}. {tr_upper(unit)}", "ar": d["ar"].strip(), "text": d["tr"].strip(),
            "hl": "", "src": "", "note": e["note"], "ctaBig": big, "ctaSmall": small, "ctaIcon": icon,
            "app": app_shot(day, 1)}
    data["say"] = say_dua(e, d, data["app"]["line"])
    url = render_reel(day, data, "dua")
    caption = (f"{e['hook'].replace(chr(10), ' ')}\n\n{d['ar'].strip()}\n\n“{d['tr'].strip()}”\n({sura} Sûresi, {a}. {unit})\n\n"
               f"{e['note'].replace(chr(10), ' ')}\n\n{cap}\n📩 Bu duayı sevdiklerine gönder.\n🔖 Kaydet, tekrar oku.\n\n{FOLLOW}\n\n"
               "#dua #kurandakidualar #amin #imsakiye #namazvakitleri")
    return url, caption


def evening_reel(day):
    return dua_reel(day) if (day - REEL_EPOCH).days % 2 == 0 else ayet_reel(day, 1)


def esma_story(day):
    """Esmâ-ül Hüsnâ series continues as the evening story (one name per day)."""
    from PIL import Image
    from playwright.sync_api import sync_playwright
    names = json.loads((HERE / "esma.json").read_text())
    item = names[(day - ESMA_START).days % 99]
    png = HERE / "story.png"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.add_init_script(f"window.__DATA__ = {json.dumps(item, ensure_ascii=False)};")
        pg.goto((HERE / "esma.html").as_uri()); pg.wait_for_timeout(800)
        pg.evaluate("render(9)"); pg.screenshot(path=str(png)); b.close()
    dst = SITE / "story" / f"esma-{day.isoformat()}.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.open(png).convert("RGB").save(dst, "JPEG", quality=92)
    return f"{BASE_URL}/story/esma-{day.isoformat()}.jpg"


def esma_post(day):
    """Same Esmâ card as the evening story, cropped to the 4:5 feed format."""
    from PIL import Image
    src = SITE / "story" / f"esma-{day.isoformat()}.jpg"
    if not src.exists():
        esma_story(day)
    item = json.loads((HERE / "esma.json").read_text())[(day - ESMA_START).days % 99]
    dst = SITE / "post" / f"esma-{day.isoformat()}.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.open(src).convert("RGB").crop((0, 215, 1080, 1565)).save(dst, "JPEG", quality=92)
    caption = (f"Esmâ-ül Hüsnâ · {item['number']}/99\n{item['transliteration']} ✨\n\n"
               "Her gün Allah'ın güzel isimlerinden birini paylaşıyoruz. Kaydet, serinin tamamını kaçırma.\n\n"
               "🤲 Yorumlara “Âmin” yaz.\n📩 Sevdiklerinle paylaş.\n\n" + FOLLOW + "\n\n"
               "#esmaülhüsna #allahın99ismi #esma #dua #imsakiye")
    return f"{BASE_URL}/post/esma-{day.isoformat()}.jpg", caption


# ---------------------------------------------------------------- Kur'an kıssaları (one narrated story a day)
import kissa_content as KC

KISSA_EPOCH = dt.date(2026, 10, 15)
KISSA_STYLE = ("Narrate the following Turkish text as a deep, warm male storyteller telling a moving story from the Quran "
               "in a short film. Native Turkish pronunciation. Speak slowly and with feeling: build tension, emphasise key words, "
               "make a clear pause between paragraphs, and read the quoted verses softly and reverently.")


def kissa_segments(k):
    """[(type, on-screen text, ref, spoken text)] – hook, beats, lesson, call to action."""
    segs = [("hook", k["hook"], "", k["hook"])]
    for b in k["beats"]:
        if isinstance(b, tuple):
            s, a = b[1].split(":")
            segs.append(("quote", b[2].strip('"'), f"{tr_upper(SURAHS[int(s) - 1])} · {a}", b[2]))
        else:
            segs.append(("line", b, "", b))
    segs.append(("lesson", k["lesson"], "", k["lesson"]))
    big, small, icon, _ = CTA[k["cta"]]
    segs.append(("cta", big.replace("\n", " "), icon + "|" + small, SPOKEN_CTA[k["cta"]]))
    return segs


KISSA_TAGS = {"hook": "[softly] [mysterious] ", "line": "", "quote": "[reverent] [slowly] ",
              "lesson": "[warmly] [heartfelt] ", "cta": "[gently] "}       # eleven_v3 delivery cues


def kissa_say(segs, tagged=False):
    paras = [re.sub(r"[()\"“”]", "", sp).replace("…", "...") for *_, sp in segs]
    return "\n\n".join((KISSA_TAGS.get(t, "") if tagged else "") + speakable(p) for (t, *_), p in zip(segs, paras))


KISSA_VOICE, KISSA_MODEL = "mF7tIc9VLrznhGooGjaT", "eleven_v3"   # ElevenLabs "Seyfullah Kartal - Deep and Muffled"


def kissa_vo_text(k):
    return kissa_say(kissa_segments(k), tagged=KISSA_MODEL == "eleven_v3")


def kissa_vo_name(k):
    import hashlib
    return "kissa-" + k["id"] + "-" + hashlib.sha1((KISSA_VOICE + KISSA_MODEL + kissa_vo_text(k)).encode()).hexdigest()[:10]


def times_from_alignment(path, text):
    """Paragraph start/end times from ElevenLabs character timings (text must be what was synthesised)."""
    al = json.loads(Path(path).read_text())
    chars, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    spoken = "".join(chars)
    out, pos = [], 0
    for para in text.split("\n\n"):
        i = spoken.find(para, pos)
        if i < 0:
            return None
        j = i + len(para) - 1; pos = j + 1
        out.append((st[i], en[j]))
    return out


def split_by_pauses(wav, texts):
    """Start/end of each paragraph in the narration: the N-1 longest pauses separate N paragraphs."""
    import wave, numpy as np
    w = wave.open(str(wav)); sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
    hop = int(sr * 0.02); n = len(x) // hop
    db = np.array([20 * np.log10(np.sqrt((x[i*hop:(i+1)*hop] ** 2).mean()) + 1e-9) for i in range(n)])
    quiet = db < max(-45, db.max() - 38)
    runs, i = [], 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]: j += 1
            if i > 0 and j < n: runs.append((j - i, i, j))
            i = j
        else: i += 1
    speech = np.where(~quiet)[0]
    t0, t1 = speech[0] * 0.02, (speech[-1] + 1) * 0.02
    k = len(texts) - 1
    gaps = sorted(sorted(runs, reverse=True)[:k], key=lambda r: r[1])
    if len(gaps) == k:
        bounds = [(g[1] * 0.02, g[2] * 0.02) for g in gaps]
        segs = [(t0 if i == 0 else bounds[i-1][1], t1 if i == k else bounds[i][0]) for i in range(k + 1)]
        ratios = [(e - s) / max(1, len(t)) for (s, e), t in zip(segs, texts)]
        med = sorted(ratios)[len(ratios) // 2]
        if all(0.35 < r / med < 2.8 for r in ratios):
            return segs
    print("kissa: pause split failed, using text lengths")
    tot = sum(map(len, texts)); acc, out = t0, []
    for t in texts:
        d = (t1 - t0) * len(t) / tot; out.append((acc, acc + d)); acc += d
    return out


def kissa_reel(day):
    n = (day - KISSA_EPOCH).days
    k = KC.KISSA[n % len(KC.KISSA)]
    segs = kissa_segments(k)
    for b in k["beats"]:                           # every quote must match the translation exactly
        if isinstance(b, tuple):
            tr, _ = quran_text(b[1])
            if norm(b[2]) not in norm(tr):
                raise SystemExit(f"kissa {k['id']}: quote mismatch {b[1]}")
    src = HERE / "vo" / f"{kissa_vo_name(k)}.mp3"
    if not src.exists():
        raise SystemExit(f"kissa {k['id']}: narration missing ({src.name})")
    tmp = HERE / "vo_tmp"; tmp.mkdir(exist_ok=True)
    wav = tmp / "kissa.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ar", "48000", "-ac", "1", str(wav)], check=True)
    js = src.with_suffix(".json")
    times = times_from_alignment(js, kissa_say(segs)) if js.exists() else None
    if times:                      # breathe: longer pauses between paragraphs than the voice leaves on its own
        import wave, numpy as np
        w = wave.open(str(wav)); sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        parts, new, t = [], [], 0.0
        for i, (a, b) in enumerate(times):
            cut0 = 0 if i == 0 else int((times[i-1][1] + a) / 2 * sr)
            cut1 = len(x) if i == len(times) - 1 else int((b + times[i+1][0]) / 2 * sr)
            chunk = x[cut0:cut1]
            new.append((t + (a - cut0 / sr), t + (b - cut0 / sr)))
            parts.append(chunk); t += len(chunk) / sr
            if i < len(times) - 1:
                nxt = segs[i + 1][0]
                gap = 0.75 if i == 0 else 0.7 if nxt in ("lesson", "cta") else 0.45 if nxt == "quote" else 0.3
                parts.append(np.zeros(int(gap * sr), np.int16)); t += gap
        ww = wave.open(str(wav), "wb"); ww.setnchannels(1); ww.setsampwidth(2); ww.setframerate(sr)
        ww.writeframes(np.concatenate(parts).tobytes()); ww.close()
        times = new
    times = times or split_by_pauses(wav, [sp for *_, sp in segs])
    lead = 0.6
    beats = []
    for (typ, text, ref, _), (a, b) in zip(segs, times):
        d = {"type": typ, "text": text, "start": round(a + lead, 3), "end": round(b + lead, 3)}
        if typ == "quote": d["ref"] = ref
        if typ == "cta": d["icon"], d["small"] = ref.split("|")
        beats.append(d)
    end_start = beats[-1]["end"] + 0.9
    data = {"title": k["title"], "seed": n, "beats": beats, "endStart": round(end_start, 2),
            "duration": round(end_start + 3.8, 2), "app": app_shot(day, 0)}
    frames = frames_dir()
    dur, _ = shoot_reel(data, frames, page="kissa.html")
    vo = tmp / "kissa_track.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af",
                    f"adelay={int(lead*1000)}|{int(lead*1000)},apad=whole_dur={dur},atrim=0:{dur},highpass=f=60,"
                    "acompressor=threshold=-20dB:ratio=2:attack=10:release=150,loudnorm=I=-16:TP=-2:LRA=9",
                    "-ar", "48000", "-ac", "1", str(vo)], check=True)
    dst = SITE / "reels" / f"kissa-{day.isoformat()}.mp4"
    encode_reel(frames, 30, int(dur + 0.999), dst, vo)
    refs = sorted({f"{SURAHS[int(b[1].split(':')[0]) - 1]} {b[1].split(':')[1]}" for b in k["beats"] if isinstance(b, tuple)},
                  key=lambda r: r)
    story = "\n".join(("“" + b[2].strip('"') + "”") if isinstance(b, tuple) else b for b in k["beats"])
    caption = (f"{k['hook']}\n\n{story}\n\n{k['lesson']}\n\n(Kaynak: {', '.join(refs)} · Meal: Diyanet Vakfı)\n\n"
               f"{CTA[k['cta']][3]}\n📩 Bu kıssayı bilmeyen birine gönder.\n\n"
               "Her gün bir Kur'an kıssası için @imsakiye.social'ı takip et.\n📲 İmsakiye uygulaması App Store'da ücretsiz.\n\n"
               "#kurankıssaları #kuran #peygamberler #ibret #imsakiye")
    return f"{BASE_URL}/reels/kissa-{day.isoformat()}.mp4", caption


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
TAGS = "#imsakiye #kandil #bayram #ramazan #dua"


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
            out["evening_post"] = (special_card(day, "sayac", card, "post"),
                                   f"{card['title']} 🌙\n{card['sub']}\n\n“{card['dua']['tr']}”\n({card['dua']['source']})\n\n"
                                   "🤲 Yorumlara “Âmin” yaz.\n📩 Sevdiklerine hatırlat.\n\n" + FOLLOW + "\n\n" + TAGS)
    return out


def main():
    day = dt.datetime.now(TZ).date() if len(sys.argv) < 2 else dt.date.fromisoformat(sys.argv[1])
    manifest = {"date": day.isoformat(), "items": []}

    def add(slot, kind, fn):
        try:
            r = fn(day)
            url, caption = (r, None) if isinstance(r, str) else r
            if day.weekday() != 4 and re.search(r"cuma", f"{url} {caption or ''}", re.I):
                raise SystemExit("Friday content on a non-Friday")        # Cuma content only ever goes out on Fridays
            manifest["items"].append({"slot": slot, "kind": kind, "url": url, "caption": caption})
        except BaseException as e:      # one failed piece must not stop the others
            print(f"{slot}: skipped ({e})")

    special = {}
    try:
        special = overrides(day)
    except BaseException as e:
        print(f"special: skipped ({e})")
    add("morning_story", "story_image", story)
    add("morning_reel", "reel", ayet_reel)
    add("noon_post", "image", (lambda d: special["noon_post"]) if "noon_post" in special else hadis_post)
    add("evening_story", "story_image", (lambda d: special["evening_story"]) if "evening_story" in special else esma_story)
    if "evening_post" in special:
        add("evening_post", "image", lambda d: special["evening_post"])
    elif "evening_story" not in special:                        # occasion days already have the noon card
        add("evening_post", "image", esma_post)
    add("evening_reel", "reel", evening_reel)
    add("kissa_reel", "reel", kissa_reel)
    out = SITE / "daily" / f"{day.isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
