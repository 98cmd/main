import type { Env } from "./env";
import type { UserRow } from "./types";
import type { BusyInterval } from "./slots";
import { decodeBase64url } from "./util";

const DEFAULT_AUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth";
const DEFAULT_TOKEN_URL = "https://oauth2.googleapis.com/token";
const DEFAULT_API_BASE = "https://www.googleapis.com";

export const OAUTH_SCOPES = [
  "openid",
  "email",
  "profile",
  "https://www.googleapis.com/auth/calendar.readonly",
  "https://www.googleapis.com/auth/calendar.events",
].join(" ");

export class GoogleApiError extends Error {
  constructor(
    public status: number,
    public body: string,
  ) {
    super(`Google API error ${status}: ${body.slice(0, 300)}`);
  }
}

export function redirectUri(origin: string): string {
  return `${origin}/auth/callback`;
}

export function buildAuthUrl(env: Env, origin: string, state: string): string {
  const url = new URL(env.GOOGLE_AUTH_BASE ?? DEFAULT_AUTH_BASE);
  url.searchParams.set("client_id", env.GOOGLE_CLIENT_ID ?? "");
  url.searchParams.set("redirect_uri", redirectUri(origin));
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", OAUTH_SCOPES);
  url.searchParams.set("access_type", "offline");
  url.searchParams.set("prompt", "consent");
  url.searchParams.set("state", state);
  return url.toString();
}

export interface TokenResponse {
  access_token: string;
  expires_in: number;
  refresh_token?: string;
  id_token?: string;
}

async function tokenRequest(env: Env, body: Record<string, string>): Promise<TokenResponse> {
  const res = await fetch(env.GOOGLE_TOKEN_URL ?? DEFAULT_TOKEN_URL, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(body).toString(),
  });
  if (!res.ok) throw new GoogleApiError(res.status, await res.text());
  return (await res.json()) as TokenResponse;
}

export function exchangeCode(env: Env, origin: string, code: string): Promise<TokenResponse> {
  return tokenRequest(env, {
    code,
    client_id: env.GOOGLE_CLIENT_ID ?? "",
    client_secret: env.GOOGLE_CLIENT_SECRET ?? "",
    redirect_uri: redirectUri(origin),
    grant_type: "authorization_code",
  });
}

export function refreshAccessToken(env: Env, refreshToken: string): Promise<TokenResponse> {
  return tokenRequest(env, {
    refresh_token: refreshToken,
    client_id: env.GOOGLE_CLIENT_ID ?? "",
    client_secret: env.GOOGLE_CLIENT_SECRET ?? "",
    grant_type: "refresh_token",
  });
}

/**
 * id_token(JWT)のペイロードを取り出す。トークンはGoogleのTLSエンドポイントから
 * 直接受け取ったものなので署名検証は省略する。
 */
export function decodeIdToken(idToken: string): {
  email: string;
  name: string | null;
  picture: string | null;
} {
  const payload = JSON.parse(decodeBase64url(idToken.split(".")[1])) as {
    email?: string;
    name?: string;
    picture?: string;
  };
  if (!payload.email) throw new Error("id_token missing email");
  return {
    email: payload.email.toLowerCase(),
    name: payload.name ?? null,
    picture: payload.picture ?? null,
  };
}

/** アクセストークンを返す。期限が近い場合はリフレッシュしてDBへ保存 */
export async function getValidAccessToken(
  env: Env,
  db: DurableObjectStub<import("./db").AppDB>,
  user: UserRow,
): Promise<string> {
  const margin = 60_000;
  if (
    user.access_token &&
    user.token_expires_at &&
    user.token_expires_at - margin > Date.now()
  ) {
    return user.access_token;
  }
  if (!user.refresh_token) throw new Error("no refresh token; re-login required");
  const tokens = await refreshAccessToken(env, user.refresh_token);
  const expiresAt = Date.now() + tokens.expires_in * 1000;
  await db.query(
    "UPDATE users SET access_token = ?, token_expires_at = ? WHERE id = ?",
    [tokens.access_token, expiresAt, user.id],
  );
  return tokens.access_token;
}

async function apiFetch<T>(
  env: Env,
  token: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const base = env.GOOGLE_API_BASE ?? DEFAULT_API_BASE;
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) throw new GoogleApiError(res.status, await res.text());
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface CalendarListEntry {
  id: string;
  summary: string;
  primary?: boolean;
  accessRole: string;
}

export async function listCalendars(env: Env, token: string): Promise<CalendarListEntry[]> {
  const data = await apiFetch<{ items?: CalendarListEntry[] }>(
    env,
    token,
    "/calendar/v3/users/me/calendarList?maxResults=100",
  );
  return data.items ?? [];
}

export async function freeBusyQuery(
  env: Env,
  token: string,
  calendarIds: string[],
  timeMin: number,
  timeMax: number,
): Promise<BusyInterval[]> {
  if (calendarIds.length === 0) return [];
  const data = await apiFetch<{
    calendars?: Record<string, { busy?: { start: string; end: string }[] }>;
  }>(env, token, "/calendar/v3/freeBusy", {
    method: "POST",
    body: JSON.stringify({
      timeMin: new Date(timeMin).toISOString(),
      timeMax: new Date(timeMax).toISOString(),
      items: calendarIds.map((id) => ({ id })),
    }),
  });
  const busy: BusyInterval[] = [];
  for (const cal of Object.values(data.calendars ?? {})) {
    for (const b of cal.busy ?? []) {
      busy.push({ start: Date.parse(b.start), end: Date.parse(b.end) });
    }
  }
  return busy;
}

export interface InsertEventInput {
  calendarId: string;
  summary: string;
  description: string;
  start: number;
  end: number;
  guestEmail: string;
  guestName: string;
  /** 経由ラベル。extendedProperties.private はゲストのカレンダーには共有されない */
  channelLabel: string;
  bookingId: number;
}

export interface GoogleEvent {
  id: string;
  hangoutLink?: string;
  conferenceData?: {
    entryPoints?: { entryPointType: string; uri: string }[];
  };
}

export async function insertEvent(
  env: Env,
  token: string,
  input: InsertEventInput,
): Promise<{ eventId: string; meetUrl: string | null }> {
  const event = await apiFetch<GoogleEvent>(
    env,
    token,
    `/calendar/v3/calendars/${encodeURIComponent(input.calendarId)}/events?conferenceDataVersion=1&sendUpdates=all`,
    {
      method: "POST",
      body: JSON.stringify({
        summary: input.summary,
        description: input.description,
        start: { dateTime: new Date(input.start).toISOString() },
        end: { dateTime: new Date(input.end).toISOString() },
        attendees: [{ email: input.guestEmail, displayName: input.guestName }],
        conferenceData: {
          createRequest: {
            requestId: `booking-${input.bookingId}-${input.start}`,
            conferenceSolutionKey: { type: "hangoutsMeet" },
          },
        },
        extendedProperties: {
          private: { channel: input.channelLabel, bookingId: String(input.bookingId) },
        },
        reminders: { useDefault: true },
      }),
    },
  );
  const meetUrl =
    event.hangoutLink ??
    event.conferenceData?.entryPoints?.find((e) => e.entryPointType === "video")?.uri ??
    null;
  return { eventId: event.id, meetUrl };
}

export async function deleteEvent(
  env: Env,
  token: string,
  calendarId: string,
  eventId: string,
): Promise<void> {
  await apiFetch<void>(
    env,
    token,
    `/calendar/v3/calendars/${encodeURIComponent(calendarId)}/events/${encodeURIComponent(eventId)}?sendUpdates=all`,
    { method: "DELETE" },
  );
}
