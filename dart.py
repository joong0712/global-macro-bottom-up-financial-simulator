"""Open DART 재무제표 조회와 데이터 가공 기능."""

import os
import re
from collections.abc import Iterable

import OpenDartReader
import pandas as pd
from dotenv import load_dotenv


load_dotenv()

REPORT_CODES = {
    "1분기보고서": {"code": "11013", "quarter": "1Q"},
    "반기보고서": {"code": "11012", "quarter": "2Q"},
    "3분기보고서": {"code": "11014", "quarter": "3Q"},
    "사업보고서": {"code": "11011", "quarter": "4Q"},
}

COLUMN_MAPPING = {
    "rcept_no": "접수번호",
    "reprt_code": "보고서코드",
    "bsns_year": "사업연도",
    "corp_code": "기업코드",
    "sj_div": "재무제표코드",
    "sj_nm": "재무제표",
    "account_id": "계정ID",
    "account_nm": "계정명",
    "account_detail": "계정상세",
    "thstrm_nm": "당기명",
    "thstrm_amount": "당기금액",
    "thstrm_add_amount": "당기누적금액",
    "frmtrm_nm": "전기명",
    "frmtrm_amount": "전기금액",
    "frmtrm_q_nm": "전기분기명",
    "frmtrm_q_amount": "전기분기금액",
    "frmtrm_add_amount": "전기누적금액",
    "bfefrmtrm_nm": "전전기명",
    "bfefrmtrm_amount": "전전기금액",
    "ord": "표시순서",
    "currency": "통화",
    "조회연도": "조회연도",
    "분기": "분기",
    "기간": "기간",
}

COMPANY_INDICATORS = ("매출액", "영업이익", "당기순이익")

COMPANY_ACCOUNT_IDS = {
    "매출액": ("ifrs-full_Revenue",),
    "영업이익": (
        "dart_OperatingIncomeLoss",
        "ifrs-full_OperatingIncomeLoss",
    ),
    "당기순이익": ("ifrs-full_ProfitLoss",),
}

COMPANY_ACCOUNT_NAMES = {
    "매출액": ("매출액", "영업수익", "수익(매출액)"),
    "영업이익": ("영업이익", "영업이익(손실)", "영업손익"),
    "당기순이익": (
        "당기순이익",
        "당기순이익(손실)",
        "분기순이익",
        "분기순이익(손실)",
        "반기순이익",
        "반기순이익(손실)",
    ),
}

AMOUNT_UNITS = {
    "원": 1,
    "백만원": 1_000_000,
    "억원": 100_000_000,
    "조원": 1_000_000_000_000,
}


