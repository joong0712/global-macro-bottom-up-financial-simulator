"""한국은행 ECOS 거시경제 통계 조회 기능."""

import os
import re
from dataclasses import dataclass
from typing import Callable

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


load_dotenv()

MONTH_PATTERN = re.compile(r"^\d{6}$")
ECOS_API_URL = "https://ecos.bok.or.kr/api/StatisticSearch"


@dataclass(frozen=True)
class IndicatorSpec:
    stat_code: str
    item_code: str
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


def _m2_to_trillion_won(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    # ECOS 원자료 단위인 십억원(10억 원)을 조원으로 환산한다.
    result["값"] = result["값"] / 1000
    return result


def _policy_rate_changes(frame: pd.DataFrame) -> pd.DataFrame:
    """일별 기준금리에서 실제 금리 변경 시점만 남긴다."""
    result = frame.copy()
    changed = result["값"].ne(result["값"].shift())
    return result.loc[changed].reset_index(drop=True)


INDICATORS = {
    "기준금리": IndicatorSpec(
        "722Y001", "0101000", "D", "%",
        "한국은행 기준금리",
        "직전 발표값 대비", "%p",
        transform=_policy_rate_changes,
    ),
    "원/달러 환율": IndicatorSpec(
        "731Y004", "0000001/0000100", "M", "원",
        "월평균 원/미국달러 매매기준율",
        "전월 대비", "원",
    ),
    "소비자물가 상승률": IndicatorSpec(
        "901Y009", "0", "M", "%",
        "소비자물가지수 총지수의 전년동월비",
        "전월 대비", "%p",
        transform=_year_over_year,
    ),
    "국고채 3년": IndicatorSpec(
        "721Y001", "5020000", "M", "%",
        "국고채 3년 월평균 유통수익률",
        "전월 대비", "%p",
    ),
    "국고채 10년": IndicatorSpec(
        "721Y001", "5050000", "M", "%",
        "국고채 10년 월평균 유통수익률",
        "전월 대비", "%p",
    ),
    "GDP 성장률": IndicatorSpec(
        "902Y015", "KOR", "Q", "%",
        "한국의 실질 GDP 전기비 성장률",
        "전분기 대비", "%p",
    ),
    "M2": IndicatorSpec(
        "161Y005", "BBHS00", "M", "조원",
        "광의통화 M2 평잔·계절조정계열",
        "전월 대비", "조원",
        decimals=1,
        transform=_m2_to_trillion_won,
    ),
    "생산자물가 상승률": IndicatorSpec(
        "404Y014", "*AA", "M", "%",
        "생산자물가지수 총지수의 전년동월비",
        "전월 대비", "%p",
        transform=_year_over_year,
    ),
    "실업률": IndicatorSpec(
        "901Y027", "I61BC/I28B", "M", "%",
        "통계청 경제활동인구조사 계절조정 실업률",
        "전월 대비", "%p",
    ),
}

CORE_INDICATORS = (
    "기준금리",
    "원/달러 환율",
    "소비자물가 상승률",
    "국고채 3년",
    "국고채 10년",
    "GDP 성장률",
)

SUPPLEMENTARY_INDICATORS = (
    "M2",
    "생산자물가 상승률",
    "실업률",
)

ECOS_MARKET_INDICES = {
    "코스피": ("802Y001", "0001000"),
    "코스닥": ("802Y001", "0089000"),
}

EXCHANGE_CURRENCIES = {
    "원/달러": {
        "chart_type": "candlestick",
        "stat_code": "731Y003",
        "items": {
            "시가": "0000002",
            "고가": "0000005",
            "저가": "0000004",
            "종가": "0000003",
        },
        "description": "원/달러 일별 시가·고가·저가·15:30 종가",
    },
    "원/위안": {
        "chart_type": "candlestick",
        "stat_code": "731Y003",
        "items": {
            "시가": "0000007",
            "고가": "0000008",
            "저가": "0000009",
            "종가": "0000010",
        },
        "description": "원/위안 일별 시가·고가·저가·종가",
    },
    "원/100엔": {
        "chart_type": "line",
        "stat_code": "731Y001",
        "items": {"환율": "0000002"},
        "description": "원/일본엔(100엔) 일별 매매기준율",
    },
    "원/유로": {
        "chart_type": "line",
        "stat_code": "731Y001",
        "items": {"환율": "0000003"},
        "description": "원/유로 일별 환율",
    },
}


def _get_api_key(api_key: str | None = None) -> str:
    key = api_key or os.getenv("ECOS_API_KEY")
    if not key:
        raise ValueError("ECOS_API_KEY가 설정되지 않았습니다.")
    return key


def _validate_month(value: str, field_name: str) -> None:
    if not MONTH_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name}은 YYYYMM 형식이어야 합니다.")
    try:
        pd.to_datetime(value, format="%Y%m")
    except ValueError as error:
        raise ValueError(f"{field_name}에 올바른 월을 입력해 주세요.") from error


