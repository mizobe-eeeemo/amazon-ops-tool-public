from __future__ import annotations

import json

import streamlit as st

from lib.browser_use_client import (
    BrowserUseRunResult,
    get_browser_use_session,
    get_browser_use_config,
    run_seller_central_access_check,
    run_seller_central_metrics_fetch,
    stop_browser_use_session,
)
from lib.claude_client import complete
from lib.db import add_chat_message, get_chat_messages
from lib.prompts import INTERNAL_KNOWLEDGE, QA_SYSTEM_PROMPT
from lib.seller_central_mapping import seller_account_label
from lib.ui import require_workspace


client = require_workspace("Q&Aチャット")

st.title("Q&Aチャット")
st.caption("クライアント別に履歴が残る運用相談スレッドです。")

seller_fetch_enabled = st.toggle(
    "Seller Central実データ取得を試す",
    value=False,
    help="オンにすると、広告費などの質問でbrowser-useを起動します。APIクレジットを使用します。",
)
if seller_fetch_enabled:
    st.warning("browser-useを起動します。ログイン、2FA、課金確認、変更確認が必要な画面では取得を止める指示を入れています。")

with st.expander("実行中のbrowser-useセッションを停止"):
    st.caption("セッションIDはライブURLの末尾にあるUUIDです。例: live.browser-use.com/session/この部分")
    stop_session_id = st.text_input("停止するセッションID", key="browser_use_stop_session_id")
    if st.button("このセッションを停止", key="stop_browser_use_session"):
        stop_result = stop_browser_use_session(stop_session_id)
        if stop_result.status == "error":
            st.error(stop_result.summary)
            if stop_result.error:
                st.caption(stop_result.error)
        else:
            st.success(f"{stop_result.summary} ステータス: {stop_result.status}")

with st.expander("browser-useセッション状態を確認"):
    st.caption("停止済みセッションでも、最新のステータス・最終ステップ・スクリーンショットURLを確認できます。")
    inspect_session_id = st.text_input("確認するセッションID", key="browser_use_inspect_session_id")
    if st.button("このセッションを確認", key="inspect_browser_use_session"):
        inspect_result = get_browser_use_session(inspect_session_id)
        if inspect_result.status == "error":
            st.error(inspect_result.summary)
            if inspect_result.error:
                st.caption(inspect_result.error)
        else:
            st.json(
                {
                    "status": inspect_result.status,
                    "is_success": inspect_result.is_success,
                    "last_step": inspect_result.last_step_summary,
                    "cost": inspect_result.total_cost_usd,
                    "screenshot": "取得あり" if inspect_result.screenshot_url else "なし",
                }
            )
            if inspect_result.screenshot_url:
                st.link_button("最終スクリーンショットを開く", inspect_result.screenshot_url)
                st.image(inspect_result.screenshot_url, caption="browser-useの最終画面")

messages = get_chat_messages(client["id"], limit=30)
for message in messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message.get("source_context"):
            st.caption(message["source_context"])


def needs_seller_data(question: str) -> bool:
    keywords = ["売上", "広告", "ACOS", "CVR", "CTR", "インプレッション", "クリック", "期間", "先週", "今月", "先月"]
    return any(keyword.lower() in question.lower() for keyword in keywords)


def needs_access_check(question: str) -> bool:
    text = question.lower()
    access_words = ["到達", "開ける", "開け", "画面", "ログイン", "2fa", "確認"]
    metric_words = ["広告費", "売上", "acos", "クリック", "cvr", "ctr", "インプレッション", "roas", "cpc"]
    return any(word in text for word in access_words) and not any(word in text for word in metric_words)


def profile_available_for_account(account_key: str | None) -> bool:
    config = get_browser_use_config()
    if not config.api_key_configured:
        return False
    if account_key == "A":
        return bool(config.seller_central_profile_id)
    if account_key == "B":
        return bool(config.seller_central_profile_id_b)
    return False


def seller_data_context(fetch_result: BrowserUseRunResult | None) -> str:
    if fetch_result is None:
        return "未実行"
    return fetch_result.prompt_context()


