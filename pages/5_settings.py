from __future__ import annotations

import hashlib

import streamlit as st

from lib.auth import get_secret, using_local_default_password
from lib.browser_use_client import get_browser_use_config
from lib.claude_client import claude_available, get_model
from lib.db import create_or_update_client, get_clients
from lib.seller_central_mapping import infer_seller_account, seller_account_label
from lib.settings import DB_PATH, DOCS_DIR, OUTPUT_DIR, ROOT_DIR
from lib.ui import require_workspace


require_workspace("設定")

st.title("設定")
st.caption("本番公開前に確認する項目です。APIキーそのものは表示しません。")

browser_use_config = get_browser_use_config()

st.subheader("環境ステータス")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Claude API", "設定済み" if claude_available() else "未設定")
col2.metric("合言葉", "初期値" if using_local_default_password() else "変更済み")
col3.metric("モデル", get_model())
col4.metric("browser-use", "設定済み" if browser_use_config.api_key_configured else "未設定")

if using_local_default_password():
    st.warning("合言葉がローカル確認用のままです。本番公開前に変更してください。")

st.subheader("パス")
st.code(
    f"""プロジェクト: {ROOT_DIR}
DB: {DB_PATH}
docs: {DOCS_DIR}
outputs: {OUTPUT_DIR}""",
    language="text",
)

st.subheader("合言葉ハッシュ生成")
new_password = st.text_input("新しい合言葉", type="password")
if new_password:
    digest = hashlib.sha256(new_password.encode("utf-8")).hexdigest()
    st.code(f'APP_PASSWORD_HASH = "{digest}"', language="toml")
    st.caption(".streamlit/secrets.toml に貼り付けてください。")

st.subheader("Secrets確認")
api_key = get_secret("ANTHROPIC_API_KEY")
if api_key and not str(api_key).startswith("sk-ant-api03-..."):
    st.success("ANTHROPIC_API_KEY は設定されています。")
else:
    st.info("ANTHROPIC_API_KEY は未設定です。APIなしでも画面デモは可能です。")

if browser_use_config.api_key_configured:
    st.success("BROWSER_USE_API_KEY は設定されています。")
else:
    st.info("BROWSER_USE_API_KEY は未設定です。Seller Central自動取得はまだ動きません。")

if browser_use_config.seller_central_profile_id:
    st.success("Seller CentralアカウントA用のbrowser-useプロファイルIDは設定されています。")
else:
    st.info("BROWSER_USE_PROFILE_ID_SELLER_CENTRAL は未設定です。アカウントAの2FA確認後に追加します。")

if browser_use_config.seller_central_profile_id_b:
    st.success("Seller CentralアカウントB用のbrowser-useプロファイルIDは設定されています。")
else:
    st.info("BROWSER_USE_PROFILE_ID_SELLER_CENTRAL_B は未設定です。アカウントBの2FA確認後に追加します。")

st.subheader("クライアント連携設定")
st.caption("スプレッドシートのC列を会社名、B列をSeller Central上のショップ名として登録します。")

clients = get_clients()
if clients:
    rows = [
        {
            "会社名": client["name"],
            "ショップ名": client.get("shop_name") or "",
            "Seller Central": seller_account_label(client.get("seller_account_key")),
            "ログインID": client.get("seller_login_id") or "",
        }
        for client in clients
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.info("クライアントはまだ登録されていません。")

with st.form("client_seller_mapping_form"):
    st.markdown("**クライアントを追加 / 更新**")
    company_name = st.text_input("会社名（スプレッドシートC列）")
    shop_name = st.text_input("ショップ名（スプレッドシートB列 / Seller Centralで選択する名前）")
    seller_login_id = st.text_input("Seller CentralログインID（スプレッドシートBL列）")
    memo = st.text_area("メモ", height=80)
    submitted = st.form_submit_button("保存")

if submitted:
    inferred_account = infer_seller_account(seller_login_id)
    if not company_name.strip():
        st.error("会社名を入力してください。")
    elif not shop_name.strip():
        st.error("ショップ名を入力してください。")
    elif not inferred_account:
        st.error("Seller CentralログインIDは amazon_consulting@eeeemo.co.jp または ac02@eeeemo.co.jp を入力してください。")
    else:
        client_id = create_or_update_client(
            name=company_name.strip(),
            shop_name=shop_name.strip(),
            seller_login_id=seller_login_id.strip(),
            seller_account_key=inferred_account,
            marketplace="Amazon.co.jp",
            memo=memo.strip(),
        )
        st.session_state["selected_client_id"] = client_id
        st.success(f"{company_name.strip()} をSeller Central{seller_account_label(inferred_account)}に紐づけました。")
        st.rerun()
