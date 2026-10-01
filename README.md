# Discord Bot

さばに症候群のScrapboxプロジェクトを支援するDiscordBotです。

## ローカルでの実行方法

1. 依存パッケージをインストール

   ```bash
   pip install -r requirements.txt
   ```

2. プロジェクトルートに`.env`を用意し、必要な環境変数を設定

   ```env
   DISCORD_TOKEN=...
   DISCORD_DEFAULT_CHANNEL_ID=...
   DISCORD_ALERT_CHANNEL_ID=...
   COSENSE_PROJECT=...
   COSENSE_SID=...
   ...
   ```

3. `.env`を環境変数として`main.py`を実行

   ```bash
   set -a; source .env; set +a; python main.py
   ```