KEY_FINANCIAL_ACCOUNT_SPECS = {
    "손익계산서": (
        {
            "label": "수익(매출액)",
            "components": (
                {
                    "ids": (
                        "ifrs-full_Revenue",
                        "ifrs-full_RevenueFromContractsWithCustomers",
                        "dart_OperatingRevenue",
                    ),
                    "names": ("수익(매출액)", "매출액", "영업수익", "수익"),
                },
            ),
        },
        {
            "label": "매출원가",
            "components": (
                {
                    "ids": ("ifrs-full_CostOfSales",),
                    "names": ("매출원가", "영업비용"),
                },
            ),
        },
        {
            "label": "판매비와관리비",
            "components": (
                {
                    "ids": (
                        "dart_TotalSellingGeneralAdministrativeExpenses",
                    ),
                    "names": (
                        "판매비와관리비",
                        "판매비 및 관리비",
                        "판매관리비",
                        "판관비",
                    ),
                },
            ),
        },
        {
            "label": "영업이익",
            "components": (
                {
                    "ids": (
                        "dart_OperatingIncomeLoss",
                        "ifrs-full_OperatingIncomeLoss",
                        "ifrs-full_ProfitLossFromOperatingActivities",
                    ),
                    "names": ("영업이익", "영업이익(손실)", "영업손익"),
                },
            ),
        },
        {
            "label": "법인세비용",
            "components": (
                {
                    "ids": (
                        "ifrs-full_IncomeTaxExpenseContinuingOperations",
                        "ifrs-full_IncomeTaxExpense",
                    ),
                    "names": (
                        "법인세비용",
                        "법인세비용(수익)",
                        "법인세비용(효익)",
                    ),
                },
            ),
        },
        {
            "label": "지배기업 소유주지분 순이익",
            "components": (
                {
                    "ids": (
                        "ifrs-full_ProfitLossAttributableToOwnersOfParent",
                    ),
                    "names": (
                        "지배기업 소유주지분 순이익",
                        "지배기업 소유주에게 귀속되는 당기순이익",
                        "지배기업의 소유주에게 귀속되는 당기순이익",
                        "지배기업 소유지분",
                        "지배기업 소유주지분",
                    ),
                },
            ),
        },
    ),
    "재무상태표": (
        {
            "label": "매출채권",
            "components": (
                {
                    "ids": (
                        "ifrs-full_CurrentTradeReceivables",
                        "ifrs-full_TradeAndOtherCurrentReceivables",
                        "dart_ShortTermTradeReceivable",
                    ),
                    "names": ("매출채권", "매출채권 및 기타채권"),
                },
            ),
        },
        {
            "label": "재고자산",
            "components": (
                {
                    "ids": ("ifrs-full_Inventories",),
                    "names": ("재고자산",),
                },
            ),
        },
        {
            "label": "매입채무",
            "components": (
                {
                    "ids": (
                        "ifrs-full_TradeAndOtherCurrentPayablesToTradeSuppliers",
                        "ifrs-full_TradeAndOtherCurrentPayables",
                        "dart_ShortTermTradePayables",
                    ),
                    "names": ("매입채무", "매입채무 및 기타채무"),
                },
            ),
        },
        {
            "label": "유형자산",
            "components": (
                {
                    "ids": ("ifrs-full_PropertyPlantAndEquipment",),
                    "names": ("유형자산",),
                },
            ),
        },
        {
            "label": "현금및현금성자산",
            "components": (
                {
                    "ids": ("ifrs-full_CashAndCashEquivalents",),
                    "names": ("현금및현금성자산",),
                },
            ),
        },
        {
            "label": "단기금융상품",
            "components": (
                {
                    "ids": (
                        "ifrs-full_ShorttermDepositsNotClassifiedAsCashEquivalents",
                        "dart_ShortTermFinancialInstruments",
                    ),
                    "names": ("단기금융상품",),
                },
            ),
        },
        {
            "label": "단기차입금 + 장기차입금 + 사채",
            "components": (
                {
                    "ids": (
                        "ifrs-full_CurrentBorrowings",
                        "ifrs-full_ShorttermBorrowings",
                        "dart_ShortTermBorrowings",
                    ),
                    "names": ("단기차입금",),
                },
                {
                    "ids": (
                        "ifrs-full_NoncurrentPortionOfNoncurrentLoansReceived",
                        "ifrs-full_LongtermBorrowings",
                        "dart_LongTermBorrowingsGross",
                    ),
                    "names": ("장기차입금",),
                },
                {
                    "ids": (
                        "ifrs-full_NoncurrentPortionOfNoncurrentBondsIssued",
                        "ifrs-full_BondsIssued",
                        "dart_BondsIssued",
                    ),
                    "names": ("사채",),
                },
            ),
        },
        {
            "label": "지배기업 소유주지분",
            "components": (
                {
                    "ids": (
                        "ifrs-full_EquityAttributableToOwnersOfParent",
                    ),
                    "names": (
                        "지배기업 소유주지분",
                        "지배기업의 소유주에게 귀속되는 자본",
                        "지배기업 소유지분",
                    ),
                },
            ),
        },
    ),
    "현금흐름표": (
        {
            "label": "영업활동 현금흐름",
            "components": (
                {
                    "ids": (
                        "ifrs-full_CashFlowsFromUsedInOperatingActivities",
                    ),
                    "names": (
                        "영업활동 현금흐름",
                        "영업활동현금흐름",
                        "영업활동으로 인한 현금흐름",
                    ),
                },
            ),
        },
        {
            "label": "감가상각비 (D&A)",
            "prefer_total": True,
            "components": (
                {
                    "ids": (
                        "ifrs-full_DepreciationAndAmortisationExpense",
                        "dart_AdjustmentsForDepreciationAndAmortisationExpense",
                    ),
                    "names": (
                        "감가상각비 및 무형자산상각비",
                        "감가상각비와 무형자산상각비",
                        "감가상각비 및 상각비",
                    ),
                },
                {
                    "ids": (
                        "ifrs-full_DepreciationExpense",
                        "dart_AdjustmentsForDepreciationExpense",
                    ),
                    "names": (
                        "감가상각비",
                        "유형자산 감가상각비",
                        "감가상각비(유형자산)",
                    ),
                },
                {
                    "ids": (
                        "ifrs-full_AmortisationExpense",
                        "dart_AdjustmentsForAmortizationExpense",
                    ),
                    "names": ("무형자산상각비", "무형자산 상각비"),
                },
            ),
        },
        {
            "label": "유형자산의 취득 (CapEx)",
            "components": (
                {
                    "ids": (
                        "ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                        "ifrs-full_PurchaseOfPropertyPlantAndEquipment",
                    ),
                    "names": ("유형자산의 취득", "유형자산 취득"),
                },
            ),
        },
        {
            "label": "배당금 지급",
            "components": (
                {
                    "ids": (
                        "ifrs-full_DividendsPaidClassifiedAsFinancingActivities",
                        "ifrs-full_DividendsPaid",
                    ),
                    "names": ("배당금 지급", "배당금의 지급", "배당금지급"),
                },
            ),
        },
        {
            "label": "기말 현금및현금성자산",
            "components": (
                {
                    "ids": (
                        "dart_CashAndCashEquivalentsAtEndOfPeriodCf",
                        "ifrs-full_CashAndCashEquivalentsCashFlowStatement",
                    ),
                    "names": (
                        "기말 현금및현금성자산",
                        "기말현금및현금성자산",
                        "기말의 현금및현금성자산",
                    ),
                },
            ),
        },
    ),
}


