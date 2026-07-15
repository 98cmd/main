import { html } from "hono/html";
import { layout } from "./layout";
import { fmtRange, minToHHMM, WEEKDAY_JP } from "../fmt";
import type {
  BookingRow,
  EventTypeRow,
  LinkRow,
  RuleRow,
  UserRow,
} from "../types";
import type { CalendarListEntry } from "../google";

/* ---------- ログイン/セットアップ ---------- */

export function setupPage(redirectUri: string) {
  return layout(
    "セットアップ",
    html`
      <h1>初期セットアップ</h1>
      <div class="card">
        <p>Google OAuth クライアントが未設定です。次の手順で設定してください。</p>
        <ol>
          <li><a href="https://console.cloud.google.com/" target="_blank">Google Cloud Console</a> でプロジェクトを作成し、<b>Google Calendar API</b> を有効化</li>
          <li>OAuth 同意画面を作成(公開ステータスは「テスト」でOK。テストユーザーに自分のGmailを追加)</li>
          <li>OAuth クライアントID(Webアプリ)を作成し、リダイレクトURIに以下を登録:<br />
            <code>${redirectUri}</code></li>
          <li>シークレットを設定:<br />
            <pre>npx wrangler secret put GOOGLE_CLIENT_ID
npx wrangler secret put GOOGLE_CLIENT_SECRET</pre>
            (Cloudflareダッシュボード → Workers → main → Settings → Variables からも設定できます)</li>
        </ol>
      </div>
    `,
  );
}

export function loginPage(error?: string) {
  return layout(
    "ログイン",
    html`
      <h1>日程調整ツール</h1>
      ${error ? html`<div class="notice error">${error}</div>` : ""}
      <div class="card">
        <p>Googleカレンダーと連携して、日程調整リンクを発行できます。</p>
        <a class="btn" href="/auth/login">Googleでログイン</a>
        <p class="muted">初回にログインしたアカウントがオーナーとして登録されます。</p>
      </div>
    `,
  );
}

/* ---------- クイック発行フォーム(共通) ---------- */

function quickIssueForm(eventTypes: EventTypeRow[], back: string) {
  if (eventTypes.length === 0) {
    return html`<p>
      まず<a href="/event-types">調整メニュー</a>を作成してください。
    </p>`;
  }
  return html`
    <form method="post" action="/links">
      <input type="hidden" name="back" value="${back}" />
      <div class="row">
        <div>
          <label>調整メニュー</label>
          <select name="event_type_id">
            ${eventTypes.map(
              (et) =>
                html`<option value="${et.id}">${et.title}(${et.duration_min}分)</option>`,
            )}
          </select>
        </div>
        <div>
          <label>経由(相手には表示されません)</label>
          <input type="text" name="channel_label" placeholder="例: 〇〇さん紹介 / X経由" required />
        </div>
        <div>
          <label>メモ(任意)</label>
          <input type="text" name="memo" placeholder="例: 展示会で名刺交換" />
        </div>
      </div>
      <button type="submit">リンクを発行</button>
    </form>
  `;
}

function issuedPanel(origin: string, link: LinkRow) {
  const url = `${origin}/b/${link.slug}`;
  return html`
    <div class="notice">
      発行しました(経由: <b>${link.channel_label}</b>)<br />
      <code>${url}</code>
      <button class="small ghost" style="margin-left:0.5rem" data-copy="${url}">URLをコピー</button>
    </div>
  `;
}

/* ---------- ダッシュボード ---------- */

