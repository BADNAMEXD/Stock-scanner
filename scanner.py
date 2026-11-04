"""Scanner A: pre-market gappers. Gap up >5%, price >$3, pre-market volume >50,000. Sends result to Telegram."""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, time
from zoneinfo import ZoneInfo

MIN_GAP, MIN_PRICE, MIN_VOLUME = 5.0, 3.0, 50_000
OUT_DIR = os.environ.get("SCAN_OUTPUT_DIR", "output")
NY = ZoneInfo("America/New_York")


def in_window(now):
    """Mon-Fri, 8:30 AM to 2:15 PM New York time (15 min grace, GitHub often starts runs late)."""
    return now.weekday() < 5 and time(8, 30) <= now.time() <= time(14, 15)


def gap_if_match(info):
    """Return gap % if price and gap rules pass, else None. Volume is checked separately."""
    price, prev = info.get("preMarketPrice"), info.get("previousClose")
    if not (price and prev):
        return None
    gap = (price / prev - 1) * 100
    return round(gap, 2) if gap > MIN_GAP and price > MIN_PRICE else None


def premarket_volume(t, today):
    """Shares traded before 9:30 AM New York today, summed from 1-minute bars."""
    # shortcut: 1-minute bars instead of info["preMarketVolume"] (field name not verified), switch once the field is confirmed
    m = t.history(period="2d", interval="1m", prepost=True)
    m = m[m.index.date == today]
    return float(m.between_time("00:00", "09:29")["Volume"].sum())


def volume_ok(vol):
    return vol > MIN_VOLUME


def catalyst(ticker):
    """Newest Yahoo headline as the one-sentence catalyst."""
    news = ticker.news
    if not news:
        return "No news found"
    item = news[0]
    return (item.get("content") or item).get("title", "No news found")


def format_report(rows):
    lines = [f"{r['ticker']} | ${r['price']:.2f} | +{r['gap_percent']:.2f}% | {r['catalyst']}" for r in rows]
    return "[Scanner A: Pre-market Gappers]\n" + ("\n".join(lines) or "No stock match.")


def send_telegram(text):
    # shortcut: Telegram rejects messages over 4096 characters and long lists are not split, upgrade by sending in chunks
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text}).encode()
    urllib.request.urlopen(url, data, timeout=15)


def main():
    now = datetime.now(NY)
    if not in_window(now):
        print("Outside scan window, stop.")
        return
    import yfinance as yf

    today = now.date()
    # shortcut: candidates from Yahoo day_gainers + most_actives can miss pre-market movers, upgrade to a full pre-market list when one is available
    symbols = {q["symbol"] for name in ("day_gainers", "most_actives") for q in yf.screen(name, count=100)["quotes"]}
    rows = []
    for sym in sorted(symbols):
        try:
            t = yf.Ticker(sym)
            info = t.info
            gap = gap_if_match(info)
            if gap is None:
                continue  # skip the slower volume lookup for stocks that already fail
            if volume_ok(premarket_volume(t, today)):
                rows.append({"ticker": sym, "price": info["preMarketPrice"], "gap_percent": gap, "catalyst": catalyst(t)})
        except Exception as e:
            print(f"skip {sym}: {e}")
    rows.sort(key=lambda r: r["gap_percent"], reverse=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{today.isoformat()}.json")  # one file per day, each run adds an entry
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
    else:
        data = {"date": today.isoformat(), "runs": []}
    data["runs"].append({"time": now.strftime("%H:%M"), "results": rows})
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    report = format_report(rows)
    print(report)
    send_telegram(report)


if __name__ == "__main__":
    main()
