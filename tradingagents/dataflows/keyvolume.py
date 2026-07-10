"""KeyVolume static-data loader (Phase 4.3).

Reads the offline CSV produced by ``scripts/keyvolume_export.py`` (see
``docs/data/keyvolume_data_format.md``) -- never fetches live data, never
imports Backtest-Trading-Lab. A missing file returns the "no data" marker
instead of raising, so the graph keeps running when one symbol/date has no
export yet (Quy tac 4, ROADMAP.md): agents must report "No data available"
rather than guess a signal.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from tradingagents.dataflows.research_platform_symbol import to_research_platform_symbol
from tradingagents.default_config import DEFAULT_CONFIG

# CSV columns as produced by Backtest-Trading-Lab's
# signals/keyvolume_line/export.py::line_to_dict (see the data-format doc).
_INT_FIELDS = {
    "id", "source_segment_start", "source_segment_end",
    "test_count", "age_bars", "survival_bars", "held_count", "broken_count",
}
_FLOAT_FIELDS = {
    "price", "anomaly_score", "reaction_strength", "creation_quality",
    "average_bounce_strength", "max_bounce_strength", "survival_score", "final_score",
}
_BOOL_FIELDS = {"is_approximate"}


@dataclass
class KeyVolumeData:
    """Parsed KeyVolume export for one symbol/date, or the "no data" marker.

    ``available=False`` means the export file itself is missing (nothing was
    ever generated for this symbol/date) -- distinct from ``available=True,
    lines=[]``, which means the export ran but the detector found zero
    KeyVolume lines in that window (a legitimate empty result, not missing
    data).
    """

    symbol: str
    date: str
    available: bool
    lines: list[dict] = field(default_factory=list)
    path: Path | None = None


def _coerce_row(row: dict) -> dict:
    """Cast CSV string values to their real types; ``""`` -> ``None``.

    An empty ``average_bounce_strength``/``max_bounce_strength`` means "this
    line was never held/bounced" (a valid value from the export, not a
    parsing failure) -- see the data-format doc.
    """
    coerced: dict = {}
    for key, value in row.items():
        if value == "":
            coerced[key] = None
        elif key in _BOOL_FIELDS:
            coerced[key] = value.strip().lower() == "true"
        elif key in _INT_FIELDS:
            coerced[key] = int(float(value))
        elif key in _FLOAT_FIELDS:
            coerced[key] = float(value)
        else:
            coerced[key] = value
    return coerced


def keyvolume_csv_path(symbol: str, date: str, data_dir: str | None = None) -> Path:
    """Resolve the static file path for (symbol, date) per the locked naming
    convention: ``{data_dir}/{SYMBOL}_{YYYY-MM-DD}.csv`` (Quy tac 4).

    ``symbol`` is mapped through ``to_research_platform_symbol`` first, so a
    Yahoo-style ticker like ``BTC-USD`` (what the CLI's ``company_of_interest``
    actually holds) resolves to the compact export filename (``BTCUSDT``).
    """
    base = Path(data_dir) if data_dir else Path(DEFAULT_CONFIG["keyvolume_data_dir"])
    return base / f"{to_research_platform_symbol(symbol)}_{date}.csv"


def load_keyvolume_data(symbol: str, date: str, data_dir: str | None = None) -> KeyVolumeData:
    """Load the static KeyVolume export for (symbol, date).

    Never raises for a missing file -- returns ``KeyVolumeData(available=False)``
    instead, so callers (the KeyVolume Agent) can short-circuit to a
    "No data available" signal without guessing (Quy tac 4).
    """
    path = keyvolume_csv_path(symbol, date, data_dir)
    if not path.is_file():
        return KeyVolumeData(symbol=symbol, date=date, available=False, lines=[], path=path)

    with path.open(newline="", encoding="utf-8") as f:
        rows = [_coerce_row(row) for row in csv.DictReader(f)]

    return KeyVolumeData(symbol=symbol, date=date, available=True, lines=rows, path=path)
