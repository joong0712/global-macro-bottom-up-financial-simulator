"""글로벌 주가지수 OHLC 조회 기능."""

import ast

import pandas as pd
import requests
import yfinance as yf


MARKET_INDICES = {
    "ECOS": {
        "코스피": ("^KS11", "KOSPI"),
        "코스닥": ("^KQ11", "KOSDAQ"),
    },
    "FRED": {
        "S&P 500": ("^GSPC", "S&P 500"),
        "다우존스": ("^DJI", "Dow Jones Industrial Average"),
        "러셀 2000": ("^RUT", "Russell 2000"),
    },
}

NAVER_INDEX_SYMBOLS = {
    "코스피": "KOSPI",
    "코스닥": "KOSDAQ",
}


def _get_naver_index_ohlc(
    symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    response = requests.get(
        "https://api.finance.naver.com/siseJson.naver",
        params={
            "symbol": symbol,
            "requestType": 1,
            "startTime": start.strftime("%Y%m%d"),
            "endTime": end.strftime("%Y%m%d"),
            "timeframe": "day",
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    rows = ast.literal_eval(response.text.strip())
    if len(rows) <= 1:
        return pd.DataFrame(
            columns=["날짜", "시가", "고가", "저가", "종가"]
        )

    frame = pd.DataFrame(rows[1:], columns=rows[0])
    frame["날짜"] = pd.to_datetime(
        frame["날짜"], format="%Y%m%d", errors="coerce"
    )
    for column in ("시가", "고가", "저가", "종가"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return (
        frame[["날짜", "시가", "고가", "저가", "종가"]]
        .dropna()
        .sort_values("날짜")
        .reset_index(drop=True)
    )


def get_market_index_ohlc(
    source_name: str,
    name: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Yahoo Finance에서 시장지수 일별 OHLC를 반환한다."""
    if source_name not in MARKET_INDICES:
        raise ValueError(f"지원하지 않는 시장 구분입니다: {source_name}")
    if name not in MARKET_INDICES[source_name]:
        raise ValueError(f"지원하지 않는 시장지수입니다: {name}")

    start = pd.to_datetime(start_date, format="%Y%m")
    end = pd.to_datetime(end_date, format="%Y%m") + pd.offsets.MonthEnd(0)
    symbol, _ = MARKET_INDICES[source_name][name]
    if source_name == "ECOS":
        return _get_naver_index_ohlc(
            NAVER_INDEX_SYMBOLS[name], start, end
        )

    frame = yf.Ticker(symbol).history(
        start=start.strftime("%Y-%m-%d"),
        end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=False,
        actions=False,
    )
    if frame.empty:
        return pd.DataFrame(
            columns=["날짜", "시가", "고가", "저가", "종가"]
        )

    result = frame.reset_index().rename(
        columns={
            "Date": "날짜",
            "Open": "시가",
            "High": "고가",
            "Low": "저가",
            "Close": "종가",
        }
    )
    result["날짜"] = pd.to_datetime(result["날짜"]).dt.tz_localize(None)
    for column in ("시가", "고가", "저가", "종가"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return (
        result[["날짜", "시가", "고가", "저가", "종가"]]
        .dropna()
        .sort_values("날짜")
        .reset_index(drop=True)
    )


def get_company_stock_ohlc(
    stock_code: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, str, str]:
    """국내 상장 종목의 일별 OHLC, 심볼, 출처를 반환한다."""
    naver_frame = _get_naver_index_ohlc(stock_code, start, end)
    if not naver_frame.empty:
        return naver_frame, stock_code, "네이버 금융 국내 종목 일봉"

    for suffix in (".KS", ".KQ"):
        symbol = f"{stock_code}{suffix}"
        frame = yf.Ticker(symbol).history(
            start=start.strftime("%Y-%m-%d"),
            end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=False,
            actions=False,
        )
        if frame.empty:
            continue

        result = frame.reset_index().rename(
            columns={
                "Date": "날짜",
                "Open": "시가",
                "High": "고가",
                "Low": "저가",
                "Close": "종가",
            }
        )
        result["날짜"] = pd.to_datetime(result["날짜"]).dt.tz_localize(None)
        for column in ("시가", "고가", "저가", "종가"):
            result[column] = pd.to_numeric(
                result[column], errors="coerce"
            )
        result = (
            result[["날짜", "시가", "고가", "저가", "종가"]]
            .dropna()
            .sort_values("날짜")
            .reset_index(drop=True)
        )
        if not result.empty:
            return result, symbol, "Yahoo Finance"

    return (
        pd.DataFrame(columns=["날짜", "시가", "고가", "저가", "종가"]),
        "",
        "",
    )
