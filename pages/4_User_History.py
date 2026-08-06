"""로그인 사용자의 분석·시나리오·AI 보고서 기록 페이지."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from auth import require_login
from user_store import delete_all_history, delete_history, list_history


st.set_page_config(page_title="내 분석 기록", page_icon="🗂️", layout="wide")
user = require_login()

EVENT_LABELS = {
    "macro_search": "매크로 조회",
    "company_financials": "기업 재무제표",
    "integrated_analysis": "통합 분석",
    "scenario": "시나리오",
    "ai_report": "AI 보고서",
}


def display_time(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")


st.title("🗂️ 내 분석 기록")
st.caption(
    "조회한 데이터, 저장한 시나리오와 생성한 AI 보고서를 사용자별로 확인합니다."
)
filter_options = {"전체": None, **{label: key for key, label in EVENT_LABELS.items()}}
selected_label = st.selectbox("기록 종류", tuple(filter_options))
records = list_history(
    user["id"],
    event_type=filter_options[selected_label],
    limit=200,
)

if not records:
    st.info("저장된 기록이 없습니다. 분석 페이지에서 조회하거나 기록을 저장해 주세요.")
else:
    summary_frame = pd.DataFrame(
        [
            {
                "기록 시각": display_time(record["created_at"]),
                "종류": EVENT_LABELS.get(record["event_type"], record["event_type"]),
                "제목": record["title"],
            }
            for record in records
        ]
    )
    st.dataframe(summary_frame, width="stretch", hide_index=True)

    st.download_button(
        "기록 목록 CSV 다운로드",
        data=summary_frame.to_csv(index=False).encode("utf-8-sig"),
        file_name="내_분석_기록.csv",
        mime="text/csv",
        on_click="ignore",
    )

    st.divider()
    for record in records:
        label = EVENT_LABELS.get(record["event_type"], record["event_type"])
        expander_title = (
            f"{display_time(record['created_at'])} · {label} · {record['title']}"
        )
        with st.expander(expander_title):
            payload = record["payload"]
            if record["event_type"] == "ai_report" and payload.get("report"):
                st.markdown(str(payload["report"]))
                remaining = {
                    key: value for key, value in payload.items() if key != "report"
                }
                if remaining:
                    st.json(remaining)
            else:
                st.json(payload)
            if st.button(
                "이 기록 삭제",
                key=f"delete_history_{record['id']}",
            ):
                delete_history(user["id"], record["id"])
                st.rerun()

    st.divider()
    with st.expander("기록 전체 삭제"):
        confirmed = st.checkbox(
            "삭제한 기록은 복구할 수 없음을 확인했습니다.",
            key="confirm_delete_all_history",
        )
        if st.button(
            "전체 기록 삭제",
            type="primary",
            disabled=not confirmed,
        ):
            deleted_count = delete_all_history(user["id"])
            st.success(f"{deleted_count}개의 기록을 삭제했습니다.")
            st.rerun()
