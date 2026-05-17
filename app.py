from __future__ import annotations

import streamlit as st

from lib.auth import require_login
from lib.db import create_client, get_recent_activity
from lib.ui import render_sidebar, select_client_card, setup_page


setup_page("ダッシュボード")
require_login()

st.title("Amazon運用 業務支援ツール V1")
st.caption("5月末デモに向けた最小版です。クライアントを選んで、各機能を確認できます。")

if "selected_client_id" not in st.session_state:
    st.subheader("クライアント選択")
    client = select_client_card()
    if st.button("このクライアントで始める", type="primary"):
        st.rerun()
    st.stop()

client = render_sidebar()

st.header(client["name"])
st.write(client.get("memo") or "このクライアントのワークスペースです。")

col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("pages/1_report.py", label="レポート作成を開く", icon="📊")
with col2:
    st.page_link("pages/2_product_registration.py", label="商品登録AI整理を開く", icon="📦")
with col3:
    st.page_link("pages/3_qa_chat.py", label="Q&Aチャットを開く", icon="💬")

st.divider()

left, right = st.columns([2, 1])
with left:
    st.subheader("最近の作業履歴")
    activities = get_recent_activity(client["id"], limit=8)
    if not activities:
        st.info("まだ履歴がありません。まずはレポート作成かQ&Aを試してください。")
    for item in activities:
        st.markdown(
            f"**{item['feature']}** / {item['action']}  \n"
            f"{item['detail']}  \n"
            f"`{item['created_at']}`"
        )

with right:
    st.subheader("クライアント追加")
    with st.form("create_client_form"):
        name = st.text_input("クライアント名")
        marketplace = st.text_input("マーケットプレイス", value="Amazon.co.jp")
        memo = st.text_area("メモ", height=90)
        submitted = st.form_submit_button("追加")
    if submitted:
        if not name.strip():
            st.error("クライアント名を入力してください。")
        else:
            try:
                client_id = create_client(name.strip(), marketplace.strip() or "Amazon.co.jp", memo.strip())
                st.session_state["selected_client_id"] = client_id
                st.success("クライアントを追加しました。")
                st.rerun()
            except Exception as exc:
                st.error(f"追加に失敗しました: {exc}")

