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
    make_key_financial_statement_tables,
    make_pivot_table,
)
from market_data import get_company_stock_ohlc
from live_market import (
    domestic_market_state,
    get_kis_intraday_stock_ohlc,
    get_live_stock,
)


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
        return pd.DataFrame(), "", "", ""

    end = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
    start = pd.Timestamp(end) - pd.DateOffset(years=3)
    frame, symbol, source = get_company_stock_ohlc(
        stock_code,
        pd.Timestamp(start),
        pd.Timestamp(end),
    )
    return frame, symbol, stock_code, source


@st.cache_data(ttl=120, show_spinner=False)
def load_company_intraday_stock(stock_code: str):
    return get_kis_intraday_stock_ohlc(stock_code)


def aggregate_intraday_candles(
    frame: pd.DataFrame,
    interval_minutes: int,
) -> pd.DataFrame:
    """1분봉을 사용자가 선택한 분 단위 OHLC로 집계한다."""
    if frame.empty:
        return frame.copy()
    result = (
        frame.set_index("날짜")
        .resample(
            f"{interval_minutes}min",
            origin="start_day",
            label="left",
            closed="left",
        )
        .agg(
            시가=("시가", "first"),
            고가=("고가", "max"),
            저가=("저가", "min"),
            종가=("종가", "last"),
        )
        .dropna()
        .reset_index()
    )
    return result[result[["시가", "고가", "저가", "종가"]].gt(0).all(axis=1)]


def stock_candlestick_chart(
    frame,
    company: str,
    *,
    intraday: bool = False,
):
    chart_frame = frame.copy()
    chart_frame["등락률"] = (
        pd.to_numeric(chart_frame["종가"], errors="coerce")
        .pct_change(fill_method=None)
        .mul(100)
    )
    # 장기간을 표시할수록 캔들 폭을 자동으로 줄여 겹침을 방지한다.
    candle_size = max(1.2, min(9.0, 720 / max(len(chart_frame), 1)))
    color = alt.condition(
        "datum.종가 >= datum.시가",
        alt.value("#089981"),
        alt.value("#F23645"),
    )
    base = alt.Chart(chart_frame).encode(
        x=alt.X(
            "날짜:T",
            title="날짜",
            axis=alt.Axis(
                format="%H:%M" if intraday else "%Y-%m-%d",
                labelAngle=0,
                tickCount=10,
                grid=True,
            ),
        ),
        color=color,
        tooltip=[
            alt.Tooltip(
                "날짜:T",
                title="시간" if intraday else "날짜",
                format=(
                    "%Y-%m-%d %H:%M"
                    if intraday
                    else "%Y-%m-%d"
                ),
            ),
            alt.Tooltip("시가:Q", title="시가", format=",.0f"),
            alt.Tooltip("고가:Q", title="고가", format=",.0f"),
            alt.Tooltip("저가:Q", title="저가", format=",.0f"),
            alt.Tooltip("종가:Q", title="종가", format=",.0f"),
            alt.Tooltip(
                "등락률:Q",
                title="등락률 (%)",
                format="+.2f",
            ),
        ],
    )
    wick = base.mark_rule(strokeWidth=1.2).encode(
        y=alt.Y(
            "저가:Q",
            title=f"{company} 주가 (원)",
            scale=alt.Scale(zero=False),
            axis=alt.Axis(orient="right"),
        ),
        y2="고가:Q",
    )
    body = base.mark_bar(
        size=candle_size,
        opacity=1,
    ).encode(y="시가:Q", y2="종가:Q")
    latest_price = pd.DataFrame(
        {"종가": [float(chart_frame.iloc[-1]["종가"])]}
    )
    price_line = (
        alt.Chart(latest_price)
        .mark_rule(
            color="#B2B5BE",
            strokeWidth=1,
            strokeDash=[4, 4],
            opacity=0.75,
        )
        .encode(y="종가:Q")
    )
    return (
        (wick + body + price_line)
        .properties(height=500, background="#131722")
        .configure_axis(
            domainColor="#434651",
            gridColor="#2A2E39",
            gridOpacity=0.8,
            labelColor="#B2B5BE",
            labelFont="Arial",
            labelFontSize=11,
            tickColor="#434651",
            titleColor="#D1D4DC",
            titleFont="Arial",
            titleFontSize=12,
        )
        .configure_view(stroke="#2A2E39", strokeWidth=1)
        .interactive(bind_y=False)
    )


