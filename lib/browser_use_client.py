from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from lib.auth import get_secret


@dataclass(frozen=True)
class BrowserUseConfig:
    api_key_configured: bool
    seller_central_profile_id: str | None
    seller_central_profile_id_b: str | None
    default_model: str
    max_cost_usd: str
    proxy_country_code: str | None
    poll_timeout_seconds: int


@dataclass(frozen=True)
class BrowserUseRunResult:
    attempted: bool
    status: str
    summary: str
    session_id: str | None = None
    live_url: str | None = None
    last_step_summary: str | None = None
    output: Any | None = None
    is_success: bool | None = None
    total_cost_usd: str | None = None
    error: str | None = None

    @property
    def finished(self) -> bool:
        return self.status in {"stopped", "timed_out", "error", "unavailable", "failed"}

    def prompt_context(self) -> str:
        payload = {
            "attempted": self.attempted,
            "status": self.status,
            "summary": self.summary,
            "session_id": self.session_id,
            "last_step_summary": self.last_step_summary,
            "output": self.output,
            "is_success": self.is_success,
            "total_cost_usd": self.total_cost_usd,
            "error": self.error,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


class BrowserUseError(RuntimeError):
    pass


def _secret_or_env(name: str, default: str | None = None) -> str | None:
    value = get_secret(name) or os.getenv(name) or default
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def get_browser_use_config() -> BrowserUseConfig:
    api_key = _secret_or_env("BROWSER_USE_API_KEY")
    profile_id = _secret_or_env("BROWSER_USE_PROFILE_ID_SELLER_CENTRAL")
    profile_id_b = _secret_or_env("BROWSER_USE_PROFILE_ID_SELLER_CENTRAL_B")
    default_model = _secret_or_env("BROWSER_USE_MODEL", "bu-mini") or "bu-mini"
    max_cost_usd = _secret_or_env("BROWSER_USE_MAX_COST_USD", "0.50") or "0.50"
    proxy_country_code = _secret_or_env("BROWSER_USE_PROXY_COUNTRY_CODE", "jp")
    if proxy_country_code and proxy_country_code.lower() in {"none", "off", "false"}:
        proxy_country_code = None
    timeout_raw = _secret_or_env("BROWSER_USE_POLL_TIMEOUT_SECONDS", "90") or "90"
    try:
        poll_timeout_seconds = max(10, min(180, int(timeout_raw)))
    except ValueError:
        poll_timeout_seconds = 90
    return BrowserUseConfig(
        api_key_configured=bool(api_key),
        seller_central_profile_id=profile_id,
        seller_central_profile_id_b=profile_id_b,
        default_model=default_model,
        max_cost_usd=max_cost_usd,
        proxy_country_code=proxy_country_code,
        poll_timeout_seconds=poll_timeout_seconds,
    )


def browser_use_available() -> bool:
    return get_browser_use_config().api_key_configured


def seller_central_profile_available() -> bool:
    config = get_browser_use_config()
    return config.api_key_configured and bool(config.seller_central_profile_id)


def seller_central_profile_b_available() -> bool:
    config = get_browser_use_config()
    return config.api_key_configured and bool(config.seller_central_profile_id_b)


def profile_available_for_account(account_key: str | None) -> bool:
    config = get_browser_use_config()
    if not config.api_key_configured:
        return False
    if account_key == "A":
        return bool(config.seller_central_profile_id)
    if account_key == "B":
        return bool(config.seller_central_profile_id_b)
    return False


def seller_central_profile_id_for_account(account_key: str | None) -> str | None:
    config = get_browser_use_config()
    if account_key == "A":
        return config.seller_central_profile_id
    if account_key == "B":
        return config.seller_central_profile_id_b
    return None


def _get_api_key() -> str | None:
    return _secret_or_env("BROWSER_USE_API_KEY")


def _normalize_v3_model(model: str) -> str:
    mapping = {
        "browser-use-2.0": "bu-mini",
        "browser-use-llm": "bu-mini",
        "claude-sonnet-4-6": "claude-sonnet-4.6",
        "claude-sonnet-4-5-20250929": "claude-sonnet-4.6",
        "claude-opus-4-7": "claude-opus-4.7",
    }
    return mapping.get(model, model)


def _browser_use_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    api_key = _get_api_key()
    if not api_key:
        raise BrowserUseError("BROWSER_USE_API_KEY is not configured.")

    url = f"https://api.browser-use.com{path}"
    body = None
    headers = {"X-Browser-Use-API-Key": api_key}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise BrowserUseError(f"browser-use API error {exc.code}: {error_body[:500]}") from exc
    except URLError as exc:
        raise BrowserUseError(f"browser-use API connection error: {exc.reason}") from exc

    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BrowserUseError("browser-use API returned invalid JSON.") from exc


SELLER_CENTRAL_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "description": "success, partial, needs_user_login, needs_confirmation, unavailable, or error",
        },
        "summary": {"type": "string"},
        "shop_name": {"type": ["string", "null"]},
        "period": {"type": ["string", "null"]},
        "currency": {"type": ["string", "null"]},
        "metrics": {
            "type": "object",
            "properties": {
                "ad_spend": {"type": ["number", "string", "null"]},
                "ad_sales": {"type": ["number", "string", "null"]},
                "acos": {"type": ["number", "string", "null"]},
                "roas": {"type": ["number", "string", "null"]},
                "impressions": {"type": ["number", "string", "null"]},
                "clicks": {"type": ["number", "string", "null"]},
                "ctr": {"type": ["number", "string", "null"]},
                "cpc": {"type": ["number", "string", "null"]},
                "orders": {"type": ["number", "string", "null"]},
                "cvr": {"type": ["number", "string", "null"]},
            },
            "additionalProperties": True,
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["status", "summary", "shop_name", "period", "metrics", "notes"],
    "additionalProperties": True,
}


