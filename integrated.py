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


def build_scenario_financial_defaults(
    statement_tables: dict[str, pd.DataFrame],
    exchange_rate: float,
    listed_shares: float | None,
) -> dict[str, object]:
    """핵심 재무제표에서 시나리오 계산용 읽기 전용 기준값을 만든다.

    외화 및 변동금리 세부 내역은 3대 재무제표에 없으므로 현금성자산·채권과
    매입채무·총차입금을 각각 환율 민감 자산·부채의 대용값으로 사용한다.
    """
    if exchange_rate <= 0:
        raise ValueError("기준 환율은 0보다 커야 합니다.")

    rows: list[pd.DataFrame] = []
    for table in statement_tables.values():
        if not table.empty:
            rows.append(table)
    if not rows:
        raise ValueError("시뮬레이션에 연결할 핵심 재무제표가 없습니다.")

    combined = pd.concat(rows, ignore_index=True)
    period_columns = [
        column
        for column in combined.columns
        if column not in ("재무제표", "계정명")
    ]
    if not period_columns:
        raise ValueError("시뮬레이션 기준 기간을 찾지 못했습니다.")
    latest_period = next(
        (
            period
            for period in reversed(period_columns)
            if pd.to_numeric(combined[period], errors="coerce").notna().any()
        ),
        None,
    )
    if latest_period is None:
        raise ValueError("최신 재무제표에 사용할 수 있는 금액이 없습니다.")

    def account_value(account_name: str) -> float | None:
        matched = combined.loc[combined["계정명"].eq(account_name), latest_period]
        if matched.empty:
            return None
        numeric = pd.to_numeric(matched, errors="coerce").dropna()
        return float(numeric.iloc[0]) if not numeric.empty else None

    values = {
        account: account_value(account)
        for account in (
            "현금및현금성자산",
            "단기금융상품",
            "매출채권",
            "매입채무",
            "단기차입금 + 장기차입금 + 사채",
            "법인세비용",
            "지배기업 소유주지분 순이익",
        )
    }
    asset_accounts = ("현금및현금성자산", "단기금융상품", "매출채권")
    liability_accounts = ("매입채무", "단기차입금 + 장기차입금 + 사채")
    fx_assets_proxy = sum(values[name] or 0.0 for name in asset_accounts)
    fx_liabilities_proxy = sum(values[name] or 0.0 for name in liability_accounts)
    gross_debt = values["단기차입금 + 장기차입금 + 사채"] or 0.0

    tax_expense = values["법인세비용"]
    owner_profit = values["지배기업 소유주지분 순이익"]
    effective_tax_rate: float | None = None
    if tax_expense is not None and owner_profit is not None:
        pretax_proxy = owner_profit + tax_expense
        if pretax_proxy > 0:
            effective_tax_rate = min(
                100.0,
                max(0.0, tax_expense / pretax_proxy * 100),
            )

    missing_accounts = [
        account for account, value in values.items() if value is None
    ]
    return {
        "period": latest_period,
        "account_values": values,
        "fx_assets_proxy_100m_krw": fx_assets_proxy,
        "fx_liabilities_proxy_100m_krw": fx_liabilities_proxy,
        "foreign_assets_million_usd": fx_assets_proxy * 100 / exchange_rate,
        "foreign_liabilities_million_usd": (
            fx_liabilities_proxy * 100 / exchange_rate
        ),
        "gross_debt_100m_krw": gross_debt,
        "gross_debt_million_usd": gross_debt * 100 / exchange_rate,
        "exchange_rate": float(exchange_rate),
        "effective_tax_rate": effective_tax_rate,
        "listed_shares": listed_shares,
        "shares_in_ten_thousands": (
            float(listed_shares) / 10_000
            if listed_shares is not None and listed_shares > 0
            else None
        ),
        "missing_accounts": missing_accounts,
    }