export function dashboardPage(props: {
  user: UserRow;
  origin: string;
  eventTypes: EventTypeRow[];
  issuedLink: LinkRow | null;
  upcoming: (BookingRow & { channel_label: string; et_title: string })[];
  channelStats: { channel_label: string; count: number }[];
  needsCalendarSetup: boolean;
}) {
  const { user, origin } = props;
  return layout(
    "ダッシュボード",
    html`
      <h1>ダッシュボード</h1>
      ${props.needsCalendarSetup
        ? html`<div class="notice">
            予定の登録先カレンダーが未設定です。<a href="/settings">設定</a>から選択してください。
          </div>`
        : ""}
      <div class="card">
        <h2>⚡ 用途別リンクをクイック発行</h2>
        ${props.issuedLink ? issuedPanel(origin, props.issuedLink) : ""}
        ${quickIssueForm(props.eventTypes, "dashboard")}
      </div>
      <div class="card">
        <h2>今後の予約</h2>
        ${props.upcoming.length === 0
          ? html`<p class="muted">予約はまだありません。</p>`
          : html`<div class="table-wrap"><table>
              <tr><th>日時</th><th>ゲスト</th><th>メニュー</th><th>経由</th><th>Meet</th></tr>
              ${props.upcoming.map(
                (b) => html`<tr>
                  <td>${fmtRange(b.start_ts, b.end_ts, user.timezone)}</td>
                  <td>${b.guest_name}<br /><span class="muted">${b.guest_email}</span></td>
                  <td>${b.et_title}</td>
                  <td><span class="badge">${b.channel_label}</span></td>
                  <td>${b.meet_url ? html`<a href="${b.meet_url}" target="_blank">参加</a>` : "-"}</td>
                </tr>`,
              )}
            </table></div>`}
        <p><a href="/bookings">すべての予約を見る →</a></p>
      </div>
      <div class="card">
        <h2>経由別の予約数</h2>
        ${props.channelStats.length === 0
          ? html`<p class="muted">データがまだありません。</p>`
          : html`<table>
              <tr><th>経由</th><th>確定予約数</th></tr>
              ${props.channelStats.map(
                (s) => html`<tr><td>${s.channel_label}</td><td>${s.count}</td></tr>`,
              )}
            </table>`}
      </div>
    `,
    { nav: true },
  );
}

/* ---------- リンク一覧 ---------- */

export function linksPage(props: {
  origin: string;
  eventTypes: EventTypeRow[];
  issuedLink: LinkRow | null;
  links: (LinkRow & { et_title: string; booking_count: number })[];
}) {
  return layout(
    "リンク",
    html`
      <h1>発行済みリンク</h1>
      <div class="card">
        <h2>⚡ クイック発行</h2>
        ${props.issuedLink ? issuedPanel(props.origin, props.issuedLink) : ""}
        ${quickIssueForm(props.eventTypes, "links")}
      </div>
      <div class="card">
        ${props.links.length === 0
          ? html`<p class="muted">リンクはまだありません。</p>`
          : html`<div class="table-wrap"><table>
              <tr><th>URL</th><th>経由</th><th>メモ</th><th>メニュー</th><th>予約</th><th>状態</th><th></th></tr>
              ${props.links.map((l) => {
                const url = `${props.origin}/b/${l.slug}`;
                return html`<tr>
                  <td><code>/b/${l.slug}</code><br />
                    <button class="small ghost" data-copy="${url}">コピー</button></td>
                  <td>${l.channel_label}</td>
                  <td>${l.memo}</td>
                  <td>${l.et_title}</td>
                  <td>${l.booking_count}</td>
                  <td>${l.is_active
                    ? html`<span class="badge ok">有効</span>`
                    : html`<span class="badge warn">停止中</span>`}</td>
                  <td>
                    <form method="post" action="/links/${l.id}/toggle" style="margin:0">
                      <button class="small ghost" type="submit">${l.is_active ? "停止" : "再開"}</button>
                    </form>
                  </td>
                </tr>`;
              })}
            </table></div>`}
      </div>
      <p class="muted">
        「経由」はこの管理画面とGoogleカレンダーの非公開プロパティにのみ保存され、
        予約ページ・URL・確定メールには一切表示されません。
      </p>
    `,
    { nav: true },
  );
}

/* ---------- 予約一覧 ---------- */

const STATUS_JP: Record<string, unknown> = {
  confirmed: html`<span class="badge ok">確定</span>`,
  canceled: html`<span class="badge warn">キャンセル</span>`,
  pending: html`<span class="badge">処理中</span>`,
};

export function bookingsPage(props: {
  tz: string;
  bookings: (BookingRow & { channel_label: string; et_title: string })[];
}) {
  return layout(
    "予約",
    html`
      <h1>予約一覧</h1>
      <div class="card">
        ${props.bookings.length === 0
          ? html`<p class="muted">予約はまだありません。</p>`
          : html`<div class="table-wrap"><table>
              <tr><th>日時</th><th>ゲスト</th><th>メニュー</th><th>経由</th><th>状態</th><th>Meet</th></tr>
              ${props.bookings.map(
                (b) => html`<tr>
                  <td>${fmtRange(b.start_ts, b.end_ts, props.tz)}</td>
                  <td>${b.guest_name}<br /><span class="muted">${b.guest_email}</span></td>
                  <td>${b.et_title}</td>
                  <td><span class="badge">${b.channel_label}</span></td>
                  <td>${STATUS_JP[b.status] ?? b.status}</td>
                  <td>${b.meet_url && b.status === "confirmed"
                    ? html`<a href="${b.meet_url}" target="_blank">URL</a>`
                    : "-"}</td>
                </tr>`,
              )}
            </table></div>`}
      </div>
    `,
    { nav: true },
  );
}

