// 戦術対抗戦ページ手動リファクタ UserScript
// ScrapboxのUserScriptページへ貼り付けて使用する。

const TACTICAL_CHALLENGE_API_BASE = "https://YOUR_BOT_HOST";
const TACTICAL_CHALLENGE_API_PATH = "/api/tactical-challenge/refactor";
const TACTICAL_CHALLENGE_SEASON_LIST_PAGE = "戦術対抗戦_シーズン一覧";
const TACTICAL_CHALLENGE_MENU_TITLE = "戦術対抗戦をリファクタ";

const currentPageTitle = () => scrapbox.Page?.title ?? "";

const notify = (message) => {
  window.alert(`戦術対抗戦ページ\n${message}`);
};

const refactorCurrentPage = async () => {
  const title = currentPageTitle();
  if (!title) {
    notify("ページを取得できませんでした。");
    return;
  }

  try {
    if (!(await isConfiguredTargetPage(title))) {
      notify("このページはリファクタ対象ではありません。");
      return;
    }
    const response = await fetch(
      `${TACTICAL_CHALLENGE_API_BASE}${TACTICAL_CHALLENGE_API_PATH}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      },
    );
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result.error || `HTTP ${response.status}`);
    }

    if (result.changed_lines === 0) {
      notify("変更はありませんでした。");
      return;
    }
    notify(
      `リファクタが完了しました。\n` +
      `変更行: ${result.changed_lines}行\n` +
      `新規アイコン: ${result.created_icons ?? 0}件`,
    );
  } catch (error) {
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
    const links = [...line.text.matchAll(/\[([^\[\]]+)\]/g)].map(
      ([, linkTitle]) => linkTitle.trim(),
    );
    return links.includes(title);
  });
};

scrapbox.PageMenu.addMenu({
  title: TACTICAL_CHALLENGE_MENU_TITLE,
  image: "kamon-play",
  onClick: refactorCurrentPage,
});
