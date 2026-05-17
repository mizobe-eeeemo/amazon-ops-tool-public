from __future__ import annotations

import streamlit as st

from lib.db import create_report_run, update_report_run
from lib.report_generator import generate_report_html, parse_uploaded_csv
from lib.ui import require_workspace


client = require_workspace("レポート作成")

st.title("レポート作成")
st.caption("CSVアップロードまたはデモデータからHTMLドラフトを作り、自然文の編集指示で更新します。")

with st.form("report_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        period = st.selectbox("対象期間", ["今月", "先月", "任意期間"], index=1)
    with col2:
        report_type = st.selectbox("レポートタイプ", ["月次", "週次", "カスタム"])
    with col3:
        output_format = st.selectbox("最終形式", ["HTML", "PowerPoint（次フェーズ）", "PDF（次フェーズ）"])

    custom_period = ""
    if period == "任意期間":
        custom_period = st.text_input("任意期間", placeholder="例: 2026/5/1〜2026/5/15")
    memo = st.text_area("補足メモ", placeholder="例: 新商品Aの広告効果を強調したい")
    uploaded_csv = st.file_uploader("実績CSV（任意）", type=["csv"])
    submitted = st.form_submit_button("ドラフト生成", type="primary")

if submitted:
    raw = uploaded_csv.getvalue() if uploaded_csv else None
    rows = parse_uploaded_csv(raw)
    selected_period = custom_period if period == "任意期間" and custom_period else period
    html_text, result = generate_report_html(
        client_name=client["name"],
        period=selected_period,
        report_type=report_type,
        memo=memo,
        rows=rows,
    )
    report_id = create_report_run(
        client_id=client["id"],
        period=selected_period,
        report_type=report_type,
        output_format=output_format,
        memo=memo,
        html=html_text,
    )
    st.session_state["current_report_id"] = report_id
    st.session_state["current_report_html"] = html_text
    st.session_state["current_report_rows"] = rows
    st.session_state["current_report_meta"] = {
        "period": selected_period,
        "report_type": report_type,
        "memo": memo,
    }
    if result.used_api:
        st.success("Claude APIでドラフトを生成しました。")
    else:
        st.info("APIキー未設定またはAPI呼び出し不可のため、デモ用ドラフトを生成しました。")

html_text = st.session_state.get("current_report_html")
if html_text:
    st.subheader("HTMLプレビュー")
    st.html(
        f"""
        <style>
          .report-preview {{ line-height: 1.75; color: #0f172a; }}
          .report-preview h1,
          .report-preview h2,
          .report-preview h3 {{ color: #1e3a8a; }}
          .report-preview section {{ border-bottom: 1px solid #e2e8f0; padding: 16px 0; }}
          .report-preview pre {{ background: #f8fafc; padding: 12px; white-space: pre-wrap; border: 1px solid #e2e8f0; }}
          .report-preview blockquote {{ border-left: 4px solid #2563eb; margin-left: 0; padding-left: 12px; color: #334155; }}
        </style>
        {html_text}
        """
    )

    st.download_button(
        "HTMLをダウンロード",
        data=html_text.encode("utf-8"),
        file_name=f"report_{client['id']}.html",
        mime="text/html",
    )

    st.subheader("編集指示")
    edit_instruction = st.text_area(
        "自然文で修正内容を入力",
        placeholder="例: 来月の打ち手をもう少し具体的にして。前年同月比の観点も追加して。",
    )
    if st.button("編集指示を反映", type="primary"):
        if not edit_instruction.strip():
            st.error("編集指示を入力してください。")
        else:
            meta = st.session_state.get("current_report_meta", {})
            rows = st.session_state.get("current_report_rows", [])
            updated_html, result = generate_report_html(
                client_name=client["name"],
                period=meta.get("period", "未指定"),
                report_type=meta.get("report_type", "月次"),
                memo=meta.get("memo", ""),
                rows=rows,
                edit_instruction=edit_instruction,
                previous_html=html_text,
            )
            st.session_state["current_report_html"] = updated_html
            update_report_run(
                report_id=int(st.session_state["current_report_id"]),
                client_id=client["id"],
                html=updated_html,
                instruction=edit_instruction,
            )
            st.success("編集指示を反映しました。")
            st.rerun()
