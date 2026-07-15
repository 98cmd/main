// Google OAuth / Calendar API のローカルスタブ(E2Eテスト用)
import { createServer } from "node:http";

const port = Number(process.argv[2] ?? 8799);

function b64url(s) {
  return Buffer.from(s).toString("base64url");
}

const log = [];
let eventSeq = 0;

function readBody(req) {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => resolve(data));
  });
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${port}`);
  const body = await readBody(req);
  log.push({ method: req.method, path: url.pathname, body });

  const json = (code, obj) => {
    res.writeHead(code, { "content-type": "application/json" });
    res.end(JSON.stringify(obj));
  };

  if (url.pathname === "/__log") return json(200, log);

  if (req.method === "POST" && url.pathname === "/token") {
    const idToken = `${b64url('{"alg":"none"}')}.${b64url(
      JSON.stringify({ email: "host@example.com", name: "ホスト太郎", picture: null }),
    )}.sig`;
    return json(200, {
      access_token: "stub-access",
      expires_in: 3600,
      refresh_token: "stub-refresh",
      id_token: idToken,
    });
  }

  if (req.method === "GET" && url.pathname === "/calendar/v3/users/me/calendarList") {
    return json(200, {
      items: [
        { id: "primary-cal", summary: "メイン", primary: true, accessRole: "owner" },
        { id: "private-cal", summary: "プライベート", accessRole: "owner" },
      ],
    });
  }

  if (req.method === "POST" && url.pathname === "/calendar/v3/freeBusy") {
    return json(200, { calendars: { "primary-cal": { busy: [] } } });
  }

  if (req.method === "POST" && /^\/calendar\/v3\/calendars\/[^/]+\/events$/.test(url.pathname)) {
    eventSeq += 1;
    return json(200, {
      id: `evt-${eventSeq}`,
      hangoutLink: `https://meet.google.com/stub-${eventSeq}`,
    });
  }

  if (req.method === "DELETE" && /^\/calendar\/v3\/calendars\/[^/]+\/events\/[^/?]+/.test(url.pathname)) {
    res.writeHead(204);
    return res.end();
  }

  json(404, { error: `stub: no route for ${req.method} ${url.pathname}` });
});

server.listen(port, "127.0.0.1", () => {
  console.log(`google stub listening on ${port}`);
});
