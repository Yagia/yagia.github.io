"""Lists every narration line the reels can need and which ElevenLabs clips are not in vo/ yet
(run after editing reels_content.py). Output feeds the el_queue table in Supabase."""
import json, sys
import daily, reels_content as RC
lines = set()
for e in RC.AYET + RC.CUMA:
    sura, a = daily.ref_name(e["ref"])
    lines.update((k, v) for k, v in daily.say_ayet(e, sura, a, "x").items() if k != "s5")
duas = json.loads((daily.HERE / "dua.json").read_text())
for e in RC.DUA:
    d = next(x for x in duas if x["id"] == e["id"])
    lines.update((k, v) for k, v in daily.say_dua(e, d, "x").items() if k != "s5")
for _, line in daily.APP_SHOTS:
    lines.add(("s5", daily.speakable(f"İmsakiye. {line}. App Store'da ücretsiz.")))
tagged = sorted({daily.el_text(k, v) for k, v in lines})
missing = [t for t in tagged if not (daily.HERE / "vo" / f"{daily.el_name(t)}.mp3").exists()]
print(len(tagged), "lines,", len(missing), "missing,", sum(map(len, missing)), "chars", file=sys.stderr)
json.dump([{"name": daily.el_name(t), "text": t} for t in missing], sys.stdout, ensure_ascii=False)
