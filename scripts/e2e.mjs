// E2Eテスト: wrangler dev + Google APIスタブに対して
// ログイン → メニュー作成 → リンク発行 → ゲスト予約 → 日程変更 → キャンセル
// のフルフローを実際のHTTPで検証する。
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const STUB_PORT = 8799;
const APP_PORT = 8788;
const STUB = `http://127.0.0.1:${STUB_PORT}`;
const APP = `http://127.0.0.1:${APP_PORT}`;

const children = [];
function cleanup() {
  for (const c of children) {
    // wranglerはさらに子(workerd)を持つため、プロセスグループごと止める
    try {
      process.kill(-c.pid, "SIGKILL");
    } catch {
      try {
        c.kill("SIGKILL");
      } catch {}
    }
  }
}
process.on("exit", cleanup);
for (const sig of ["SIGINT", "SIGTERM"]) {
  process.on(sig, () => process.exit(1));
}

let failures = 0;
function check(name, cond, extra = "") {
  if (cond) {
    console.log(`  ✓ ${name}`);
  } else {
    failures += 1;
    console.error(`  ✗ ${name} ${extra}`);
  }
}

async function waitFor(url, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`timeout waiting for ${url}`);
}

/** set-cookieヘッダから name=value を取り出す簡易ジャー */
function harvestCookies(res, jar) {
  for (const line of res.headers.getSetCookie?.() ?? []) {
    const [pair] = line.split(";");
    const eq = pair.indexOf("=");
    const name = pair.slice(0, eq).trim();
    const value = pair.slice(eq + 1).trim();
    if (value) jar[name] = value;
    else delete jar[name];
  }
}

function cookieHeader(jar) {
  return Object.entries(jar)
    .map(([k, v]) => `${k}=${v}`)
    .join("; ");
}