def get_dart_client(api_key: str | None = None):
    """환경변수 또는 인자로 받은 키를 사용해 DART 클라이언트를 만든다."""
    key = api_key or os.getenv("DART_API_KEY")
    if not key:
        raise ValueError("DART_API_KEY가 설정되지 않았습니다.")
    return OpenDartReader(key)


def get_report_items(report_name: str) -> Iterable[tuple[str, dict[str, str]]]:
    if report_name == "전체 조회":
        return REPORT_CODES.items()
    if report_name not in REPORT_CODES:
        raise ValueError(f"지원하지 않는 보고서 종류입니다: {report_name}")
    return [(report_name, REPORT_CODES[report_name])]


def get_stock_code(
    company: str,
    *,
    api_key: str | None = None,
) -> str | None:
    """DART 기업명에 대응하는 6자리 상장 종목코드를 반환한다."""
    company = company.strip()
    if not company:
        return None

    corp_codes = get_dart_client(api_key).corp_codes
    matches = corp_codes[
        corp_codes["corp_name"].astype(str).str.strip().eq(company)
    ]
    if matches.empty and company.isdigit():
        matches = corp_codes[
            corp_codes["stock_code"].astype(str).str.zfill(6).eq(
                company.zfill(6)
            )
        ]
    if matches.empty:
        return None

    stock_code = str(matches.iloc[0]["stock_code"]).strip()
    if not stock_code or stock_code.lower() == "nan":
        return None
    return stock_code.zfill(6)


