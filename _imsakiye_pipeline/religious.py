"""Port of the app's ReligiousDays (PrayerTimesCore): Diyanet's Hijri month starts 2022–2035."""
import datetime as dt, json
from pathlib import Path

TABLE = json.loads((Path(__file__).with_name("hijri_table.json")).read_text())
NAMES = {"threeMonthsBegin": "Üç Aylar", "regaib": "Regaib Kandili", "mirac": "Miraç Kandili", "berat": "Berat Kandili",
         "ramadanBegins": "Ramazan", "kadir": "Kadir Gecesi", "ramadanArefe": "Ramazan Bayramı Arifesi",
         "ramadanFeast": "Ramazan Bayramı", "kurbanArefe": "Kurban Bayramı Arifesi", "kurbanFeast": "Kurban Bayramı",
         "hijriNewYear": "Hicri Yılbaşı", "ashura": "Aşure Günü", "mevlid": "Mevlid Kandili"}
NIGHTS = {"regaib", "mirac", "berat", "kadir", "mevlid"}


def all_days():
    starts = [dt.date(gy, gm, gd) for (_, _, gy, gm, gd) in TABLE]
    out = []
    for i, (hy, hm, *_rest) in enumerate(TABLE):
        start = starts[i]
        day = lambda n: start + dt.timedelta(days=n - 1)
        if hm == 1:
            out += [("hijriNewYear", start, 1), ("ashura", day(10), 1)]
        elif hm == 3:
            out.append(("mevlid", day(11), 1))
        elif hm == 7:
            swift_wd = (start.weekday() + 1) % 7 + 1            # 1 = Sunday … 6 = Friday
            until_friday = (6 - swift_wd + 7) % 7
            out += [("threeMonthsBegin", start, 1), ("regaib", start + dt.timedelta(days=until_friday - 1), 1), ("mirac", day(26), 1)]
        elif hm == 8:
            out.append(("berat", day(14), 1))
        elif hm == 9:
            out += [("ramadanBegins", start, 1), ("kadir", day(26), 1)]
            if i + 1 < len(starts):
                out.append(("ramadanArefe", starts[i + 1] - dt.timedelta(days=1), 1))
        elif hm == 10:
            out.append(("ramadanFeast", start, 3))
        elif hm == 12:
            out += [("kurbanArefe", day(9), 1), ("kurbanFeast", day(10), 4)]
    return sorted(out, key=lambda x: x[1])


def on(day):
    """Occasions that fall on `day` (first day of a feast only)."""
    return [(k, d) for k, d, _ in all_days() if d == day]


def next_after(day, kinds=None):
    for k, d, _ in all_days():
        if d > day and (kinds is None or k in kinds):
            return k, d
    return None
