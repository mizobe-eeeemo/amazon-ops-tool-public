from __future__ import annotations

import os
from dataclasses import dataclass

from lib.auth import get_secret


@dataclass(frozen=True)
class BrowserUseConfig:
    api_key_configured: bool
    seller_central_profile_id: str | None
    seller_central_profile_id_b: str | None
    default_model: str


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
    default_model = _secret_or_env("BROWSER_USE_MODEL", "browser-use-2.0") or "browser-use-2.0"
    return BrowserUseConfig(
        api_key_configured=bool(api_key),
        seller_central_profile_id=profile_id,
        seller_central_profile_id_b=profile_id_b,
        default_model=default_model,
    )


def browser_use_available() -> bool:
    return get_browser_use_config().api_key_configured


def seller_central_profile_available() -> bool:
    config = get_browser_use_config()
    return config.api_key_configured and bool(config.seller_central_profile_id)


def seller_central_profile_b_available() -> bool:
    config = get_browser_use_config()
    return config.api_key_configured and bool(config.seller_central_profile_id_b)