def _build_seller_central_task(client: dict[str, Any], question: str) -> str:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    company_name = client.get("name") or ""
    shop_name = client.get("shop_name") or ""
    marketplace = client.get("marketplace") or "Amazon.co.jp"
    return f"""
You are controlling an already-authenticated browser profile for Amazon Seller Central Japan.

Safety rules:
- Read-only navigation only.
- Do not type, request, reveal, or store passwords, 2FA codes, API keys, recovery codes, or other secrets.
- If Amazon asks for login, password, passkey, CAPTCHA, or 2FA, stop immediately and return status "needs_user_login".
- Do not change bids, budgets, campaigns, listings, account settings, billing settings, or payments.
- Do not click any button that confirms a purchase, subscription, payment, campaign launch, paid upgrade, or billing change.
- If a paid confirmation or billing confirmation appears, stop immediately and return status "needs_confirmation".

Client:
- Company name: {company_name}
- Seller Central shop/store name to select: {shop_name}
- Marketplace: {marketplace}
- Today in Japan: {today}
- User question: {question}

Task:
1. Open Amazon Seller Central Japan. Use https://sellercentral.amazon.co.jp/ as the starting point.
2. Confirm that the active seller/store matches the shop/store name above. If there is an account/store selector and an exact or very close match exists, choose it.
3. Find the advertising performance data needed for the user question. If the question says "先月", use the last completed calendar month relative to Today in Japan. If the exact period cannot be selected, use the closest available period and explain it in notes.
4. Prefer these metrics when visible: advertising spend, ad sales, ACOS, ROAS, impressions, clicks, CTR, CPC, orders, and CVR.
5. Return only the requested structured result. Use null for metrics that are not visible.
"""


def _result_from_session(session: dict[str, Any], summary: str | None = None) -> BrowserUseRunResult:
    status = str(session.get("status") or "unknown")
    output = session.get("output")
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            pass
    output_summary = ""
    if isinstance(output, dict):
        output_summary = str(output.get("summary") or "")
    if not output_summary:
        output_summary = summary or str(session.get("lastStepSummary") or "")
    if not output_summary:
        output_summary = "browser-useの実行結果を取得しました。"
    return BrowserUseRunResult(
        attempted=True,
        status=status,
        summary=output_summary,
        session_id=session.get("id"),
        live_url=session.get("liveUrl"),
        last_step_summary=session.get("lastStepSummary"),
        output=output,
        is_success=session.get("isTaskSuccessful"),
        total_cost_usd=str(session.get("totalCostUsd")) if session.get("totalCostUsd") is not None else None,
    )


def run_seller_central_metrics_fetch(client: dict[str, Any], question: str) -> BrowserUseRunResult:
    config = get_browser_use_config()
    if not config.api_key_configured:
        return BrowserUseRunResult(
            attempted=False,
            status="unavailable",
            summary="BROWSER_USE_API_KEYが未設定のため、Seller Central自動取得は実行していません。",
        )

    account_key = client.get("seller_account_key")
    profile_id = seller_central_profile_id_for_account(account_key)
    if not profile_id:
        return BrowserUseRunResult(
            attempted=False,
            status="unavailable",
            summary="選択中クライアントに対応するbrowser-useプロフィールIDが未設定です。",
        )
    if not client.get("shop_name"):
        return BrowserUseRunResult(
            attempted=False,
            status="unavailable",
            summary="選択中クライアントのショップ名が未設定です。",
        )

    payload: dict[str, Any] = {
        "task": _build_seller_central_task(client, question),
        "model": _normalize_v3_model(config.default_model),
        "keepAlive": False,
        "maxCostUsd": config.max_cost_usd,
        "profileId": profile_id,
        "proxyCountryCode": config.proxy_country_code,
        "outputSchema": SELLER_CENTRAL_OUTPUT_SCHEMA,
        "enableRecording": False,
        "skills": True,
        "agentmail": False,
        "codeMode": False,
        "cacheScript": False,
        "autoHeal": True,
    }

    try:
        session = _browser_use_request("POST", "/api/v3/sessions", payload)
        session_id = session.get("id")
        if not session_id:
            return BrowserUseRunResult(
                attempted=True,
                status="failed",
                summary="browser-useセッションIDを取得できませんでした。",
                output=session,
            )

        final_statuses = {"stopped", "timed_out", "error"}
        deadline = time.monotonic() + config.poll_timeout_seconds
        while str(session.get("status") or "") not in final_statuses and time.monotonic() < deadline:
            time.sleep(4)
            session = _browser_use_request("GET", f"/api/v3/sessions/{session_id}")

        if str(session.get("status") or "") not in final_statuses:
            return _result_from_session(
                session,
                summary="browser-useはまだ実行中です。ライブ画面または再読み込み後の状態確認が必要です。",
            )
        return _result_from_session(session)
    except BrowserUseError as exc:
        return BrowserUseRunResult(
            attempted=True,
            status="error",
            summary="browser-use API呼び出しに失敗しました。",
            error=str(exc),
        )
