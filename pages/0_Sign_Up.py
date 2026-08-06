"""사용자 회원가입 페이지."""

import streamlit as st

from auth import current_user, set_authenticated_user
from user_store import UserAlreadyExistsError, create_user


st.set_page_config(page_title="회원가입", page_icon="✍️", layout="centered")

st.title("✍️ 회원가입")
st.caption("분석 조건과 AI 보고서를 사용자별로 저장할 계정을 만듭니다.")

if current_user():
    st.info("이미 로그인되어 있습니다.")
    st.page_link("app.py", label="대시보드로 이동", icon="📊")
else:
    with st.form("signup_form"):
        display_name = st.text_input(
            "이름",
            placeholder="표시할 이름",
            max_chars=30,
        )
        email = st.text_input(
            "이메일",
            placeholder="name@example.com",
        )
        password = st.text_input(
            "비밀번호",
            type="password",
            help="영문자와 숫자를 포함해 8자 이상 입력해 주세요.",
        )
        password_confirm = st.text_input(
            "비밀번호 확인",
            type="password",
        )
        consent = st.checkbox(
            "서비스 이용을 위해 이메일과 분석 기록을 저장하는 데 동의합니다."
        )
        submitted = st.form_submit_button(
            "계정 만들기",
            type="primary",
            width="stretch",
        )

    if submitted:
        if password != password_confirm:
            st.error("비밀번호 확인이 일치하지 않습니다.")
        elif not consent:
            st.error("회원가입을 위해 정보 저장에 동의해 주세요.")
        else:
            try:
                user = create_user(email, display_name, password)
            except UserAlreadyExistsError as error:
                st.error(str(error))
            except ValueError as error:
                st.error(str(error))
            except Exception:
                st.error("회원가입 처리 중 오류가 발생했습니다.")
            else:
                set_authenticated_user(user)
                st.success("회원가입이 완료되었습니다.")
                st.switch_page("app.py")

    st.divider()
    st.page_link("pages/0_Login.py", label="로그인으로 돌아가기", icon="🔐")
