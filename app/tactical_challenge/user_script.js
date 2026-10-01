// Scrapbox標準UserScriptへ貼り付ける。

const TACTICAL_CHALLENGE_SEASON_LIST_PAGE = "戦術対抗戦_シーズン一覧";
const TACTICAL_CHALLENGE_MENU_TITLE = "戦術対抗戦ページをリファクタ";
const TACTICAL_CHALLENGE_REQUEST_SOURCE = "tactical-challenge-native";
const TACTICAL_CHALLENGE_RESPONSE_SOURCE = "tactical-challenge-bridge";
const TACTICAL_CHALLENGE_REQUEST_TIMEOUT_MS = 60000;
const TACTICAL_CHALLENGE_STATUS_ID = "tactical-challenge-status";
const TACTICAL_CHALLENGE_LOG_PREFIX = "[戦術対抗戦リファクタ]";

const log = (message, details) => {
  if (details === undefined) {
    console.log(TACTICAL_CHALLENGE_LOG_PREFIX, message);
  } else {
    console.log(TACTICAL_CHALLENGE_LOG_PREFIX, message, details);
  }
};

const logError = (message, error) => {
  console.error(TACTICAL_CHALLENGE_LOG_PREFIX, message, error);
};

const currentPageTitle = () => scrapbox.Page?.title ?? "";

const notify = (message) => {
  window.alert(`戦術対抗戦ページ\n${message}`);
};

// クリック直後から現在の処理状態を画面上へ表示する。
const showStatus = (message, isError = false) => {
  let status = document.getElementById(TACTICAL_CHALLENGE_STATUS_ID);
  if (!status) {
    status = document.createElement("div");
    status.id = TACTICAL_CHALLENGE_STATUS_ID;
    Object.assign(status.style, {
      position: "fixed",
      left: "50%",
      bottom: "24px",
      zIndex: "2147483647",
      padding: "10px 16px",
      borderRadius: "8px",
      color: "white",
      boxShadow: "0 2px 8px rgba(0, 0, 0, 0.3)",
      transform: "translateX(-50%)",
    });
    document.body.append(status);
  }
  status.textContent = message;
  status.style.background = isError ? "#c62828" : "#3949ab";
};

// 通信中継スクリプトへ処理を依頼し、同じリクエストIDの結果を待つ。
const requestRefactorThroughBridge = (title) => new Promise((resolve, reject) => {
  const requestId = crypto.randomUUID();
  log("通信中継へリクエストを送信", { requestId, title });
  const timeoutId = setTimeout(() => {
    window.removeEventListener("message", handleResponse);
    logError("通信中継がタイムアウト", { requestId, title });
    reject(new Error("通信中継スクリプトから応答がありません。"));
  }, TACTICAL_CHALLENGE_REQUEST_TIMEOUT_MS);

  function handleResponse(event) {
    const message = event.data;
    if (
      message?.source !== TACTICAL_CHALLENGE_RESPONSE_SOURCE
      || message?.requestId !== requestId
    ) {
      return;
    }
    clearTimeout(timeoutId);
    window.removeEventListener("message", handleResponse);
    log("通信中継から応答を受信", { requestId, ok: message.ok });
    if (message.ok) {
      resolve(message.result);
    } else {
      reject(new Error(message.error || "リファクタに失敗しました。"));
    }
  }

  window.addEventListener("message", handleResponse);
  window.postMessage(
    {
      source: TACTICAL_CHALLENGE_REQUEST_SOURCE,
      requestId,
      title,
    },
    location.origin,
  );
});

// 表示中のページが対象なら、通信中継スクリプト経由でリファクタする。
const refactorCurrentPage = async () => {
  showStatus("対象ページを確認しています…");
  const title = currentPageTitle();
  log("ボタンが押されました", { title });
  if (!title) {
    showStatus("ページを取得できませんでした。", true);
    notify("ページを取得できませんでした。");
    return;
  }

  try {
    if (!(await isConfiguredTargetPage(title))) {
      log("対象外ページと判定", { title });
      showStatus("このページはリファクタ対象ではありません。", true);
      notify("このページはリファクタ対象ではありません。");
      return;
    }
    log("対象ページと判定", { title });
    showStatus("リファクタしています…");
    const result = await requestRefactorThroughBridge(title);
    if (result.changed_lines === 0) {
      log("リファクタが完了しました", {
        title,
        changedLines: 0,
        createdIcons: result.created_icons ?? 0,
      });
      showStatus("完了しました。変更はありません。");
      notify("変更はありませんでした。");
      return;
    }
    log("リファクタが完了しました", {
      title,
      changedLines: result.changed_lines,
      createdIcons: result.created_icons ?? 0,
    });
    showStatus("リファクタが完了しました。");
    notify(
      `リファクタが完了しました。\n` +
      `変更行: ${result.changed_lines}行\n` +
      `新規アイコン: ${result.created_icons ?? 0}件`,
    );
    log("更新結果を表示するためページを再読み込みします", { title });
    location.reload();
  } catch (error) {
    logError("リファクタに失敗", error);
    showStatus("リファクタに失敗しました。", true);
    notify(`リファクタに失敗しました。\n${error.message}`);
  }
};

const isConfiguredTargetPage = async (title) => {
  const project = encodeURIComponent(scrapbox.Project.name);
  const seasonPage = encodeURIComponent(TACTICAL_CHALLENGE_SEASON_LIST_PAGE);
  const response = await fetch(`/api/pages/${project}/${seasonPage}`);
  if (!response.ok) return false;
  const page = await response.json();
  return (page.lines ?? []).some((line) => {
    if (typeof line.text !== "string") return false;
    const links = [...line.text.matchAll(/\[([^\[\]]+)]/g)].map(
      ([, linkTitle]) => linkTitle.trim(),
    );
    return links.includes(title);
  });
};

scrapbox.PageMenu.addMenu({
  title: TACTICAL_CHALLENGE_MENU_TITLE,
  image: "https://gyazo.com/909f476fb28cffcbbcf4018eb5a670c4.png",
  onClick: refactorCurrentPage,
});
log("PageMenuへボタンを登録しました");
