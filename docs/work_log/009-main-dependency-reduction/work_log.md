# main.pyのDiscord依存削減

## 目的

`main.py`からDiscordクライアントの実装詳細を切り離し、起動入口とDiscordライフサイクルの責務を分離する。

## 対象

- 対象機能: Discordクライアントの生成、イベント、共有HTTPセッション、定期タスク登録
- 対象ファイル: `main.py`、`app/client_tasks.py`、新設するDiscordクライアントモジュール、関連テスト
- 関連仕様書: `docs/specifications/アプリケーション仕様.md`

## 作業記録

### 2026-10-01

#### 実施内容

- Discordクライアントの依存を`main.py`から分離するテストを先に追加した。
- `app/discord_bot.py`を追加し、Discordクライアント生成、通知、HTTPセッション、イベント、定期タスク登録を集約した。
- `main.py`から`aiohttp`、`discord`、`DiscordNotifier`、`register_scheduled_tasks`の直接依存を削除した。
- Discordライフサイクルの既存テストを`app.discord_bot`境界のテストへ移した。
- `RuntimeState.validate_env()`を追加し、環境変数検証を実行時状態の責務として集約した。
- `main.py`から環境検証関数の直接依存を削除した。
- `main.py`のグローバル`runtime`、空の`RuntimeState`、`initialize_runtime()`を削除した。
- `main()`内でRuntimeStateを生成し、検証後にDiscord起動処理へ渡す構成にした。
- `initialize_runtime()`内で`RuntimeState.validate_env()`を実行し、検証済みの状態だけを返すようにした。
- `main.py`から環境検証呼び出しを削除した。
- `app/web_server.py`のグローバルFlaskアプリ、サーバー、スレッド状態を`WebServer`クラスへ集約した。
- `main.py`で`WebServer`を生成し、Discordクライアントへ同じインスタンスを渡す構成にした。
- Web API登録関数とグローバル停止関数への依存を削除した。

#### 確認結果

- 実行したテスト: `tests/unit` 119件、`tests/integration` 6件
- テスト結果: 125件成功
- `python -m compileall`と`git diff --check`も成功
- `RuntimeState.validate_env()`移行後の関連テスト8件が成功
- グローバルruntime削除後の関連テスト8件、構文チェック、`git diff --check`が成功
- 初期化時検証への変更後の関連テスト8件が成功
- Webサーバー変更後、ユニット119件・統合6件が成功
- 構文チェックと`git diff --check`が成功
- `WebServer`内部のサーバーとスレッド状態を`State`へ集約し、個別属性の初期化・リセット重複を整理した。
- 変更後のWebサーバー関連6件、構文チェック、`git diff --check`が成功した。
- `DiscordBot`をクラス主体へ整理し、イベントハンドラを属性として保持する`create_client()`と`run()`の二重構造を削除した。
- `main.py`は`DiscordBot(runtime, web_server).run()`を呼び出す構成にした。
- 変更後のDiscord・起動関連テスト8件が成功した。
- `client_tasks.py`の内容を`bot_jobs.py`へ統合し、定期タスクの実装と登録を同じモジュールで管理するようにした。
- `client_tasks.py`を削除し、参照先を更新した。
- 統合後の関連テスト9件、構文チェック、`git diff --check`が成功した。
- `run_daily_loop()`からDiscord Clientへの直接依存を外し、`wait_until_ready`と`is_closed`をコールバックとして受け取る形にした。
- 日次スケジューラの汎用性を保ちつつ、既存の待機順序・実行時刻・例外通知の振る舞いを維持した。
- 変更後のスケジューラ関連14件、構文チェック、`git diff --check`が成功した。
- `app/`以下の全Python定義を確認し、単純な処理にはコメントを追加せず、状態遷移・非同期処理・外部通信・複雑な解析処理に限定してdocstringを追加した。
- コメント追加後の関連15件、`git diff --check`が成功した。
- 追加したdocstringの句点を削除し、コメントの表記規則を反映した。
- コメントの付与基準と句点を付けない表記規則を`AGENTS.md`へ記載した。
- 外部サービスへの接続結果: 外部接続なし

#### 判断・注意事項

- `main.py`から`aiohttp`、`discord`、通知、タスク登録の詳細依存を除去する。

## 未完了事項

- [x] Discordクライアントモジュールを実装する。
- [x] `main.py`を更新する。
- [x] テストと構文チェックを実行する。
