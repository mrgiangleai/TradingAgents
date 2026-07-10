"""Liquidity Sweep static-data loader (Phase 6, mirrors dataflows/keyvolume.py).

Reads the offline CSV produced by ``scripts/liquidity_sweep_export.py``
(see ``docs/data/liquidity_data_format.md``) -- never fetches live data,
never imports Backtest-Trading-Lab. A missing file returns the "no data"
marker instead of raising (Quy tac 4): agents must report "No data
available" rather than guess a signal.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from tradingagents.dataflows.research_platform_symbol import to_research_platform_symbol
from tradingagents.default_config import DEFAULT_CONFIG

# CSV columns as produced by Backtest-Trading-Lab's
# signals/liquidity_sweep/export.py::event_to_dict (see the data-format doc).
_INT_FIELDS = {"id", "line_id", "index"}
_FLOAT_FIELDS = {
    "line_price", "keyvolume_final_score",
    "sweep_strength", "sweep_depth", "rejection_strength",
}


@dataclass
class LiquiditySweepData:
    """Parsed Liquidity Sweep export for one symbol/date, or the "no data" marker.

    ``available=False`` means the export file itself is missing -- distinct
    from ``available=True, events=[]``, which means the export ran but the
    detector found zero sweep events in that window (Module 2 events are
    much rarer than Module 1's, so this is a common, legitimate result).
    """

    symbol: str
    date: str
    available: bool
    events: list[dict] = field(default_factory=list)
    path: Path | None = None


def _coerce_row(row: dict) -> dict:
    """Cast CSV string values to their real types. No empty-field cases are
    expected here (unlike KeyVolume's bounce fields) -- LiquiditySweepEvent
    has no optional numeric fields."""
    coerced: dict = {}
    for key, value in row.items():
        if key in _INT_FIELDS:
            coerced[key] = int(float(value))
        elif key in _FLOAT_FIELDS:
            coerced[key] = float(value)
        else:
            coerced[key] = value
    return coerced


def liquidity_sweep_csv_path(symbol: str, date: str, data_dir: str | None = None) -> Path:
    """Resolve the static file path for (symbol, date): ``{data_dir}/{SYMBOL}_{YYYY-MM-DD}.csv``.

    ``symbol`` is mapped through ``to_research_platform_symbol`` first -- see
    ``keyvolume_csv_path``'s docstring for why (same reasoning applies here).
    """
    base = Path(data_dir) if data_dir else Path(DEFAULT_CONFIG["liquidity_sweep_data_dir"])
    return base / f"{to_research_platform_symbol(symbol)}_{date}.csv"


def load_liquidity_sweep_data(symbol: str, date: str, data_dir: str | None = None) -> LiquiditySweepData:
    """Load the static Liquidity Sweep export for (symbol, date).

    Never raises for a missing file -- returns ``LiquiditySweepData(available=False)``
    instead, so callers (the Liquidity Sweep Agent) can short-circuit to a
    "No data available" signal without guessing (Quy tac 4).
    """
    path = liquidity_sweep_csv_path(symbol, date, data_dir)
    if not path.is_file():
        return LiquiditySweepData(symbol=symbol, date=date, available=False, events=[], path=path)

    with path.open(newline="", encoding="utf-8") as f:
        rows = [_coerce_row(row) for row in csv.DictReader(f)]

    return LiquiditySweepData(symbol=symbol, date=date, available=True, events=rows, path=path)
