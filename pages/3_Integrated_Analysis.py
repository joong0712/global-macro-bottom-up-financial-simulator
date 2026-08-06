"""기업 주요 손익과 매크로 지표를 함께 보는 통합 분석 페이지."""

import os

import pandas as pd
import streamlit as st

from auth import record_user_history, require_login
from ai_report import (
    generate_ai_report,
    report_to_pdf,
    report_context_fingerprint,
)
from dart import (
    COMPANY_INDICATORS,
    fetch_financial_statements,
    get_company_indicator,
    get_stock_code,
    make_key_financial_statement_tables,
)
from integrated import (
    MACRO_INDICATORS,
    aggregate_macro_indicator,
    build_financial_report_snapshot,
    build_scenario_financial_defaults,
    calculate_scenario_effects,
    get_aggregation_description,
    get_macro_indicator,
    normalize_comparison,
)
from live_market import get_kis_stock_snapshot
from twelve_data import get_live_usd_krw


st.set_page_config(
    page_title="기업-매크로 통합 분석",
    page_icon="🔗",
    layout="wide",
)
require_login()


@st.cache_data(ttl=3600, show_spinner=False)
def load_company_data(
    company: str,
    start_year: int,
    end_year: int,
    indicator_name: str,
    frequency: str,
    preferred_account_name: str,
):
    return get_company_indicator(
        company,
        start_year,
        end_year,
        indicator_name,
        frequency,
        preferred_account_name=preferred_account_name or None,
    )


@st.cache_data(ttl=3600, show_spinner=False)
def load_macro_data(
    indicator_name: str,
    start_year: int,
    end_year: int,
):
    return get_macro_indicator(indicator_name, start_year, end_year)


@st.cache_data(ttl=3600, show_spinner=False)
def load_scenario_reference_data(
    company: str,
    end_year: int,
) -> tuple[dict[str, object], list[str]]:
    """최신 공시·환율·상장주식 수를 시뮬레이션 기준값으로 연결한다."""
    warnings: list[str] = []
    financial_df, dart_warnings = fetch_financial_statements(
        company,
        max(2015, end_year - 2),
        end_year,
        "사업보고서",
    )
    warnings.extend(dart_warnings)
    if financial_df.empty:
        raise ValueError("최근 사업보고서 재무제표를 조회하지 못했습니다.")

    try:
        exchange_frame, _ = get_live_usd_krw(outputsize=5)
        if exchange_frame.empty:
            raise ValueError("실시간 환율 응답이 비어 있습니다.")
        exchange_rate = float(exchange_frame.iloc[-1]["종가"])
        exchange_source = "Twelve Data USD/KRW 최근 시세"
    except Exception as error:
        fallback_frame, _ = get_macro_indicator(
            "원/달러 환율",
            max(2015, end_year - 1),
            end_year,
        )
        if fallback_frame.empty:
            raise ValueError(f"기준 환율을 조회하지 못했습니다: {error}") from error
        exchange_rate = float(fallback_frame.iloc[-1]["값"])
        exchange_source = "한국은행 ECOS 원/달러 환율 최근값"
        warnings.append(
            f"실시간 환율 대신 ECOS 최근값을 사용했습니다: {error}"
        )

    listed_shares = None
    market_snapshot: dict[str, float | None] = {}
    stock_code = get_stock_code(company)
    if stock_code:
        try:
            market_snapshot = get_kis_stock_snapshot(stock_code)
            listed_shares = market_snapshot["listed_shares"]
        except Exception as error:
            warnings.append(f"상장주식 수를 조회하지 못했습니다: {error}")
    else:
        warnings.append("상장 종목코드를 찾지 못해 EPS 영향은 계산하지 않습니다.")

    statement_tables = make_key_financial_statement_tables(financial_df, "억원")
    defaults = build_scenario_financial_defaults(
        statement_tables,
        exchange_rate,
        listed_shares,
    )
    defaults["exchange_source"] = exchange_source
    defaults["stock_code"] = stock_code
    defaults["market_snapshot"] = market_snapshot
    defaults["financial_report_snapshot"] = build_financial_report_snapshot(
        statement_tables
    )
    return defaults, warnings