def build_financial_report_snapshot(
    statement_tables: dict[str, pd.DataFrame],
) -> dict[str, object]:
    """핵심 재무표에서 실무 보고서용 요약값과 원자료를 만든다."""
    available = [table for table in statement_tables.values() if not table.empty]
    if not available:
        return {"unit": "억원", "periods": [], "key_metrics": {}, "statements": {}}

    combined = pd.concat(available, ignore_index=True)
    periods = [
        column
        for column in combined.columns
        if column not in ("재무제표", "계정명")
    ]
    usable_periods = [
        period
        for period in periods
        if pd.to_numeric(combined[period], errors="coerce").notna().any()
    ]
    recent_periods = usable_periods[-3:]
    if not recent_periods:
        return {"unit": "억원", "periods": [], "key_metrics": {}, "statements": {}}

    def account_value(account_name: str, period: str) -> float | None:
        matched = combined.loc[combined["계정명"].eq(account_name), period]
        numeric = pd.to_numeric(matched, errors="coerce").dropna()
        return float(numeric.iloc[0]) if not numeric.empty else None

    latest = recent_periods[-1]
    previous = recent_periods[-2] if len(recent_periods) > 1 else None
    account_labels = {
        "revenue": "수익(매출액)",
        "operating_income": "영업이익",
        "net_income": "지배기업 소유주지분 순이익",
        "operating_cash_flow": "영업활동 현금흐름",
        "capex": "유형자산의 취득 (CapEx)",
        "cash": "현금및현금성자산",
        "short_term_financial_products": "단기금융상품",
        "gross_debt": "단기차입금 + 장기차입금 + 사채",
        "equity": "지배기업 소유주지분",
    }

    values = {
        key: account_value(label, latest)
        for key, label in account_labels.items()
    }
    previous_values = {
        key: account_value(label, previous) if previous else None
        for key, label in account_labels.items()
    }

    def ratio(numerator: float | None, denominator: float | None) -> float | None:
        if numerator is None or denominator in (None, 0):
            return None
        return round(numerator / denominator * 100, 4)

    def growth(current: float | None, prior: float | None) -> float | None:
        if current is None or prior in (None, 0):
            return None
        return round((current / prior - 1) * 100, 4)

    cash_total = (
        values["cash"] + values["short_term_financial_products"]
        if values["cash"] is not None
        and values["short_term_financial_products"] is not None
        else None
    )
    net_debt = (
        values["gross_debt"] - cash_total
        if values["gross_debt"] is not None and cash_total is not None
        else None
    )
    free_cash_flow = (
        values["operating_cash_flow"] - abs(values["capex"])
        if values["operating_cash_flow"] is not None
        and values["capex"] is not None
        else None
    )
    previous_cash_total = (
        previous_values["cash"]
        + previous_values["short_term_financial_products"]
        if previous_values["cash"] is not None
        and previous_values["short_term_financial_products"] is not None
        else None
    )
    previous_net_debt = (
        previous_values["gross_debt"] - previous_cash_total
        if previous_values["gross_debt"] is not None
        and previous_cash_total is not None
        else None
    )
    previous_free_cash_flow = (
        previous_values["operating_cash_flow"]
        - abs(previous_values["capex"])
        if previous_values["operating_cash_flow"] is not None
        and previous_values["capex"] is not None
        else None
    )
    key_metrics = {
        "latest_period": latest,
        "previous_period": previous,
        "revenue_100m_krw": values["revenue"],
        "previous_revenue_100m_krw": previous_values["revenue"],
        "revenue_growth_pct": growth(
            values["revenue"], previous_values["revenue"]
        ),
        "operating_income_100m_krw": values["operating_income"],
        "previous_operating_income_100m_krw": previous_values[
            "operating_income"
        ],
        "operating_income_growth_pct": growth(
            values["operating_income"], previous_values["operating_income"]
        ),
        "operating_margin_pct": ratio(
            values["operating_income"], values["revenue"]
        ),
        "previous_operating_margin_pct": ratio(
            previous_values["operating_income"], previous_values["revenue"]
        ),
        "controlling_net_income_100m_krw": values["net_income"],
        "previous_controlling_net_income_100m_krw": previous_values[
            "net_income"
        ],
        "net_margin_pct": ratio(values["net_income"], values["revenue"]),
        "previous_net_margin_pct": ratio(
            previous_values["net_income"], previous_values["revenue"]
        ),
        "operating_cash_flow_100m_krw": values["operating_cash_flow"],
        "previous_operating_cash_flow_100m_krw": previous_values[
            "operating_cash_flow"
        ],
        "capex_100m_krw": values["capex"],
        "previous_capex_100m_krw": previous_values["capex"],
        "simple_fcf_100m_krw": free_cash_flow,
        "previous_simple_fcf_100m_krw": previous_free_cash_flow,
        "gross_debt_100m_krw": values["gross_debt"],
        "previous_gross_debt_100m_krw": previous_values["gross_debt"],
        "cash_and_short_investments_100m_krw": cash_total,
        "previous_cash_and_short_investments_100m_krw": previous_cash_total,
        "net_debt_100m_krw": net_debt,
        "previous_net_debt_100m_krw": previous_net_debt,
        "controlling_equity_100m_krw": values["equity"],
        "previous_controlling_equity_100m_krw": previous_values["equity"],
    }

    statements: dict[str, list[dict[str, object]]] = {}
    for statement_name, table in statement_tables.items():
        rows: list[dict[str, object]] = []
        for _, source_row in table.iterrows():
            row: dict[str, object] = {"account": str(source_row["계정명"])}
            for period in recent_periods:
                value = source_row.get(period)
                row[period] = float(value) if pd.notna(value) else None
            rows.append(row)
        statements[statement_name] = rows

    return {
        "unit": "억원",
        "periods": recent_periods,
        "key_metrics": key_metrics,
        "statements": statements,
        "calculation_notes": {
            "simple_fcf": "영업활동 현금흐름 - 유형자산 취득액의 절댓값",
            "net_debt": "총차입금 - 현금및현금성자산 - 단기금융상품",
        },
    }


