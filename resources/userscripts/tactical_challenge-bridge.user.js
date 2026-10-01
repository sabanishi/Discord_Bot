// ==UserScript==
// @name         戦術対抗戦リファクタ通信中継
// @namespace    discord-bot.tactical-challenge
// @version      1.0.0
// @description  Scrapbox標準UserScriptとBot APIの通信だけを中継する
// @match        https://scrapbox.io/*
// @grant        GM.xmlHttpRequest
// @connect      discord-bot-5wni.onrender.com
// @inject-into  content
// @run-at       document-start
// ==/UserScript==

(() => {
  const API_URL = "https://discord-bot-5wni.onrender.com/api/tactical-challenge/refactor";
  const REQUEST_SOURCE = "tactical-challenge-native";
  const RESPONSE_SOURCE = "tactical-challenge-bridge";
  const LOG_PREFIX = "[戦術対抗戦リファクタ中継]";

  const log = (message, details) => {
    if (details === undefined) {
      console.log(LOG_PREFIX, message);
    } else {
      console.log(LOG_PREFIX, message, details);
    }
  };

  const logError = (message, details) => {
    console.error(LOG_PREFIX, message, details);
  };

  // Scrapbox標準UserScriptからの依頼だけをBot APIへ中継する。
  window.addEventListener("message", (event) => {
    const message = event.data;
    if (
      message?.source !== REQUEST_SOURCE
      || typeof message?.requestId !== "string"
      || typeof message?.title !== "string"
    ) {
      return;
    }

    log("Scrapboxからリクエストを受信", {
      requestId: message.requestId,
      title: message.title,
    });
    log("Bot APIへリクエストを送信", { requestId: message.requestId });

    GM.xmlHttpRequest({
      method: "POST",
      url: API_URL,
      headers: { "Content-Type": "application/json" },
      data: JSON.stringify({ title: message.title }),
      onload: (response) => {
        log("Bot APIから応答を受信", {
          requestId: message.requestId,
          status: response.status,
        });
        let result;
        try {
          result = JSON.parse(response.responseText || "{}");
        } catch (_error) {
          logError("Bot APIのJSON解析に失敗", { requestId: message.requestId });
          sendResponse(message.requestId, false, null, "サーバーの応答が不正です。");
          return;
        }
        if (response.status < 200 || response.status >= 300) {
          logError("Bot APIがエラーを返しました", {
            requestId: message.requestId,
            status: response.status,
          });
          sendResponse(
            message.requestId,
            false,
            null,
            result.error || `HTTP ${response.status}`,
          );
          return;
        }
        sendResponse(message.requestId, true, result, null);
      },
      onerror: () => {
        logError("Bot APIへの接続に失敗", { requestId: message.requestId });
        sendResponse(
          message.requestId,
          false,
          null,
          "Botサーバーへ接続できませんでした。",
        );
      },
      ontimeout: () => {
        logError("Bot APIへの接続がタイムアウト", { requestId: message.requestId });
        sendResponse(
          message.requestId,
          false,
          null,
          "Botサーバーとの通信がタイムアウトしました。",
        );
      },
    });
  });

  const sendResponse = (requestId, ok, result, error) => {
    log("Scrapboxへ応答を送信", { requestId, ok });
    window.postMessage(
      {
        source: RESPONSE_SOURCE,
        requestId,
        ok,
        result,
        error,
      },
      location.origin,
    );
  };

  log("通信中継スクリプトを読み込みました");
})();
