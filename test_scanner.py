from datetime import datetime
from zoneinfo import ZoneInfo

from scanner import format_report, gap_if_match, in_window, volume_ok
from scanner_b import format_report_b, in_window_b, is_hit, tickers_from

ny = ZoneInfo("America/New_York")

# Scanner A: gap and price rules
ok = {"preMarketPrice": 10.6, "previousClose": 10.0}
assert gap_if_match(ok) == 6.0
assert gap_if_match({**ok, "preMarketPrice": 10.4}) is None                  # gap 4%, not over 5%
assert gap_if_match({"preMarketPrice": 3.0, "previousClose": 2.0}) is None   # price 3.00, not over $3
assert gap_if_match({}) is None                                              # no pre-market data

# Scanner A: volume rule
assert volume_ok(50_001)
assert not volume_ok(50_000)                                                 # must be over 50,000

# Scanner A: time window (Mon-Fri, 8:30 AM to 2:15 PM New York)
assert in_window(datetime(2026, 11, 3, 8, 30, tzinfo=ny))
assert in_window(datetime(2026, 11, 3, 14, 0, tzinfo=ny))
assert not in_window(datetime(2026, 11, 3, 8, 0, tzinfo=ny))
assert not in_window(datetime(2026, 11, 3, 14, 30, tzinfo=ny))
assert not in_window(datetime(2026, 11, 7, 10, 0, tzinfo=ny))                # Saturday

row = {"ticker": "ABC", "price": 10.6, "gap_percent": 6.0, "catalyst": "ABC wins deal"}
assert format_report([row]) == "[Scanner A: Pre-market Gappers]\nABC | $10.60 | +6.00% | ABC wins deal"
assert format_report([]) == "[Scanner A: Pre-market Gappers]\nNo stock match."

# Scanner B: time window (Mon-Fri, 8:35 AM to 3:00 PM New York)
assert in_window_b(datetime(2026, 11, 3, 8, 35, tzinfo=ny))
assert in_window_b(datetime(2026, 11, 3, 14, 35, tzinfo=ny))
assert not in_window_b(datetime(2026, 11, 3, 15, 5, tzinfo=ny))
assert not in_window_b(datetime(2026, 11, 3, 8, 5, tzinfo=ny))
assert not in_window_b(datetime(2026, 11, 7, 10, 5, tzinfo=ny))              # Saturday

# Scanner B: all 4 rules
assert is_hit(12, 11, 10, 9, 11.5, 11.8)
assert not is_hit(10.9, 11, 10, 9, 8, 8)                                     # not above yesterday's high
assert not is_hit(12, 11, 8, 9, 11.5, 11.8)                                  # yesterday's close under 200 SMA
assert not is_hit(12, 11, 10, 9, 12.5, 11.8)                                 # not above pre-market high
assert not is_hit(12, 11, 10, 9, 11.5, 12.2)                                 # not above high of day before this candle
assert not is_hit(12, 11, 10, 9, None, 11.8)                                 # no pre-market data
assert not is_hit(12, 11, 10, float("nan"), 11.5, 11.8)                      # not enough history for 200 SMA

# Scanner B: ticker list and report format
data = {"runs": [{"results": [{"ticker": "B"}, {"ticker": "A"}]}, {"results": [{"ticker": "A"}]}]}
assert tickers_from(data) == ["A", "B"]
assert format_report_b([("ABC", 10.6)]) == "[Scanner B: Trend-join Long Hits]\nABC | Entry $10.60"
assert format_report_b([]) == "[Scanner B: Trend-join Long Hits]\nNo stock match."
print("all checks pass")
