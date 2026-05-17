from __future__ import annotations

import streamlit as st

from lib.auth import logout, require_login
from lib.db import get_client, get_clients, init_db


def setup_page(title: str) -> None:
    st.set_page_config(page_title=f"{title} | Amazon運用V1", page_icon="📊", layout="wide")
    st.markdown(
        """
        <style>
          [data-testid="stSidebarNav"] {
            display: none;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    init_db()


def select_client_card() -> dict | None:
    clients = get_clients()
    if not clients:
        st.error("クライアントがまだ登録されていません。")
        return None

    selected = st.selectbox(
        "クライアントを選択",
        clients,
        index=0,
        format_func=lambda client: client["name"],
    )
    st.session_state["selected_client_id"] = selected["id"]
    return selected


def render_sidebar() -> dict:
    clients = get_clients()
    selected_id = st.session_state.get("selected_client_id")
    if not selected_id and clients:
        selected_id = clients[0]["id"]
        st.session_state["selected_client_id"] = selected_id

    current_index = 0
    for index, client in enumerate(clients):
        if client["id"] == selected_id:
            current_index = index
            break

    with st.sidebar:
        st.subheader("ワークスペース")
        selected = st.selectbox(
            "クライアント",
            clients,
            index=current_index,
            format_func=lambda client: client["name"],
            key="sidebar_client_select",
        )
        st.session_state["selected_client_id"] = selected["id"]
        st.caption(selected.get("marketplace", "Amazon.co.jp"))

        st.divider()
        st.page_link("app.py", label="ダッシュボード", icon="🏠")
        st.page_link("pages/1_report.py", label="レポート作成", icon="📊")
        st.page_link("pages/2_product_registration.py", label="商品登録AI整理", icon="📦")
        st.page_link("pages/3_qa_chat.py", label="Q&Aチャット", icon="💬")
        st.page_link("pages/4_history.py", label="履歴", icon="📜")
        st.page_link("pages/5_settings.py", label="設定", icon="⚙️")

        st.divider()
        if st.button("ログアウト"):
            logout()

    return selected


def require_workspace(title: str) -> dict:
    setup_page(title)
    require_login()

    selected_id = st.session_state.get("selected_client_id")
    if not selected_id:
        st.title("クライアント選択")
        client = select_client_card()
        if st.button("このクライアントで始める", type="primary"):
            st.rerun()
        st.stop()

    client = get_client(int(selected_id))
    if client is None:
        st.session_state.pop("selected_client_id", None)
        st.warning("選択中のクライアントが見つかりません。もう一度選んでください。")
        st.stop()

    sidebar_client = render_sidebar()
    st.caption(f"選択中: {sidebar_client['name']}")
    return sidebar_client
