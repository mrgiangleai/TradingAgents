"""Symbol mapping for static exports from Backtest-Trading-Lab ("Trading
Research Platform") -- KeyVolume/Liquidity Sweep only.

Completely separate from ``symbol_utils.py::normalize_symbol`` (the
Yahoo/yfinance symbol path used by the analysts' data fetching): that
function always collapses crypto tickers to the dashed Yahoo form
(``BTCUSDT``/``BTC-USDT``/``btcusdt`` all -> ``BTC-USD``), which is what
``cli/utils.py::get_ticker()`` stores as ``company_of_interest``. But the
static export files from scripts/keyvolume_export.py and
scripts/liquidity_sweep_export.py are named with the compact Binance-style
symbol instead (``BTCUSDT_2026-07-09.csv`` -- see
docs/data/keyvolume_data_format.md section 4). This module bridges that one
gap for the two loaders only; it does not change what gets passed to
yfinance/Yahoo anywhere.
"""

from __future__ import annotations

import re

# Yahoo-style dashed crypto symbol -> compact Binance-style base+quote.
# normalize_symbol() only ever produces the "-USD" form, but "-USDT"/"-USDC"
# are accepted too for direct callers that didn't go through that function.
_DASHED_CRYPTO_PATTERN = re.compile(r"^([A-Z0-9]+)-(USD|USDT|USDC)$")

# Binance's actual USD-quoted spot pairs are USDT pairs (it has no plain
# "-USD" market) -- matches the quote currency already used by every real
# export sample generated so far (BTCUSDT, DOGEUSDT).
_DEFAULT_QUOTE = "USDT"


def to_research_platform_symbol(symbol: str) -> str:
    """Map a Yahoo-style dashed crypto symbol to the compact symbol the
    KeyVolume/Liquidity Sweep static exports use (``BTC-USD`` -> ``BTCUSDT``).

    Anything that doesn't match the dashed crypto pattern (a stock ticker,
    or a symbol already in compact form like ``BTCUSDT``) passes through
    unchanged -- this function only ever narrows the gap between the two
    conventions, never invents a symbol that wasn't already implied.
    """
    s = symbol.strip().upper()
    match = _DASHED_CRYPTO_PATTERN.match(s)
    if match:
        base = match.group(1)
        return f"{base}{_DEFAULT_QUOTE}"
    return s