def calculate_scenario_effects(
    defaults: dict[str, object],
    exchange_change: float,
    korea_rate_change: float,
    usa_rate_change: float,
) -> dict[str, float | None]:
    """자동 연결 기준값과 매크로 충격으로 시나리오 영향을 계산한다."""
    foreign_assets = float(defaults["foreign_assets_million_usd"])
    foreign_liabilities = float(defaults["foreign_liabilities_million_usd"])
    gross_debt = float(defaults["gross_debt_100m_krw"])
    usd_debt = float(defaults["gross_debt_million_usd"])
    exchange_rate = float(defaults["exchange_rate"])

    foreign_exchange_effect = (
        (foreign_assets - foreign_liabilities) * exchange_change / 100
    )
    krw_interest_change = gross_debt * korea_rate_change / 100
    usd_debt_in_100m_krw = usd_debt * exchange_rate / 100
    usd_interest_change = usd_debt_in_100m_krw * usa_rate_change / 100
    interest_expense_change = krw_interest_change + usd_interest_change
    pretax_effect = foreign_exchange_effect - interest_expense_change

    tax_rate = defaults.get("effective_tax_rate")
    net_income_effect = (
        pretax_effect * (1 - float(tax_rate) / 100)
        if tax_rate is not None
        else None
    )
    shares = defaults.get("shares_in_ten_thousands")
    eps_effect = (
        net_income_effect * 10_000 / float(shares)
        if (
            net_income_effect is not None
            and shares is not None
            and float(shares) > 0
        )
        else None
    )
    return {
        "foreign_exchange_effect_100m_krw": foreign_exchange_effect,
        "interest_expense_change_100m_krw": interest_expense_change,
        "pretax_effect_100m_krw": pretax_effect,
        "net_income_effect_100m_krw": net_income_effect,
        "eps_effect_krw": eps_effect,
    }


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
