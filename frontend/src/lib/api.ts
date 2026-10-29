// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type J = any;

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public detail?: J) {
    super(message);
  }
}

export const DEMO_TIME_KEY = "fm:demo-time";

export function getDemoTime(): string | null {
  try { return localStorage.getItem(DEMO_TIME_KEY); } catch { return null; }
}
export function setDemoTime(iso: string | null) {
  try { iso ? localStorage.setItem(DEMO_TIME_KEY, iso) : localStorage.removeItem(DEMO_TIME_KEY); } catch {}
}

export async function api<T = J>(path: string, opts: { method?: string; body?: J; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const demo = typeof window !== "undefined" ? getDemoTime() : null;
  if (demo) headers["x-demo-time"] = demo;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["content-type"] = "application/json"; body = JSON.stringify(opts.body); }
  const res = await fetch(`/api/v1${path}`, { method: opts.method ?? (body ? "POST" : "GET"), headers, body, credentials: "same-origin", cache: "no-store" });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: J = null;
  try { data = text ? JSON.parse(text) : null; } catch {}
  if (!res.ok) {
    const e = data?.error;
    throw new ApiError(res.status, e?.code ?? "error", e?.message ?? `Something went wrong (${res.status}).`, e?.detail);
  }
  return data as T;
}

export const idem = () => `k-${crypto.randomUUID()}`;
