from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.settings import DATA_DIR, DB_PATH, DEFAULT_CLIENTS


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterable[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                marketplace TEXT NOT NULL,
                memo TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                feature TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            );

            CREATE TABLE IF NOT EXISTS report_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                period TEXT NOT NULL,
                report_type TEXT NOT NULL,
                output_format TEXT NOT NULL,
                memo TEXT DEFAULT '',
                html TEXT NOT NULL,
                edit_history_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            );

            CREATE TABLE IF NOT EXISTS product_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                source_summary TEXT NOT NULL,
                output_filename TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                source_context TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            );
            """
        )
    seed_clients()


def seed_clients() -> None:
    with connect() as conn:
        for client in DEFAULT_CLIENTS:
            conn.execute(
                """
                INSERT OR IGNORE INTO clients (name, marketplace, memo, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (client["name"], client["marketplace"], client["memo"], utc_now()),
            )


def get_clients() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def get_client(client_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    return row_to_dict(row)


def create_client(name: str, marketplace: str, memo: str = "") -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO clients (name, marketplace, memo, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, marketplace, memo, utc_now()),
        )
    return int(cursor.lastrowid)


def log_activity(client_id: int, feature: str, action: str, detail: str = "") -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO activity_logs (client_id, feature, action, detail, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (client_id, feature, action, detail, utc_now()),
        )


def get_recent_activity(client_id: int, limit: int = 10) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM activity_logs
            WHERE client_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (client_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def create_report_run(
    client_id: int,
    period: str,
    report_type: str,
    output_format: str,
    memo: str,
    html: str,
    edit_history: list[dict[str, str]] | None = None,
) -> int:
    now = utc_now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO report_runs
                (client_id, period, report_type, output_format, memo, html,
                 edit_history_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                period,
                report_type,
                output_format,
                memo,
                html,
                json.dumps(edit_history or [], ensure_ascii=False),
                now,
                now,
            ),
        )
    log_activity(client_id, "レポート", "ドラフト生成", f"{period} / {report_type}")
    return int(cursor.lastrowid)


def update_report_run(report_id: int, client_id: int, html: str, instruction: str) -> None:
    with connect() as conn:
        row = conn.execute(
            "SELECT edit_history_json FROM report_runs WHERE id = ?",
            (report_id,),
        ).fetchone()
        history = json.loads(row["edit_history_json"]) if row else []
        history.append({"instruction": instruction, "updated_at": utc_now()})
        conn.execute(
            """
            UPDATE report_runs
            SET html = ?, edit_history_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (html, json.dumps(history, ensure_ascii=False), utc_now(), report_id),
        )
    log_activity(client_id, "レポート", "編集指示", instruction[:80])


def get_reports(client_id: int, limit: int = 30) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM report_runs
            WHERE client_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (client_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def create_product_run(
    client_id: int,
    source_summary: str,
    output_filename: str,
    summary: dict[str, Any],
) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO product_runs
                (client_id, source_summary, output_filename, summary_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                client_id,
                source_summary,
                output_filename,
                json.dumps(summary, ensure_ascii=False),
                utc_now(),
            ),
        )
    log_activity(client_id, "商品登録", "Excel生成", source_summary[:80])
    return int(cursor.lastrowid)


def get_product_runs(client_id: int, limit: int = 30) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM product_runs
            WHERE client_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (client_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def add_chat_message(
    client_id: int,
    role: str,
    content: str,
    source_context: str = "",
) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO chat_messages
                (client_id, role, content, source_context, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (client_id, role, content, source_context, utc_now()),
        )
    if role == "assistant":
        log_activity(client_id, "Q&A", "回答生成", content[:80])
    return int(cursor.lastrowid)


def get_chat_messages(client_id: int, limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM chat_messages
            WHERE client_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (client_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def export_path(filename: str) -> Path:
    from lib.settings import OUTPUT_DIR

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR / filename

