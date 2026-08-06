"""Streamlit 로그인 세션과 사용자 기록 연결 도우미."""

from __future__ import annotations

from typing import Any

import streamlit as st

from user_store import add_history, authenticate_user


AUTH_SESSION_KEY = "authenticated_user"


def current_user() -> dict[str, Any] | None:
    user = st.session_state.get(AUTH_SESSION_KEY)
    return user if isinstance(user, dict) and user.get("id") else None


def login(email: str, password: str) -> dict[str, Any] | None:
    user = authenticate_user(email, password)
    if user:
        st.session_state[AUTH_SESSION_KEY] = user
    return user


def set_authenticated_user(user: dict[str, Any]) -> None:
    st.session_state[AUTH_SESSION_KEY] = user


def logout() -> None:
    st.session_state.clear()


def render_user_sidebar() -> None:
    user = current_user()
    if not user:
        return
    with st.sidebar:
        st.caption("로그인 사용자")
        st.write(f"**{user['display_name']}**")
        st.caption(str(user["email"]))
        st.page_link("pages/4_User_History.py", label="내 분석 기록", icon="🗂️")
        if st.button("로그아웃", key="global_logout", width="stretch"):
            logout()
            st.switch_page("pages/0_Login.py")


def require_login() -> dict[str, Any]:
    user = current_user()
    if not user:
        st.warning("로그인 후 이용할 수 있는 페이지입니다.")
        left, right = st.columns(2)
        left.page_link("pages/0_Login.py", label="로그인", icon="🔐")
        right.page_link("pages/0_Sign_Up.py", label="회원가입", icon="✍️")
        st.stop()
    render_user_sidebar()
    return user


def record_user_history(
    event_type: str,
    title: str,
    payload: dict[str, Any] | None = None,
) -> int | None:
    user = current_user()
    if not user:
        return None
    return add_history(user["id"], event_type, title, payload)
