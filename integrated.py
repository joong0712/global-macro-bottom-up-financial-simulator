"""기업 지표와 한국·미국 매크로 지표의 비교 데이터 가공."""

import pandas as pd

from ecos import INDICATORS, get_indicator
from fred import FRED_INDICATORS, get_fred_indicator


MACRO_INDICATORS = {
    "원/달러 환율": ("ECOS", "원/달러 환율"),
    "한국 기준금리": ("ECOS", "기준금리"),
    "미국 기준금리": ("FRED", "연방기금금리"),
    "소비자물가": ("ECOS", "소비자물가 상승률"),
}


def get_macro_indicator(
    display_name: str,
    start_year: int,
    end_year: int,
) -> tuple[pd.DataFrame, object]:
    """통합 화면에서 선택한 매크로 계열과 표시 메타데이터를 반환한다."""
    if display_name not in MACRO_INDICATORS:
        raise ValueError(f"지원하지 않는 매크로 지표입니다: {display_name}")

    source, source_name = MACRO_INDICATORS[display_name]
    start_date = f"{start_year}01"
    end_date = f"{end_year}12"

    if source == "ECOS":
        return (
            get_indicator(source_name, start_date, end_date),
            INDICATORS[source_name],
        )
    return (
        get_fred_indicator(source_name, start_date, end_date),
        FRED_INDICATORS[source_name],
    )


def aggregate_macro_indicator(
    macro_data: pd.DataFrame,
    frequency: str,
) -> pd.DataFrame:
    """매크로 관측값을 연평균 또는 분기평균으로 통일한다."""
    if frequency not in ("연간", "분기"):
        raise ValueError("매크로 데이터 주기는 연간 또는 분기여야 합니다.")
    if macro_data.empty:
        return pd.DataFrame(columns=["기간", "값"])

    result = macro_data.copy()
    result["연도"] = result["날짜"].dt.year

    if frequency == "연간":
        return (
            result.groupby("연도", as_index=False)["값"]
            .mean()
            .assign(기간=lambda frame: frame["연도"].astype(str))
            [["연도", "기간", "값"]]
        )

    result["분기번호"] = result["날짜"].dt.quarter
    quarterly = (
        result.groupby(["연도", "분기번호"], as_index=False)["값"]
        .mean()
        .sort_values(["연도", "분기번호"])
    )
    quarterly["분기"] = quarterly["분기번호"].map(lambda value: f"{value}Q")
    quarterly["기간"] = (
        quarterly["연도"].astype(str)
        + " "
        + quarterly["분기번호"].map(lambda value: f"Q{value}")
    )
    return quarterly[["연도", "분기", "기간", "값"]].reset_index(drop=True)


def get_aggregation_description(
    display_name: str,
    frequency: str,
) -> str:
    period = "연평균" if frequency == "연간" else "분기평균"
    if display_name == "원/달러 환율":
        return f"ECOS 월평균 매매기준율을 {period}으로 집계"
    return f"원자료 관측값을 {period}으로 집계"


def normalize_comparison(
    company_data: pd.DataFrame,
    macro_data: pd.DataFrame,
    company_name: str,
    macro_name: str,
    frequency: str,
    method: str = "기준시점 100",
) -> tuple[pd.DataFrame, str | None]:
    """선택 방식으로 두 지표를 같은 주기와 척도로 변환한다."""
    if company_data.empty or macro_data.empty:
        return (
            pd.DataFrame(columns=["기간", company_name, macro_name]),
            None,
        )

    combined = company_data.merge(
        macro_data,
        on="기간",
        how="inner",
        suffixes=("_기업", "_매크로"),
    )
    if combined.empty:
        return (
            pd.DataFrame(columns=["기간", company_name, macro_name]),
            None,
        )

    if method == "z-score":
        def z_score(series: pd.Series) -> pd.Series:
            standard_deviation = series.std(ddof=0)
            if standard_deviation == 0 or pd.isna(standard_deviation):
                return pd.Series(0.0, index=series.index)
            return (series - series.mean()) / standard_deviation

        return (
            pd.DataFrame(
                {
                    "기간": combined["기간"],
                    company_name: z_score(combined["값_기업"]),
                    macro_name: z_score(combined["값_매크로"]),
                }
            ),
            f"{combined.iloc[0]['기간']}~{combined.iloc[-1]['기간']}",
        )

    if method == "기간별 증감률":
        changed = pd.DataFrame(
            {
                "기간": combined["기간"],
                company_name: combined["값_기업"].pct_change() * 100,
                macro_name: combined["값_매크로"].pct_change() * 100,
            }
        ).dropna().reset_index(drop=True)
        return changed, None

    if method != "기준시점 100":
        raise ValueError(f"지원하지 않는 정규화 방식입니다: {method}")

    base_period = str(combined.iloc[0]["기간"])
    company_base = float(combined.iloc[0]["값_기업"])
    macro_base = float(combined.iloc[0]["값_매크로"])
    if company_base == 0 or macro_base == 0:
        raise ValueError(
            f"정규화 기준 시점({base_period})의 값이 0입니다. "
            "z-score 또는 기간별 증감률을 선택해 주세요."
        )

    normalized = pd.DataFrame(
        {
            "기간": combined["기간"],
            company_name: combined["값_기업"] / company_base * 100,
            macro_name: combined["값_매크로"] / macro_base * 100,
        }
    )
    return normalized, base_period