def _api_period(month: str, cycle: str, *, is_end: bool) -> str:
    if cycle == "Q":
        quarter = (int(month[4:]) - 1) // 3 + 1
        return f"{month[:4]}Q{quarter}"
    if cycle == "D":
        timestamp = pd.to_datetime(month, format="%Y%m")
        if is_end:
            timestamp += pd.offsets.MonthEnd(0)
        return timestamp.strftime("%Y%m%d")
    return month


def _parse_time(value: str, cycle: str) -> pd.Timestamp:
    if cycle == "Q":
        match = re.fullmatch(r"(\d{4})Q([1-4])", value)
        if not match:
            return pd.NaT
        year, quarter = map(int, match.groups())
        return pd.Timestamp(year=year, month=quarter * 3, day=1)

    time_format = "%Y%m%d" if cycle == "D" else "%Y%m"
    return pd.to_datetime(value, format=time_format, errors="coerce")


def _row_limit(cycle: str, start_period: str, end_period: str) -> int:
    """조회 주기와 기간에 맞는 최소 행 한도를 계산한다."""
    if cycle != "D":
        return 1_000
    start = pd.to_datetime(start_period, format="%Y%m%d")
    end = pd.to_datetime(end_period, format="%Y%m%d")
    return min(max((end - start).days + 10, 100), 10_000)


def _build_ecos_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _request_ecos_json(
    client: requests.Session,
    url: str,
) -> dict:
    """인증키가 포함된 요청 URL을 노출하지 않고 ECOS를 호출한다."""
    try:
        response = client.get(url, timeout=(10, 30))
        response.raise_for_status()
        return response.json()
    except requests.Timeout as error:
        raise RuntimeError(
            "ECOS 서버 응답 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요."
        ) from error
    except requests.RequestException as error:
        raise RuntimeError(
            "ECOS 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요."
        ) from error
    except ValueError as error:
        raise RuntimeError("ECOS API 응답을 해석하지 못했습니다.") from error


def _get_statistic_rows(
    *,
    stat_code: str,
    cycle: str,
    start_period: str,
    end_period: str,
    item_code: str,
    api_key: str | None = None,
    limit: int | None = None,
    session: requests.Session | None = None,
) -> list[dict]:
    row_limit = limit or _row_limit(cycle, start_period, end_period)
    url = (
        f"{ECOS_API_URL}/{_get_api_key(api_key)}/json/kr/1/{row_limit}/"
        f"{stat_code}/{cycle}/{start_period}/{end_period}/{item_code}"
    )
    owns_session = session is None
    client = session or _build_ecos_session()
    try:
        result = _request_ecos_json(client, url)
    finally:
        if owns_session:
            client.close()

    if "StatisticSearch" not in result:
        message = result.get("RESULT", {}).get(
            "MESSAGE",
            "ECOS API 응답 형식을 확인할 수 없습니다.",
        )
        raise RuntimeError(message)
    return result["StatisticSearch"].get("row", [])


def get_exchange_chart_data(
    currency: str,
    start_date: str,
    end_date: str,
    *,
    api_key: str | None = None,
) -> tuple[str, pd.DataFrame, str]:
    """통화별 일별 환율 차트 데이터를 반환한다.

    ECOS가 OHLC를 제공하는 달러·위안은 candlestick, 엔·유로는 line이다.
    """
    if currency not in EXCHANGE_CURRENCIES:
        raise ValueError(f"지원하지 않는 환율입니다: {currency}")

    _validate_month(start_date, "조회 시작 월")
    _validate_month(end_date, "조회 종료 월")
    if start_date > end_date:
        raise ValueError("조회 시작 월은 종료 월보다 늦을 수 없습니다.")

    start_timestamp = pd.to_datetime(start_date, format="%Y%m")
    end_timestamp = (
        pd.to_datetime(end_date, format="%Y%m") + pd.offsets.MonthEnd(0)
    )
    config = EXCHANGE_CURRENCIES[currency]
    series_frames: list[pd.DataFrame] = []

    for column_name, item_code in config["items"].items():
        rows = _get_statistic_rows(
            stat_code=config["stat_code"],
            cycle="D",
            start_period=start_timestamp.strftime("%Y%m%d"),
            end_period=end_timestamp.strftime("%Y%m%d"),
            item_code=item_code,
            api_key=api_key,
        )
        if not rows:
            continue

        frame = pd.DataFrame(rows)[["TIME", "DATA_VALUE"]].rename(
            columns={"TIME": "날짜", "DATA_VALUE": column_name}
        )
        frame["날짜"] = pd.to_datetime(
            frame["날짜"],
            format="%Y%m%d",
            errors="coerce",
        )
        frame[column_name] = pd.to_numeric(
            frame[column_name],
            errors="coerce",
        )
        series_frames.append(frame.dropna())

    if not series_frames:
        return (
            config["chart_type"],
            pd.DataFrame(columns=["날짜", *config["items"]]),
            config["description"],
        )

    result = series_frames[0]
    for frame in series_frames[1:]:
        result = result.merge(frame, on="날짜", how="inner")

    return (
        config["chart_type"],
        result.sort_values("날짜").reset_index(drop=True),
        config["description"],
    )


