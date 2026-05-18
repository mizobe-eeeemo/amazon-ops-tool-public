from __future__ import annotations


SELLER_ACCOUNT_A_LOGIN = "amazon_consulting@eeeemo.co.jp"
SELLER_ACCOUNT_B_LOGIN = "ac02@eeeemo.co.jp"

SELLER_ACCOUNT_LABELS = {
    "A": "アカウントA",
    "B": "アカウントB",
}


def normalize_seller_login(login_id: str) -> str:
    return login_id.strip().lower()


def infer_seller_account(login_id: str) -> str:
    normalized = normalize_seller_login(login_id)
    if normalized == SELLER_ACCOUNT_A_LOGIN:
        return "A"
    if normalized == SELLER_ACCOUNT_B_LOGIN:
        return "B"
    return ""


def seller_account_label(account_key: str | None) -> str:
    if not account_key:
        return "未設定"
    return SELLER_ACCOUNT_LABELS.get(account_key, account_key)
