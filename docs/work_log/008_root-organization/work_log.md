# ルート直下ファイルの整理

## 目的

実行入口とアプリケーション本体を分離し、ルート直下のファイル数を減らす。

## 対象

- 対象機能: アプリケーションのモジュール配置
- 対象ファイル: ルート直下のPythonモジュール、テスト、作業ログ
- 関連仕様書: `docs/specifications/アプリケーション仕様.md`

## 作業記録

### 2026-10-01

#### 実施内容

- `main.py`とCLI入口をルートに残し、アプリケーション本体を`app/`パッケージへ移動した。
- 作業ログを008として作成した。
- `main.py`とCLI以外のアプリケーションモジュールを`app/`パッケージへ移動した。
- 全アプリケーション・テストのインポートを`app.*`へ更新した。
- Web配信用静的ファイルの基準パスをプロジェクトルート基準へ修正した。
- `tactical_challenge/`を`app/tactical_challenge/`へ統合した。
- テストを`tests/unit`、`tests/integration`、`tests/live`へ分類し、戦術対抗戦のユニットテストも`tests/unit/tactical_challenge`へ集約した。
- 配信対象のUserScriptを`resources/userscripts/`へ集約した。
- `niconico.user.js`、戦術対抗戦の通常UserScript、中継用UserScriptの参照パスを更新した。

#### 確認結果

- 実行したテスト: `tests/unit` 120件、`tests/integration` 6件
- テスト結果: 合計126件成功
- `python -m compileall`と`git diff --check`も成功
- UserScript配信・内容確認テスト10件が成功
- 外部サービスへの接続結果:

#### 判断・注意事項

- `main.py`はルートに残し、補助的な実行入口は`tools/`へ配置する。
- 外部ライブテストは従来どおりDNS環境に依存するため、今回も実行対象外とした。
- `check_link_warnings.py`を`tools/check_link_warnings.py`へ移動した。
- 移動後もCLI引数テストが成功することを確認した。

## 未完了事項

- [x] 移動後のインポートを更新する。
- [x] 全ローカルテストを実行する。
