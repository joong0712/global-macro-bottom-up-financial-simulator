"""한국 ECOS와 미국 FRED 거시경제 지표 대시보드."""

from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

from auth import record_user_history, require_login

from ecos import (
    CORE_INDICATORS,
    EXCHANGE_CURRENCIES,
    INDICATORS,
    SUPPLEMENTARY_INDICATORS,
    get_exchange_chart_data,
    get_macro_indicators,
)
from fred import (
    FRED_CORE_INDICATORS,
    FRED_INDICATORS,
    FRED_SUPPLEMENTARY_INDICATORS,
    get_fred_indicators,
)
from market_data import MARKET_INDICES, get_market_index_ohlc
from live_market import (
    domestic_market_state,
    forex_market_state,
    get_live_index,
    get_live_usd_krw_ticks,
)
from twelve_data import get_live_usd_krw


st.set_page_config(
    page_title="매크로 지표",
    page_icon="📈",
    layout="wide",
)
require_login()

@st.cache_data(ttl=1800, show_spinner=False)
def load_ecos_indicators(
    start_date: str,
    end_date: str,
    names: tuple[str, ...],
):
    return get_macro_indicators(start_date, end_date, names)


@st.cache_data(ttl=300, show_spinner=False)
def load_fred_indicators(
    start_date: str,
    end_date: str,
    names: tuple[str, ...],
):
    return get_fred_indicators(start_date, end_date, names)


@st.cache_data(ttl=3600, show_spinner=False)
def load_exchange_data(
    currency: str,
    start_date: str,
    end_date: str,
):
    return get_exchange_chart_data(currency, start_date, end_date)


@st.cache_data(ttl=60, show_spinner=False)
def load_live_usd_krw():
    return get_live_usd_krw()


@st.cache_data(ttl=300, show_spinner=False)
def load_market_index(
    source_name: str,
    name: str,
    start_date: str,
    end_date: str,
):
    return get_market_index_ohlc(
        source_name, name, start_date, end_date
    )


def format_value(spec: Any, value: float) -> str:
    return f"{value:,.{spec.decimals}f}{spec.unit}"


def format_delta(spec: Any, value: float) -> str:
    return (
        f"{spec.comparison} "
        f"{value:+,.{spec.decimals}f}{spec.delta_unit}"
    )


def format_period(spec: Any, date, *, for_chart: bool = False) -> str:
    if spec.cycle == "Q":
        quarter = (date.month - 1) // 3 + 1
        if for_chart:
            return f"{date.year} Q{quarter}"
        return f"{date.year}년 {quarter}분기"
    if spec.cycle == "A":
        return f"{date.year}"
    if spec.cycle == "D":
        return date.strftime("%Y-%m-%d")
    return date.strftime("%Y-%m")


def source_description(spec: Any) -> str:
    if hasattr(spec, "stat_code"):
        return (
            f"출처: 한국은행 ECOS · 통계코드: {spec.stat_code} · "
            f"항목코드: {spec.item_code}"
        )
    return f"출처: Federal Reserve Bank of St. Louis FRED · Series: {spec.series_id}"


@st.fragment(run_every="1m")
def render_live_exchange_metric(spec: Any, fallback_frame) -> None:
    """원/달러 실시간 카드와 ECOS 장애 대체값을 표시한다."""
    try:
        market_frame, _, ticks, stream_error = (
            load_synchronized_usd_krw()
        )
    except Exception as error:
        market_frame = pd.DataFrame()
        stream_error = str(error)

    if not market_frame.empty:
        latest = market_frame.iloc[-1]
        latest_time = pd.Timestamp(latest["날짜"])
        previous_day = market_frame[
            pd.to_datetime(market_frame["날짜"]).dt.date
            < latest_time.date()
        ]
        comparison = (
            float(previous_day.iloc[-1]["종가"])
            if not previous_day.empty
            else (
                float(market_frame.iloc[-2]["종가"])
                if len(market_frame) > 1
                else float(latest["종가"])
            )
        )
        current = float(latest["종가"])
        delta = current - comparison
        delta_rate = delta / comparison * 100 if comparison else 0.0
        st.metric(
            "원/달러 환율",
            f"{current:,.2f}원",
            f"{delta:+,.2f}원 ({delta_rate:+.2f}%)",
            help="Twelve Data USD/KRW 실시간 시장 중간환율",
        )
        live_received = bool(ticks)
        state = forex_market_state(
            latest_time.to_pydatetime(),
            has_live_tick=live_received,
            error=stream_error,
        )
        st.caption(
            f"{'●' if state.is_live else '○'} {state.label} · "
            f"{state.detail} · 기준 {latest_time:%H:%M} KST · "
            "1분마다 갱신"
        )
        if stream_error and not live_received:
            st.caption("WebSocket 연결 중 · 최신 1분봉을 표시합니다.")
        return

    latest = fallback_frame.iloc[-1]
    current_value = float(latest["값"])
    previous_value = (
        float(fallback_frame.iloc[-2]["값"])
        if len(fallback_frame) > 1
        else None
    )
    delta = (
        format_delta(spec, current_value - previous_value)
        if previous_value is not None
        else None
    )
    st.metric(
        "원/달러 환율",
        format_value(spec, current_value),
        delta,
        help=spec.description,
    )
    st.caption(
        f"한국은행 ECOS 공식환율 · "
        f"{format_period(spec, latest['날짜'])} · 실시간 아님"
    )


