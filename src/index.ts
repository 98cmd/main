const page = `<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>日程調整ツール</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
      background: #0f172a;
      color: #e2e8f0;
    }
    main { text-align: center; padding: 2rem; }
    h1 { font-size: 1.5rem; font-weight: 600; }
    p { color: #94a3b8; }
  </style>
</head>
<body>
  <main>
    <h1>📅 日程調整ツール</h1>
    <p>準備中です。もうすぐ公開します。</p>
  </main>
</body>
</html>`;

export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/healthz") {
      return Response.json({ ok: true });
    }

    return new Response(page, {
      headers: { "content-type": "text/html; charset=utf-8" },
    });
  },
} satisfies ExportedHandler;
