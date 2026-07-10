"""Offline export adapter: Backtest-Trading-Lab's KeyVolume Engine -> static CSV.

This script is the one place TradingAgents' KeyVolume integration ever
touches Backtest-Trading-Lab or a live exchange API. Per ROADMAP.md's
locked decision ("Tich hop KeyVolume ... bang file CSV/JSON tinh export
tu Backtest-Trading-Lab. Chua dung API o giai doan MVP"), it must be run
OFFLINE, by hand, ahead of time -- never from inside TradingAgents'
runtime graph. The graph only ever reads the static file this script
produces (see tradingagents/dataflows/keyvolume.py).

Why this has to run with Backtest-Trading-Lab's Python interpreter, not
TradingAgents': it imports that repo's `signals.keyvolume_line` package
and `data.binance_data` (which needs `ccxt`) directly, as a read-only
consumer of their already-public service/export contract
(signals/keyvolume_line/service.py, export.py) -- the same contract
`app.py` and the preview scripts already use there. Nothing in
Backtest-Trading-Lab is modified; Module 1's detector/scoring logic is
untouched (it is FROZEN there).

Usage (must use Backtest-Trading-Lab's own venv):

    /path/to/Backtest-Trading-Lab/.venv/bin/python scripts/keyvolume_export.py \\
        BTCUSDT 2026-07-09

    # optional flags:
    #   --timeframe 1h            (default: 1h)
    #   --lookback-candles 720    (default: 720 = 30 days at 1h; unvalidated,
    #                               conservative default -- enough history for
    #                               KeyVolume lines to reach a mature lifecycle
    #                               state, mirrors the preview app's own
    #                               default candle counts)
    #   --lab-path /path/to/Backtest-Trading-Lab   (default: sibling dir)
    #   --output-dir /path/to/TradingAgents/data/keyvolume  (default: sibling dir)

Anti-lookahead (Quy tac 6): fetches candles starting `lookback_candles`
bars before the END of `date` (UTC), then truncates anything at or after
the start of the next UTC day. Binance/ccxt's `since_ms` + `limit` pair
does not itself guarantee an upper bound, so the truncation step below is
load-bearing, not defensive boilerplate -- without it a script run today
against a past `date` could silently leak newer candles into a
supposedly historical snapshot.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_TIMEFRAME_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
}

# Longest-first so USDT/USDC/BUSD/FDUSD match before the bare USD suffix.
_QUOTE_CURRENCIES = ("USDT", "USDC", "BUSD", "FDUSD", "USD")


def to_ccxt_symbol(compact_symbol: str) -> str:
    """``BTCUSDT`` -> ``BTC/USDT``. Raises ValueError for an unrecognized quote."""
    s = compact_symbol.strip().upper()
    for quote in _QUOTE_CURRENCIES:
        if s.endswith(quote) and len(s) > len(quote):
            return f"{s[:-len(quote)]}/{quote}"
    raise ValueError(
        f"Could not split {compact_symbol!r} into base/quote "
        f"(known quotes: {', '.join(_QUOTE_CURRENCIES)})"
    )


def to_file_symbol(compact_symbol: str) -> str:
    """Canonical file-name form: upper-cased, no separator (matches ROADMAP.md
    Quy tac 4's ``data/keyvolume/{SYMBOL}_{YYYY-MM-DD}.csv`` example)."""
    return compact_symbol.strip().upper()


def fetch_ohlcv_through_date(get_ohlcv, symbol: str, timeframe: str, date_str: str, lookback_candles: int):
    """Fetch candles ending at the close of ``date_str`` (UTC), never later.

    Single ``get_ohlcv`` call when ``lookback_candles`` fits Binance's
    per-request cap (~1000); paginates forward otherwise, exactly like
    Backtest-Trading-Lab's own ``fetch_extended_ohlcv`` except anchored to
    an explicit historical end date instead of "now".
    """
    import pandas as pd

    seconds = _TIMEFRAME_SECONDS[timeframe]
    trade_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_exclusive = trade_date + timedelta(days=1)  # start of the next UTC day
    since_ms = int((end_exclusive - timedelta(seconds=lookback_candles * seconds)).timestamp() * 1000)

    frames = []
    remaining = lookback_candles
    batch_limit = 1000
    cursor_ms = since_ms
    max_iterations = (lookback_candles // batch_limit) + 5

    for _ in range(max_iterations):
        if remaining <= 0:
            break
        chunk = get_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=min(batch_limit, remaining),
            since_ms=cursor_ms,
        )
        if chunk.empty:
            break
        frames.append(chunk)
        remaining -= len(chunk)
        next_cursor_ms = int(chunk["timestamp"].iloc[-1].timestamp() * 1000) + seconds * 1000
        if next_cursor_ms <= cursor_ms:
            break
        cursor_ms = next_cursor_ms
        if len(chunk) < batch_limit:
            break

    if not frames:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    combined = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset="timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # Load-bearing anti-lookahead truncation -- see module docstring.
    end_exclusive_naive = end_exclusive.replace(tzinfo=None)
    combined = combined[combined["timestamp"] < end_exclusive_naive].reset_index(drop=True)

    if len(combined) > lookback_candles:
        combined = combined.tail(lookback_candles).reset_index(drop=True)

    return combined


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("symbol", help="Compact broker-style symbol, e.g. BTCUSDT")
    parser.add_argument("date", help="Trade date, YYYY-MM-DD (UTC calendar day)")
    parser.add_argument("--timeframe", default="1h", choices=list(_TIMEFRAME_SECONDS))
    parser.add_argument("--lookback-candles", type=int, default=720)
    parser.add_argument(
        "--lab-path",
        default=str(Path(__file__).resolve().parent.parent.parent / "Backtest-Trading-Lab"),
        help="Path to the Backtest-Trading-Lab repo root (default: sibling directory)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent.parent / "data" / "keyvolume"),
        help="Directory to write the CSV into (default: TradingAgents/data/keyvolume)",
    )
    args = parser.parse_args()

    lab_path = Path(args.lab_path).resolve()
    if not (lab_path / "signals" / "keyvolume_line").is_dir():
        print(
            f"error: {lab_path} does not look like a Backtest-Trading-Lab checkout "
            "(signals/keyvolume_line/ not found). Pass --lab-path explicitly.",
            file=sys.stderr,
        )
        return 1
    sys.path.insert(0, str(lab_path))

    try:
        from data.binance_data import get_ohlcv
        from signals.keyvolume_line import KeyVolumeLineConfig
        from signals.keyvolume_line.service import KeyVolumeService
    except ImportError as exc:
        print(
            f"error: failed to import Backtest-Trading-Lab modules ({exc}). "
            "This script must be run with THAT repo's venv (it needs ccxt), "
            f"e.g.:\n  {lab_path}/.venv/bin/python {__file__} {args.symbol} {args.date}",
            file=sys.stderr,
        )
        return 1

    ccxt_symbol = to_ccxt_symbol(args.symbol)
    print(f"Fetching {ccxt_symbol} {args.timeframe} candles through {args.date} (UTC, exclusive of the next day)...")
    df = fetch_ohlcv_through_date(get_ohlcv, ccxt_symbol, args.timeframe, args.date, args.lookback_candles)
    if df.empty:
        print(f"error: no OHLCV candles returned for {ccxt_symbol} up to {args.date}", file=sys.stderr)
        return 1
    print(f"  {len(df)} candles, {df['timestamp'].iloc[0]} .. {df['timestamp'].iloc[-1]}")

    service = KeyVolumeService(KeyVolumeLineConfig())
    result = service.run(df)
    print(f"KeyVolumeService produced {len(result.lines)} lines")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{to_file_symbol(args.symbol)}_{args.date}.csv"
    service.export_csv(result, out_path)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