@st.fragment(run_every="1s")
def render_live_stock_metrics(
    stock_code: str,
    fallback: dict,
) -> None:
    live, live_error = get_live_stock(stock_code)
    state = domestic_market_state(
        live.received_at if live is not None else None,
        live_error,
    )
    metric_columns = st.columns(4)
    if live is not None:
        live_change_rate = live.change_rate
        if live_change_rate is None and live.change is not None:
            previous_close = live.price - live.change
            if previous_close:
                live_change_rate = live.change / previous_close * 100
        live_delta = (
            f"{live.change:+,.0f}원 ({live_change_rate:+.2f}%)"
            if live.change is not None and live_change_rate is not None
            else None
        )
        metric_columns[0].metric(
            "실시간 현재가",
            f"{live.price:,.0f}원",
            live_delta,
        )
        for column, label, value in zip(
            metric_columns[1:],
            ("시가", "고가", "저가"),
            (live.open, live.high, live.low),
        ):
            column.metric(label, f"{value:,.0f}원" if value is not None else "-")
        st.caption(
            f"{'●' if state.is_live else '○'} {state.label} · "
            f"{state.detail} · 종목코드: {stock_code}"
        )
    else:
        price_change = fallback["종가"] - fallback["이전종가"]
        change_rate = (
            price_change / fallback["이전종가"] * 100
            if fallback["이전종가"]
            else 0.0
        )
        metric_columns[0].metric(
            "최근 종가",
            f"{fallback['종가']:,.0f}원",
            f"{price_change:+,.0f}원 ({change_rate:+.2f}%)",
        )
        for column, label in zip(metric_columns[1:], ("시가", "고가", "저가")):
            column.metric(label, f"{fallback[label]:,.0f}원")
        st.caption(f"○ {state.label} · {state.detail}")


@st.fragment(run_every="5s")
def render_live_stock_candlestick(
    display_frame,
    company: str,
    stock_code: str,
) -> None:
    chart_frame = display_frame.copy()
    live, _ = get_live_stock(stock_code)
    if live is not None:
        today = pd.Timestamp(live.received_at.date())
        today_row = pd.DataFrame(
            [{
                "날짜": today,
                "시가": live.open,
                "고가": live.high,
                "저가": live.low,
                "종가": live.price,
            }]
        )
        chart_frame = chart_frame[
            pd.to_datetime(chart_frame["날짜"]).dt.normalize() != today
        ]
        chart_frame = (
            pd.concat([chart_frame, today_row], ignore_index=True)
            .sort_values("날짜")
            .reset_index(drop=True)
        )
    st.altair_chart(
        stock_candlestick_chart(chart_frame, company),
        width="stretch",
    )