/* ---------- 調整メニュー ---------- */

function rulesSummary(rules: RuleRow[]): string {
  if (rules.length === 0) return "受付時間未設定";
  const days = [...new Set(rules.map((r) => r.weekday))]
    .sort()
    .map((w) => WEEKDAY_JP[w])
    .join("");
  const start = Math.min(...rules.map((r) => r.start_min));
  const end = Math.max(...rules.map((r) => r.end_min));
  return `${days} ${minToHHMM(start)}〜${minToHHMM(end)}`;
}

export function eventTypesPage(props: {
  eventTypes: (EventTypeRow & { rules: RuleRow[]; link_count: number })[];
}) {
  return layout(
    "調整メニュー",
    html`
      <h1>調整メニュー</h1>
      <p><a class="btn" href="/event-types/new">+ 新規作成</a></p>
      ${props.eventTypes.length === 0
        ? html`<div class="card"><p class="muted">
            「30分打ち合わせ」「60分商談」のような調整メニューを作成すると、リンクを発行できるようになります。
          </p></div>`
        : props.eventTypes.map(
            (et) => html`<div class="card">
              <h2>${et.title} <span class="muted">(${et.duration_min}分)</span>
                ${et.is_active ? "" : html`<span class="badge warn">無効</span>`}</h2>
              <p class="muted">
                ${rulesSummary(et.rules)} ・ ${et.min_notice_hours}時間前まで受付 ・
                前${et.buffer_before_min}分/後${et.buffer_after_min}分バッファ ・
                ${et.days_ahead}日先まで ・ リンク${et.link_count}件
              </p>
              <a class="btn small ghost" href="/event-types/${et.id}" style="color:var(--accent)">編集</a>
              <a class="btn small ghost" href="/event-types/${et.id}/candidates" style="color:var(--accent)">候補日テキスト</a>
            </div>`,
          )}
    `,
    { nav: true },
  );
}

export function eventTypeFormPage(props: {
  et: EventTypeRow | null;
  rules: RuleRow[];
}) {
  const { et, rules } = props;
  const weekdays = new Set(rules.map((r) => r.weekday));
  if (!et) [1, 2, 3, 4, 5].forEach((w) => weekdays.add(w)); // 新規は平日デフォルト
  const startMin = rules.length ? Math.min(...rules.map((r) => r.start_min)) : 10 * 60;
  const endMin = rules.length ? Math.max(...rules.map((r) => r.end_min)) : 18 * 60;
  return layout(
    et ? "メニュー編集" : "メニュー作成",
    html`
      <h1>${et ? "メニュー編集" : "メニュー作成"}</h1>
      <div class="card">
        <form method="post" action="${et ? `/event-types/${et.id}` : "/event-types"}">
          <label>タイトル(ゲストに表示されます)</label>
          <input type="text" name="title" required value="${et?.title ?? ""}" placeholder="例: 30分オンライン打ち合わせ" />
          <label>説明(任意・ゲストに表示されます)</label>
          <textarea name="description" rows="2">${et?.description ?? ""}</textarea>
          <div class="row">
            <div>
              <label>所要時間(分)</label>
              <input type="number" name="duration_min" min="5" max="480" value="${et?.duration_min ?? 30}" />
            </div>
            <div>
              <label>枠の間隔(分)</label>
              <input type="number" name="slot_step_min" min="5" max="240" value="${et?.slot_step_min ?? 30}" />
            </div>
            <div>
              <label>何日先まで</label>
              <input type="number" name="days_ahead" min="1" max="90" value="${et?.days_ahead ?? 21}" />
            </div>
          </div>
          <div class="row">
            <div>
              <label>前バッファ(分)</label>
              <input type="number" name="buffer_before_min" min="0" max="120" value="${et?.buffer_before_min ?? 0}" />
            </div>
            <div>
              <label>後バッファ(分)</label>
              <input type="number" name="buffer_after_min" min="0" max="120" value="${et?.buffer_after_min ?? 0}" />
            </div>
            <div>
              <label>最短受付(時間前)</label>
              <input type="number" name="min_notice_hours" min="0" max="168" value="${et?.min_notice_hours ?? 12}" />
            </div>
            <div>
              <label>1日の上限(空欄=無制限)</label>
              <input type="number" name="max_per_day" min="1" max="50" value="${et?.max_per_day ?? ""}" />
            </div>
          </div>
          <label>受付曜日</label>
          <div class="row" style="margin-top:0.2rem">
            ${WEEKDAY_JP.map(
              (name, w) => html`<div style="min-width:60px;flex:0">
                <label style="margin-top:0">
                  <input type="checkbox" name="weekday" value="${w}" ${weekdays.has(w) ? "checked" : ""} /> ${name}
                </label>
              </div>`,
            )}
          </div>
          <div class="row">
            <div>
              <label>受付開始</label>
              <input type="time" name="start_time" value="${minToHHMM(startMin)}" />
            </div>
            <div>
              <label>受付終了</label>
              <input type="time" name="end_time" value="${minToHHMM(endMin)}" />
            </div>
          </div>
          ${et
            ? html`<label style="margin-top:0.9rem">
                <input type="checkbox" name="is_active" value="1" ${et.is_active ? "checked" : ""} /> 有効(オフにすると全リンクで受付停止)
              </label>`
            : ""}
          <button type="submit">${et ? "保存" : "作成"}</button>
        </form>
      </div>
    `,
    { nav: true },
  );
}

