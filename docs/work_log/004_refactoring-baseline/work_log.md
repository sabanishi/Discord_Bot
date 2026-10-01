# 2026-10-01

## リファクタ前の基準確認

リファクタリングに着手する前の基準状態を確認した。コードや仕様は変更していない。

### テスト実行結果

- `python -m unittest discover -v`
  - 80件中73件成功。
  - 7件は外部サービスへの接続時にDNS解決に失敗してエラーとなった。
  - エラーになった対象は、Cosenseのライブテスト4件、攻略Wikiのライブテスト2件、Gyazoを含むライブテスト1件。
  - 失敗原因はテスト assertion ではなく、`scrapbox.io`、`bluearchive.wikiru.jp` などの名前解決ができなかったこと。
- 外部APIを使用しないテスト
  - `tests/` とライブテストを除く `tactical_challenge/tests/` を実行。
  - 合計69件、全件成功。

### 現行構成と主な責務

- `main.py`
  - 環境変数の読み込み・検証
  - 日記ページのテンプレート展開、作成、更新確認
  - Discord通知
  - 日記、戦術対抗戦、リンク警告の定期実行ループ
  - Discordイベント登録とBot起動
  - Webサーバー起動
- `web_server.py`
  - Flaskアプリ、UserScript配信ルート、戦術対抗戦API登録、Webサーバースレッド起動
- `link_warning.py`
  - Scrapboxリンク数取得、除外ページ解析、警告状態管理
- `check_link_warnings.py`
  - リンク警告機能の手動・繰り返し実行用CLI
- `tactical_challenge/`
  - Wiki解析、略称解析、対象ページ解析、差分生成、Cosense/Gyazo通信、対象ページ更新、HTTP APIを機能単位で分離済み

### 現行の起動上の特徴

- `main.py` のトップレベルで環境変数を読み込み、検証する。
- `main.py` のトップレベルでWebサーバーを起動し、Discord Botを起動する。
- `web_server.py` はFlaskアプリをモジュールとして公開しており、テストはこれを直接利用している。
- 戦術対抗戦の定期実行とUserScriptからの手動実行は、同じ `refactor_target_pages` を利用している。

### 現行の主要設定

- 必須設定: `DISCORD_TOKEN`、`DISCORD_DEFAULT_CHANNEL_ID`、`DISCORD_ALERT_CHANNEL_ID`、`COSENSE_PROJECT`、`COSENSE_SID`
- 戦術対抗戦で追加要求される設定: `GYAZO_ACCESS_TOKEN`
- 日記の実行時刻: `CREATE_PAGE_TIME`（既定 `7:00`）、`CHECK_PAGE_TIME`（既定 `21:15`）
- リンク警告: `LINK_WARNING_ENABLED`、`LINK_WARNING_INTERVAL_MINUTES`、`LINK_WARNING_THRESHOLD`、`LINK_WARNING_RESOLVE_THRESHOLD`、`LINK_WARNING_CONFIG_PAGE`
- メンション対象: `MENTION_TARGET`

### リファクタ時の基準

- 通常テスト69件が成功する状態を維持する。
- 外部ライブテストはネットワークおよび認証情報の状態に依存するため、通常テストとは分けて評価する。
- 通知文、実行時刻、環境変数の意味、外部APIへの書き込み内容は仕様変更なしで維持する。
- 今後の変更では、まず仕様を表すテストを追加し、未実装状態での失敗を確認してから最小限の実装を行う。
