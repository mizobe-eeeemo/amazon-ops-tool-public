from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st

from lib.auth import get_secret


@dataclass
class ClaudeResult:
    text: str
    used_api: bool
    error: str | None = None


def get_api_key() -> str | None:
    key = get_secret("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not key or str(key).startswith("sk-ant-api03-..."):
        return None
    return str(key)


def get_model() -> str:
    return str(get_secret("ANTHROPIC_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")))


def claude_available() -> bool:
    return bool(get_api_key())


def complete(prompt: str, system: str = "", max_tokens: int = 1800) -> ClaudeResult:
    api_key = get_api_key()
    if not api_key:
        return ClaudeResult(text="", used_api=False, error="ANTHROPIC_API_KEY is not configured.")

    try:
        from anthropic import Anthropic
    except Exception as exc:
        return ClaudeResult(text="", used_api=False, error=f"anthropic package is not installed: {exc}")

    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=get_model(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        chunks: list[str] = []
        for block in message.content:
            if getattr(block, "type", None) == "text":
                chunks.append(block.text)
        return ClaudeResult(text="\n".join(chunks).strip(), used_api=True)
    except Exception as exc:
        st.warning("Claude API呼び出しに失敗したため、デモ用の仮生成に切り替えます。")
        return ClaudeResult(text="", used_api=False, error=str(exc))

