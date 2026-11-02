"""Estimate tomorrow's 18K price from the recent trend plus the tone of today's gold news.

Writes data/forecast.json (shown on the dashboard) and appends to data/forecasts.csv
so the dashboard can show how accurate past estimates were.
This is a rough indicator, not financial advice.
"""
import csv, json, statistics, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DATA = Path(__file__).resolve().parent.parent / "data"
HEADERS = {"User-Agent": "Mozilla/5.0 gold-dashboard/1.0"}

FEEDS = [
    ("en", "gold price outlook"),
    ("en", "gold prices Fed dollar"),
    ("ar", "توقعات سعر الذهب مصر"),
]
UP = ["rise", "rises", "rising", "gain", "gains", "jump", "surge", "rally", "record high", "climb",
      "bullish", "rate cut", "safe haven", "weaker dollar", "tension", "higher",
      "ارتفاع", "يرتفع", "صعود", "قفزة", "زيادة", "مكاسب", "يقفز", "أعلى"]
DOWN = ["fall", "falls", "falling", "drop", "drops", "slip", "slide", "decline", "plunge", "tumble",
        "bearish", "rate hike", "stronger dollar", "profit-taking", "lower", "selloff",
        "انخفاض", "تراجع", "يتراجع", "هبوط", "ينخفض", "خسائر", "أدنى"]


def fetch_news():
    items = []
    for lang, q in FEEDS:
        params = {"q": q + " when:2d", "hl": "ar-EG" if lang == "ar" else "en-US",
                  "gl": "EG" if lang == "ar" else "US", "ceid": "EG:ar" if lang == "ar" else "US:en"}
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=20) as r:
                root = ET.fromstring(r.read())
        except Exception as e:  # news is optional; trend still works
            print(f"news feed failed ({q}): {e}")
            continue
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            if title and all(title != x["title"] for x in items):
                items.append({"title": title, "link": link})
    return items[:40]


def score(title):
    t = title.lower()
    return sum(w in t for w in UP) - sum(w in t for w in DOWN)


def main():
    rows = list(csv.DictReader((DATA / "prices.csv").open(encoding="utf-8")))
    pts = [(date.fromisoformat(r["date"]), float(r["price_egp"])) for r in rows]
    pts.sort()
    last_d, last_p = pts[-1]

    # Daily % changes, spread evenly over gaps between data points
    daily = []
    for (d0, p0), (d1, p1) in zip(pts, pts[1:]):
        days = max(1, (d1 - d0).days)
        daily.append(((p1 / p0) ** (1 / days) - 1) * 100)
    recent = daily[-7:] if daily else [0.0]
    trend = statistics.mean(recent)
    vol = statistics.pstdev(daily[-20:]) if len(daily) >= 5 else 1.0
    vol = min(max(vol, 0.5), 2.5)

    news = fetch_news()
    scored = [dict(n, s=score(n["title"])) for n in news]
    up = sum(1 for n in scored if n["s"] > 0)
    down = sum(1 for n in scored if n["s"] < 0)
    tone = (up - down) / max(1, up + down)  # -1 .. +1

    pct = 0.5 * trend + 0.6 * tone          # trend half-weighted, news adds up to ±0.6%
    pct = max(-2.0, min(2.0, pct))
    est = round(last_p * (1 + pct / 100))
    low = round(last_p * (1 + (pct - vol) / 100))
    high = round(last_p * (1 + (pct + vol) / 100))
    direction = "Up" if pct >= 0.25 else "Down" if pct <= -0.25 else "Flat"

    today = datetime.now(ZoneInfo("Africa/Cairo")).date()
    target = (today + timedelta(days=1)).isoformat()
    fc = {
        "generated": datetime.now(ZoneInfo("Africa/Cairo")).isoformat(timespec="minutes"),
        "base_date": last_d.isoformat(), "base_price": round(last_p),
        "target_date": target, "estimate": est, "low": low, "high": high,
        "change_pct": round(pct, 2), "direction": direction,
        "trend_pct_per_day": round(trend, 2), "news_tone": round(tone, 2),
        "news_up": up, "news_down": down, "news_total": len(scored),
        "headlines": [n for n in scored if n["s"] != 0][:8] or scored[:8],
    }
    (DATA / "forecast.json").write_text(json.dumps(fc, ensure_ascii=False, indent=1), encoding="utf-8")

    hist = DATA / "forecasts.csv"
    hrows = list(csv.DictReader(hist.open(encoding="utf-8"))) if hist.exists() else []
    hrows = [r for r in hrows if r["target_date"] != target]
    hrows.append({"target_date": target, "estimate": est, "low": low, "high": high})
    with hist.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["target_date", "estimate", "low", "high"])
        w.writeheader()
        w.writerows(sorted(hrows, key=lambda r: r["target_date"]))
    print(f"Estimate for {target}: {est} EGP ({pct:+.2f}%), range {low}-{high}, news {up} up / {down} down")


if __name__ == "__main__":
    main()
