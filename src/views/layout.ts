import { html, raw } from "hono/html";

const CSS = `
:root {
  --bg: #f6f7fb; --card: #ffffff; --text: #1a2233; --muted: #67718a;
  --accent: #3556e0; --accent-hover: #2a45bd; --border: #e3e6ef;
  --ok: #157347; --warn: #b02a37;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font-family: "Hiragino Sans", "Noto Sans JP", system-ui, sans-serif;
  font-size: 15px; line-height: 1.65;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
main { max-width: 780px; margin: 0 auto; padding: 1.2rem 1rem 4rem; }
header.site {
  background: var(--card); border-bottom: 1px solid var(--border);
}
header.site .inner {
  max-width: 780px; margin: 0 auto; padding: 0.6rem 1rem;
  display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
}
header.site .brand { font-weight: 700; }
header.site nav { display: flex; gap: 0.9rem; flex-wrap: wrap; font-size: 0.92rem; }
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 1.1rem 1.2rem; margin: 1rem 0;
}
.card h2 { margin: 0 0 0.6rem; font-size: 1.05rem; }
h1 { font-size: 1.3rem; margin: 1rem 0 0.4rem; }
p.muted, span.muted { color: var(--muted); font-size: 0.9rem; }
table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
th, td { text-align: left; padding: 0.45rem 0.5rem; border-bottom: 1px solid var(--border); vertical-align: top; }
th { color: var(--muted); font-weight: 600; white-space: nowrap; }
.table-wrap { overflow-x: auto; }
label { display: block; font-size: 0.88rem; color: var(--muted); margin-top: 0.7rem; }
input[type=text], input[type=email], input[type=number], input[type=time], select, textarea {
  width: 100%; padding: 0.45rem 0.6rem; margin-top: 0.15rem;
  border: 1px solid var(--border); border-radius: 7px; font-size: 0.95rem;
  background: #fff; color: var(--text); font-family: inherit;
}
.row { display: flex; gap: 0.8rem; flex-wrap: wrap; }
.row > div { flex: 1; min-width: 130px; }
button, .btn {
  display: inline-block; margin-top: 0.9rem; padding: 0.5rem 1.1rem;
  background: var(--accent); border: none; border-radius: 7px;
  color: #fff; font-size: 0.95rem; cursor: pointer; font-family: inherit;
}
button:hover, .btn:hover { background: var(--accent-hover); text-decoration: none; }
button.small, .btn.small { padding: 0.25rem 0.7rem; font-size: 0.85rem; margin-top: 0; }
button.ghost { background: transparent; color: var(--accent); border: 1px solid var(--border); }
button.danger { background: var(--warn); }
.badge {
  display: inline-block; padding: 0.05rem 0.55rem; border-radius: 999px;
  font-size: 0.78rem; border: 1px solid var(--border); background: var(--bg);
}
.badge.ok { color: var(--ok); border-color: var(--ok); }
.badge.warn { color: var(--warn); border-color: var(--warn); }
.notice {
  border-left: 4px solid var(--accent); background: #eef1fd;
  padding: 0.7rem 0.9rem; border-radius: 6px; margin: 0.8rem 0; font-size: 0.92rem;
}
.notice.error { border-color: var(--warn); background: #fdf0f1; }
code, pre {
  font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 0.86em;
  background: #eef0f6; border-radius: 5px;
}
code { padding: 0.1em 0.4em; }
pre { padding: 0.8rem 1rem; overflow-x: auto; }
.slot-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr)); gap: 0.5rem; margin-top: 0.6rem; }
.slot-grid button { margin: 0; padding: 0.45rem 0.2rem; font-size: 0.9rem; background: #fff; color: var(--accent); border: 1px solid var(--accent); }
.slot-grid button:hover, .slot-grid button.selected { background: var(--accent); color: #fff; }
.day-list { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.6rem; }
.day-list button { margin: 0; padding: 0.4rem 0.7rem; font-size: 0.88rem; background: #fff; color: var(--text); border: 1px solid var(--border); }
.day-list button.selected { background: var(--accent); color: #fff; border-color: var(--accent); }
.avatar { width: 44px; height: 44px; border-radius: 50%; }
.host-head { display: flex; align-items: center; gap: 0.8rem; }
`;

const COPY_SCRIPT = `
document.addEventListener("click", async (e) => {
  const el = e.target.closest("[data-copy]");
  if (!el) return;
  e.preventDefault();
  try {
    await navigator.clipboard.writeText(el.dataset.copy);
    const original = el.textContent;
    el.textContent = "コピーしました ✓";
    setTimeout(() => { el.textContent = original; }, 1500);
  } catch {}
});
`;

export interface LayoutOpts {
  /** ログイン中のホスト向けナビを表示するか */
  nav?: boolean;
}

export function layout(title: string, body: unknown, opts: LayoutOpts = {}) {
  return html`<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex" />
  <title>${title}</title>
  <style>${raw(CSS)}</style>
</head>
<body>
  <header class="site">
    <div class="inner">
      <span class="brand">📅 日程調整</span>
      ${opts.nav
        ? html`<nav>
            <a href="/dashboard">ダッシュボード</a>
            <a href="/links">リンク</a>
            <a href="/bookings">予約</a>
            <a href="/event-types">調整メニュー</a>
            <a href="/settings">設定</a>
          </nav>`
        : ""}
    </div>
  </header>
  <main>${body}</main>
  <script>${raw(COPY_SCRIPT)}</script>
</body>
</html>`;
}
