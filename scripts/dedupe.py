"""Keep one row per date in data/prices.csv (the first one)."""
import csv
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "data" / "prices.csv"
rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
seen, out = set(), []
for r in rows:
    if r["date"] not in seen:
        seen.add(r["date"])
        out.append(r)
out.sort(key=lambda r: r["date"])
with CSV.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["date", "price_egp", "note", "source"])
    w.writeheader()
    w.writerows(out)