def build_prompt(question: str, history: list[dict], fetch_result: BrowserUseRunResult | None = None) -> str:
    recent = "\n".join(f"{item['role']}: {item['content']}" for item in history[-12:])
    account_key = client.get("seller_account_key") or ""
    shop_name = client.get("shop_name") or "未設定"
    browser_profile_status = "設定済み" if profile_available_for_account(account_key) else "未設定"
    if needs_seller_data(question) and fetch_result:
        data_note = "この質問はSeller Centralデータ確認が必要そうです。下の自動取得結果を優先して、取れた値・取れなかった値を明確に分けて回答してください。"
    elif needs_seller_data(question):
        data_note = "この質問はSeller Centralデータ確認が必要そうです。自動取得結果が未実行の場合は、対象ショップと使用アカウントを確認し、必要な指標を案内してください。"
    else:
        data_note = "この質問は履歴と社内ナレッジ中心で回答できます。"
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

【Seller Central自動取得結果】
{seller_data_context(fetch_result)}

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


def fetch_status_label(fetch_result: BrowserUseRunResult | None) -> str:
    if fetch_result is None:
        return "未実行（実データ取得スイッチがオフ）"
    if fetch_result.status == "stopped":
        if fetch_result.is_success is True:
            return "完了"
        return "停止"
    if fetch_result.status == "timed_out":
        return "時間切れ"
    if fetch_result.status in {"running", "created", "idle"}:
        return "実行中"
    if fetch_result.status == "unavailable":
        return "未実行"
    if fetch_result.status == "error":
        return "エラー"
    return fetch_result.status


def seller_central_check_block(fetch_result: BrowserUseRunResult | None = None) -> str:
    account_key = client.get("seller_account_key") or ""
    shop_name = client.get("shop_name") or "未設定"
    profile_status = "設定済み" if profile_available_for_account(account_key) else "未設定"
    lines = [
        "## Seller Central連携確認\n\n"
        f"- 対象ショップ名: {shop_name}\n"
        f"- 使用Seller Central: {seller_account_label(account_key)}\n"
        f"- browser-useプロフィール: {profile_status}\n"
        f"- 自動取得ステータス: {fetch_status_label(fetch_result)}"
    ]
    if fetch_result:
        if fetch_result.summary:
            lines.append(f"- 取得メモ: {fetch_result.summary}")
        if fetch_result.total_cost_usd:
            lines.append(f"- browser-use推定コスト: ${fetch_result.total_cost_usd}")
        if fetch_result.live_url:
            lines.append(f"- 実行画面: {fetch_result.live_url}")
        if fetch_result.screenshot_url:
            lines.append("- 最終スクリーンショット: 取得あり（Q&A画面のセッション状態確認から開けます）")
    return "\n".join(lines)


def source_context_for(result_used_api: bool, fetch_result: BrowserUseRunResult | None) -> str:
    parts = ["Claude APIで回答" if result_used_api else "デモ回答"]
    if fetch_result:
        parts.append(f"browser-use: {fetch_status_label(fetch_result)}")
    elif seller_fetch_enabled:
        parts.append("browser-use: 未実行")
    return " / ".join(parts)


question = st.chat_input("質問を入力")
if question:
    add_chat_message(client["id"], "user", question)
    fetch_result = None
    if needs_seller_data(question) and seller_fetch_enabled:
        with st.spinner("browser-useでSeller Centralを確認しています。ログインや2FAが必要になった場合は取得を止めます。"):
            if needs_access_check(question):
                fetch_result = run_seller_central_access_check(client, question)
            else:
                fetch_result = run_seller_central_metrics_fetch(client, question)
    prompt = build_prompt(question, messages, fetch_result)
    result = complete(prompt, system=QA_SYSTEM_PROMPT, max_tokens=1400)
    answer = result.text or fallback_answer(question)
    if needs_seller_data(question):
        if fetch_result and fetch_result.output:
            answer = f"{answer}\n\n---\n\n### browser-use取得結果\n\n```json\n{json.dumps(fetch_result.output, ensure_ascii=False, indent=2)}\n```"
        answer = f"{seller_central_check_block(fetch_result)}\n\n---\n\n{answer}"
    source_context = source_context_for(result.used_api, fetch_result)
    add_chat_message(client["id"], "assistant", answer, source_context=source_context)
    st.rerun()