def csv_bytes(frame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def macro_source_description(spec) -> str:
    if hasattr(spec, "stat_code"):
        return (
            f"한국은행 ECOS {spec.stat_code} / {spec.item_code}"
        )
    return f"FRED {spec.series_id}"


def dataframe_records(frame: pd.DataFrame | None) -> list[dict[str, object]]:
    """AI 컨텍스트에 넣을 수 있도록 결측치를 제거한 레코드로 변환한다."""
    if frame is None or frame.empty:
        return []
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def build_ai_report_context(
    *,
    company: str,
    start_year: int,
    end_year: int,
    frequency: str,
    company_indicator: str,
    macro_indicator: str,
    normalization_method: str,
    company_data: pd.DataFrame,
    macro_data: pd.DataFrame,
    normalized: pd.DataFrame | None,
    company_source: str,
    macro_source: str,
) -> dict[str, object]:
    scenario_context = st.session_state.get("scenario_report_context")
    if not isinstance(scenario_context, dict) or scenario_context.get(
        "company"
    ) != company:
        scenario_context = {"상태": "시나리오 기준값을 불러오지 못함"}
    market_info = scenario_context.get("시장정보", {})
    financial_summary = scenario_context.get("핵심재무요약", {})
    scenario_analysis = {
        key: value
        for key, value in scenario_context.items()
        if key not in ("시장정보", "핵심재무요약")
    }
    return {
        "기업": company,
        "분석기간": f"{start_year}~{end_year}",
        "비교주기": frequency,
        "기업지표": company_indicator,
        "매크로지표": macro_indicator,
        "정규화방식": normalization_method,
        "기업지표계열": dataframe_records(company_data),
        "매크로지표계열": dataframe_records(macro_data),
        "정규화비교계열": dataframe_records(normalized),
        "시장정보": market_info,
        "핵심재무요약": financial_summary,
        "시나리오": scenario_analysis,
        "데이터출처": {
            "기업": company_source,
            "매크로": macro_source,
            "재무": "금융감독원 Open DART 연결 사업보고서",
            "상장주식수": "한국투자증권 KIS",
        },
        "해석주의": [
            "정규화 비교는 방향과 흐름을 보기 위한 것이며 인과관계를 뜻하지 않음",
            "시나리오는 공시 계정 대용값을 사용한 단순 민감도 분석임",
            "환헤지와 통화별·고정변동금리별 세부 내역은 반영하지 않음",
        ],
    }


def render_ai_report(company: str, context: dict[str, object]) -> None:
    st.subheader("✨ AI 분석 보고서")
    st.caption(
        "현재 화면의 기업·매크로·시나리오 데이터만 Gemini에 전달하여 "
        "한국어 보고서를 생성합니다."
    )
    st.info(
        "Gemini 무료 구간에서는 전송 데이터가 Google 제품 개선에 사용될 수 "
        "있습니다. 이 기능은 공개 기업·시장 데이터만 전송합니다."
    )
    configured = bool(os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY"))
    if not configured:
        st.warning("GEMINI_KEY가 설정되지 않아 AI 보고서를 생성할 수 없습니다.")
        return

    fingerprint = report_context_fingerprint(context)
    if st.button(
        "AI 보고서 생성",
        type="primary",
        key="generate_ai_report",
        width="stretch",
    ):
        try:
            with st.spinner("AI가 분석 보고서를 작성하고 있습니다..."):
                report, model = generate_ai_report(context)
            st.session_state["generated_ai_report"] = {
                "fingerprint": fingerprint,
                "company": company,
                "model": model,
                "report": report,
            }
            record_user_history(
                "ai_report",
                f"{company} AI 분석 보고서",
                {
                    "company": company,
                    "model": model,
                    "report": report,
                    "analysis_context": context,
                },
            )
        except Exception as error:
            st.error(f"AI 보고서 생성 중 오류가 발생했습니다: {error}")

    stored = st.session_state.get("generated_ai_report")
    if not isinstance(stored, dict):
        return
    if stored.get("fingerprint") != fingerprint:
        st.caption(
            "분석 조건이 변경되었습니다. 현재 데이터 기준으로 보고서를 다시 "
            "생성해 주세요."
        )
        return

    report = str(stored.get("report", ""))
    if not report:
        return
    st.caption(f"생성 모델: {stored.get('model', '-')}")
    with st.container(border=True):
        st.markdown(report)
    try:
        pdf_data = report_to_pdf(report, title=f"{company} AI 분석 보고서")
    except Exception as error:
        st.error(f"PDF 변환 중 오류가 발생했습니다: {error}")
    else:
        st.download_button(
            "PDF 보고서 다운로드",
            data=pdf_data,
            file_name=f"{company}_AI_분석_보고서.pdf",
            mime="application/pdf",
            key="download_ai_report_pdf",
            on_click="ignore",
        )


@st.fragment
def render_scenario_simulator(company_name: str, end_year: int) -> None:
    with st.expander("🧪 시나리오 시뮬레이션", expanded=False):
        st.caption(
            f"{company_name}의 최신 공시 재무값을 자동 연결했습니다. "
            "재무 기준값은 고정되며 사용자는 환율과 금리 변화만 조작합니다."
        )

        try:
            with st.spinner("시뮬레이션 기준 재무값을 연결하고 있습니다..."):
                defaults, reference_warnings = load_scenario_reference_data(
                    company_name,
                    end_year,
                )
        except Exception as error:
            st.error(f"시뮬레이션 기준값을 불러오지 못했습니다: {error}")
            return

        for warning in reference_warnings:
            st.warning(warning)

        krw_floating_debt = float(defaults["gross_debt_100m_krw"])
        assumed_exchange_rate = float(defaults["exchange_rate"])
        tax_rate = defaults["effective_tax_rate"]

        scenario = st.selectbox(
            "시나리오 종류",
            ("환율", "한국 금리", "미국 금리", "복합 시나리오"),
            key="simulator_scenario",
        )

        st.markdown("##### 자동 연결된 계산 기준")
        basis_columns = st.columns(3)
        basis_columns[0].metric(
            "환율 민감 자산 대용값",
            f"{float(defaults['fx_assets_proxy_100m_krw']):,.0f}억원",
            help="현금및현금성자산 + 단기금융상품 + 매출채권",
        )
        basis_columns[1].metric(
            "환율 민감 부채 대용값",
            f"{float(defaults['fx_liabilities_proxy_100m_krw']):,.0f}억원",
            help="매입채무 + 단기·장기차입금 + 사채",
        )
        basis_columns[2].metric(
            "총차입금",
            f"{krw_floating_debt:,.0f}억원",
            help="단기차입금 + 장기차입금 + 사채",
        )
        calculation_columns = st.columns(3)
        calculation_columns[0].metric(
            "기준 환율",
            f"{assumed_exchange_rate:,.2f}원/USD",
        )
        calculation_columns[1].metric(
            "자동 산출 유효세율",
            f"{float(tax_rate):.2f}%" if tax_rate is not None else "산출 불가",
            help="법인세비용 ÷ (지배기업 순이익 + 법인세비용)",
        )
        calculation_columns[2].metric(
            "상장주식 수",
            (
                f"{float(defaults['listed_shares']):,.0f}주"
                if defaults["listed_shares"] is not None
                else "조회 불가"
            ),
        )
        st.caption(
            f"재무 기준: DART 연결 사업보고서 {defaults['period']} · "
            f"환율: {defaults['exchange_source']} · "
            f"상장주식 수: 한국투자증권 KIS"
        )
        if defaults["missing_accounts"]:
            st.warning(
                "공시에서 확인되지 않은 자동 연결 계정: "
                + ", ".join(defaults["missing_accounts"])
                + ". 해당 항목은 대용값 합계에서 제외했습니다."
            )
        st.info(
            "3대 재무제표에는 통화별 자산·부채와 고정·변동금리 구분이 없어 "
            "위 계정 합계를 자동 대용값으로 사용합니다. 한국·미국 금리 "
            "시나리오는 각각 총차입금 전체가 해당 금리에 민감하다고 가정합니다."
        )

        st.markdown("##### 시나리오 변화량")
        exchange_change = 0
        korea_rate_change = 0.0
        usa_rate_change = 0.0

        if scenario in ("환율", "복합 시나리오"):
            exchange_change = st.slider(
                "원/달러 환율 변화",
                min_value=-200,
                max_value=200,
                value=0,
                step=10,
                format="%d원",
                key="simulator_exchange_change",
            )
        if scenario in ("한국 금리", "복합 시나리오"):
            korea_rate_change = st.slider(
                "한국 금리 변화",
                min_value=-2.0,
                max_value=2.0,
                value=0.0,
                step=0.25,
                format="%.2f%%p",
                key="simulator_korea_rate_change",
            )
        if scenario in ("미국 금리", "복합 시나리오"):
            usa_rate_change = st.slider(
                "미국 금리 변화",
                min_value=-2.0,
                max_value=2.0,
                value=0.0,
                step=0.25,
                format="%.2f%%p",
                key="simulator_usa_rate_change",
            )

        effects = calculate_scenario_effects(
            defaults,
            exchange_change,
            korea_rate_change,
            usa_rate_change,
        )
        foreign_exchange_effect = float(
            effects["foreign_exchange_effect_100m_krw"] or 0.0
        )
        interest_expense_change = float(
            effects["interest_expense_change_100m_krw"] or 0.0
        )
        net_income_effect = effects["net_income_effect_100m_krw"]
        eps_effect = effects["eps_effect_krw"]
        st.session_state["scenario_report_context"] = {
            "company": company_name,
            "시나리오종류": scenario,
            "재무기준기간": defaults["period"],
            "기준환율_원_USD": assumed_exchange_rate,
            "환율민감자산_대용값_억원": defaults[
                "fx_assets_proxy_100m_krw"
            ],
            "환율민감부채_대용값_억원": defaults[
                "fx_liabilities_proxy_100m_krw"
            ],
            "총차입금_억원": krw_floating_debt,
            "유효세율_퍼센트": tax_rate,
            "상장주식수_주": defaults["listed_shares"],
            "시장정보": {
                "종목코드": defaults["stock_code"],
                "주가_원": defaults["market_snapshot"].get("price"),
                "시가총액_억원": defaults["market_snapshot"].get(
                    "market_cap_100m_krw"
                ),
                "가격기준": "한국투자증권 KIS 조회 시점",
            },
            "핵심재무요약": defaults["financial_report_snapshot"],
            "사용자변수": {
                "환율변화_원": exchange_change,
                "한국금리변화_퍼센트포인트": korea_rate_change,
                "미국금리변화_퍼센트포인트": usa_rate_change,
            },
            "계산결과": effects,
            "누락계정": defaults["missing_accounts"],
            "대용값주의": (
                "통화별 자산·부채 및 고정·변동금리 구분이 없어 핵심 계정 "
                "합계와 총차입금을 대용값으로 사용"
            ),
        }

        st.divider()
        st.markdown("##### 예상 영향")
        result_columns = st.columns(4)
        result_columns[0].metric(
            "외화자산·부채 순효과",
            f"{foreign_exchange_effect:+,.0f}억원",
            help="(달러 자산 - 달러 부채) × 환율 변화",
        )
        result_columns[1].metric(
            "연간 이자비용 변화",
            f"{interest_expense_change:+,.0f}억원",
            help="금리 상승 시 양수는 이자비용 증가를 의미합니다.",
            delta_color="inverse",
        )
        result_columns[2].metric(
            "예상 순이익 변화",
            (
                f"{net_income_effect:+,.0f}억원"
                if net_income_effect is not None
                else "계산 불가"
            ),
        )
        result_columns[3].metric(
            "예상 EPS 변화",
            f"{eps_effect:+,.0f}원" if eps_effect is not None else "계산 불가",
            help="유효세율과 상장주식 수가 자동 조회되어야 계산됩니다.",
        )

        with st.popover("계산식과 해석 기준"):
            st.write(
                "환율 효과(억원) = (달러 자산 - 달러 부채, 백만 USD) "
                "× 환율 변화(원) ÷ 100"
            )
            st.write(
                "이자비용 변화 = 원화 변동금리 차입금 × 한국 금리 변화 "
                "+ 달러 변동금리 차입금의 원화 환산액 × 미국 금리 변화"
            )
            st.write(
                "순이익 변화 = (환율 효과 - 이자비용 변화) × (1 - 유효세율)"
            )
            st.write(
                "EPS 변화 = 순이익 변화 ÷ 발행주식 수"
            )

        st.warning(
            "이 결과는 공시 계정 대용값과 사용자가 선택한 매크로 충격에 따른 "
            "단순 추정치입니다. "
            "환헤지, 고정·변동금리 비중, 세무 효과, 회계상 환산손익 및 "
            "사업별 매출 민감도는 반영하지 않았으며 투자 판단 근거가 아닙니다."
        )
        if st.button(
            "현재 시나리오 기록 저장",
            key="save_current_scenario",
            width="stretch",
        ):
            record_user_history(
                "scenario",
                f"{company_name} {scenario} 시나리오",
                st.session_state["scenario_report_context"],
            )
            st.success("현재 시나리오를 내 기록에 저장했습니다.")


st.title("🏢 기업-매크로 통합 분석")
st.caption(
    "기업 실적과 매크로 지표의 흐름을 나란히 비교합니다. "
    "이 화면은 두 지표 사이의 인과관계를 의미하지 않습니다."
)

with st.form("integrated_analysis_form"):
    company_column, period_column, frequency_column = st.columns(3)
    company = company_column.text_input(
        "기업명",
        value="삼성전자",
        placeholder="예: 삼성전자",
    )
    with period_column:
        year_columns = st.columns(2)
        start_year = year_columns[0].number_input(
            "시작 연도",
            min_value=2015,
            max_value=2030,
            value=2021,
            step=1,
        )
        end_year = year_columns[1].number_input(
            "종료 연도",
            min_value=2015,
            max_value=2030,
            value=2025,
            step=1,
        )
    frequency = frequency_column.selectbox(
        "비교 주기",
        ("연간", "분기"),
        help=(
            "기업과 매크로 데이터를 같은 주기로 통일합니다. "
            "매크로 값은 선택 주기의 평균입니다."
        ),
    )

    indicator_columns = st.columns(2)
    company_indicator = indicator_columns[0].selectbox(
        "기업 지표",
        COMPANY_INDICATORS,
    )
    macro_indicator = indicator_columns[1].selectbox(
        "매크로 지표",
        tuple(MACRO_INDICATORS),
    )
    normalization_method = st.selectbox(
        "정규화 방식",
        ("기준시점 100", "z-score", "기간별 증감률"),
        help=(
            "기준시점 100은 흐름 비교에 직관적이며, 값이 0이거나 "
            "음수인 기업은 z-score가 더 적합합니다."
        ),
    )
    use_custom_account = st.checkbox(
        "기업별 계정명 직접 지정",
        help=(
            "표준 계정 매핑이 실패하는 경우 DART 재무제표 페이지에서 "
            "확인한 계정명을 정확히 입력합니다."
        ),
    )
    preferred_account_name = ""
    if use_custom_account:
        preferred_account_name = st.text_input(
            "직접 사용할 계정명",
            placeholder="예: 영업수익",
        )
    search_button = st.form_submit_button(
        "통합 비교",
        type="primary",
        width="stretch",
    )

submitted_now = bool(search_button)
if search_button:
    st.session_state["integrated_last_form"] = {
        "company": company,
        "start_year": int(start_year),
        "end_year": int(end_year),
        "frequency": frequency,
        "company_indicator": company_indicator,
        "macro_indicator": macro_indicator,
        "normalization_method": normalization_method,
        "preferred_account_name": preferred_account_name,
    }
elif "integrated_last_form" in st.session_state:
    saved_form = st.session_state["integrated_last_form"]
    company = saved_form["company"]
    start_year = saved_form["start_year"]
    end_year = saved_form["end_year"]
    frequency = saved_form["frequency"]
    company_indicator = saved_form["company_indicator"]
    macro_indicator = saved_form["macro_indicator"]
    normalization_method = saved_form["normalization_method"]
    preferred_account_name = saved_form["preferred_account_name"]
    search_button = True

if not search_button:
    st.info("기업, 기간, 비교 지표를 선택한 뒤 통합 비교를 실행해 주세요.")
else:
    try:
        if int(start_year) > int(end_year):
            raise ValueError("시작 연도는 종료 연도보다 클 수 없습니다.")

        with st.spinner("기업과 매크로 데이터를 조회하고 있습니다..."):
            company_data, warnings = load_company_data(
                company.strip(),
                int(start_year),
                int(end_year),
                company_indicator,
                frequency,
                preferred_account_name,
            )
            raw_macro_data, macro_spec = load_macro_data(
                macro_indicator,
                int(start_year),
                int(end_year),
            )
            macro_data = aggregate_macro_indicator(
                raw_macro_data,
                frequency,
            )
    except Exception as error:
        st.error(f"통합 데이터 조회 중 오류가 발생했습니다: {error}")
    else:
        for warning in warnings:
            st.warning(warning)

        if company_data.empty:
            st.error(
                f"{company.strip()}의 {company_indicator} 데이터를 "
                "조회하지 못했습니다. DART 재무제표 페이지에서 실제 "
                "계정명을 확인한 뒤 '기업별 계정명 직접 지정'을 사용해 주세요."
            )
        elif macro_data.empty:
            st.error(f"{macro_indicator} 데이터를 조회하지 못했습니다.")
        else:
            if submitted_now:
                record_user_history(
                    "integrated_analysis",
                    f"{company.strip()} 통합 분석",
                    {
                        "company": company.strip(),
                        "start_year": int(start_year),
                        "end_year": int(end_year),
                        "frequency": frequency,
                        "company_indicator": company_indicator,
                        "macro_indicator": macro_indicator,
                        "normalization_method": normalization_method,
                        "company_data_points": int(len(company_data)),
                        "macro_data_points": int(len(macro_data)),
                    },
                )
            st.subheader(
                f"{company.strip()} {company_indicator} ↔ {macro_indicator}"
            )

            company_latest = company_data.iloc[-1]
            macro_latest = macro_data.iloc[-1]
            metric_columns = st.columns(2)
            metric_columns[0].metric(
                f"{company_indicator} ({company_latest['기간']})",
                f"{float(company_latest['값']):,.0f}억원",
            )
            metric_columns[1].metric(
                f"{macro_indicator} ({macro_latest['기간']})",
                f"{float(macro_latest['값']):,.{macro_spec.decimals}f}"
                f"{macro_spec.unit}",
            )
            aggregation_label = (
                "환율 집계"
                if macro_indicator == "원/달러 환율"
                else "매크로 집계"
            )
            st.caption(
                f"비교 주기: {frequency} · {aggregation_label}: "
                f"{get_aggregation_description(macro_indicator, frequency)}"
            )

            expected_count = (
                int(end_year) - int(start_year) + 1
            ) * (4 if frequency == "분기" else 1)
            if len(company_data) < expected_count:
                st.warning(
                    f"기업 지표는 예상 {expected_count}개 기간 중 "
                    f"{len(company_data)}개가 조회됐습니다. 미공시 기간, 빈 값 "
                    "또는 기업별 계정명 차이로 일부 기간이 제외될 수 있습니다."
                )

            st.divider()
            chart_columns = st.columns(2)

            with chart_columns[0]:
                st.subheader(f"{company.strip()} {company_indicator} 추이")
                company_chart = company_data.copy()
                st.line_chart(company_chart, x="기간", y="값")
                report_basis = (
                    "연결 사업보고서"
                    if frequency == "연간"
                    else "연결 분기·반기·사업보고서의 단일 분기값"
                )
                st.caption(f"단위: 억원 · DART {report_basis} 기준")
                st.download_button(
                    "기업 지표 CSV 다운로드",
                    data=csv_bytes(company_chart),
                    file_name=(
                        f"{company.strip()}_{company_indicator}_"
                        f"{frequency}.csv"
                    ),
                    mime="text/csv",
                    on_click="ignore",
                )

            with chart_columns[1]:
                st.subheader(f"{macro_indicator} 추이")
                macro_chart = macro_data.copy()
                st.line_chart(macro_chart, x="기간", y="값")
                st.caption(
                    f"단위: {macro_spec.unit} · {macro_spec.description} · "
                    f"{get_aggregation_description(macro_indicator, frequency)} "
                    f"· 출처: {macro_source_description(macro_spec)}"
                )
                st.download_button(
                    "매크로 지표 CSV 다운로드",
                    data=csv_bytes(macro_chart),
                    file_name=f"{macro_indicator}_{frequency}.csv",
                    mime="text/csv",
                    on_click="ignore",
                )

            st.divider()
            st.subheader("정규화 비교")
            try:
                normalized, base_period = normalize_comparison(
                    company_data,
                    macro_data,
                    company_indicator,
                    macro_indicator,
                    frequency,
                    normalization_method,
                )
            except ValueError as error:
                st.warning(str(error))
                normalized = None
                base_period = None

            if normalized is None:
                pass
            elif len(normalized) < 2:
                st.warning(
                    "정규화 비교에는 같은 기간의 데이터가 2개 이상 필요합니다."
                )
            else:
                if normalization_method == "기준시점 100":
                    st.info(
                        f"정규화 기준 시점: {base_period} = 100 "
                        f"(비교 주기: {frequency})"
                    )
                elif normalization_method == "z-score":
                    st.info(
                        f"z-score 산출 표본 기간: {base_period} "
                        f"(비교 주기: {frequency})"
                    )
                else:
                    st.info(
                        f"정규화 기준: 직전 {frequency} 대비 증감률(%)"
                    )
                st.line_chart(
                    normalized,
                    x="기간",
                    y=[company_indicator, macro_indicator],
                )
                normalization_notes = {
                    "기준시점 100": (
                        "기업값과 매크로 평균값을 첫 공통 시점 100 기준으로 "
                        "지수화했습니다."
                    ),
                    "z-score": (
                        "각 지표를 선택 기간의 평균 0, 표준편차 1로 "
                        "표준화했습니다."
                    ),
                    "기간별 증감률": (
                        f"각 지표를 직전 {frequency} 대비 증감률로 변환했습니다."
                    ),
                }
                st.caption(
                    normalization_notes[normalization_method]
                    + " 방향과 흐름을 비교하기 위한 차트이며 인과관계나 "
                    "영향의 크기를 의미하지 않습니다."
                )
                st.dataframe(
                    normalized,
                    width="stretch",
                    hide_index=True,
                )
                st.download_button(
                    "정규화 비교 CSV 다운로드",
                    data=csv_bytes(normalized),
                    file_name=(
                        f"{company.strip()}_{company_indicator}_"
                        f"{macro_indicator}_{normalization_method}.csv"
                    ),
                    mime="text/csv",
                    on_click="ignore",
                )

            st.divider()
            render_scenario_simulator(company.strip(), int(end_year))

            st.divider()
            ai_context = build_ai_report_context(
                company=company.strip(),
                start_year=int(start_year),
                end_year=int(end_year),
                frequency=frequency,
                company_indicator=company_indicator,
                macro_indicator=macro_indicator,
                normalization_method=normalization_method,
                company_data=company_data,
                macro_data=macro_data,
                normalized=normalized,
                company_source=f"DART {report_basis}",
                macro_source=macro_source_description(macro_spec),
            )
            render_ai_report(company.strip(), ai_context)
