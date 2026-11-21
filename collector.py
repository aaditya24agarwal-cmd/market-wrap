"""
WORKER 1: THE COLLECTOR
Gets the last trading day's market numbers + a few news headlines,
prints them as a readable table, and saves everything in data.json.

Setup (once):   pip install yfinance feedparser
Run:            python collector.py
"""

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import feedparser
import yfinance as yf

# (group, display name, Yahoo Finance ticker, kind)
# kind "price" -> show % change.  kind "yield" -> show change in basis points.
MARKETS = [
    ("India", "Nifty 50", "^NSEI", "price"),
    ("India", "Sensex", "^BSESN", "price"),
    ("India", "USD/INR", "USDINR=X", "price"),
    ("US", "S&P 500", "^GSPC", "price"),
    ("US", "Dow Jones", "^DJI", "price"),
    ("US", "Nasdaq", "^IXIC", "price"),
    ("Europe", "FTSE 100", "^FTSE", "price"),
    ("Europe", "DAX", "^GDAXI", "price"),
    ("Asia", "Nikkei 225", "^N225", "price"),
    ("Asia", "Hang Seng", "^HSI", "price"),
    ("Money & Rates", "US 10Y yield (%)", "^TNX", "yield"),
    ("Money & Rates", "Dollar Index", "DX-Y.NYB", "price"),
    ("Commodities", "Gold", "GC=F", "price"),
    ("Commodities", "Brent crude", "BZ=F", "price"),
]

# Free news feeds. If one stops working, the script just skips it.
FEEDS = {
    "ET Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "CNBC": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "BBC Business": "http://feeds.bbci.co.uk/news/business/rss.xml",
}
HEADLINES_PER_FEED = 5


# When each stock market's session is finished (local time zone, hour, minute),
# including a small buffer for data delays. A price bar dated TODAY before this time is
# a live, half-finished session, not a close, so we skip it and use the last real close.
# Currencies, gold and oil trade almost around the clock, so they are not listed.
CLOSING_TIMES = {
    "^NSEI": ("Asia/Kolkata", 15, 45),
    "^BSESN": ("Asia/Kolkata", 15, 45),
    "^GSPC": ("America/New_York", 16, 15),
    "^DJI": ("America/New_York", 16, 15),
    "^IXIC": ("America/New_York", 16, 15),
    "^FTSE": ("Europe/London", 16, 45),
    "^GDAXI": ("Europe/Berlin", 17, 45),
    "^N225": ("Asia/Tokyo", 15, 45),
    "^HSI": ("Asia/Hong_Kong", 16, 25),
}


def session_in_progress(ticker, bar_date, now_utc):
    """True if this bar belongs to a session that has not finished yet."""
    rule = CLOSING_TIMES.get(ticker)
    if rule is None:
        return False
    zone, hour, minute = rule
    local_now = now_utc.astimezone(ZoneInfo(zone))
    if bar_date != local_now.date():
        return False
    return (local_now.hour, local_now.minute) < (hour, minute)


def get_market_row(group, name, ticker, kind):
    """Download recent prices and compare the latest close with the one before it."""
    try:
        closes = yf.Ticker(ticker).history(period="10d")["Close"].dropna()
        if len(closes) >= 2 and session_in_progress(
                ticker, closes.index[-1].date(), datetime.now(timezone.utc)):
            closes = closes.iloc[:-1]  # drop the live, unfinished session
        if len(closes) < 2:
            return None
        last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
        row = {
            "group": group,
            "name": name,
            "ticker": ticker,
            "kind": kind,
            "last": round(last, 2),
            "prev": round(prev, 2),
            "as_of": str(closes.index[-1].date()),
        }
        if kind == "yield":
            row["change"] = round((last - prev) * 100, 1)  # basis points
        else:
            row["change"] = round((last - prev) / prev * 100, 2)  # percent
        return row
    except Exception as err:
        print(f"  [skipped {name}: {err}]")
        return None


def get_headlines():
    """Fetch the top few headlines from each news feed."""
    items = []
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:HEADLINES_PER_FEED]:
                items.append({"source": source, "title": entry.get("title", "").strip()})
        except Exception as err:
            print(f"  [skipped feed {source}: {err}]")
    return items


def main():
    print("Collecting market numbers...")
    markets = []
    for group, name, ticker, kind in MARKETS:
        row = get_market_row(group, name, ticker, kind)
        if row:
            markets.append(row)

    print("Collecting headlines...")
    headlines = get_headlines()

    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "markets": markets,
        "headlines": headlines,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Readable printout
    print("\n=== MARKETS (latest close vs previous close) ===")
    for r in markets:
        unit = "bps" if r["kind"] == "yield" else "%"
        sign = "+" if r["change"] > 0 else ""
        print(f"{r['group']:<14}{r['name']:<20}{r['last']:>12,.2f}  {sign}{r['change']}{unit}   ({r['as_of']})")

    print("\n=== HEADLINES ===")
    for h in headlines:
        print(f"[{h['source']}] {h['title']}")

    print(f"\nSaved {len(markets)} markets and {len(headlines)} headlines to data.json")


if __name__ == "__main__":
    main()
