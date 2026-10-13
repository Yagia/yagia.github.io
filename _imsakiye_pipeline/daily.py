"""Daily content for @imsakiye.social.

Renders into ../imsakiye/ (published by GitHub Pages):
  story/<YYYY-MM-DD>.jpg   today's prayer times for 8 cities (Diyanet, cross-checked)
  reels/esma-<YYYY-MM-DD>.mp4   Esmâ-ül Hüsnâ series, one name per day
  daily/<YYYY-MM-DD>.json  manifest the Supabase publisher reads (captions, urls)

Nothing is published here; Supabase posts the files at the scheduled times.
If the prayer-time sources disagree, no story is produced for that day.
"""
import datetime as dt, json, shutil, subprocess, sys, urllib.request
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
ESMA_START = dt.date(2026, 10, 15)       # day 1 of the series
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


def esma_reel(day):
    names = json.loads((HERE / "esma.json").read_text())
    n = ((day - ESMA_START).days % 99) + 1
    item = names[n - 1]
    frames = HERE / "frames"
    shutil.rmtree(frames, ignore_errors=True); frames.mkdir()
    fps, dur = 30, 12
    shoot("esma.html", item, frames, [i / fps for i in range(fps * dur)])
    subprocess.run([sys.executable, str(HERE / "music.py"), str(dur), str(HERE / "music.wav"), str(dur + 5), "calm"], check=True)
    dst = SITE / "reels" / f"esma-{day.isoformat()}.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames / "%05d.jpg"),
                    "-i", str(HERE / "music.wav"), "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
                    "-crf", "20", "-preset", "slow", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest",
                    "-movflags", "+faststart", str(dst)], check=True)
    caption = (f"Esmâ-ül Hüsnâ · {n}/99\n{item['transliteration']} ✨\n\n"
               "Her gün Allah'ın güzel isimlerinden birini paylaşıyoruz. Takipte kal, serinin tamamını kaçırma.\n\n"
               "📲 99 ismin tamamı İmsakiye uygulamasında, App Store'da ücretsiz.\n\n"
               "#esmaülhüsna #allahın99ismi #imsakiye #dua #zikir #islam")
    return f"{BASE_URL}/reels/esma-{day.isoformat()}.mp4", caption


def main():
    day = dt.datetime.now(TZ).date() if len(sys.argv) < 2 else dt.date.fromisoformat(sys.argv[1])
    manifest = {"date": day.isoformat(), "items": []}
    try:
        manifest["items"].append({"slot": "morning_story", "kind": "story_image", "url": story(day)})
    except SystemExit as e:
        print(e)
    url, caption = esma_reel(day)
    manifest["items"].append({"slot": "evening_reel", "kind": "reel", "url": url, "caption": caption})
    out = SITE / "daily" / f"{day.isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
