"""Lists every narration line the reels can need and which ones are not in vo/ yet (run after editing reels_content.py)."""
import json, sys
import daily, reels_content as RC
texts = set()
for e in RC.AYET + RC.CUMA:
    sura, a = daily.ref_name(e["ref"])
    texts.update(v for k, v in daily.say_ayet(e, sura, a, "x").items() if k != "s5")
duas = json.loads((daily.HERE / "dua.json").read_text())
for e in RC.DUA:
    d = next(x for x in duas if x["id"] == e["id"])
    texts.update(v for k, v in daily.say_dua(e, d, "x").items() if k != "s5")
for _, line in daily.APP_SHOTS:
    texts.add(f"İmsakiye. {line}. App Store'da ücretsiz.")
missing = sorted(t for t in texts if not (daily.HERE / "vo" / f"{daily.vo_name(t)}.mp3").exists())
print(len(texts), "lines,", len(missing), "missing,", sum(map(len, missing)), "chars", file=sys.stderr)
json.dump([{"name": "vo_" + daily.vo_name(t), "text": t} for t in missing], sys.stdout, ensure_ascii=False)
