from __future__ import annotations

import json
import re

import streamlit as st

from lib import browser_use_client
from lib.claude_client import complete
from lib.db import add_chat_message, get_chat_messages, get_clients
from lib.prompts import INTERNAL_KNOWLEDGE, QA_SYSTEM_PROMPT
from lib.seller_central_mapping import seller_account_label
from lib.ui import require_workspace


SESSION_ID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
BrowserUseRunResult = browser_use_client.BrowserUseRunResult
get_browser_use_config = browser_use_client.get_browser_use_config
get_browser_use_session = browser_use_client.get_browser_use_session
run_seller_central_access_check = browser_use_client.run_seller_central_access_check
run_seller_central_metrics_fetch = browser_use_client.run_seller_central_metrics_fetch
stop_browser_use_session = browser_use_client.stop_browser_use_session


def check_browser_use_downloads(session_id: str) -> BrowserUseRunResult:
    checker = getattr(browser_use_client, "check_browser_use_downloads", None)
    if checker:
        return checker(session_id)
    return BrowserUseRunResult(
        attempted=False,
        status="unavailable",
        summary="ダウンロード確認機能の読み込みがまだ完了していません。ページを再読み込みしてからもう一度お試しください。",
    )


def is_amazon_ads_report_pickup_question(question: str) -> bool:
    checker = getattr(browser_use_client, "is_amazon_ads_report_pickup_question", None)
    if checker:
        return bool(checker(question))
    keywords = ["レポート一覧", "既存レポート", "作成済みレポート", "保留中", "処理中", "該当行"]
    return any(keyword in question for keyword in keywords)


def is_visible_report_download_question(question: str) -> bool:
    checker = getattr(browser_use_client, "is_visible_report_download_question", None)
    if checker:
        return bool(checker(question))
    keywords = ["下向きダウンロードアイコンだけ", "下向き矢印を1回", "ダウンロードアイコンだけ", "矢印だけ"]
    return "ダウンロード" in question and any(keyword in question for keyword in keywords)


def run_amazon_ads_report_pickup(client: dict, question: str) -> BrowserUseRunResult:
    runner = getattr(browser_use_client, "run_amazon_ads_report_pickup", None)
    if runner:
        return runner(client, question)
    return browser_use_client.run_seller_central_metrics_fetch(client, question)


def run_visible_report_download(client: dict, question: str) -> BrowserUseRunResult:
    runner = getattr(browser_use_client, "run_visible_report_download", None)
    if runner:
        return runner(client, question)
    return run_amazon_ads_report_pickup(client, question)


client = require_workspace("Q&Aチャット")

st.title("Q&Aチャット")
st.caption("クライアント別に履歴が残る運用相談スレッドです。")
st.info(
    "現在の自動取得対象: "
    f"{client['name']} / Seller Centralショップ名: {client.get('shop_name') or '未設定'} / "
    f"Seller Central: {seller_account_label(client.get('seller_account_key'))}"
)

seller_fetch_enabled = st.toggle(
    "Seller Central実データ取得を試す",
    value=False,
    help="オンにすると、広告費などの質問でbrowser-useを起動します。APIクレジットを使用します。",
)
if seller_fetch_enabled:
    st.warning("browser-useを起動します。広告レポートの作成・ダウンロードは許可済みとして進めます。ログイン、2FA、課金確認、広告変更確認が必要な画面では取得を止めます。")

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

with st.expander("前回セッションのダウンロードだけ確認"):
    st.caption("ブラウザ操作を再実行せず、browser-useのダウンロード一覧だけを確認します。署名付きダウンロードURLは表示しません。")
    download_session_id = st.text_input(
        "ダウンロードを確認するセッションID",
        key="browser_use_download_session_id",
        placeholder="例: live.browser-use.com/session/ の末尾にあるUUID",
    )
    if st.button("このセッションのダウンロードを確認", key="inspect_browser_use_downloads"):
        download_result = check_browser_use_downloads(download_session_id)
        output = download_result.output if isinstance(download_result.output, dict) else {}
        output_status = output.get("status")
        if download_result.status == "error":
            st.error(download_result.summary)
            if download_result.error:
                st.caption(download_result.error)
        elif output_status == "success":
            st.success(download_result.summary)
        else:
            st.warning(download_result.summary)
        if output:
            st.json(output)

