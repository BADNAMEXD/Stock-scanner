"""Scanner B: 'Trend-join Long' check on the tickers Scanner A found today. Sends result to Telegram."""
import json
import os
from datetime import datetime, time

from scanner import NY, OUT_DIR, send_telegram


def in_window_b(now):
    """Mon-Fri, 8:35 AM to 3:00 PM New York time."""
    return now.weekday() < 5 and time(8, 35) <= now.time() <= time(15, 0)


def tickers_from(data):
    """Union of all tickers Scanner A found today, across all its runs."""
    return sorted({r["ticker"] for run in data["runs"] for r in run["results"]})


def is_hit(price, y_high, y_close, sma200, pm_high, hod_before):
    """All 4 rules: above yesterday's high, yesterday's close above 200 SMA, above pre-market high, above high of day before this candle."""
    vals = (price, y_high, y_close, sma200, pm_high, hod_before)
    if any(v is None or v != v for v in vals):  # missing or NaN
        return False
    return price > y_high and y_close > sma200 and price > pm_high and price > hod_before


def format_report_b(hits, empty="No stock match."):
    lines = [f"{sym} | Entry ${price:.2f}" for sym, price in hits]
    return "[Scanner B: Trend-join Long Hits]\n" + ("\n".join(lines) or empty)


def check(yf, sym, today):
    """Return current price if sym is a hit, else None."""
    t = yf.Ticker(sym)
    d = t.history(period="1y", interval="1d")
    d = d[d.index.date < today]  # completed days only
    m = t.history(period="2d", interval="1m", prepost=True)
    m = m[m.index.date == today]  # today's bars only, pre-market included
    if len(d) < 200 or len(m) < 2:
        return None
    pm = m.between_time("00:00", "09:29")["High"]
    price = float(m["Close"].iloc[-1])
    # shortcut: high of day = day high before the latest candle with pre-market included, upgrade if only regular hours should count
    ok = is_hit(
        price,
        float(d["High"].iloc[-1]),
        float(d["Close"].iloc[-1]),
        float(d["Close"].rolling(200).mean().iloc[-1]),
        float(pm.max()) if len(pm) else None,
        float(m["High"].iloc[:-1].max()),
    )
    return price if ok else None


def main():
    now = datetime.now(NY)
    if not in_window_b(now):
        print("Outside scan window, stop.")
        return
    import yfinance as yf

    today = now.date()
    path = os.path.join(OUT_DIR, f"{today.isoformat()}.json")
    if not os.path.exists(path):
        report = format_report_b([], "No tickers from Scanner A yet.")
    else:
        with open(path) as f:
            symbols = tickers_from(json.load(f))
        hits = []
        for sym in symbols:
            try:
                price = check(yf, sym, today)
                if price is not None:
                    hits.append((sym, price))
            except Exception as e:
                print(f"skip {sym}: {e}")
        report = format_report_b(hits)
    print(report)
    send_telegram(report)


if __name__ == "__main__":
    main()
