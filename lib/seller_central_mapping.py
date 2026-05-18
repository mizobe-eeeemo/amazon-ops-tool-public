from __future__ import annotations

import csv
import io


SELLER_ACCOUNT_A_LOGIN = "amazon_consulting@eeeemo.co.jp"
SELLER_ACCOUNT_B_LOGIN = "ac02@eeeemo.co.jp"

COMPANY_NAME_INDEX = 2
SHOP_NAME_INDEX = 3
SELLER_LOGIN_INDEX = 63

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


def parse_client_mapping_csv(csv_text: str, has_header: bool = True) -> tuple[list[dict[str, str]], list[str]]:
    rows = csv.reader(io.StringIO(csv_text))
    parsed: list[dict[str, str]] = []
    warnings: list[str] = []

    for row_number, row in enumerate(rows, start=1):
        if has_header and row_number == 1:
            continue
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) <= SELLER_LOGIN_INDEX:
            warnings.append(f"{row_number}行目: BL列まで存在しないためスキップしました。")
            continue

        company_name = row[COMPANY_NAME_INDEX].strip()
        shop_name = row[SHOP_NAME_INDEX].strip()
        seller_login_id = row[SELLER_LOGIN_INDEX].strip()
        seller_account_key = infer_seller_account(seller_login_id)

        if not company_name:
            warnings.append(f"{row_number}行目: C列の会社名が空のためスキップしました。")
            continue
        if not shop_name:
            warnings.append(f"{row_number}行目: D列のショップ名が空のためスキップしました。")
            continue
        if not seller_account_key:
            warnings.append(f"{row_number}行目: BL列のログインIDがA/B判定対象外のためスキップしました。")
            continue

        parsed.append(
            {
                "company_name": company_name,
                "shop_name": shop_name,
                "seller_login_id": seller_login_id,
                "seller_account_key": seller_account_key,
            }
        )

    return parsed, warnings
