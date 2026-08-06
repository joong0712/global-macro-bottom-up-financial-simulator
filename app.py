"""글로벌 매크로-바텀업 금융 시뮬레이터 메인 페이지."""

import streamlit as st

from auth import current_user, render_user_sidebar


st.set_page_config(
    page_title="글로벌 매크로-바텀업 금융 시뮬레이터",
    page_icon="📊",
    layout="wide",
)

user = current_user()
if not user:
    st.title("📊 글로벌 매크로-바텀업 금융 시뮬레이터")
    st.write(
        "기업 재무와 매크로 변수를 함께 분석하고 개인별 분석 기록을 관리합니다."
    )
    st.info("분석 기능을 이용하려면 로그인하거나 새 계정을 만들어 주세요.")
    login_column, signup_column = st.columns(2)
    login_column.page_link(
        "pages/0_Login.py",
        label="로그인",
        icon="🔐",
    )
    signup_column.page_link(
        "pages/0_Sign_Up.py",
        label="회원가입",
        icon="✍️",
    )
    st.stop()

render_user_sidebar()

st.title("📊 글로벌 매크로-바텀업 금융 시뮬레이터")
st.caption(f"{user['display_name']}님, 환영합니다.")
st.write(
    "왼쪽 사이드바에서 분석할 페이지를 선택하세요. "
    "매크로, 기업 재무제표, 기업-매크로 통합 비교를 확인할 수 있습니다."
)

ecos_column, dart_column, integrated_column, history_column = st.columns(4)

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

with history_column:
    st.subheader("🗂️ 내 분석 기록")
    st.write("조회, 시나리오와 AI 보고서 기록을 사용자별로 확인합니다.")
    st.page_link(
        "pages/4_User_History.py",
        label="내 기록 페이지",
        icon="🗂️",
    )
