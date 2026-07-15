import { Hono } from "hono";
import type { Env } from "./env";
import { authRoutes } from "./routes/auth";
import { hostRoutes } from "./routes/host";
import { publicRoutes } from "./routes/public";
import { messagePage } from "./views/public";

export { AppDB } from "./db";

const app = new Hono<{ Bindings: Env }>();

// CSRF対策: クロスオリジンからのPOSTを拒否する
// (ブラウザはクロスオリジン送信時に必ずOriginヘッダを付ける)
app.use("*", async (c, next) => {
  if (c.req.method === "POST") {
    const reqOrigin = c.req.header("origin");
    if (reqOrigin && reqOrigin !== new URL(c.req.url).origin) {
      return c.text("Forbidden", 403);
    }
  }
  await next();
});

// 公開ルート(ゲスト向け)と認証ルートを先に登録し、
// 認証必須のホスト向けルートを最後にマウントする
app.route("/", publicRoutes);
app.route("/", authRoutes);
app.route("/", hostRoutes);

app.notFound((c) =>
  c.html(messagePage("ページが見つかりません", "URLをご確認ください。"), 404),
);

app.onError((err, c) => {
  console.error("unhandled error", err);
  return c.html(
    messagePage("エラーが発生しました", "時間をおいて再度お試しください。"),
    500,
  );
});

export default app;
