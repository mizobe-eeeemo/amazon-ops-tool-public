from __future__ import annotations

import hashlib

import streamlit as st

from lib.auth import get_secret, using_local_default_password
from lib.browser_use_client import get_browser_use_config
from lib.claude_client import claude_available, get_model
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