async function main() {
  // 1. スタブ起動
  const stub = spawn("node", ["scripts/google-stub.mjs", String(STUB_PORT)], {
    stdio: "inherit",
    detached: true,
  });
  children.push(stub);

  // 2. wrangler dev 起動(状態は一時ディレクトリへ)
  const persistDir = mkdtempSync(join(tmpdir(), "e2e-state-"));
  const wrangler = spawn(
    "npx",
    [
      "wrangler", "dev",
      "--port", String(APP_PORT),
      "--persist-to", persistDir,
      "--var", "GOOGLE_CLIENT_ID:test-client",
      "--var", "GOOGLE_CLIENT_SECRET:test-secret",
      "--var", `GOOGLE_AUTH_BASE:${STUB}/auth`,
      "--var", `GOOGLE_TOKEN_URL:${STUB}/token`,
      "--var", `GOOGLE_API_BASE:${STUB}`,
    ],
    {
      stdio: ["ignore", "inherit", "inherit"],
      detached: true,
      env: {
        ...process.env,
        NO_PROXY: "127.0.0.1,localhost",
        no_proxy: "127.0.0.1,localhost",
        WRANGLER_SEND_METRICS: "false",
      },
    },
  );
  children.push(wrangler);

  await waitFor(`${APP}/healthz`);
  console.log("app is up");

  const jar = {};

  // --- ログインフロー ---
  console.log("login flow");
  let res = await fetch(`${APP}/auth/login`, { redirect: "manual" });
  harvestCookies(res, jar);
  const authLocation = res.headers.get("location") ?? "";
  check("login redirects to Google", authLocation.startsWith(`${STUB}/auth`));
  const state = new URL(authLocation).searchParams.get("state");
  check("state param present", !!state);

  res = await fetch(`${APP}/auth/callback?code=dummy&state=${state}`, {
    redirect: "manual",
    headers: { cookie: cookieHeader(jar) },
  });
  harvestCookies(res, jar);
  check("callback redirects to dashboard", res.headers.get("location") === "/dashboard", String(res.status));
  check("session cookie set", !!jar.sid);

  const authed = { cookie: cookieHeader(jar) };
  res = await fetch(`${APP}/dashboard`, { headers: authed });
  let body = await res.text();
  check("dashboard renders", res.status === 200 && body.includes("ダッシュボード"));

  // --- メニュー作成 ---
  console.log("event type");
  const etForm = new URLSearchParams({
    title: "30分オンライン打ち合わせ",
    description: "Zoom不可・Meetのみ",
    duration_min: "30",
    slot_step_min: "30",
    days_ahead: "7",
    buffer_before_min: "0",
    buffer_after_min: "0",
    min_notice_hours: "0",
    max_per_day: "",
    start_time: "00:00",
    end_time: "23:30",
  });
  for (let w = 0; w <= 6; w++) etForm.append("weekday", String(w));
  res = await fetch(`${APP}/event-types`, {
    method: "POST",
    redirect: "manual",
    headers: { ...authed, "content-type": "application/x-www-form-urlencoded" },
    body: etForm.toString(),
  });
  check("event type created", res.status === 302);

  // --- リンク発行(経由付き) ---
  console.log("link issue");
  res = await fetch(`${APP}/links`, {
    method: "POST",
    redirect: "manual",
    headers: { ...authed, "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      event_type_id: "1",
      channel_label: "X経由テスト",
      memo: "e2e",
      back: "links",
    }).toString(),
  });
  const issuedLoc = res.headers.get("location") ?? "";
  const slug = /issued=([A-Za-z0-9]+)/.exec(issuedLoc)?.[1];
  check("link issued", !!slug, issuedLoc);

  // --- ゲスト側: 経由が漏れていないか ---
  console.log("guest page");
  res = await fetch(`${APP}/b/${slug}`);
  body = await res.text();
  check("guest page renders", res.status === 200 && body.includes("30分オンライン打ち合わせ"));
  check("channel label hidden from guest page", !body.includes("X経由テスト"));

  res = await fetch(`${APP}/api/slots/${slug}`);
  const slotsData = await res.json();
  check("slots returned", Array.isArray(slotsData.slots) && slotsData.slots.length > 0);
  const [slot1, slot2] = slotsData.slots;

  // --- 予約 ---
  console.log("booking");
  res = await fetch(`${APP}/api/book/${slug}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      start: slot1.start,
      name: "山田太郎",
      email: "guest@example.com",
      note: "よろしくお願いします",
      tz: "Asia/Tokyo",
    }),
  });
  const booked = await res.json();
  check("booking succeeds", res.status === 200 && booked.ok === true, JSON.stringify(booked));
  check("meet url issued", (booked.meetUrl ?? "").startsWith("https://meet.google.com/"));
  check("cancel url issued", (booked.cancelUrl ?? "").includes("/cancel/"));

  // 同じ枠は取れない
  res = await fetch(`${APP}/api/book/${slug}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      start: slot1.start,
      name: "二重予約",
      email: "dup@example.com",
      tz: "Asia/Tokyo",
    }),
  });
  check("double booking rejected", res.status === 409);

  // 枠一覧からも消えている
  res = await fetch(`${APP}/api/slots/${slug}`);
  const slotsAfter = await res.json();
  check(
    "booked slot removed from availability",
    !slotsAfter.slots.some((s) => s.start === slot1.start),
  );

  // --- カレンダーイベントの検証(スタブのログ) ---
  const log = await (await fetch(`${STUB}/__log`)).json();
  const inserts = log.filter((l) => l.method === "POST" && /\/events$/.test(l.path));
  check("calendar event inserted", inserts.length === 1);
  const event = JSON.parse(inserts[0].body || "{}");
  check("meet conference requested", event.conferenceData?.createRequest?.conferenceSolutionKey?.type === "hangoutsMeet");
  check("guest invited as attendee", event.attendees?.[0]?.email === "guest@example.com");
  check("channel stored in private extended props", event.extendedProperties?.private?.channel === "X経由テスト");
  check(
    "channel NOT in guest-visible fields",
    !String(event.summary).includes("X経由テスト") && !String(event.description).includes("X経由テスト"),
  );

  // --- ホスト側では経由が見える ---
  res = await fetch(`${APP}/dashboard`, { headers: authed });
  body = await res.text();
  check("channel visible on host dashboard", body.includes("X経由テスト"));
  check("guest listed on dashboard", body.includes("山田太郎"));

  // --- 日程変更 ---
  console.log("reschedule");
  const cancelToken = booked.cancelUrl.split("/cancel/")[1];
  res = await fetch(`${APP}/b/${slug}?rt=${cancelToken}`);
  body = await res.text();
  check("reschedule mode banner", body.includes("日程変更モード"));

  res = await fetch(`${APP}/api/book/${slug}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      start: slot2.start,
      name: "山田太郎",
      email: "guest@example.com",
      tz: "Asia/Tokyo",
      rescheduleToken: cancelToken,
    }),
  });
  const rebooked = await res.json();
  check("reschedule succeeds", rebooked.ok === true, JSON.stringify(rebooked));

  const log2 = await (await fetch(`${STUB}/__log`)).json();
  const deletes = log2.filter((l) => l.method === "DELETE");
  check("old event deleted on reschedule", deletes.some((d) => d.path.includes("evt-1")));

  // --- キャンセル ---
  console.log("cancel");
  const newToken = rebooked.cancelUrl.split("/cancel/")[1];
  res = await fetch(`${APP}/cancel/${newToken}`);
  body = await res.text();
  check("cancel page renders", res.status === 200 && body.includes("キャンセル"));

  res = await fetch(`${APP}/cancel/${newToken}`, { method: "POST" });
  body = await res.text();
  check("cancel succeeds", res.status === 200 && body.includes("キャンセルしました"));

  const log3 = await (await fetch(`${STUB}/__log`)).json();
  check(
    "second event deleted on cancel",
    log3.filter((l) => l.method === "DELETE").some((d) => d.path.includes("evt-2")),
  );

  // --- 同一枠への並行予約: 1件だけ成功すること ---
  console.log("concurrent booking");
  res = await fetch(`${APP}/api/slots/${slug}`);
  const slot3 = (await res.json()).slots[0];
  const race = await Promise.all(
    ["A", "B", "C"].map((who) =>
      fetch(`${APP}/api/book/${slug}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          start: slot3.start,
          name: `並行${who}`,
          email: `race-${who}@example.com`,
          tz: "Asia/Tokyo",
        }),
      }).then((r) => r.json()),
    ),
  );
  const okCount = race.filter((r) => r.ok).length;
  check("exactly one concurrent booking wins", okCount === 1, JSON.stringify(race));

  // 未知のスラッグは404
  res = await fetch(`${APP}/b/nonexistent`);
  check("unknown slug returns 404", res.status === 404);

  // クロスオリジンPOSTは拒否される
  res = await fetch(`${APP}/api/book/${slug}`, {
    method: "POST",
    headers: { "content-type": "application/json", origin: "https://evil.example.com" },
    body: JSON.stringify({ start: 0, name: "x", email: "x@example.com" }),
  });
  check("cross-origin POST rejected", res.status === 403);

  rmSync(persistDir, { recursive: true, force: true });
  console.log(failures === 0 ? "\nE2E: ALL PASSED" : `\nE2E: ${failures} FAILED`);
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