def csv_bytes(frame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


@st.fragment(run_every="5m")
def render_current_metrics(
    *,
    source_name: str,
    form_key: str,
    specs: dict[str, Any],
    selected_names: tuple[str, ...],
    start_date: str,
    end_date: str,
    loader: Callable,
    fallback_data: dict,
) -> None:
    st.subheader("현재 지표")

    # 상단 카드는 사용자가 선택한 상세 차트 종료월과 관계없이
    # 현재 월까지의 최신 공표값을 조회한다.
    current_month = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m")
    latest_end_date = max(end_date, current_month)

    try:
        indicator_data, refresh_errors = loader(
            start_date,
            latest_end_date,
            selected_names,
        )
    except Exception as error:
        indicator_data = fallback_data
        refresh_errors = {}
        st.warning(
            f"최신값 확인에 실패해 이전 조회값을 표시합니다: {error}"
        )

    checked_at = datetime.now(ZoneInfo("Asia/Seoul"))
    cadence = (
        "ECOS 최신 공표값(환율은 일별)"
        if source_name == "ECOS"
        else "FRED 최신 공표값"
    )
    st.caption(
        f"자동 최신값 확인: 5분 간격 · 마지막 확인: "
        f"{checked_at:%Y-%m-%d %H:%M:%S} KST · {cadence} · "
        "실시간 시장 시세가 아닙니다."
    )

    for name, message in refresh_errors.items():
        st.warning(f"{name} 최신값 확인 실패: {message}")

    available_names = [
        name
        for name in selected_names
        if name in indicator_data and not indicator_data[name].empty
    ]
    for row_start in range(0, len(available_names), 3):
        metric_columns = st.columns(3)
        for column, name in zip(
            metric_columns,
            available_names[row_start:row_start + 3],
        ):
            spec = specs[name]
            frame = indicator_data[name]
            latest = frame.iloc[-1]
            current_value = float(latest["값"])
            previous_value = (
                float(frame.iloc[-2]["값"]) if len(frame) > 1 else None
            )
            delta = (
                format_delta(spec, current_value - previous_value)
                if previous_value is not None
                else None
            )
            with column:
                if source_name == "ECOS" and name == "원/달러 환율":
                    render_live_exchange_metric(spec, frame)
                    continue
                st.metric(
                    label=name,
                    value=format_value(spec, current_value),
                    delta=delta,
                    help=spec.description,
                )
                st.caption(
                    f"기준 시점: {format_period(spec, latest['날짜'])}"
                )


def candlestick_chart(
    frame,
    name: str,
    *,
    unit: str = "포인트",
    intraday: bool = False,
):
    # 고정 폭 캔들은 장기간/분봉 전체 보기에서 서로 겹친다.
    # 표시 개수에 맞춰 폭을 줄여 축소 상태에서도 캔들을 구분한다.
    candle_size = max(1.2, min(9.0, 720 / max(len(frame), 1)))
    color = alt.condition(
        "datum.종가 >= datum.시가",
        alt.value("#089981"),
        alt.value("#F23645"),
    )
    base = alt.Chart(frame).encode(
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
                title="시각" if intraday else "날짜",
                format="%Y-%m-%d %H:%M" if intraday else "%Y-%m-%d",
            ),
            alt.Tooltip("시가:Q", title="시가", format=",.2f"),
            alt.Tooltip("고가:Q", title="고가", format=",.2f"),
            alt.Tooltip("저가:Q", title="저가", format=",.2f"),
            alt.Tooltip("종가:Q", title="종가", format=",.2f"),
        ],
    )
    wick = base.mark_rule(strokeWidth=1.2).encode(
        y=alt.Y(
            "저가:Q",
            title=f"{name} ({unit})",
            scale=alt.Scale(zero=False),
            axis=alt.Axis(orient="right"),
        ),
        y2="고가:Q",
    )
    body = base.mark_bar(
        size=candle_size,
        opacity=1,
    ).encode(
        y="시가:Q",
        y2="종가:Q",
    )
    latest_price = pd.DataFrame(
        {"종가": [float(frame.iloc[-1]["종가"])]}
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
        .properties(height=520, background="#131722")
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


def _merge_live_forex_candle(frame, ticks):
    if not ticks:
        return frame
    result = frame.copy()
    tick_frame = pd.DataFrame(ticks, columns=["날짜", "가격"])
    tick_frame["분"] = pd.to_datetime(tick_frame["날짜"]).dt.floor("min")
    live_candles = (
        tick_frame.groupby("분")["가격"]
        .agg(시가="first", 고가="max", 저가="min", 종가="last")
        .reset_index()
        .rename(columns={"분": "날짜"})
    )
    result = result[~result["날짜"].isin(live_candles["날짜"])]
    return (
        pd.concat([result, live_candles], ignore_index=True)
        .sort_values("날짜")
        .reset_index(drop=True)
    )


@st.cache_data(ttl=60, show_spinner=False)
def load_synchronized_usd_krw():
    """카드와 차트가 공유하는 동일한 1분 환율 스냅샷을 반환한다."""
    frame, meta = load_live_usd_krw()
    ticks, stream_error = get_live_usd_krw_ticks()
    return (
        _merge_live_forex_candle(frame, ticks),
        meta,
        ticks,
        stream_error,
    )


@st.fragment(run_every="1m")
def render_live_exchange_chart() -> None:
    try:
        frame, meta, ticks, stream_error = load_synchronized_usd_krw()
    except Exception as error:
        st.warning(
            "실시간 환율을 불러오지 못했습니다. "
            f"Twelve Data 설정 또는 호출 한도를 확인해 주세요: {error}"
        )
        return

    if frame.empty:
        st.warning("조회 가능한 실시간 원/달러 환율이 없습니다.")
        return

    period_options = {
        "1시간": pd.Timedelta(hours=1),
        "4시간": pd.Timedelta(hours=4),
        "12시간": pd.Timedelta(hours=12),
    }
    selected_period = st.pills(
        "실시간 차트 표시 기간",
        tuple(period_options),
        default="4시간",
        selection_mode="single",
        key="live_usd_krw_period",
    )
    cutoff = frame["날짜"].max() - period_options.get(
        selected_period or "4시간"
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
        "현재가",
        f"{float(latest['종가']):,.2f}원",
        f"{float(latest['종가']) - previous_close:+,.2f}원",
    )
    for column, label in zip(metric_columns[1:], ("시가", "고가", "저가")):
        column.metric(label, f"{float(latest[label]):,.2f}원")

    chart_state = forex_market_state(
        pd.Timestamp(latest["날짜"]).to_pydatetime(),
        has_live_tick=bool(ticks),
        error=stream_error,
    )
    st.caption(
        f"{'●' if chart_state.is_live else '○'} {chart_state.label} · "
        f"{chart_state.detail} · 진행 중인 1분봉 갱신 · "
        f"최종 시세: {latest['날짜']:%Y-%m-%d %H:%M} KST · "
        f"출처: Twelve Data · 거래소/피드: {meta.get('exchange', 'Forex')}"
    )
    if stream_error and not ticks:
        st.caption(f"WebSocket 연결 중: {stream_error}")
    st.altair_chart(
        candlestick_chart(
            display_frame,
            "원/달러",
            unit="원",
            intraday=True,
        ),
        width="stretch",
    )


def _render_market_index_content(
    frame,
    source_name: str,
    form_key: str,
    selected_name: str,
    live=None,
    live_error: str | None = None,
) -> None:
    range_options = {
        "1개월": 1,
        "3개월": 3,
        "6개월": 6,
        "1년": 12,
        "전체": None,
    }
    selected_range = st.pills(
        "차트 표시 기간",
        tuple(range_options),
        default="6개월",
        selection_mode="single",
        key=f"{form_key}_{selected_name}_market_range",
    )
    months = range_options.get(selected_range or "6개월")
    chart_frame = frame.copy()
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

    display_frame = chart_frame
    if months is not None:
        cutoff = chart_frame["날짜"].max() - pd.DateOffset(months=months)
        display_frame = chart_frame[
            chart_frame["날짜"] >= cutoff
        ].reset_index(drop=True)

    latest = display_frame.iloc[-1]
    previous_close = (
        float(display_frame.iloc[-2]["종가"])
        if len(display_frame) > 1
        else float(latest["종가"])
    )
    if source_name == "ECOS":
        index_code = {"코스피": "0001", "코스닥": "1001"}[selected_name]
        fallback = {
            label: float(latest[label])
            for label in ("시가", "고가", "저가", "종가")
        }
        fallback["이전종가"] = previous_close
        render_live_index_metrics(index_code, fallback)
    else:
        metric_columns = st.columns(4)
        metric_columns[0].metric(
            "종가",
            f"{float(latest['종가']):,.2f}",
            f"{float(latest['종가']) - previous_close:+,.2f}",
        )
        for column, label in zip(
            metric_columns[1:], ("시가", "고가", "저가")
        ):
            column.metric(label, f"{float(latest[label]):,.2f}")

    symbol, index_name = MARKET_INDICES[source_name][selected_name]
    market_source = (
        "네이버 금융 일봉 + KIS 실시간 지수"
        if source_name == "ECOS"
        else "Yahoo Finance"
    )
    st.caption(
        f"기준 시점: {latest['날짜']:%Y-%m-%d} · "
        f"{index_name} ({symbol}) · 일별 OHLC · 출처: {market_source}"
    )
    st.altair_chart(
        candlestick_chart(display_frame, selected_name),
        width="stretch",
    )


@st.fragment(run_every="1s")
def render_live_index_metrics(
    index_code: str,
    fallback: dict,
) -> None:
    live, live_error = get_live_index(index_code)
    state = domestic_market_state(
        live.received_at if live is not None else None,
        live_error,
    )
    metric_columns = st.columns(4)
    if live is not None:
        metric_columns[0].metric(
            "실시간 현재지수",
            f"{live.price:,.2f}",
            f"{live.change:+,.2f} ({live.change_rate:+.2f}%)",
        )
        for column, label, value in zip(
            metric_columns[1:],
            ("시가", "고가", "저가"),
            (live.open, live.high, live.low),
        ):
            column.metric(label, f"{value:,.2f}")
        st.caption(
            f"{'●' if state.is_live else '○'} {state.label} · "
            f"{state.detail}"
        )
    else:
        metric_columns[0].metric(
            "최근 종가",
            f"{fallback['종가']:,.2f}",
            f"{fallback['종가'] - fallback['이전종가']:+,.2f}",
        )
        for column, label in zip(
            metric_columns[1:], ("시가", "고가", "저가")
        ):
            column.metric(label, f"{fallback[label]:,.2f}")
        st.caption(f"○ {state.label} · {state.detail}")


@st.fragment(run_every="30s")
def render_live_domestic_index(
    form_key: str,
    selected_name: str,
    start_date: str,
    end_date: str,
) -> None:
    try:
        frame = load_market_index(
            "ECOS", selected_name, start_date, end_date
        )
    except Exception as error:
        st.warning(f"{selected_name} 조회 실패: {error}")
        return
    if frame.empty:
        st.warning("선택 기간에 조회 가능한 시장지수 데이터가 없습니다.")
        return
    index_code = {"코스피": "0001", "코스닥": "1001"}[selected_name]
    live, live_error = get_live_index(index_code)
    _render_market_index_content(
        frame,
        "ECOS",
        form_key,
        selected_name,
        live,
        live_error,
    )


@st.fragment
def render_market_indices(
    source_name: str,
    form_key: str,
    start_date: str,
    end_date: str,
) -> None:
    names = tuple(MARKET_INDICES[source_name])
    selected_name = st.pills(
        "시장지수 선택",
        names,
        default=names[0],
        selection_mode="single",
        key=f"{form_key}_market_index",
    )
    if selected_name is None:
        return
    if source_name == "ECOS":
        render_live_domestic_index(
            form_key, selected_name, start_date, end_date
        )
        return
    try:
        frame = load_market_index(
            source_name, selected_name, start_date, end_date
        )
    except Exception as error:
        st.warning(f"{selected_name} 조회 실패: {error}")
        return
    if frame.empty:
        st.warning("선택 기간에 조회 가능한 시장지수 데이터가 없습니다.")
        return
    _render_market_index_content(
        frame, source_name, form_key, selected_name
    )


@st.fragment(run_every="1m")
def render_detail_chart(
    *,
    source_name: str,
    form_key: str,
    specs: dict[str, Any],
    available_names: list[str],
    indicator_data: dict,
    start_date: str,
    end_date: str,
) -> None:
    selected_name = st.pills(
        "상세 지표 선택",
        available_names,
        default=available_names[0],
        selection_mode="single",
        key=f"{form_key}_detail_indicator",
    )
    if selected_name is None:
        st.info("확인할 지표를 선택해 주세요.")
        return

    if source_name == "ECOS" and selected_name == "원/달러 환율":
        data_mode = st.pills(
            "환율 데이터",
            ("실시간 시장환율", "ECOS 공식환율"),
            default="ECOS 공식환율",
            selection_mode="single",
            key=f"{form_key}_exchange_data_mode",
        )
        if data_mode == "실시간 시장환율":
            render_live_exchange_chart()
            return

        currency = st.pills(
            "환율 선택",
            tuple(EXCHANGE_CURRENCIES),
            default="원/달러",
            selection_mode="single",
            key=f"{form_key}_exchange_currency",
        )
        if currency is None:
            st.info("확인할 환율을 선택해 주세요.")
            return

        try:
            with st.spinner(f"{currency} 일별 환율을 조회하고 있습니다..."):
                chart_type, exchange_frame, description = load_exchange_data(
                    currency,
                    start_date,
                    end_date,
                )
        except Exception as error:
            st.error(f"{currency} 환율 조회 실패: {error}")
            return

        if exchange_frame.empty:
            st.warning("선택 기간에 조회 가능한 환율 데이터가 없습니다.")
            return

        range_options = {
            "1개월": 1,
            "3개월": 3,
            "6개월": 6,
            "1년": 12,
            "전체": None,
        }
        selected_range = st.pills(
            "차트 표시 기간",
            tuple(range_options),
            default="6개월",
            selection_mode="single",
            key=f"{form_key}_{currency}_chart_range",
        )
        months = range_options.get(selected_range or "6개월")
        display_frame = exchange_frame
        if months is not None:
            cutoff = exchange_frame["날짜"].max() - pd.DateOffset(
                months=months
            )
            display_frame = exchange_frame[
                exchange_frame["날짜"] >= cutoff
            ].reset_index(drop=True)

        if chart_type == "candlestick":
            st.caption(
                f"{description} · 단위: 원 · 출처: 한국은행 ECOS "
                f"통계코드 731Y003"
            )
            latest = display_frame.iloc[-1]
            ohlc_columns = st.columns(4)
            for column, label in zip(
                ohlc_columns,
                ("시가", "고가", "저가", "종가"),
            ):
                column.metric(
                    label,
                    f"{float(latest[label]):,.2f}원",
                )
            st.markdown(
                "<span style='color:#E53935'>■ 상승(종가 ≥ 시가)</span>"
                "&nbsp;&nbsp;&nbsp;"
                "<span style='color:#1565C0'>■ 하락(종가 < 시가)</span>",
                unsafe_allow_html=True,
            )
            st.altair_chart(
                candlestick_chart(display_frame, currency, unit="원"),
                width="stretch",
            )
        else:
            st.caption(
                f"{description} · 단위: 원 · 출처: 한국은행 ECOS "
                f"통계코드 731Y001 · OHLC 미제공으로 선 차트 표시"
            )
            st.line_chart(display_frame, x="날짜", y="환율")

        st.dataframe(
            display_frame,
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            f"{currency} CSV 다운로드",
            data=csv_bytes(exchange_frame),
            file_name=f"ECOS_{currency}_일별.csv",
            mime="text/csv",
            key=f"{form_key}_{currency}_download",
            on_click="ignore",
        )
        return

    spec = specs[selected_name]
    frame = indicator_data[selected_name]
    st.caption(
        f"{spec.description} · 단위: {spec.unit} · "
        f"{source_description(spec)}"
    )
    chart_frame = frame.copy()
    chart_frame["기간"] = chart_frame["날짜"].map(
        lambda date: format_period(spec, date, for_chart=True)
    )
    st.line_chart(chart_frame, x="기간", y="값")
    st.dataframe(
        chart_frame[["기간", "값"]].rename(
            columns={"값": f"{selected_name} ({spec.unit})"}
        ),
        width="stretch",
        hide_index=True,
    )
    st.download_button(
        f"{selected_name} CSV 다운로드",
        data=csv_bytes(chart_frame[["기간", "날짜", "값"]]),
        file_name=f"{source_name}_{selected_name}.csv",
        mime="text/csv",
        key=f"{form_key}_{selected_name}_download",
        on_click="ignore",
    )


def render_dashboard(
    *,
    source_name: str,
    form_key: str,
    specs: dict[str, Any],
    core_names: tuple[str, ...],
    supplementary_names: tuple[str, ...],
    loader: Callable,
) -> None:
    with st.form(form_key):
        start_column, end_column = st.columns(2)
        start_date = start_column.text_input(
            "조회 시작 월",
            value="202001",
            help="YYYYMM 형식으로 입력하세요. 예: 202001",
            key=f"{form_key}_start",
        )
        end_date = end_column.text_input(
            "조회 종료 월",
            value="202612",
            help="YYYYMM 형식으로 입력하세요. 예: 202612",
            key=f"{form_key}_end",
        )
        extra_labels = ", ".join(supplementary_names)
        include_supplementary = st.checkbox(
            f"추가 지표 포함 ({extra_labels})",
            value=False,
            key=f"{form_key}_extra",
        )
        search_button = st.form_submit_button(
            f"{source_name} 지표 조회",
            type="primary",
            width="stretch",
        )

    result_key = f"{form_key}_result"
    if search_button:
        selected_names = core_names
        if include_supplementary:
            selected_names += supplementary_names

        with st.spinner(f"{source_name} 거시경제 지표를 조회하고 있습니다..."):
            try:
                indicator_data, errors = loader(
                    start_date,
                    end_date,
                    selected_names,
                )
            except Exception as error:
                st.error(f"{source_name} 지표 조회 실패: {error}")
                return

        st.session_state[result_key] = {
            "start_date": start_date,
            "end_date": end_date,
            "selected_names": selected_names,
            "indicator_data": indicator_data,
            "errors": errors,
        }
        record_user_history(
            "macro_search",
            f"{source_name} 매크로 지표 조회",
            {
                "source": source_name,
                "start_month": start_date,
                "end_month": end_date,
                "indicators": list(selected_names),
                "successful_indicators": [
                    name
                    for name in selected_names
                    if name in indicator_data and not indicator_data[name].empty
                ],
                "errors": errors,
            },
        )
    elif result_key in st.session_state:
        saved_result = st.session_state[result_key]
        start_date = saved_result["start_date"]
        end_date = saved_result["end_date"]
        selected_names = saved_result["selected_names"]
        indicator_data = saved_result["indicator_data"]
        errors = saved_result["errors"]
    else:
        st.info("조회 기간과 지표를 설정한 뒤 조회해 주세요.")
        return

    for name, message in errors.items():
        st.warning(f"{name} 조회 실패: {message}")

    available_names = [
        name
        for name in selected_names
        if name in indicator_data and not indicator_data[name].empty
    ]
    if not available_names:
        st.error("조회 가능한 지표 데이터가 없습니다.")
        return

    render_current_metrics(
        source_name=source_name,
        form_key=form_key,
        specs=specs,
        selected_names=selected_names,
        start_date=start_date,
        end_date=end_date,
        loader=loader,
        fallback_data=indicator_data,
    )

    st.divider()
    st.subheader("상세 추이")
    render_detail_chart(
        source_name=source_name,
        form_key=form_key,
        specs=specs,
        available_names=available_names,
        indicator_data=indicator_data,
        start_date=start_date,
        end_date=end_date,
    )
    st.divider()
    st.subheader("주요 시장지수")
    render_market_indices(source_name, form_key, start_date, end_date)


st.title("📈 글로벌 매크로 지표")
st.caption("한국은행 ECOS · 미국 연방준비은행 FRED")

korea_tab, usa_tab = st.tabs(["🇰🇷 한국", "🇺🇸 미국"])

with korea_tab:
    st.subheader("한국 주요 거시경제 지표")
    render_dashboard(
        source_name="ECOS",
        form_key="ecos_search",
        specs=INDICATORS,
        core_names=CORE_INDICATORS,
        supplementary_names=SUPPLEMENTARY_INDICATORS,
        loader=load_ecos_indicators,
    )

with usa_tab:
    st.subheader("미국 주요 거시경제 지표")
    render_dashboard(
        source_name="FRED",
        form_key="fred_search",
        specs=FRED_INDICATORS,
        core_names=FRED_CORE_INDICATORS,
        supplementary_names=FRED_SUPPLEMENTARY_INDICATORS,
        loader=load_fred_indicators,
    )
