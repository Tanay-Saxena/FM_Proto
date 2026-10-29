export function money(minor: number, currency = "INR", locale = "en-IN") {
  const whole = minor % 100 === 0;
  return new Intl.NumberFormat(locale, { style: "currency", currency, minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: 2 }).format(minor / 100);
}

export function clock(iso: string, tz?: string) {
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", timeZone: tz });
}

export function ago(iso: string) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export function minutesSince(iso: string) {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
}

/** UTC instant for HH:MM today in an IANA timezone (used by the demo clock presets). */
export function todayAtInZone(hh: number, mm: number, tz: string): string {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
  const [y, m, d] = parts.split("-").map(Number);
  const guess = Date.UTC(y, m - 1, d, hh, mm);
  const offsetParts = new Intl.DateTimeFormat("en-US", { timeZone: tz, hour12: false, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).formatToParts(new Date(guess));
  const get = (t: string) => Number(offsetParts.find((p) => p.type === t)?.value);
  const asLocal = Date.UTC(get("year"), get("month") - 1, get("day"), get("hour") % 24, get("minute"));
  return new Date(guess - (asLocal - guess)).toISOString();
}

export const STATE_LABEL: Record<string, string> = {
  submitted: "Sent to kitchen", accepted: "Accepted", preparing: "Preparing", ready: "Ready", served: "Served", rejected: "Rejected", cancelled: "Cancelled",
};

/** 485 -> "8h 5m", 42 -> "42 min" */
export function dur(mins: number) {
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60), m = mins % 60;
  return h >= 24 ? `${Math.floor(h / 24)}d ${h % 24}h` : m ? `${h}h ${m}m` : `${h}h`;
}
