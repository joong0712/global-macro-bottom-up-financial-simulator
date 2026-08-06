"""사용자 로그인 페이지."""

import streamlit as st

from auth import current_user, login, logout


st.set_page_config(page_title="로그인", page_icon="🔐", layout="centered")

st.title("🔐 로그인")
st.caption("개인 분석 기록을 안전하게 구분하기 위해 로그인합니다.")

user = current_user()
if user:
    st.success(f"{user['display_name']}님으로 로그인되어 있습니다.")
    st.page_link("app.py", label="대시보드로 이동", icon="📊")
    if st.button("로그아웃", width="stretch"):
        logout()
        st.rerun()
else:
    with st.form("login_form"):
        email = st.text_input(
            "이메일",
            placeholder="name@example.com",
        )
        password = st.text_input(
            "비밀번호",
            type="password",
            placeholder="비밀번호를 입력하세요",
        )
        submitted = st.form_submit_button(
            "로그인",
            type="primary",
            width="stretch",
        )

    if submitted:
        if not email.strip() or not password:
            st.error("이메일과 비밀번호를 모두 입력해 주세요.")
        else:
            try:
                authenticated = login(email, password)
            except Exception:
                st.error("MySQL 연결을 확인한 후 다시 시도해 주세요.")
            else:
                if authenticated:
                    st.success("로그인되었습니다.")
                    st.switch_page("app.py")
                else:
                    st.error(
                        "이메일 또는 비밀번호가 올바르지 않습니다."
                    )

    st.divider()
    st.write("아직 계정이 없나요?")
    st.page_link("pages/0_Sign_Up.py", label="회원가입", icon="✍️")
