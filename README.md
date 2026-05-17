# Amazon Ops Tool V1

Amazon運用チーム向けのStreamlit試作品です。

## 機能

- クライアント選択
- レポート作成ドラフト
- 商品登録AI整理
- Q&Aチャット
- 履歴確認

## Streamlit Cloud設定

Streamlit CloudのSecretsに以下を設定します。

```toml
APP_PASSWORD_HASH = "設定画面で生成したハッシュ"
ANTHROPIC_API_KEY = "sk-ant-api03-..."
ANTHROPIC_MODEL = "claude-sonnet-4-6"
```

`ANTHROPIC_API_KEY` が未設定でも、デモ回答で画面確認できます。

