"""Streaming 18 legacy + broad technical-factor panel, screened for future data.

Designed for private local factor research. This file does NOT evaluate the
locked 2026 confirmation set, score securities or place any trades.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .data import validate_prices, load_calendar
from .factors import compute_symbol_factors
from .indicators_expanded import compute_indicators, catalog_frame
from .targets import make_symbol_targets


def one_symbol_matrix(symbol_prices: pd.DataFrame, sessions: pd.DatetimeIndex,
                      signal_start: str, signal_end: str) -> pd.DataFrame:
    """Input rows for one ticker including pre-signal warmup and post-signal labels."""
    if symbol_prices.ticker.nunique() != 1:
        raise ValueError("Exactly one symbol per partition")
    symbol = str(symbol_prices.ticker.iloc[0])
    c = symbol_prices.drop(columns="ticker").set_index("date").reindex(sessions)
    # Context date features only use <= signal-date bars; labels use future.
    baseline = compute_symbol_factors(c).add_prefix("legacy__")
    expanded = compute_indicators(c).add_prefix("ta__")
    labels = make_symbol_targets(c)
    out = pd.concat([baseline, expanded, labels], axis=1)
    signal = (out.index >= pd.Timestamp(signal_start)) & (out.index <= pd.Timestamp(signal_end))
    out = out.loc[signal].copy()
    out.insert(0, "date", out.index)
    out.insert(1, "ticker", symbol)
    if out.columns.duplicated().any():
        raise ValueError("Duplicate merged technical feature names")
    return out.reset_index(drop=True)


def private_matrix(input_files: list[Path], calendar_file: Path, output_dir: Path,
                   signal_start: str = "2019-01-01",
                   signal_end: str = "2025-12-31",
                   batch_tickers: int = 25,
                   allow_2026_confirmation: bool = False,
                   smoke_tickers: int | None = None) -> dict:
    if batch_tickers < 1:
        raise ValueError("batch_tickers must be positive")
    if pd.Timestamp(signal_end) < pd.Timestamp(signal_start):
        raise ValueError("Invalid signal date bounds")
    if pd.Timestamp(signal_end) > pd.Timestamp("2025-12-31") and not allow_2026_confirmation:
        raise ValueError("2026 confirmation set is locked; explicit authorization required")
    if not input_files:
        raise ValueError("No screened source files supplied")
    inputs = []
    for path in input_files:
        raw = pd.read_csv(path, dtype={"ticker": "string"}, parse_dates=["date"])
        if "unsafe_session" not in raw:
            raise ValueError(f"Unscreened market prices rejected: {path}")
        inputs.append(validate_prices(raw))
    frame = pd.concat(inputs, ignore_index=True)
    if frame.duplicated(["date", "ticker"]).any():
        raise ValueError("Same ticker and trading day duplicated across annual files")
    if smoke_tickers is not None:
        if smoke_tickers < 1:
            raise ValueError("smoke_tickers must be positive")
        selected = sorted(frame.ticker.dropna().unique().tolist())[:smoke_tickers]
        frame = frame.loc[frame.ticker.isin(selected)].copy()
    sessions = load_calendar(calendar_file, frame)
    output_dir.mkdir(parents=True, exist_ok=True)
    segments, batch, nrows = [], [], 0
    feature_names = []
    try:
        for symbol, group in frame.groupby("ticker", sort=True):
            matrix = one_symbol_matrix(group, sessions, signal_start, signal_end)
            if not feature_names:
                feature_names = [k for k in matrix if k.startswith("legacy__") or k.startswith("ta__")]
            if not matrix.empty:
                nrows += len(matrix)
                batch.append(matrix)
            if len(batch) >= batch_tickers:
                part = output_dir / f"factor_matrix_part_{len(segments):04d}.parquet"
                pd.concat(batch, ignore_index=True).to_parquet(part, index=False)
                segments.append(str(part.name))
                batch.clear()
        if batch:
            part = output_dir / f"factor_matrix_part_{len(segments):04d}.parquet"
            pd.concat(batch, ignore_index=True).to_parquet(part, index=False)
            segments.append(str(part.name))
    finally:
        batch.clear()
    catalog = catalog_frame()
    if "ta__ichi_cloud_top_gap" not in feature_names:
        raise ValueError("Ichimoku feature missing from matrix")
    meta = {
        "status": "TECHNICAL_MATRIX_ONLY_NOT_EVALUATED",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "signal_start": signal_start, "signal_end": signal_end,
        "source_files": [p.name for p in input_files],
        "tickers_in_input": int(frame.ticker.nunique()),
        "signal_rows": int(nrows),
        "indicator_count": len(feature_names),
        "old_indicator_count": sum(k.startswith("legacy__") for k in feature_names),
        "new_indicator_count": sum(k.startswith("ta__") for k in feature_names),
        "parts": segments,
        "research_only": True,
        "smoke_test_subset_not_for_inference": smoke_tickers is not None,
        "corporate_actions_adjusted_and_verified": False,
        "ordinary_share_historical_membership_verified": False,
        "holdout_2026_opened": bool(pd.Timestamp(signal_end).year >= 2026),
        "notes": [
            "All factors calculated at close T, labels only available for evaluation T+H.",
            "Per-session suspect corporate-action events masked; official event adjustment not certified.",
            "Do not upload per-security matrix to GitHub or an open CI artifact.",
            "The broad 170-variable indicator set is correlated and unvalidated as investment alpha.",
        ],
        "indicator_families": {str(k): int(v) for k,v in catalog.groupby("family").size().items()},
    }
    (output_dir / "factor_matrix_manifest.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: meta[k] for k in ("status", "signal_rows", "indicator_count",
                                          "old_indicator_count", "new_indicator_count",
                                          "holdout_2026_opened")},
                     ensure_ascii=False))
    return meta


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--prices", type=Path, nargs="+", required=True, help="private screened annual CSV.gz files")
    p.add_argument("--calendar", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--signal-start", default="2019-01-01")
    p.add_argument("--signal-end", default="2025-12-31")
    p.add_argument("--batch-tickers", type=int, default=25)
    p.add_argument("--smoke-tickers", type=int, help="Deterministic code-ordered small subset; engineering only")
    p.add_argument("--allow-2026-confirmation", action="store_true",
                   help="Explicitly open the confirmation holdout. Do not use while tuning.")
    a = p.parse_args(argv)
    private_matrix(a.prices, a.calendar, a.output, a.signal_start, a.signal_end,
                   a.batch_tickers, a.allow_2026_confirmation, a.smoke_tickers)


if __name__ == "__main__":
    main()
