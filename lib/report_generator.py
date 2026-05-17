from __future__ import annotations

import csv
import html
from datetime import datetime
from io import StringIO

from lib.claude_client import ClaudeResult, complete
from lib.prompts import REPORT_SYSTEM_PROMPT


def parse_uploaded_csv(raw: bytes | None) -> list[dict[str, str]]:
    if not raw:
        return []
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(StringIO(text))
    return [dict(row) for row in reader]


def summarize_rows(rows: list[dict[str, str]], limit: int = 8) -> str:
    if not rows:
        return "アップロードCSVなし。現在はデモ用の仮データで作成します。"

    headers = list(rows[0].keys())
    lines = [", ".join(headers)]
    for row in rows[:limit]:
        lines.append(", ".join(str(row.get(header, "")) for header in headers))
    if len(rows) > limit:
        lines.append(f"...ほか {len(rows) - limit} 行")
    return "\n".join(lines)


def build_report_prompt(
    client_name: str,
    period: str,
    report_type: str,
    memo: str,
    data_summary: str,
    edit_instruction: str | None = None,
    previous_html: str | None = None,
) -> str:
    edit_block = ""
    if edit_instruction:
        edit_block = f"""
【編集指示】
{edit_instruction}

【前回ドラフトHTML】
{previous_html or ""}
"""

    return f"""
以下の条件でAmazon運用レポートのHTML本文を作成してください。
HTMLは section / h2 / h3 / p / ul / li / table 程度のシンプルなタグだけで出力してください。

【クライアント名】
{client_name}

【対象期間】
{period}

【レポート種別】
{report_type}

【補足メモ】
{memo or "なし"}

【データ概要】
{data_summary}
{edit_block}
"""


def fallback_report_html(
    client_name: str,
    period: str,
    report_type: str,
    memo: str,
    data_summary: str,
    edit_instruction: str | None = None,
    previous_html: str | None = None,
) -> str:
    safe_client = html.escape(client_name)
    safe_period = html.escape(period)
    safe_type = html.escape(report_type)
    safe_memo = html.escape(memo or "なし")
    safe_data = html.escape(data_summary)
    edited = ""
    if edit_instruction:
        edited = f"""
        <section>
          <h2>編集反映メモ</h2>
          <p>以下の指示を反映する前提で、ドラフトを更新しました。</p>
          <blockquote>{html.escape(edit_instruction)}</blockquote>
        </section>
        """

    return f"""
    <article class="report-preview">
      <section>
        <h1>{safe_client} {safe_type}レポート</h1>
        <p><strong>対象期間:</strong> {safe_period}</p>
        <p><strong>作成日時:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
      </section>
      <section>
        <h2>サマリー</h2>
        <ul>
          <li>売上・広告・商品ページの主要指標を確認し、変化の大きい項目から優先して見ます。</li>
          <li>現時点ではSeller Central自動取得の接続前のため、アップロードデータまたは仮データで確認しています。</li>
          <li>本番ではbrowser-useで取得した実績データを使い、前月比・前年比を入れます。</li>
        </ul>
      </section>
      <section>
        <h2>運用メモ</h2>
        <p>{safe_memo}</p>
      </section>
      <section>
        <h2>データ確認</h2>
        <pre>{safe_data}</pre>
      </section>
      {edited}
      <section>
        <h2>次の打ち手</h2>
        <ol>
          <li>変化の大きいASIN・キャンペーンを特定し、要因を確認します。</li>
          <li>成果が出ているキーワードの予算・入札を優先的に調整します。</li>
          <li>商品ページ側の訴求、画像、レビュー状況を確認し、広告以外の改善余地も見ます。</li>
        </ol>
      </section>
    </article>
    """


def generate_report_html(
    client_name: str,
    period: str,
    report_type: str,
    memo: str,
    rows: list[dict[str, str]],
    edit_instruction: str | None = None,
    previous_html: str | None = None,
) -> tuple[str, ClaudeResult]:
    data_summary = summarize_rows(rows)
    prompt = build_report_prompt(
        client_name=client_name,
        period=period,
        report_type=report_type,
        memo=memo,
        data_summary=data_summary,
        edit_instruction=edit_instruction,
        previous_html=previous_html,
    )
    result = complete(prompt, system=REPORT_SYSTEM_PROMPT, max_tokens=2400)
    if result.text:
        return result.text, result

    html_text = fallback_report_html(
        client_name=client_name,
        period=period,
        report_type=report_type,
        memo=memo,
        data_summary=data_summary,
        edit_instruction=edit_instruction,
        previous_html=previous_html,
    )
    return html_text, result