messages = get_chat_messages(client["id"], limit=30)
for message in messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message.get("source_context"):
            st.caption(message["source_context"])


def needs_seller_data(question: str) -> bool:
    keywords = ["売上", "広告", "ACOS", "CVR", "CTR", "インプレッション", "クリック", "期間", "先週", "今月", "先月", "レポート", "ダウンロード"]
    return any(keyword.lower() in question.lower() for keyword in keywords)


def needs_access_check(question: str) -> bool:
    text = question.lower()
    if is_amazon_ads_report_pickup_question(question):
        return False
    access_words = ["到達", "開ける", "開け", "画面", "ログイン", "2fa", "確認"]
    metric_words = ["広告費", "売上", "acos", "クリック", "cvr", "ctr", "インプレッション", "roas", "cpc"]
    access_only_words = ["だけ確認", "到達できるか", "到達確認", "数値取得はしない", "取得はしない", "取得しない"]
    if any(word in text for word in access_only_words):
        return True
    return any(word in text for word in access_words) and not any(word in text for word in metric_words)


def browser_use_session_id_from_text(text: str) -> str | None:
    match = SESSION_ID_PATTERN.search(text)
    return match.group(0) if match else None


def mentioned_other_client(question: str, selected_client: dict) -> dict | None:
    selected_id = selected_client.get("id")
    for candidate in get_clients():
        if candidate.get("id") == selected_id:
            continue
        names = [candidate.get("name") or "", candidate.get("shop_name") or ""]
        if any(name and len(name) >= 2 and name in question for name in names):
            return candidate
    return None


def client_mismatch_result(other_client: dict) -> BrowserUseRunResult:
    return BrowserUseRunResult(
        attempted=False,
        status="unavailable",
        summary=(
            "質問文の対象クライアントと、左メニューで選択中のクライアントが違うため、"
            "安全のためbrowser-useを起動しませんでした。"
        ),
        output={
            "status": "blocked",
            "summary": "選択中クライアントを確認してください。",
            "blocked_by": "selected_client_mismatch",
            "mentioned_client": other_client.get("name"),
            "mentioned_shop_name": other_client.get("shop_name"),
            "selected_client": client.get("name"),
            "selected_shop_name": client.get("shop_name"),
            "metrics": {},
            "notes": [
                "左メニューのクライアント選択を、質問文の対象クライアントに切り替えてから再実行してください。"
            ],
        },
    )


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
        data_note = (
            "この質問はSeller Centralデータ確認が必要そうです。下の自動取得結果を優先して、取れた値・取れなかった値を明確に分けて回答してください。"
            "sourceがdownloaded_ad_reportの場合は、広告レポート由来の提出用数値として扱ってください。"
            "estimated_metricsがある場合は、必ず「概算」と明記し、実広告費として扱わないでください。"
        )
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
            "この内容はSeller Centralの実績確認が必要です。"
            "自動取得が未実行または未完了の場合は、対象期間と見たい指標を指定してから、"
            "Seller Central実データ取得をオンにして進めます。"
        )
    return (
        "履歴に残しました。APIキー設定後はClaudeが文脈を踏まえて回答します。"
        "現時点のデモ回答としては、結論、根拠、次の確認事項の3点に分けて整理するのがよいです。"
    )


def yen(value: object) -> str:
    try:
        return f"{float(value):,.0f}円"
    except (TypeError, ValueError):
        return "未取得"


def number_text(value: object) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "未取得"


def percent_text(value: object) -> str:
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "未取得"


