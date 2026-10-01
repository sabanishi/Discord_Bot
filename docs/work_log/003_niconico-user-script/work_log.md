## ニコニコ動画サムネイル取得UserScriptの配信

- `/Users/sukehisakawayasusuke/Downloads/niconico.js` の内容を、配信用ファイル `niconico.user.js` としてプロジェクト直下に追加した。
- `GET /userscripts/niconico.user.js` でUserScriptをインライン配信するエンドポイントを `web_server.py` に追加した。
- 配信内容、JavaScript MIMEタイプ、インライン配信、UserScriptメタデータを検証するテストを追加した。
- 追加テストは実装前に404で失敗し、実装後に成功した。
- 実行確認: `python -m unittest tactical_challenge.tests.test_niconico_user_script_delivery tactical_challenge.tests.test_user_script_delivery`
- ニコニコUserScriptの配信テストを、機能固有の `tactical_challenge/tests/` からプロジェクト共通の `tests/` へ移動した。
- 既存の戦術対抗戦通信中継UserScriptの配信テストも、プロジェクト共通の `tests/` へ移動した。
