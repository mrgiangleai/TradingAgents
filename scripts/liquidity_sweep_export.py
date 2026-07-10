"""Offline export adapter: Backtest-Trading-Lab's Liquidity Sweep Engine -> static CSV.

Mirrors scripts/keyvolume_export.py's role and constraints exactly (see
that file's docstring for the full rationale) -- this is the one place
TradingAgents' Liquidity Sweep integration ever touches Backtest-Trading-Lab
or a live exchange API, and it must be run OFFLINE, ahead of time, never
from inside TradingAgents' runtime graph.

Why `run_core_pipeline` and not `LiquiditySweepService.run(df, lines)`
directly: Module 2 (Liquidity Sweep) takes Module 1's (KeyVolume)
`lines` as an input, and architecture_handoff.md documents a real,
previously-shipped bug (found in app.py itself, fixed 2026-07-09) from
chaining `KeyVolumeService.run(df)` then feeding its COMPLETE, end-of-
dataset `lines` into `LiquiditySweepService.run(df, lines)` -- early
candles then "see" line status that didn't exist yet at that point in
history (a lookahead leak). `signals/engine_kit/pipeline.py::run_core_pipeline`
is Backtest-Trading-Lab's own fix: one shared per-candle loop calling
each detector's `step()` in order. This script uses that function
exactly as-is and only reads its `.liquidity_sweep` result -- no
detection logic is reimplemented here (Quy tac: khong copy logic engine).

Usage (must use Backtest-Trading-Lab's own venv):

    /path/to/Backtest-Trading-Lab/.venv/bin/python scripts/liquidity_sweep_export.py \\
        BTCUSDT 2026-07-09

    # optional flags: --timeframe 1h (default), --lookback-candles 720 (default),
    #   --lab-path, --output-dir (default: TradingAgents/data/liquidity)

Anti-lookahead (Quy tac 6): identical truncation logic to
scripts/keyvolume_export.py (duplicated rather than imported, so each
export script stays a fully standalone single-file CLI tool runnable on
its own -- see that file if the two ever need to be kept in sync).
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

_QUOTE_CURRENCIES = ("USDT", "USDC", "BUSD", "FDUSD", "USD")


def to_ccxt_symbol(compact_symbol: str) -> str:
    s = compact_symbol.strip().upper()
    for quote in _QUOTE_CURRENCIES:
        if s.endswith(quote) and len(s) > len(quote):
            return f"{s[:-len(quote)]}/{quote}"
    raise ValueError(
        f"Could not split {compact_symbol!r} into base/quote "
        f"(known quotes: {', '.join(_QUOTE_CURRENCIES)})"
    )


def to_file_symbol(compact_symbol: str) -> str:
    return compact_symbol.strip().upper()


def fetch_ohlcv_through_date(get_ohlcv, symbol: str, timeframe: str, date_str: str, lookback_candles: int):
    """Fetch candles ending at the close of ``date_str`` (UTC), never later.

    Identical logic to scripts/keyvolume_export.py::fetch_ohlcv_through_date.
    """
    import pandas as pd

    seconds = _TIMEFRAME_SECONDS[timeframe]
    trade_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_exclusive = trade_date + timedelta(days=1)
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
        default=str(Path(__file__).resolve().parent.parent / "data" / "liquidity"),
        help="Directory to write the CSV into (default: TradingAgents/data/liquidity)",
    )
    args = parser.parse_args()

    lab_path = Path(args.lab_path).resolve()
    if not (lab_path / "signals" / "liquidity_sweep").is_dir():
        print(
            f"error: {lab_path} does not look like a Backtest-Trading-Lab checkout "
            "(signals/liquidity_sweep/ not found). Pass --lab-path explicitly.",
            file=sys.stderr,
        )
        return 1
    sys.path.insert(0, str(lab_path))

    try:
        from data.binance_data import get_ohlcv
        from signals.engine_kit.pipeline import run_core_pipeline
        from signals.liquidity_sweep.export import export_events_to_csv
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

    # run_core_pipeline composes Module 1 (KeyVolume) -> 2 (Liquidity Sweep)
    # in one anti-lookahead-safe shared loop -- see module docstring. We
    # only keep .liquidity_sweep; Module 1's own lines are already exported
    # separately by scripts/keyvolume_export.py.
    pipeline_result = run_core_pipeline(df)
    result = pipeline_result.liquidity_sweep
    print(f"Liquidity Sweep detector produced {len(result.events)} events (against {len(pipeline_result.keyvolume.lines)} KeyVolume lines)")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{to_file_symbol(args.symbol)}_{args.date}.csv"

    export_events_to_csv(result.events, out_path)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