def automated_fetch_answer(fetch_result: BrowserUseRunResult) -> str:
    output = fetch_result.output if isinstance(fetch_result.output, dict) else {}
    metrics = output.get("metrics") if isinstance(output.get("metrics"), dict) else {}
    source = output.get("source")
    output_status = output.get("status")

    if source == "downloaded_ad_report" or output_status == "success":
        return (
            "広告レポート由来の数値を取得できました。\n\n"
            "| 指標 | 取得結果 |\n"
            "|---|---:|\n"
            f"| 広告費 | {yen(metrics.get('ad_spend'))} |\n"
            f"| 広告売上 | {yen(metrics.get('ad_sales'))} |\n"
            f"| ACOS | {percent_text(metrics.get('acos'))} |\n"
            f"| クリック数 | {number_text(metrics.get('clicks'))} |\n\n"
            "この値はダウンロード済み広告レポートの解析結果として扱えます。"
        )

    blocked_by = output.get("blocked_by")
    if blocked_by == "report_processing_not_ready":
        return (
            "該当レポートはまだ保留中または処理中でした。ブラウザ更新1回後も未完了のため、ここで停止しています。\n\n"
            "手動取得には切り替えません。時間を置いて、同じ既存レポート行のダウンロードアイコンだけを再確認します。"
        )
    if blocked_by == "matching_report_not_found":
        return (
            "短時間確認では、該当するキャンペーンレポート行を確定できませんでした。\n\n"
            "手動取得には切り替えません。次は、表示中のレポート一覧で「スポンサープロダクト広告 キャンペーン レポート」の行と下向き矢印だけに対象を絞って再実行します。"
        )
    if blocked_by == "matching_report_not_visible":
        return (
            "表示中画面では、対象のキャンペーンレポート行を確認できませんでした。\n\n"
            "手動取得には切り替えません。次は、Amazon Adsレポート一覧を表示した状態に寄せてから、同じ下向き矢印クリック専用タスクを再実行します。"
        )
    if blocked_by == "download_icon_not_available":
        return (
            "対象のキャンペーンレポート行は見えましたが、押せるダウンロードアイコンを確認できませんでした。\n\n"
            "手動取得には切り替えません。次は同じ行のダウンロードアイコン表示だけを再確認します。"
        )
    if blocked_by == "selected_client_mismatch":
        return (
            "質問文の対象クライアントと、左メニューで選択中のクライアントが違っていたため、browser-useを起動せずに止めました。\n\n"
            "左メニューのクライアント選択を対象クライアントに切り替えてから、同じ依頼文で再実行してください。"
        )

    return (
        "今回は広告レポートのダウンロード完了までは確認できませんでした。\n\n"
        "手動取得には切り替えません。見えているレポート一覧にはダウンロードアイコンがあるため、次は既存のキャンペーンレポート行の下向き矢印を1回押す専用タスクとして再実行します。"
    )


def fetch_status_label(fetch_result: BrowserUseRunResult | None) -> str:
    if fetch_result is None:
        return "未実行（実データ取得スイッチがオフ）"
    if isinstance(fetch_result.output, dict):
        output_status = fetch_result.output.get("status")
        if output_status == "success":
            if fetch_result.status == "stopped":
                return "完了（停止済み）"
            return "完了"
        if output_status == "partial":
            if fetch_result.status == "stopped":
                return "一部取得（停止済み）"
            return "一部取得"
        if output_status == "blocked":
            return "要確認"
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
            other_client = mentioned_other_client(question, client)
            if other_client:
                fetch_result = client_mismatch_result(other_client)
            else:
                session_id = browser_use_session_id_from_text(question)
                if session_id and "ダウンロード" in question:
                    fetch_result = check_browser_use_downloads(session_id)
                elif is_visible_report_download_question(question):
                    fetch_result = run_visible_report_download(client, question)
                elif is_amazon_ads_report_pickup_question(question):
                    fetch_result = run_amazon_ads_report_pickup(client, question)
                elif needs_access_check(question):
                    fetch_result = run_seller_central_access_check(client, question)
                else:
                    fetch_result = run_seller_central_metrics_fetch(client, question)
    if needs_seller_data(question) and fetch_result is not None:
        answer = automated_fetch_answer(fetch_result)
        result_used_api = False
    else:
        prompt = build_prompt(question, messages, fetch_result)
        result = complete(prompt, system=QA_SYSTEM_PROMPT, max_tokens=1400)
        answer = result.text or fallback_answer(question)
        result_used_api = result.used_api
    if needs_seller_data(question):
        if fetch_result and fetch_result.output:
            answer = f"{answer}\n\n---\n\n### browser-use取得結果\n\n```json\n{json.dumps(fetch_result.output, ensure_ascii=False, indent=2)}\n```"
        answer = f"{seller_central_check_block(fetch_result)}\n\n---\n\n{answer}"
    source_context = source_context_for(result_used_api, fetch_result)
    add_chat_message(client["id"], "assistant", answer, source_context=source_context)
    st.rerun()
