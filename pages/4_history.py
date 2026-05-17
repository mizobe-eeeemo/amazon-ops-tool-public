from __future__ import annotations

import json

import streamlit as st

from lib.db import get_chat_messages, get_product_runs, get_reports
from lib.ui import require_workspace


client = require_workspace("履歴")

st.title("履歴")
st.caption("選択中クライアントのレポート、商品登録、Q&A履歴を確認します。")

tab_reports, tab_products, tab_chat = st.tabs(["レポート", "商品登録", "Q&A"])

with tab_reports:
    reports = get_reports(client["id"], limit=50)
    if not reports:
        st.info("レポート履歴はまだありません。")
    for report in reports:
        with st.expander(f"{report['period']} / {report['report_type']} / {report['updated_at']}"):
            st.write(report.get("memo") or "メモなし")
            history = json.loads(report.get("edit_history_json") or "[]")
            st.caption(f"編集回数: {len(history)}")
            st.download_button(
                "HTMLをダウンロード",
                data=report["html"].encode("utf-8"),
                file_name=f"report_{report['id']}.html",
                mime="text/html",
                key=f"report_download_{report['id']}",
            )

with tab_products:
    product_runs = get_product_runs(client["id"], limit=50)
    if not product_runs:
        st.info("商品登録履歴はまだありません。")
    for run in product_runs:
        summary = json.loads(run["summary_json"])
        st.markdown(
            f"**{run['created_at']}**  \n"
            f"{run['source_summary']}  \n"
            f"出力: `{run['output_filename']}` / 商品数: {summary.get('product_count', 0)}"
        )

with tab_chat:
    messages = get_chat_messages(client["id"], limit=100)
    if not messages:
        st.info("Q&A履歴はまだありません。")
    for message in messages:
        speaker = "ユーザー" if message["role"] == "user" else "AI"
        st.markdown(f"**{speaker}** `{message['created_at']}`")
        st.write(message["content"])
        if message.get("source_context"):
            st.caption(message["source_context"])
        st.divider()

