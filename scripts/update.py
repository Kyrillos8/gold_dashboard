"""Append today's 18K gold price (EGP per gram) to data/prices.csv.

18K price = global gold price (USD/oz) / 31.1035 g * 0.75 purity * USD->EGP rate.
"""
import csv, json, sys, urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CSV = Path(__file__).resolve().parent.parent / "data" / "prices.csv"
HEADERS = {"User-Agent": "gold-dashboard/1.0"}


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    today = datetime.now(ZoneInfo("Africa/Cairo")).date().isoformat()
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    if any(r["date"] == today for r in rows):
        print(f"{today} already recorded")
        return

    usd_oz = float(get_json("https://api.gold-api.com/price/XAU")["price"])
    usd_egp = float(get_json("https://open.er-api.com/v6/latest/USD")["rates"]["EGP"])
    price = round(usd_oz / 31.1035 * 0.75 * usd_egp)
    if not 1000 < price < 50000:
        sys.exit(f"Suspicious price {price}, not saving")

    rows.append({
        "date": today,
        "price_egp": price,
        "note": f"Market rate (gold ${usd_oz:,.0f}/oz x {usd_egp:.2f} EGP/USD)",
        "source": "gold-api.com + open.er-api.com",
    })
    rows.sort(key=lambda r: r["date"])
    with CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "price_egp", "note", "source"])
        w.writeheader()
        w.writerows(rows)
    print(f"Added {today}: {price} EGP/gram")


if __name__ == "__main__":
    main()