def get_ecos_market_index(
    name: str,
    start_date: str,
    end_date: str,
    *,
    api_key: str | None = None,
) -> pd.DataFrame:
    """ECOS의 코스피·코스닥 일별 지수를 반환한다."""
    if name not in ECOS_MARKET_INDICES:
        raise ValueError(f"지원하지 않는 시장지수입니다: {name}")

    _validate_month(start_date, "조회 시작 월")
    _validate_month(end_date, "조회 종료 월")
    if start_date > end_date:
        raise ValueError("조회 시작 월은 종료 월보다 늦을 수 없습니다.")

    stat_code, item_code = ECOS_MARKET_INDICES[name]
    rows = _get_statistic_rows(
        stat_code=stat_code,
        cycle="D",
        start_period=_api_period(start_date, "D", is_end=False),
        end_period=_api_period(end_date, "D", is_end=True),
        item_code=item_code,
        api_key=api_key,
    )
    if not rows:
        return pd.DataFrame(columns=["날짜", "값"])

    frame = pd.DataFrame(rows)[["TIME", "DATA_VALUE"]].rename(
        columns={"TIME": "날짜", "DATA_VALUE": "값"}
    )
    frame["날짜"] = pd.to_datetime(
        frame["날짜"], format="%Y%m%d", errors="coerce"
    )
    frame["값"] = pd.to_numeric(frame["값"], errors="coerce")
    return frame.dropna().sort_values("날짜").reset_index(drop=True)


def get_indicator(
    name: str,
    start_date: str = "202001",
    end_date: str = "202612",
    *,
    api_key: str | None = None,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """하나의 ECOS 지표를 날짜·값 형태로 반환한다."""
    if name not in INDICATORS:
        raise ValueError(f"지원하지 않는 ECOS 지표입니다: {name}")

    _validate_month(start_date, "조회 시작 월")
    _validate_month(end_date, "조회 종료 월")
    if start_date > end_date:
        raise ValueError("조회 시작 월은 종료 월보다 늦을 수 없습니다.")

    spec = INDICATORS[name]
    request_start = start_date
    if spec.transform is _year_over_year:
        request_start = (
            pd.to_datetime(start_date, format="%Y%m") - pd.DateOffset(months=12)
        ).strftime("%Y%m")

    start_period = _api_period(
        request_start,
        spec.cycle,
        is_end=False,
    )
    end_period = _api_period(end_date, spec.cycle, is_end=True)

    rows = _get_statistic_rows(
        stat_code=spec.stat_code,
        cycle=spec.cycle,
        start_period=start_period,
        end_period=end_period,
        item_code=spec.item_code,
        api_key=api_key,
        session=session,
    )
    if not rows:
        return pd.DataFrame(columns=["날짜", "값"])

    frame = pd.DataFrame(rows)[["TIME", "DATA_VALUE"]].rename(
        columns={"TIME": "날짜", "DATA_VALUE": "값"}
    )
    frame["날짜"] = frame["날짜"].map(
        lambda value: _parse_time(str(value), spec.cycle)
    )
    frame["값"] = pd.to_numeric(frame["값"], errors="coerce")
    frame = frame.dropna().sort_values("날짜").reset_index(drop=True)

    if spec.transform:
        frame = spec.transform(frame)

    start_timestamp = pd.to_datetime(start_date, format="%Y%m")
    return frame[frame["날짜"] >= start_timestamp].reset_index(drop=True)


def get_macro_indicators(
    start_date: str,
    end_date: str,
    names: tuple[str, ...] = CORE_INDICATORS,
    *,
    api_key: str | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """여러 지표를 조회하며 개별 지표 오류를 분리해 반환한다."""
    data: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}

    with _build_ecos_session() as session:
        for name in names:
            try:
                data[name] = get_indicator(
                    name,
                    start_date,
                    end_date,
                    api_key=api_key,
                    session=session,
                )
            except Exception as error:
                errors[name] = str(error)

    return data, errors


def get_base_rate(
    start_date: str = "202001",
    end_date: str = "202612",
    *,
    api_key: str | None = None,
) -> pd.DataFrame:
    """기존 호출부와 호환되는 기준금리 조회 함수."""
    frame = get_indicator(
        "기준금리",
        start_date,
        end_date,
        api_key=api_key,
    )
    return frame.rename(columns={"값": "기준금리"})
