"""Input validation for daily OHLCV research; no external API calls."""
from pathlib import Path
import pandas as pd

REQUIRED = ("date", "ticker", "open", "high", "low", "close", "volume", "turnover")


def load_prices(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"ticker": "string"})
    return validate_prices(frame)


def validate_prices(df: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(REQUIRED) - set(df.columns))
    if missing:
        raise ValueError(f"필수 열 누락: {', '.join(missing)}")
    out = df.loc[:, REQUIRED].copy()
    ticker = out["ticker"].astype("string").str.strip()
    if ticker.isna().any() or ~ticker.str.fullmatch(r"\d{1,6}").fillna(False).all():
        raise ValueError("종목코드는 1~6자리 숫자여야 합니다.")
    out["ticker"] = ticker.str.zfill(6)
    out["date"] = pd.to_datetime(out["date"], errors="raise").dt.normalize()
    if out["date"].isna().any():
        raise ValueError("날짜가 비어 있습니다.")
    for field in REQUIRED[2:]:
        out[field] = pd.to_numeric(out[field], errors="raise")
        if out[field].isna().any():
            raise ValueError(f"{field} 값에 결측치가 있습니다.")
    if (out[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC 가격은 양수여야 합니다.")
    if (out[["volume", "turnover"]] < 0).any().any():
        raise ValueError("거래량/거래대금은 음수가 될 수 없습니다.")
    if (out["high"] < out[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("고가는 시가·종가·저가 이상이어야 합니다.")
    if (out["low"] > out[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("저가는 시가·종가·고가 이하여야 합니다.")
    if out.duplicated(["date", "ticker"]).any():
        raise ValueError("종목·날짜 중복 발견")
    return out.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)


def load_calendar(path: str | Path | None, df: pd.DataFrame) -> pd.DatetimeIndex:
    """Use a verified KRX exchange calendar in actual historical research."""
    if path is None:
        return pd.DatetimeIndex(df["date"].drop_duplicates().sort_values())
    calendar = pd.read_csv(path)
    if "date" not in calendar:
        raise ValueError("거래일 달력 파일에 date 열이 필요합니다.")
    dates = pd.DatetimeIndex(pd.to_datetime(calendar["date"], errors="raise").dt.normalize())
    if dates.isna().any() or dates.has_duplicates:
        raise ValueError("거래일 달력에 누락 또는 중복된 날짜가 있습니다.")
    dates = dates.sort_values()
    if (~df["date"].isin(dates)).any():
        raise ValueError("거래일 달력에 없는 주가 날짜가 있습니다.")
    return dates
