from __future__ import annotations

import streamlit as st

from lib.browser_use_client import get_browser_use_config
from lib.claude_client import complete
from lib.db import add_chat_message, get_chat_messages
from lib.prompts import INTERNAL_KNOWLEDGE, QA_SYSTEM_PROMPT
from lib.seller_central_mapping import seller_account_label
from lib.ui import require_workspace


client = require_workspace("Q&Aチャット")

st.title("Q&Aチャット")
st.caption("クライアント別に履歴が残る運用相談スレッドです。")

messages = get_chat_messages(client["id"], limit=30)
for message in messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message.get("source_context"):
            st.caption(message["source_context"])


def needs_seller_data(question: str) -> bool:
    keywords = ["売上", "広告", "ACOS", "CVR", "CTR", "インプレッション", "クリック", "期間", "先週", "今月", "先月"]
    return any(keyword.lower() in question.lower() for keyword in keywords)


def profile_available_for_account(account_key: str | None) -> bool:
    config = get_browser_use_config()
    if not config.api_key_configured:
        return False
    if account_key == "A":
        return bool(config.seller_central_profile_id)
    if account_key == "B":
        return bool(config.seller_central_profile_id_b)
    return False


def build_prompt(question: str, history: list[dict]) -> str:
    recent = "\n".join(f"{item['role']}: {item['content']}" for item in history[-12:])
    account_key = client.get("seller_account_key") or ""
    shop_name = client.get("shop_name") or "未設定"
    browser_profile_status = "設定済み" if profile_available_for_account(account_key) else "未設定"
    data_note = (
        "この質問はSeller Centralデータ確認が必要そうです。V1現段階では自動取得の実行前に、対象ショップと使用アカウントを確認してください。"
        if needs_seller_data(question)
        else "この質問は履歴と社内ナレッジ中心で回答できます。"
    )
    return f"""
【クライアント】
{client['name']}

【Seller Central連携設定】
対象ショップ名: {shop_name}
使用Seller Central: {seller_account_label(account_key)}
browser-useプロフィール: {browser_profile_status}

【社内ナレッジ】
{INTERNAL_KNOWLEDGE}

【直近履歴】
{recent or "なし"}

【データ取得判定】
{data_note}

【今回の質問】
{question}
"""


def fallback_answer(question: str) -> str:
    if needs_seller_data(question):
        return (
            "この内容はSeller Centralの実績確認が必要です。V1の現段階では自動取得をまだ接続していないため、"
            "対象期間、売上、広告費、ACOS、クリック数、CVRが分かるCSVを確認できると分析できます。"
            "まずは期間と見たい指標を指定してください。"
        )
    return (
        "履歴に残しました。APIキー設定後はClaudeが文脈を踏まえて回答します。"
        "現時点のデモ回答としては、結論、根拠、次の確認事項の3点に分けて整理するのがよいです。"
    )


def seller_central_check_block() -> str:
    account_key = client.get("seller_account_key") or ""
    shop_name = client.get("shop_name") or "未設定"
    profile_status = "設定済み" if profile_available_for_account(account_key) else "未設定"
    return (
        "## Seller Central連携確認\n\n"
        f"- 対象ショップ名: {shop_name}\n"
        f"- 使用Seller Central: {seller_account_label(account_key)}\n"
        f"- browser-useプロフィール: {profile_status}\n"
        "- 自動取得ステータス: 実行前（次の実装でSeller Central取得を接続）"
    )


question = st.chat_input("質問を入力")
if question:
    add_chat_message(client["id"], "user", question)
    prompt = build_prompt(question, messages)
    result = complete(prompt, system=QA_SYSTEM_PROMPT, max_tokens=1400)
    answer = result.text or fallback_answer(question)
    if needs_seller_data(question):
        answer = f"{seller_central_check_block()}\n\n---\n\n{answer}"
    source_context = (
        "Claude APIで回答 / Seller Central連携確認済み"
        if result.used_api and needs_seller_data(question)
        else "Claude APIで回答"
        if result.used_api
        else "デモ回答 / Seller Central自動取得は未接続"
    )
    add_chat_message(client["id"], "assistant", answer, source_context=source_context)
    st.rerun()
