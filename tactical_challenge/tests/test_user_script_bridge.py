from pathlib import Path
import subprocess
import unittest


TACTICAL_CHALLENGE_DIR = Path(__file__).parents[1]
NATIVE_SCRIPT = TACTICAL_CHALLENGE_DIR / "user_script.js"
BRIDGE_SCRIPT = TACTICAL_CHALLENGE_DIR / "request_bridge.user.js"


class UserScriptBridgeTest(unittest.TestCase):
    def test_native_script_owns_scrapbox_ui_and_sends_browser_message(self):
        source = NATIVE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("scrapbox.PageMenu.addMenu", source)
        self.assertIn("window.postMessage", source)
        self.assertIn('showStatus("対象ページを確認しています…")', source)
        self.assertIn('showStatus("リファクタしています…")', source)
        self.assertIn('[戦術対抗戦リファクタ]', source)
        self.assertNotIn("GM.xmlHttpRequest", source)

    def test_bridge_owns_only_privileged_external_request(self):
        source = BRIDGE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("// @grant        GM.xmlHttpRequest", source)
        self.assertIn("// @connect      discord-bot-5wni.onrender.com", source)
        self.assertIn("GM.xmlHttpRequest({", source)
        self.assertIn('[戦術対抗戦リファクタ中継]', source)
        self.assertNotIn("PageMenu", source)

    def test_native_script_and_bridge_complete_refactor_request(self):
        harness = r"""
const fs = require("fs");
const vm = require("vm");
const nativeSource = fs.readFileSync(process.argv[1], "utf8");
const bridgeSource = fs.readFileSync(process.argv[2], "utf8");
const listeners = new Map();
const alerts = [];
const logs = [];
let reloadCalled = false;
let menu;
let statusElement;
const document = {
  getElementById: () => statusElement,
  createElement: () => ({ style: {} }),
  body: { append: (element) => { statusElement = element; } },
};
const window = {
  alert: (message) => alerts.push(message),
  addEventListener: (type, callback) => {
    const callbacks = listeners.get(type) ?? [];
    callbacks.push(callback);
    listeners.set(type, callbacks);
  },
  removeEventListener: (type, callback) => {
    listeners.set(type, (listeners.get(type) ?? []).filter((item) => item !== callback));
  },
  postMessage: (data) => {
    setTimeout(() => {
      for (const callback of listeners.get("message") ?? []) {
        callback({ source: null, data });
      }
    }, 0);
  },
};
const context = {
  window,
  scrapbox: {
    Project: { name: "project" },
    Page: { title: "対象ページ" },
    PageMenu: { addMenu: (value) => { menu = value; } },
  },
  fetch: async () => ({
    ok: true,
    json: async () => ({ lines: [{ text: " [対象ページ]" }] }),
  }),
  GM: {
    xmlHttpRequest: (options) => setTimeout(() => options.onload({
      status: 200,
      responseText: JSON.stringify({ changed_lines: 2, created_icons: 1 }),
    }), 0),
  },
  crypto: { randomUUID: () => "request-id" },
  location: { origin: "https://scrapbox.io", reload: () => { reloadCalled = true; } },
  document,
  console: { log: (...values) => logs.push(values.join(" ")), error: (...values) => logs.push(values.join(" ")) },
  setTimeout,
  clearTimeout,
  Promise,
};
vm.createContext(context);
vm.runInContext(bridgeSource, context);
vm.runInContext(nativeSource, context);
if (!menu) throw new Error("ScrapboxのPageMenuへ登録されていません");
menu.onClick();
if (statusElement?.textContent !== "対象ページを確認しています…") {
  throw new Error(`クリック直後の表示が不正です: ${statusElement?.textContent}`);
}
setTimeout(() => {
  if (!alerts.some((message) => message.includes("変更行: 2行") && message.includes("新規アイコン: 1件"))) {
    throw new Error(`完了通知が不正です: ${JSON.stringify(alerts)}`);
  }
  if (!logs.some((message) => message.includes("ボタンが押されました"))) {
    throw new Error(`クリックログがありません: ${JSON.stringify(logs)}`);
  }
  if (!logs.some((message) => message.includes("Bot APIから応答を受信"))) {
    throw new Error(`API応答ログがありません: ${JSON.stringify(logs)}`);
  }
  if (!logs.some((message) => message.includes("リファクタが完了しました"))) {
    throw new Error(`完了ログがありません: ${JSON.stringify(logs)}`);
  }
  if (!reloadCalled) throw new Error("成功後にページが再読み込みされていません");
}, 30);
"""
        result = subprocess.run(
            ["node", "-e", harness, str(NATIVE_SCRIPT), str(BRIDGE_SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
