"""Open DART 기업 재무제표 조회 페이지."""

from datetime import datetime
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

from dart import (
    AMOUNT_UNITS,
    REPORT_CODES,
    fetch_financial_statements,
    get_stock_code,
    make_pivot_table,
    split_financial_statements,
)
from market_data import get_company_stock_ohlc


st.set_page_config(
    page_title="기업 재무제표",
    page_icon="📑",
    layout="wide",
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_financial_statements(
    company: str,
    start_year: int,
    end_year: int,
    report_name: str,
):
    return fetch_financial_statements(
        company,
        start_year,
        end_year,
        report_name,
    )


@st.cache_data(ttl=300, show_spinner=False)
def load_company_stock(company: str):
    stock_code = get_stock_code(company)
    if not stock_code:
        return pd.DataFrame(), "", ""

    end = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
    start = pd.Timestamp(end) - pd.DateOffset(years=3)
    frame, symbol, source = get_company_stock_ohlc(
        stock_code,
        pd.Timestamp(start),
        pd.Timestamp(end),
    )
    return frame, symbol, stock_code, source


def stock_candlestick_chart(frame, company: str):
    color = alt.condition(
        "datum.종가 >= datum.시가",
        alt.value("#E53935"),
        alt.value("#1565C0"),
    )
    base = alt.Chart(frame).encode(
        x=alt.X(
            "날짜:T",
            title="날짜",
            axis=alt.Axis(
                format="%Y-%m-%d",
                labelAngle=-45,
                tickCount=10,
                grid=False,
            ),
        ),
        color=color,
        tooltip=[
            alt.Tooltip("날짜:T", title="날짜", format="%Y-%m-%d"),
            alt.Tooltip("시가:Q", title="시가", format=",.0f"),
            alt.Tooltip("고가:Q", title="고가", format=",.0f"),
            alt.Tooltip("저가:Q", title="저가", format=",.0f"),
            alt.Tooltip("종가:Q", title="종가", format=",.0f"),
        ],
    )
    wick = base.mark_rule(strokeWidth=2).encode(
        y=alt.Y(
            "저가:Q",
            title=f"{company} 주가 (원)",
            scale=alt.Scale(zero=False),
        ),
        y2="고가:Q",
    )
    body = base.mark_bar(
        size=8,
        opacity=0.95,
        stroke="#FFFFFF",
        strokeWidth=0.5,
    ).encode(y="시가:Q", y2="종가:Q")
    return (wick + body).properties(height=500).interactive(bind_y=False)


def render_company_stock_chart(company: str) -> None:
    st.subheader("주가 추이")
    try:
        frame, symbol, stock_code, source = load_company_stock(company)
    except Exception as error:
        st.warning(f"주가 데이터를 불러오지 못했습니다: {error}")
        return
    if frame.empty:
        st.info("상장 종목코드를 찾지 못했거나 조회 가능한 주가가 없습니다.")
        return

    range_options = {
        "1개월": 1,
        "3개월": 3,
        "6개월": 6,
        "1년": 12,
        "3년": 36,
    }
    selected_range = st.pills(
        "주가 표시 기간",
        tuple(range_options),
        default="1년",
        selection_mode="single",
        key="company_stock_range",
    )
    cutoff = frame["날짜"].max() - pd.DateOffset(
        months=range_options.get(selected_range or "1년")
    )
    display_frame = frame[frame["날짜"] >= cutoff].reset_index(drop=True)
    latest = display_frame.iloc[-1]
    previous_close = (
        float(display_frame.iloc[-2]["종가"])
        if len(display_frame) > 1
        else float(latest["종가"])
    )

    metric_columns = st.columns(4)
    metric_columns[0].metric(
        "종가",
        f"{float(latest['종가']):,.0f}원",
        f"{float(latest['종가']) - previous_close:+,.0f}원",
    )
    for column, label in zip(metric_columns[1:], ("시가", "고가", "저가")):
        column.metric(label, f"{float(latest[label]):,.0f}원")

    st.caption(
        f"최신 일봉 · 기준 시점: {latest['날짜']:%Y-%m-%d} · "
        f"종목코드: {stock_code} · 심볼: {symbol} · "
        f"출처: {source} · 장중 데이터는 변동될 수 있습니다."
    )
    st.altair_chart(
        stock_candlestick_chart(display_frame, company),
        width="stretch",
    )


def dataframe_with_number_format(frame):
    numeric_columns = frame.columns[2:]
    formats = {column: "{:,.2f}" for column in numeric_columns}
    return frame.style.format(formats, na_rep="-")


def csv_bytes(frame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


st.title("📑 기업 재무제표")
st.caption("Open DART 연결재무제표 조회")

with st.form("dart_search_form"):
    company = st.text_input("기업명", placeholder="예: 삼성전자")

    start_column, end_column, unit_column = st.columns(3)
    start_year = start_column.number_input(
        "시작 연도",
        min_value=2015,
        max_value=2030,
        value=2022,
        step=1,
    )
    end_year = end_column.number_input(
        "종료 연도",
        min_value=2015,
        max_value=2030,
        value=2024,
        step=1,
    )
    amount_unit = unit_column.selectbox(
        "금액 단위",
        tuple(AMOUNT_UNITS),
        index=2,
    )
    report_name = st.selectbox(
        "보고서 종류",
        ["전체 조회", *REPORT_CODES.keys()],
    )
    search_button = st.form_submit_button(
        "재무제표 조회",
        type="primary",
        width="stretch",
    )

if search_button:
    try:
        with st.spinner("재무제표를 조회하고 있습니다..."):
            financial_df, warnings = load_financial_statements(
                company.strip(),
                int(start_year),
                int(end_year),
                report_name,
            )
        st.session_state["dart_result"] = {
            "company": company.strip(),
            "report_name": report_name,
            "data": financial_df,
            "warnings": warnings,
        }
    except Exception as error:
        st.error(f"재무제표 조회 중 오류가 발생했습니다: {error}")

result = st.session_state.get("dart_result")
if result is None:
    st.info("기업과 조회 기간을 설정한 뒤 재무제표를 조회해 주세요.")
else:
    for warning in result["warnings"]:
        st.warning(warning)

    financial_df = result["data"]
    if financial_df.empty:
        st.error("선택 기간에 조회 가능한 재무제표가 없습니다.")
    else:
        st.subheader(f"{result['company']} · {result['report_name']}")
        st.caption(
            f"출처: 금융감독원 Open DART · 연결재무제표(CFS) · "
            f"표시 단위: {amount_unit}"
        )

        render_company_stock_chart(result["company"])
        st.divider()

        full_pivot = make_pivot_table(financial_df, amount_unit)
        st.dataframe(
            dataframe_with_number_format(full_pivot),
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            "전체 재무제표 CSV 다운로드",
            data=csv_bytes(full_pivot),
            file_name=(
                f"{result['company']}_{result['report_name']}_"
                f"{amount_unit}.csv"
            ),
            mime="text/csv",
            on_click="ignore",
        )

        st.divider()
        st.subheader("3대 재무제표")
        statements = split_financial_statements(financial_df)
        tabs = st.tabs(list(statements))

        for tab, (statement_name, statement_df) in zip(
            tabs,
            statements.items(),
        ):
            with tab:
                if statement_df.empty:
                    st.info("조회된 데이터가 없습니다.")
                else:
                    statement_pivot = make_pivot_table(
                        statement_df,
                        amount_unit,
                    )
                    st.dataframe(
                        dataframe_with_number_format(statement_pivot),
                        width="stretch",
                        hide_index=True,
                    )
                    st.download_button(
                        f"{statement_name} CSV 다운로드",
                        data=csv_bytes(statement_pivot),
                        file_name=(
                            f"{result['company']}_{statement_name}_"
                            f"{amount_unit}.csv"
                        ),
                        mime="text/csv",
                        key=f"download_{statement_name}",
                        on_click="ignore",
                    )
