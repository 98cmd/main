export interface UserRow {
  id: number;
  email: string;
  name: string | null;
  picture: string | null;
  refresh_token: string | null;
  access_token: string | null;
  token_expires_at: number | null;
  timezone: string;
  booking_calendar_id: string | null;
  created_at: number;
}

export interface EventTypeRow {
  id: number;
  user_id: number;
  title: string;
  description: string;
  duration_min: number;
  buffer_before_min: number;
  buffer_after_min: number;
  min_notice_hours: number;
  max_per_day: number | null;
  days_ahead: number;
  slot_step_min: number;
  is_active: number;
  created_at: number;
}

export interface RuleRow {
  id: number;
  event_type_id: number;
  weekday: number;
  start_min: number;
  end_min: number;
}

export interface LinkRow {
  id: number;
  slug: string;
  event_type_id: number;
  channel_label: string;
  memo: string;
  is_active: number;
  expires_at: number | null;
  max_bookings: number | null;
  created_at: number;
}

export interface BookingRow {
  id: number;
  link_id: number;
  event_type_id: number;
  guest_name: string;
  guest_email: string;
  guest_note: string;
  guest_tz: string;
  start_ts: number;
  end_ts: number;
  host_date: string;
  status: "pending" | "confirmed" | "canceled";
  google_event_id: string | null;
  calendar_id: string | null;
  meet_url: string | null;
  cancel_token: string;
  created_at: number;
  canceled_at: number | null;
}

export interface BusyCalendarRow {
  user_id: number;
  calendar_id: string;
  summary: string | null;
}
