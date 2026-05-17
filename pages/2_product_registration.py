from __future__ import annotations

from datetime import datetime

import streamlit as st

from lib.db import create_product_run, export_path
from lib.excel_handler import create_product_workbook
from lib.ui import require_workspace


client = require_workspace("商品登録AI整理")

st.title("商品登録AI整理")
st.caption("テンプレートExcelと商品情報テキストを受け取り、AI整理結果シートを追加します。")

template_file = st.file_uploader("商品登録テンプレートExcel（任意）", type=["xlsx"])
product_text = st.text_area(
    "クライアント提供の商品情報",
    height=240,
    placeholder="ChatWorkなどで届いた商品情報をそのまま貼り付けます。複数商品は空行で区切ると扱いやすいです。",
)
memo = st.text_area("補足メモ", height=100)
support_files = st.file_uploader(
    "補足ファイル（V1ではファイル名のみ履歴化）",
    type=["txt", "pdf", "docx", "png", "jpg", "jpeg"],
    accept_multiple_files=True,
)

if st.button("Excelを生成", type="primary"):
    if not product_text.strip():
        st.error("商品情報テキストを入力してください。")
    else:
        try:
            template_bytes = template_file.getvalue() if template_file else None
            workbook_bytes, summary = create_product_workbook(template_bytes, product_text, memo)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"product_registration_{client['id']}_{timestamp}.xlsx"
            export_path(filename).write_bytes(workbook_bytes)
            source_summary = f"商品数: {summary['product_count']} / 補足ファイル: {len(support_files or [])}件"
            create_product_run(client["id"], source_summary, filename, summary)
            st.session_state["latest_product_workbook"] = workbook_bytes
            st.session_state["latest_product_filename"] = filename
            st.session_state["latest_product_summary"] = summary
            st.success("Excelを生成しました。")
        except Exception as exc:
            st.error(f"Excel生成に失敗しました: {exc}")

summary = st.session_state.get("latest_product_summary")
if summary:
    st.subheader("生成結果")
    col1, col2 = st.columns(2)
    col1.metric("商品数", summary["product_count"])
    col2.metric("要確認あり", summary["needs_review"])
    st.download_button(
        "生成したExcelをダウンロード",
        data=st.session_state["latest_product_workbook"],
        file_name=st.session_state["latest_product_filename"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

