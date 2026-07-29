"""Twelve Data 실시간 외환 시세 조회 기능."""

import os

import pandas as pd
import requests
from dotenv import load_dotenv


load_dotenv()

TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"


def get_live_usd_krw(
    *,
    interval: str = "1min",
    outputsize: int = 720,
    api_key: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """USD/KRW 최근 분봉 OHLC와 메타데이터를 반환한다."""
    key = (
        api_key
        or os.getenv("TWELVE_DATA_API_KEY")
        or os.getenv("TWELVE_API_KEY")
    )
    if not key:
        raise ValueError(
            "TWELVE_DATA_API_KEY 또는 TWELVE_API_KEY가 설정되지 않았습니다."
        )

    response = requests.get(
        TWELVE_DATA_URL,
        params={
            "symbol": "USD/KRW",
            "interval": interval,
            "outputsize": outputsize,
            "timezone": "Asia/Seoul",
            "order": "ASC",
            "apikey": key,
        },
        timeout=15,
    )
    if not response.ok:
        raise RuntimeError(
            f"Twelve Data HTTP 오류({response.status_code})"
        )
    result = response.json()

    if result.get("status") == "error":
        raise RuntimeError(result.get("message", "Twelve Data 조회에 실패했습니다."))

    values = result.get("values", [])
    if not values:
        return pd.DataFrame(
            columns=["날짜", "시가", "고가", "저가", "종가"]
        ), result.get("meta", {})

    frame = pd.DataFrame(values).rename(
        columns={
            "datetime": "날짜",
            "open": "시가",
            "high": "고가",
            "low": "저가",
            "close": "종가",
        }
    )
    frame["날짜"] = (
        pd.to_datetime(frame["날짜"], errors="coerce", utc=True)
        .dt.tz_convert("Asia/Seoul")
        .dt.tz_localize(None)
    )
    for column in ("시가", "고가", "저가", "종가"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = (
        frame[["날짜", "시가", "고가", "저가", "종가"]]
        .dropna()
        .sort_values("날짜")
        .reset_index(drop=True)
    )
    return frame, result.get("meta", {})


def get_market_etf_daily(
    symbol: str,
    *,
    exchange: str | None = None,
    outputsize: int = 5000,
    api_key: str | None = None,
) -> pd.DataFrame:
    """시장지수 추종 ETF의 일별 OHLC를 반환한다."""
    key = (
        api_key
        or os.getenv("TWELVE_DATA_API_KEY")
        or os.getenv("TWELVE_API_KEY")
    )
    if not key:
        raise ValueError(
            "TWELVE_DATA_API_KEY 또는 TWELVE_API_KEY가 설정되지 않았습니다."
        )

    params = {
        "symbol": symbol,
        "interval": "1day",
        "outputsize": outputsize,
        "order": "ASC",
        "apikey": key,
    }
    if exchange:
        params["exchange"] = exchange

    response = requests.get(
        TWELVE_DATA_URL,
        params=params,
        timeout=15,
    )
    if not response.ok:
        raise RuntimeError(
            f"Twelve Data HTTP 오류({response.status_code})"
        )
    result = response.json()
    if result.get("status") == "error":
        raise RuntimeError(
            result.get("message", f"{symbol} 조회에 실패했습니다.")
        )

    frame = pd.DataFrame(result.get("values", [])).rename(
        columns={
            "datetime": "날짜",
            "open": "시가",
            "high": "고가",
            "low": "저가",
            "close": "종가",
        }
    )
    if frame.empty:
        return pd.DataFrame(
            columns=["날짜", "시가", "고가", "저가", "종가"]
        )
    frame["날짜"] = pd.to_datetime(frame["날짜"], errors="coerce")
    for column in ("시가", "고가", "저가", "종가"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return (
        frame[["날짜", "시가", "고가", "저가", "종가"]]
        .dropna()
        .sort_values("날짜")
        .reset_index(drop=True)
    )


def get_iwm_daily(
    *,
    outputsize: int = 5000,
    api_key: str | None = None,
) -> pd.DataFrame:
    """기존 호출부와 호환되는 IWM 일별 종가 조회 함수."""
    frame = get_market_etf_daily(
        "IWM", outputsize=outputsize, api_key=api_key
    )
    return frame[["날짜", "종가"]].rename(columns={"종가": "값"})
