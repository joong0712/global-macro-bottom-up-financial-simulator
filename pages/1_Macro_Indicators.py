"""한국 ECOS와 미국 FRED 거시경제 지표 대시보드."""

from typing import Any, Callable

import streamlit as st

from ecos import (
    CORE_INDICATORS,
    INDICATORS,
    SUPPLEMENTARY_INDICATORS,
    get_macro_indicators,
)
from fred import (
    FRED_CORE_INDICATORS,
    FRED_INDICATORS,
    FRED_SUPPLEMENTARY_INDICATORS,
    get_fred_indicators,
)


st.set_page_config(
    page_title="매크로 지표",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_ecos_indicators(
    start_date: str,
    end_date: str,
    names: tuple[str, ...],
):
    return get_macro_indicators(start_date, end_date, names)


@st.cache_data(ttl=3600, show_spinner=False)
def load_fred_indicators(
    start_date: str,
    end_date: str,
    names: tuple[str, ...],
):
    return get_fred_indicators(start_date, end_date, names)


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


def csv_bytes(frame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


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

    if not search_button:
        st.info("조회 기간과 지표를 설정한 뒤 조회해 주세요.")
        return

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

    st.subheader("현재 지표")
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
                st.metric(
                    label=name,
                    value=format_value(spec, current_value),
                    delta=delta,
                    help=spec.description,
                )
                st.caption(
                    f"기준 시점: {format_period(spec, latest['날짜'])}"
                )

    st.divider()
    st.subheader("상세 추이")
    detail_tabs = st.tabs(available_names)

    for detail_tab, name in zip(detail_tabs, available_names):
        with detail_tab:
            spec = specs[name]
            frame = indicator_data[name]
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
                    columns={"값": f"{name} ({spec.unit})"}
                ),
                width="stretch",
                hide_index=True,
            )
            st.download_button(
                f"{name} CSV 다운로드",
                data=csv_bytes(
                    chart_frame[["기간", "날짜", "값"]]
                ),
                file_name=f"{source_name}_{name}.csv",
                mime="text/csv",
                key=f"{form_key}_{name}_download",
                on_click="ignore",
            )


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
