from __future__ import annotations

import hashlib
import hmac
from typing import Any

import streamlit as st


LOCAL_DEMO_PASSWORD = "local-demo"
LOCAL_DEMO_HASH = hashlib.sha256(LOCAL_DEMO_PASSWORD.encode("utf-8")).hexdigest()


def get_secret(name: str, default: Any = None) -> Any:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def configured_password_hash() -> str:
    return str(get_secret("APP_PASSWORD_HASH", LOCAL_DEMO_HASH))


def using_local_default_password() -> bool:
    return configured_password_hash() == LOCAL_DEMO_HASH


def verify_password(password: str) -> bool:
    return hmac.compare_digest(hash_password(password), configured_password_hash())


def render_login() -> None:
    st.title("Amazon運用 業務支援ツール V1")
    st.caption("チーム共通の合言葉でログインします。")

    if using_local_default_password():
        st.warning("ローカル確認用の合言葉を使っています。本番公開前に必ず変更してください。")
        st.info("ローカル確認用の合言葉: local-demo")

    with st.form("login_form"):
        password = st.text_input("合言葉", type="password")
        submitted = st.form_submit_button("ログイン")

    if submitted:
        if verify_password(password):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("合言葉が違います。もう一度入力してください。")


def require_login() -> None:
    if not st.session_state.get("authenticated"):
        render_login()
        st.stop()


def logout() -> None:
    st.session_state.pop("authenticated", None)
    st.session_state.pop("selected_client_id", None)
    st.rerun()

