// ==UserScript==
// @name         Cosense Niconico Thumbnail Bridge
// @namespace    https://scrapbox.io/
// @version      1.0.0
// @description  Cosense Niconico Embedのためにニコニコ公式サムネイル情報を取得する
// @match        https://scrapbox.io/*
// @grant        GM_xmlhttpRequest
// @connect      ext.nicovideo.jp
// @inject-into  content
// @run-at       document-start
// ==/UserScript==

(function () {
  "use strict";

  var REQUEST_CLASS = "niconico-thumbnail-bridge-request";

  function processRequest(request) {
    if (!request || request.nodeType !== 1) return;
    if (!request.classList.contains(REQUEST_CLASS)) return;

    var requestId = request.getAttribute("data-request-id");
    var videoId = request.getAttribute("data-video-id");

    if (!requestId || !videoId) return;
    if (request.getAttribute("data-bridge-started") === "true") return;

    request.setAttribute("data-bridge-started", "true");

    GM_xmlhttpRequest({
      method: "GET",
      url:
        "https://ext.nicovideo.jp/api/getthumbinfo/" +
        encodeURIComponent(videoId),
      timeout: 15000,

      onload: function (response) {
        if (!request.isConnected) return;

        if (response.status < 200 || response.status >= 300) {
          finishError(
            request,
            "HTTP " + response.status + " " + response.statusText
          );
          return;
        }

        request.textContent = response.responseText || "";
        request.setAttribute("data-status", "ok");
      },

      onerror: function () {
        if (!request.isConnected) return;
        finishError(request, "GM_xmlhttpRequest failed");
      },

      ontimeout: function () {
        if (!request.isConnected) return;
        finishError(request, "GM_xmlhttpRequest timed out");
      },

      onabort: function () {
        if (!request.isConnected) return;
        finishError(request, "GM_xmlhttpRequest aborted");
      },
    });
  }

  function finishError(request, message) {
    request.setAttribute("data-error", message);
    request.setAttribute("data-status", "error");
  }

  function scanAddedNode(node) {
    if (!node || node.nodeType !== 1) return;

    processRequest(node);

    var requests = node.querySelectorAll("." + REQUEST_CLASS);
    for (var i = 0; i < requests.length; i++) {
      processRequest(requests[i]);
    }
  }

  function installObserver() {
    if (!document.documentElement) {
      setTimeout(installObserver, 0);
      return;
    }

    var existing = document.querySelectorAll("." + REQUEST_CLASS);
    for (var i = 0; i < existing.length; i++) {
      processRequest(existing[i]);
    }

    var observer = new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i++) {
        var addedNodes = mutations[i].addedNodes;

        for (var j = 0; j < addedNodes.length; j++) {
          scanAddedNode(addedNodes[j]);
        }
      }
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });
  }

  installObserver();
})();
