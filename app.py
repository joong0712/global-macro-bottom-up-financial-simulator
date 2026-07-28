"""글로벌 매크로-바텀업 금융 시뮬레이터 메인 페이지."""

import streamlit as st


st.set_page_config(
    page_title="글로벌 매크로-바텀업 금융 시뮬레이터",
    page_icon="📊",
    layout="wide",
)

st.title("📊 글로벌 매크로-바텀업 금융 시뮬레이터")
st.write(
    "왼쪽 사이드바에서 분석할 페이지를 선택하세요. "
    "매크로, 기업 재무제표, 기업-매크로 통합 비교를 확인할 수 있습니다."
)

ecos_column, dart_column, integrated_column = st.columns(3)

with ecos_column:
    st.subheader("🌏 글로벌 매크로 지표")
    st.write(
        "ECOS의 한국 지표와 FRED의 미국 지표를 국가별 탭에서 조회합니다."
    )
    st.page_link(
        "pages/1_Macro_Indicators.py",
        label="매크로 지표 페이지",
        icon="📈",
    )

with dart_column:
    st.subheader("🏢 기업 재무제표")
    st.write("Open DART에서 기업의 분기·연도별 연결재무제표를 조회합니다.")
    st.page_link(
        "pages/2_Company_Financials.py",
        label="기업 재무제표 페이지",
        icon="📑",
    )

with integrated_column:
    st.subheader("🔗 기업-매크로 통합")
    st.write("기업 실적과 선택한 매크로 지표의 흐름을 한 화면에서 비교합니다.")
    st.page_link(
        "pages/3_Integrated_Analysis.py",
        label="통합 분석 페이지",
        icon="🔗",
    )
