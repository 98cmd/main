import { html, raw } from "hono/html";
import { layout } from "./layout";
import { fmtRange } from "../fmt";
import type { BookingRow, EventTypeRow, UserRow } from "../types";

function jsonForScript(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

const BOOKING_SCRIPT = `
const $ = (s) => document.querySelector(s);
const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Tokyo";
let slots = [];
let selectedDay = null;
let selectedSlot = null;

const dayFmt = new Intl.DateTimeFormat("ja-JP", { timeZone: tz, month: "numeric", day: "numeric", weekday: "short" });
const timeFmt = new Intl.DateTimeFormat("ja-JP", { timeZone: tz, hour: "2-digit", minute: "2-digit", hour12: false });
const dayKeyFmt = new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" });

function groupByDay() {
  const map = new Map();
  for (const s of slots) {
    const key = dayKeyFmt.format(new Date(s.start));
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(s);
  }
  return map;
}

function renderDays() {
  const days = groupByDay();
  const el = $("#days");
  el.innerHTML = "";
  if (days.size === 0) {
    $("#slot-area").innerHTML = '<p class="muted">現在、予約可能な枠がありません。</p>';
    return;
  }
  for (const [key, daySlots] of days) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = dayFmt.format(new Date(daySlots[0].start));
    btn.className = key === selectedDay ? "selected" : "";
    btn.onclick = () => { selectedDay = key; selectedSlot = null; renderDays(); renderTimes(); };
    el.appendChild(btn);
  }
  if (!selectedDay || !days.has(selectedDay)) {
    selectedDay = days.keys().next().value;
    renderDays();
    renderTimes();
  }
}

function renderTimes() {
  const days = groupByDay();
  const el = $("#times");
  el.innerHTML = "";
  for (const s of days.get(selectedDay) ?? []) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = timeFmt.format(new Date(s.start));
    btn.className = selectedSlot && selectedSlot.start === s.start ? "selected" : "";
    btn.onclick = () => { selectedSlot = s; renderTimes(); showForm(); };
    el.appendChild(btn);
  }
}

function fmtSlot(s) {
  return dayFmt.format(new Date(s.start)) + " " + timeFmt.format(new Date(s.start)) + "〜" + timeFmt.format(new Date(s.end));
}

function showForm() {
  $("#form-area").style.display = "block";
  $("#chosen").textContent = fmtSlot(selectedSlot) + "(" + tz + ")";
  $("#form-area").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function loadSlots() {
  $("#slot-area").style.display = "block";
  try {
    const res = await fetch("/api/slots/" + DATA.slug + "?tz=" + encodeURIComponent(tz));
    if (!res.ok) throw new Error();
    slots = (await res.json()).slots;
    renderDays();
  } catch {
    $("#slot-area").innerHTML = '<p class="muted">空き枠の取得に失敗しました。再読み込みしてください。</p>';
  }
}

document.querySelector("#booking-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!selectedSlot) return;
  const btn = $("#submit-btn");
  btn.disabled = true;
  btn.textContent = "確定中…";
  $("#book-error").style.display = "none";
  try {
    const res = await fetch("/api/book/" + DATA.slug, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        start: selectedSlot.start,
        name: $("#g-name").value,
        email: $("#g-email").value,
        note: $("#g-note").value,
        tz,
        rescheduleToken: DATA.rescheduleToken,
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "failed");
    $("#page-body").style.display = "none";
    $("#done-when").textContent = fmtSlot(selectedSlot) + "(" + tz + ")";
    if (data.meetUrl) {
      $("#done-meet").innerHTML = 'Google Meet: <a href="' + data.meetUrl + '">' + data.meetUrl + "</a>";
    }
    $("#done-cancel").href = data.cancelUrl;
    $("#done-area").style.display = "block";
    window.scrollTo(0, 0);
  } catch (err) {
    const msg = err.message === "slot_taken"
      ? "選択した枠は先に埋まってしまいました。別の枠をお選びください。"
      : "予約に失敗しました。時間をおいて再度お試しください。";
    $("#book-error").textContent = msg;
    $("#book-error").style.display = "block";
    btn.disabled = false;
    btn.textContent = "この日程で確定する";
    selectedSlot = null;
    loadSlots();
  }
});

loadSlots();
`;

export function guestBookingPage(props: {
  slug: string;
  et: EventTypeRow;
  host: UserRow;
  rescheduleToken: string | null;
}) {
  const data = {
    slug: props.slug,
    rescheduleToken: props.rescheduleToken,
  };
  return layout(
    `${props.et.title} | 日程調整`,
    html`
      <div id="page-body">
        <div class="card">
          <div class="host-head">
            ${props.host.picture
              ? html`<img class="avatar" src="${props.host.picture}" alt="" />`
              : ""}
            <div>
              <b>${props.host.name ?? ""}</b>
              <p class="muted" style="margin:0">${props.et.title}(${props.et.duration_min}分・Google Meet)</p>
            </div>
          </div>
          ${props.et.description
            ? html`<p style="margin-bottom:0">${props.et.description}</p>`
            : ""}
          ${props.rescheduleToken
            ? html`<div class="notice">日程変更モードです。新しい日時を選ぶと、元の予定は自動でキャンセルされます。</div>`
            : ""}
        </div>
        <div class="card" id="slot-area" style="display:none">
          <h2>日付を選択</h2>
          <div class="day-list" id="days"></div>
          <div class="slot-grid" id="times"></div>
        </div>
        <div class="card" id="form-area" style="display:none">
          <h2>予約者情報</h2>
          <p><b id="chosen"></b></p>
          <form id="booking-form">
            <label>お名前</label>
            <input type="text" id="g-name" required maxlength="100" />
            <label>メールアドレス(Googleカレンダーの招待が届きます)</label>
            <input type="email" id="g-email" required maxlength="200" />
            <label>メッセージ(任意)</label>
            <textarea id="g-note" rows="2" maxlength="1000"></textarea>
            <div class="notice error" id="book-error" style="display:none"></div>
            <button type="submit" id="submit-btn">この日程で確定する</button>
          </form>
        </div>
      </div>
      <div id="done-area" style="display:none">
        <div class="card">
          <h2>✅ 予約が確定しました</h2>
          <p><b id="done-when"></b></p>
          <p id="done-meet"></p>
          <p>Googleカレンダーの招待メールをお送りしました。</p>
          <p class="muted">
            変更・キャンセルは<a id="done-cancel" href="#">こちら</a>から行えます(招待メールからも操作できます)。
          </p>
        </div>
      </div>
      <script>const DATA = ${raw(jsonForScript(data))};</script>
      <script>${raw(BOOKING_SCRIPT)}</script>
    `,
  );
}

export function messagePage(title: string, message: string) {
  return layout(
    title,
    html`<div class="card"><h2>${title}</h2><p>${message}</p></div>`,
  );
}

export function cancelPage(props: {
  booking: BookingRow;
  etTitle: string;
  slug: string;
  guestTz: string;
}) {
  const { booking } = props;
  return layout(
    "予約の変更・キャンセル",
    html`
      <h1>予約の変更・キャンセル</h1>
      <div class="card">
        <p>
          <b>${props.etTitle}</b><br />
          ${fmtRange(booking.start_ts, booking.end_ts, props.guestTz)}(${props.guestTz})<br />
          ${booking.guest_name} 様
        </p>
        ${booking.status === "canceled"
          ? html`<div class="notice">この予約はキャンセル済みです。</div>
              <p><a class="btn" href="/b/${props.slug}">新しく予約する</a></p>`
          : html`
              <a class="btn" href="/b/${props.slug}?rt=${booking.cancel_token}">日程を変更する</a>
              <form method="post" action="/cancel/${booking.cancel_token}" style="display:inline">
                <button class="danger" type="submit" onclick="return confirm('この予約をキャンセルしますか?')">
                  キャンセルする
                </button>
              </form>
            `}
      </div>
    `,
  );
}
