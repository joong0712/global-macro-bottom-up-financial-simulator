"""Labels: signal at T close; enter T+1 open; exit T+H close."""
import numpy as np
import pandas as pd

HORIZONS = (5, 10)


def make_symbol_targets(frame: pd.DataFrame, horizons: tuple[int, ...] = HORIZONS) -> pd.DataFrame:
    """A full exchange-session indexed frame is required; never skip missing sessions."""
    result = pd.DataFrame(index=frame.index)
    risk = frame["unsafe_session"].fillna(False).astype(bool) if "unsafe_session" in frame else pd.Series(False, index=frame.index)
    for horizon in horizons:
        if horizon < 1:
            raise ValueError("보유 기간은 양수여야 합니다.")
        entry = frame["open"].shift(-1)
        exit_close = frame["close"].shift(-horizon)
        forward_high = pd.concat([frame["high"].shift(-i) for i in range(1, horizon + 1)], axis=1)
        forward_low = pd.concat([frame["low"].shift(-i) for i in range(1, horizon + 1)], axis=1)
        forward_volume = pd.concat([frame["volume"].shift(-i) for i in range(1, horizon + 1)], axis=1)
        future_risk = pd.concat([risk.shift(-i) for i in range(1, horizon + 1)], axis=1)
        valid = (
            forward_high.notna().all(axis=1) &
            forward_low.notna().all(axis=1) &
            forward_volume.gt(0).all(axis=1) &
            ~future_risk.fillna(True).any(axis=1) & ~risk &
            entry.gt(0) & exit_close.gt(0)
        )
        result[f"entry_date_{horizon}"] = pd.Series(frame.index, index=frame.index).shift(-1)
        result[f"exit_date_{horizon}"] = pd.Series(frame.index, index=frame.index).shift(-horizon)
        result[f"forward_return_{horizon}"] = exit_close.div(entry).sub(1).where(valid)
        result[f"mfe_{horizon}"] = forward_high.max(axis=1).div(entry).sub(1).where(valid)
        result[f"mae_{horizon}"] = forward_low.min(axis=1).div(entry).sub(1).where(valid)
    return result.replace([np.inf, -np.inf], np.nan)


def build_panel(prices: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    from .factors import compute_symbol_factors
    rows = []
    for ticker, symbol_df in prices.groupby("ticker", sort=True):
        full = symbol_df.drop(columns="ticker").set_index("date").sort_index().reindex(calendar)
        factors, targets = compute_symbol_factors(full), make_symbol_targets(full)
        combined = pd.concat([full, factors, targets], axis=1)
        combined = combined.loc[symbol_df["date"]]
        combined.insert(0, "date", combined.index)
        combined.insert(1, "ticker", ticker)
        rows.append(combined.reset_index(drop=True))
    return (pd.concat(rows, ignore_index=True)
            .sort_values(["date", "ticker"]).reset_index(drop=True)) if rows else pd.DataFrame()