export function candidatesPage(props: {
  et: EventTypeRow;
  tz: string;
  slots: { start: number; end: number }[];
}) {
  const lines = props.slots.map((s) => `・${fmtRange(s.start, s.end, props.tz)}`);
  const text = lines.join("\n");
  return layout(
    "候補日テキスト",
    html`
      <h1>候補日テキスト</h1>
      <p class="muted">${props.et.title}(${props.et.duration_min}分)の直近の空き枠です。メールに貼り付けて使えます。</p>
      <div class="card">
        ${props.slots.length === 0
          ? html`<p class="muted">空き枠が見つかりませんでした。</p>`
          : html`<pre>${text}</pre>
              <button data-copy="${text}">全てコピー</button>`}
      </div>
    `,
    { nav: true },
  );
}

/* ---------- 設定 ---------- */

const COMMON_TZS = [
  "Asia/Tokyo",
  "Asia/Seoul",
  "Asia/Singapore",
  "America/Los_Angeles",
  "America/New_York",
  "Europe/London",
  "UTC",
];

export function settingsPage(props: {
  user: UserRow;
  calendars: CalendarListEntry[];
  busyIds: Set<string>;
  saved: boolean;
}) {
  const { user } = props;
  const bookingCal = user.booking_calendar_id ?? "primary";
  return layout(
    "設定",
    html`
      <h1>設定</h1>
      ${props.saved ? html`<div class="notice">保存しました。</div>` : ""}
      <div class="card">
        <div class="host-head">
          ${user.picture ? html`<img class="avatar" src="${user.picture}" alt="" />` : ""}
          <div>
            <b>${user.name ?? user.email}</b><br />
            <span class="muted">${user.email}</span>
          </div>
        </div>
      </div>
      <form method="post" action="/settings">
        <div class="card">
          <h2>タイムゾーン</h2>
          <input type="text" name="timezone" list="tzs" value="${user.timezone}" />
          <datalist id="tzs">
            ${COMMON_TZS.map((tz) => html`<option value="${tz}"></option>`)}
          </datalist>
        </div>
        <div class="card">
          <h2>予定の登録先カレンダー</h2>
          <p class="muted">確定した予定(Google Meet付き)を作成するカレンダーです。</p>
          ${props.calendars
            .filter((c) => ["owner", "writer"].includes(c.accessRole))
            .map(
              (c) => html`<label style="margin-top:0.3rem">
                <input type="radio" name="booking_calendar_id" value="${c.id}"
                  ${c.id === bookingCal || (bookingCal === "primary" && c.primary) ? "checked" : ""} />
                ${c.summary}${c.primary ? "(メイン)" : ""}
              </label>`,
            )}
        </div>
        <div class="card">
          <h2>空き判定に使うカレンダー</h2>
          <p class="muted">チェックしたカレンダーに予定がある時間帯は、予約枠に表示されません。</p>
          ${props.calendars.map(
            (c) => html`<label style="margin-top:0.3rem">
              <input type="checkbox" name="busy_calendar" value="${c.id}"
                ${props.busyIds.has(c.id) ? "checked" : ""} />
              ${c.summary}${c.primary ? "(メイン)" : ""}
            </label>`,
          )}
        </div>
        <button type="submit">保存</button>
      </form>
      <div class="card">
        <h2>その他</h2>
        <p><a href="/auth/login">Googleと再連携する</a>(権限エラーが出る場合)</p>
        <form method="post" action="/auth/logout" style="margin:0">
          <button class="ghost" type="submit">ログアウト</button>
        </form>
      </div>
    `,
    { nav: true },
  );
}
