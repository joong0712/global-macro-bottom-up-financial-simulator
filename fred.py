"""미국 FRED 거시경제 통계 조회 및 가공 기능."""

import os
import re
from dataclasses import dataclass
from typing import Callable

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred


load_dotenv()

MONTH_PATTERN = re.compile(r"^\d{6}$")


@dataclass(frozen=True)
class FredIndicatorSpec:
    series_id: str
    cycle: str
    unit: str
    description: str
    comparison: str
    delta_unit: str
    decimals: int = 2
    transform: Callable[[pd.DataFrame], pd.DataFrame] | None = None


def _year_over_year(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["값"] = result["값"].pct_change(12) * 100
    return result.dropna().reset_index(drop=True)


def _monthly_average(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.set_index("날짜")["값"]
        .resample("MS")
        .mean()
        .dropna()
        .rename_axis("날짜")
        .reset_index()
    )


def _billions_to_trillions(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["값"] = result["값"] / 1000
    return result


FRED_INDICATORS = {
    "연방기금금리": FredIndicatorSpec(
        "FEDFUNDS", "M", "%",
        "미국 연방기금 실효금리",
        "직전 발표값 대비", "%p",
    ),
    "달러 지수": FredIndicatorSpec(
        "DTWEXBGS", "M", "지수",
        "명목 광의 무역가중 달러지수의 월평균",
        "전월 대비", "p",
        transform=_monthly_average,
    ),
    "소비자물가 상승률": FredIndicatorSpec(
        "CPIAUCSL", "M", "%",
        "미국 도시소비자 CPI의 전년동월비",
        "전월 대비", "%p",
        transform=_year_over_year,
    ),
    "미 국채 3년": FredIndicatorSpec(
        "GS3", "M", "%",
        "미국 국채 3년 월평균 시장수익률",
        "전월 대비", "%p",
    ),
    "미 국채 10년": FredIndicatorSpec(
        "GS10", "M", "%",
        "미국 국채 10년 월평균 시장수익률",
        "전월 대비", "%p",
    ),
    "GDP 성장률": FredIndicatorSpec(
        "A191RL1Q225SBEA", "Q", "%",
        "미국 실질 GDP 전기비 연율",
        "전분기 대비", "%p",
    ),
    "M2": FredIndicatorSpec(
        "M2SL", "M", "조달러",
        "미국 M2 통화량·계절조정",
        "전월 대비", "조달러",
        decimals=2,
        transform=_billions_to_trillions,
    ),
    "생산자물가 상승률": FredIndicatorSpec(
        "PPIACO", "M", "%",
        "미국 전 상품 생산자물가지수의 전년동월비",
        "전월 대비", "%p",
        transform=_year_over_year,
    ),
    "실업률": FredIndicatorSpec(
        "UNRATE", "M", "%",
        "미국 계절조정 실업률",
        "전월 대비", "%p",
    ),
}

FRED_CORE_INDICATORS = (
    "연방기금금리",
    "달러 지수",
    "소비자물가 상승률",
    "미 국채 3년",
    "미 국채 10년",
    "GDP 성장률",
)

FRED_SUPPLEMENTARY_INDICATORS = (
    "M2",
    "생산자물가 상승률",
    "실업률",
)


def _get_api_key(api_key: str | None = None) -> str:
    key = api_key or os.getenv("FRED_API_KEY")
    if not key:
        raise ValueError("FRED_API_KEY가 설정되지 않았습니다.")
    return key


def _parse_month(value: str, field_name: str) -> pd.Timestamp:
    if not MONTH_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name}은 YYYYMM 형식이어야 합니다.")
    try:
        return pd.to_datetime(value, format="%Y%m")
    except ValueError as error:
        raise ValueError(f"{field_name}에 올바른 월을 입력해 주세요.") from error


def get_fred_indicator(
    name: str,
    start_date: str,
    end_date: str,
    *,
    api_key: str | None = None,
    client: Fred | None = None,
) -> pd.DataFrame:
    """하나의 FRED 지표를 날짜·값 형태로 반환한다."""
    if name not in FRED_INDICATORS:
        raise ValueError(f"지원하지 않는 FRED 지표입니다: {name}")

    start = _parse_month(start_date, "조회 시작 월")
    end = _parse_month(end_date, "조회 종료 월") + pd.offsets.MonthEnd(0)
    if start > end:
        raise ValueError("조회 시작 월은 종료 월보다 늦을 수 없습니다.")

    spec = FRED_INDICATORS[name]
    request_start = start
    if spec.transform is _year_over_year:
        request_start -= pd.DateOffset(months=12)

    fred = client or Fred(api_key=_get_api_key(api_key))
    series = fred.get_series(
        spec.series_id,
        observation_start=request_start.strftime("%Y-%m-%d"),
        observation_end=end.strftime("%Y-%m-%d"),
    )
    frame = (
        series.rename("값")
        .rename_axis("날짜")
        .reset_index()
        .dropna()
        .sort_values("날짜")
        .reset_index(drop=True)
    )
    frame["날짜"] = pd.to_datetime(frame["날짜"])
    frame["값"] = pd.to_numeric(frame["값"], errors="coerce")
    frame = frame.dropna().reset_index(drop=True)

    if spec.transform:
        frame = spec.transform(frame)

    return frame[frame["날짜"] >= start].reset_index(drop=True)


def get_fred_indicators(
    start_date: str,
    end_date: str,
    names: tuple[str, ...] = FRED_CORE_INDICATORS,
    *,
    api_key: str | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """여러 FRED 지표를 조회하며 개별 오류를 분리해 반환한다."""
    data: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    client = Fred(api_key=_get_api_key(api_key))

    for name in names:
        try:
            data[name] = get_fred_indicator(
                name,
                start_date,
                end_date,
                client=client,
            )
        except Exception as error:
            errors[name] = str(error)

    return data, errors