@st.fragment(run_every="5s")
def render_intraday_stock_candlestick(
    candle_frame: pd.DataFrame,
    company: str,
    stock_code: str,
    interval_minutes: int,
) -> None:
    """선택 분봉의 진행 중인 마지막 캔들에 실시간 체결가를 반영한다."""
    chart_frame = candle_frame.copy()
    live, _ = get_live_stock(stock_code)
    if live is not None:
        received_at = pd.Timestamp(live.received_at).tz_localize(None)
        candle_time = received_at.floor(f"{interval_minutes}min")
        same_candle = chart_frame["날짜"].eq(candle_time)
        if same_candle.any():
            index = chart_frame.index[same_candle][-1]
            chart_frame.loc[index, "고가"] = max(
                float(chart_frame.loc[index, "고가"]),
                live.price,
            )
            chart_frame.loc[index, "저가"] = min(
                float(chart_frame.loc[index, "저가"]),
                live.price,
            )
            chart_frame.loc[index, "종가"] = live.price
        elif (
            chart_frame.empty
            or candle_time > pd.Timestamp(chart_frame.iloc[-1]["날짜"])
        ):
            chart_frame = pd.concat(
                [
                    chart_frame,
                    pd.DataFrame(
                        [{
                            "날짜": candle_time,
                            "시가": live.price,
                            "고가": live.price,
                            "저가": live.price,
                            "종가": live.price,
                        }]
                    ),
                ],
                ignore_index=True,
            )
    st.altair_chart(
        stock_candlestick_chart(
            chart_frame,
            company,
            intraday=True,
        ),
        width="stretch",
    )


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

    interval_options = {
        "1분": 1,
        "5분": 5,
        "10분": 10,
        "30분": 30,
        "1시간": 60,
        "일봉": None,
    }
    selected_interval = st.pills(
        "차트 봉",
        tuple(interval_options),
        default="일봉",
        selection_mode="single",
        key="company_stock_interval",
    ) or "일봉"

    latest = frame.iloc[-1]
    previous_close = (
        float(frame.iloc[-2]["종가"])
        if len(frame) > 1
        else float(latest["종가"])
    )
    fallback = {
        label: float(latest[label])
        for label in ("시가", "고가", "저가", "종가")
    }
    fallback["이전종가"] = previous_close
    render_live_stock_metrics(stock_code, fallback)

    interval_minutes = interval_options[selected_interval]
    if interval_minutes is not None:
        try:
            intraday_frame = load_company_intraday_stock(stock_code)
            candle_frame = aggregate_intraday_candles(
                intraday_frame,
                interval_minutes,
            )
        except Exception as error:
            st.warning(f"분봉 데이터를 불러오지 못했습니다: {error}")
            return
        if candle_frame.empty:
            st.info("최근 거래일의 조회 가능한 분봉 데이터가 없습니다.")
            return
        trading_date = pd.Timestamp(candle_frame.iloc[-1]["날짜"])
        st.caption(
            f"한국투자증권 최근 거래일 분봉 · {trading_date:%Y-%m-%d} · "
            f"{selected_interval}봉 · 종목코드: {stock_code} · "
            "차트는 5초마다 진행 중인 봉의 실시간 체결가를 반영합니다."
        )
        render_intraday_stock_candlestick(
            candle_frame,
            company,
            stock_code,
            interval_minutes,
        )
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
    st.caption(
        f"최신 일봉 · 기준 시점: {latest['날짜']:%Y-%m-%d} · "
        f"종목코드: {stock_code} · 심볼: {symbol} · "
        f"출처: {source} · 장중 데이터는 변동될 수 있습니다."
    )
    render_live_stock_candlestick(display_frame, company, stock_code)


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

        st.subheader("통합 재무제표")
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
        st.subheader("핵심 3대 재무제표")
        st.caption(
            "기업가치 평가와 현금흐름 분석에 필요한 19개 핵심 계정만 "
            "표시합니다. DART 원문에 없는 계정은 '-'로 표시됩니다."
        )
        statements = make_key_financial_statement_tables(
            financial_df,
            amount_unit,
        )
        tabs = st.tabs(list(statements))

        for tab, (statement_name, statement_df) in zip(
            tabs, statements.items()
        ):
            with tab:
                if statement_df.empty:
                    st.info("조회된 데이터가 없습니다.")
                else:
                    value_columns = statement_df.columns[2:]
                    available = statement_df[value_columns].notna().any(
                        axis=1
                    )
                    missing_accounts = statement_df.loc[
                        ~available, "계정명"
                    ].tolist()
                    st.caption(
                        f"조회된 핵심 계정: {int(available.sum())}/"
                        f"{len(statement_df)}개"
                    )
                    st.dataframe(
                        dataframe_with_number_format(statement_df),
                        width="stretch",
                        hide_index=True,
                    )
                    if missing_accounts:
                        st.caption(
                            "DART 원문 미제공: "
                            + ", ".join(missing_accounts)
                        )
                    st.download_button(
                        f"{statement_name} CSV 다운로드",
                        data=csv_bytes(statement_df),
                        file_name=(
                            f"{result['company']}_{statement_name}_"
                            f"{amount_unit}.csv"
                        ),
                        mime="text/csv",
                        key=f"download_{statement_name}",
                        on_click="ignore",
                    )