def fetch_financial_statements(
    company: str,
    start_year: int,
    end_year: int,
    report_name: str,
    *,
    api_key: str | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """기간별 연결재무제표를 조회한다.

    일부 연도/분기 조회가 실패해도 나머지 결과를 반환하며, 실패 내용은
    두 번째 반환값에 담는다.
    """
    company = company.strip()
    if not company:
        raise ValueError("기업명을 입력해 주세요.")
    if start_year > end_year:
        raise ValueError("시작 연도는 종료 연도보다 클 수 없습니다.")

    client = get_dart_client(api_key)
    results: list[pd.DataFrame] = []
    warnings: list[str] = []

    for year in range(start_year, end_year + 1):
        for current_report_name, report_info in get_report_items(report_name):
            try:
                frame = client.finstate_all(
                    company,
                    year,
                    report_info["code"],
                    fs_div="CFS",
                )
                if frame is not None and not frame.empty:
                    frame = frame.copy()
                    frame["조회연도"] = year
                    frame["분기"] = report_info["quarter"]
                    frame["기간"] = f"{str(year)[-2:]}/{report_info['quarter']}"
                    results.append(frame)
            except Exception as error:
                warnings.append(
                    f"{year}년 {current_report_name} 자료를 불러오지 못했습니다: {error}"
                )

    if not results:
        return pd.DataFrame(), warnings

    financial_df = pd.concat(results, ignore_index=True)
    return financial_df.rename(columns=COLUMN_MAPPING), warnings


def parse_amounts(series: pd.Series) -> pd.Series:
    """DART 금액 문자열을 부호를 보존한 숫자로 변환한다."""
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .replace({"-": None, "": None, "nan": None, "None": None})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def make_pivot_table(
    df: pd.DataFrame,
    amount_unit: str = "억원",
) -> pd.DataFrame:
    if df.empty:
        return df
    if amount_unit not in AMOUNT_UNITS:
        raise ValueError(f"지원하지 않는 금액 단위입니다: {amount_unit}")

    pivot_source = df.copy()
    pivot_source["표시금액"] = (
        parse_amounts(pivot_source["당기금액"])
        / AMOUNT_UNITS[amount_unit]
    )

    return (
        pivot_source.pivot_table(
            index=["재무제표", "계정명"],
            columns="기간",
            values="표시금액",
            aggfunc="first",
        )
        .reset_index()
    )


def _normalize_account_text(value: object) -> str:
    """계정명 비교를 위해 공백과 구두점을 제거한다."""
    text = "" if value is None or pd.isna(value) else str(value)
    return re.sub(
        r"[^0-9A-Za-z가-힣]",
        "",
        text,
    ).lower()


def _period_sort_key(period: object) -> tuple[int, int, str]:
    text = str(period)
    matched = re.fullmatch(r"(\d{2,4})/([1-4])Q", text)
    if not matched:
        return (9999, 9, text)
    year = int(matched.group(1))
    if year < 100:
        year += 2000
    return (year, int(matched.group(2)), text)


def _extract_key_component(
    statement_df: pd.DataFrame,
    component: dict[str, tuple[str, ...]],
) -> pd.Series:
    """한 표준 계정 후보에서 기간별 최우선 공시값을 선택한다."""
    if statement_df.empty:
        return pd.Series(dtype="float64")

    source = statement_df.copy()
    source["_계정ID"] = source["계정ID"].astype(str).str.lower()
    source["_계정명"] = source["계정명"].map(_normalize_account_text)
    source["_금액"] = parse_amounts(source["당기금액"])
    source["_우선순위"] = 10_000

    matched = pd.Series(False, index=source.index)
    for priority, account_id in enumerate(component.get("ids", ())):
        current = source["_계정ID"].eq(account_id.lower())
        source.loc[current, "_우선순위"] = priority
        matched |= current

    name_offset = 1_000
    for priority, account_name in enumerate(component.get("names", ())):
        current = source["_계정명"].eq(
            _normalize_account_text(account_name)
        )
        update = current & source["_우선순위"].eq(10_000)
        source.loc[update, "_우선순위"] = name_offset + priority
        matched |= current

    matched_source = source.loc[matched].dropna(subset=["_금액"])
    if matched_source.empty:
        return pd.Series(dtype="float64")

    if "표시순서" in matched_source:
        matched_source["_표시순서"] = pd.to_numeric(
            matched_source["표시순서"], errors="coerce"
        ).fillna(999_999)
    else:
        matched_source["_표시순서"] = 999_999

    return (
        matched_source.sort_values(
            ["기간", "_우선순위", "_표시순서"]
        )
        .drop_duplicates("기간", keep="first")
        .set_index("기간")["_금액"]
        .astype(float)
    )


def make_key_financial_statement_tables(
    df: pd.DataFrame,
    amount_unit: str = "억원",
) -> dict[str, pd.DataFrame]:
    """가치평가에 필요한 19개 핵심 계정만 3대 재무제표로 반환한다.

    기업마다 다른 계정명은 표준 계정 ID와 별칭으로 맞춘다. Gross Debt는
    단기차입금·장기차입금·사채를 합산하며, D&A는 합계 계정을 우선 사용하고
    합계가 없을 때 감가상각비와 무형자산상각비를 더한다. 원문에 없는 계정도
    행은 유지하고 값은 결측치로 남겨 임의 대체를 방지한다.
    """
    if amount_unit not in AMOUNT_UNITS:
        raise ValueError(f"지원하지 않는 금액 단위입니다: {amount_unit}")

    empty_result = {
        statement_name: pd.DataFrame(
            columns=["재무제표", "계정명"]
        )
        for statement_name in KEY_FINANCIAL_ACCOUNT_SPECS
    }
    if df.empty:
        return empty_result

    periods = sorted(
        df["기간"].dropna().astype(str).unique(),
        key=_period_sort_key,
    )
    statement_names = {
        "손익계산서": ("손익계산서", "포괄손익계산서"),
        "재무상태표": ("재무상태표",),
        "현금흐름표": ("현금흐름표",),
    }
    tables: dict[str, pd.DataFrame] = {}

    for statement_name, account_specs in KEY_FINANCIAL_ACCOUNT_SPECS.items():
        statement_df = df[
            df["재무제표"].isin(statement_names[statement_name])
        ]
        rows: list[dict[str, object]] = []

        for account_spec in account_specs:
            components = [
                _extract_key_component(statement_df, component)
                for component in account_spec["components"]
            ]
            if account_spec.get("prefer_total"):
                total = components[0]
                parts = (
                    pd.concat(components[1:], axis=1).sum(
                        axis=1, min_count=1
                    )
                    if len(components) > 1
                    else pd.Series(dtype="float64")
                )
                values = total.combine_first(parts)
            elif len(components) == 1:
                values = components[0]
            else:
                values = pd.concat(components, axis=1).sum(
                    axis=1,
                    min_count=1,
                )

            row: dict[str, object] = {
                "재무제표": statement_name,
                "계정명": account_spec["label"],
            }
            for period in periods:
                value = values.get(period, pd.NA)
                row[period] = (
                    float(value) / AMOUNT_UNITS[amount_unit]
                    if pd.notna(value)
                    else pd.NA
                )
            rows.append(row)

        tables[statement_name] = pd.DataFrame(
            rows,
            columns=["재무제표", "계정명", *periods],
        )

    return tables


def split_financial_statements(
    df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """조회 결과를 3대 재무제표로 나눈다."""
    if df.empty:
        return {
            "재무상태표": df.copy(),
            "손익계산서": df.copy(),
            "현금흐름표": df.copy(),
        }

    return {
        "재무상태표": df[df["재무제표"] == "재무상태표"],
        "손익계산서": df[
            df["재무제표"].isin(["손익계산서", "포괄손익계산서"])
        ],
        "현금흐름표": df[df["재무제표"] == "현금흐름표"],
    }


def extract_company_indicator(
    financial_df: pd.DataFrame,
    indicator_name: str,
    frequency: str = "연간",
    preferred_account_name: str | None = None,
) -> pd.DataFrame:
    """주요 손익 지표를 연간 또는 단일 분기 억원 단위로 추출한다."""
    if indicator_name not in COMPANY_INDICATORS:
        raise ValueError(f"지원하지 않는 기업 지표입니다: {indicator_name}")
    if frequency not in ("연간", "분기"):
        raise ValueError("기업 데이터 주기는 연간 또는 분기여야 합니다.")
    if financial_df.empty:
        return pd.DataFrame(columns=["연도", "기간", "값"])

    income_statements = financial_df[
        financial_df["재무제표"].isin(["손익계산서", "포괄손익계산서"])
    ].copy()
    preferred_account_name = (preferred_account_name or "").strip()
    if preferred_account_name:
        matched = income_statements[
            income_statements["계정명"] == preferred_account_name
        ].copy()
    else:
        account_ids = COMPANY_ACCOUNT_IDS[indicator_name]
        matched = income_statements[
            income_statements["계정ID"].isin(account_ids)
        ].copy()

    # 기업별 사용자 정의 계정 때문에 표준 ID가 없을 때 계정명으로 보완한다.
    if matched.empty and not preferred_account_name:
        matched = income_statements[
            income_statements["계정명"].isin(
                COMPANY_ACCOUNT_NAMES[indicator_name]
            )
        ].copy()
    if matched.empty:
        return pd.DataFrame(columns=["연도", "기간", "값"])

    matched["재무제표순서"] = matched["재무제표"].map(
        {"손익계산서": 0, "포괄손익계산서": 1}
    )
    matched["값"] = parse_amounts(matched["당기금액"]) / 100_000_000
    if "당기누적금액" in matched.columns:
        matched["누적값"] = (
            parse_amounts(matched["당기누적금액"]) / 100_000_000
        )
    else:
        matched["누적값"] = pd.NA
    matched = (
        matched.dropna(subset=["값"])
        .sort_values(["조회연도", "분기", "재무제표순서"])
        .drop_duplicates(["조회연도", "분기"], keep="first")
    )

    if frequency == "연간":
        annual = matched[matched["분기"] == "4Q"].copy()
        annual["기간"] = annual["조회연도"].astype(str)
        return (
            annual[["조회연도", "기간", "값"]]
            .rename(columns={"조회연도": "연도"})
            .sort_values("연도")
            .reset_index(drop=True)
        )

    quarterly_rows: list[dict[str, object]] = []
    for year, year_data in matched.groupby("조회연도"):
        values = {
            row["분기"]: float(row["값"])
            for _, row in year_data.iterrows()
        }
        for quarter in ("1Q", "2Q", "3Q"):
            if quarter in values:
                quarterly_rows.append(
                    {
                        "연도": int(year),
                        "분기": quarter,
                        "기간": f"{year} Q{quarter[0]}",
                        "값": values[quarter],
                    }
                )

        # 사업보고서 당기금액은 연간 누적이므로 앞선 단일 분기를 차감한다.
        if "4Q" in values:
            earlier_values = [
                values[quarter]
                for quarter in ("1Q", "2Q", "3Q")
                if quarter in values
            ]
            fourth_quarter = values["4Q"] - sum(earlier_values)
            quarterly_rows.append(
                {
                    "연도": int(year),
                    "분기": "4Q",
                    "기간": f"{year} Q4",
                    "값": fourth_quarter,
                }
            )

    return pd.DataFrame(
        quarterly_rows,
        columns=["연도", "분기", "기간", "값"],
    )


def get_company_indicator(
    company: str,
    start_year: int,
    end_year: int,
    indicator_name: str,
    frequency: str = "연간",
    preferred_account_name: str | None = None,
    *,
    api_key: str | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """기업 주요 손익 지표를 요청 주기 기준으로 조회한다."""
    report_name = "사업보고서" if frequency == "연간" else "전체 조회"
    financial_df, warnings = fetch_financial_statements(
        company,
        start_year,
        end_year,
        report_name,
        api_key=api_key,
    )
    result = extract_company_indicator(
        financial_df,
        indicator_name,
        frequency,
        preferred_account_name,
    )
    if result.empty and not financial_df.empty:
        aliases = ", ".join(COMPANY_ACCOUNT_NAMES[indicator_name])
        if preferred_account_name:
            warnings.append(
                f"직접 지정한 계정명 '{preferred_account_name}'을 "
                "손익계산서에서 찾지 못했습니다."
            )
        else:
            warnings.append(
                f"{indicator_name}에 대응하는 표준 계정 ID 또는 계정명을 "
                f"찾지 못했습니다. 확인한 계정명 후보: {aliases}"
            )
    return result, warnings
