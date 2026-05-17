from __future__ import annotations

import hashlib

import streamlit as st

from lib.auth import get_secret, using_local_default_password
from lib.claude_client import claude_available, get_model
from lib.settings import DB_PATH, DOCS_DIR, OUTPUT_DIR, ROOT_DIR
from lib.ui import require_workspace


require_workspace("設定")

st.title("設定")
st.caption("本番公開前に確認する項目です。APIキーそのものは表示しません。")

st.subheader("環境ステータス")
col1, col2, col3 = st.columns(3)
col1.metric("Claude API", "設定済み" if claude_available() else "未設定")
col2.metric("合言葉", "初期値" if using_local_default_password() else "変更済み")
col3.metric("モデル", get_model())

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

