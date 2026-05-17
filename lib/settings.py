from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs"
DOCS_DIR = ROOT_DIR / "docs"
DB_PATH = DATA_DIR / "app.db"

DEFAULT_CLIENTS = [
    {
        "name": "サンプルクライアントA",
        "marketplace": "Amazon.co.jp",
        "memo": "月次レポートと商品登録の動作確認用です。",
    },
    {
        "name": "サンプルクライアントB",
        "marketplace": "Amazon.co.jp",
        "memo": "Q&Aチャットの履歴確認用です。",
    },
]

