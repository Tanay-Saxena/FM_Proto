"use client";
import { useCallback, useEffect, useState } from "react";
import { api, getDemoTime, J } from "./api";

export function themeVars(theme: J): React.CSSProperties {
  const r = theme.radius === "sharp" ? ["6px", "10px"] : theme.radius === "round" ? ["22px", "32px"] : ["14px", "22px"];
  return { "--brand": theme.brand, "--brand-ink": theme.brand_ink, "--accent": theme.accent, "--surface": theme.surface, "--r": r[0], "--r-lg": r[1] } as React.CSSProperties;
}

/** A tiny localStorage-backed state hook that never throws (private windows, blocked storage). */
export function useStored<T>(key: string, initial: T): [T, (v: T | ((p: T) => T)) => void] {
  const [val, setVal] = useState<T>(initial);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    try { const raw = localStorage.getItem(key); if (raw) setVal(JSON.parse(raw)); } catch {}
    setReady(true);
  }, [key]);
  const set = useCallback((v: T | ((p: T) => T)) => {
    setVal((prev) => {
      const next = typeof v === "function" ? (v as (p: T) => T)(prev) : v;
      try { localStorage.setItem(key, JSON.stringify(next)); } catch {}
      return next;
    });
  }, [key]);
  return [ready ? val : initial, set];
}

export type CartLine = { id: string; item_id: string; name: string; hue: number; unit_minor: number; quantity: number; option_ids: string[]; option_labels: string[]; notes: string };

export function useCart(slug: string) {
  const [lines, setLines] = useStored<CartLine[]>(`fm:cart:${slug}`, []);
  const add = (l: Omit<CartLine, "id">) =>
    setLines((prev) => {
      const sig = `${l.item_id}|${[...l.option_ids].sort().join(",")}|${l.notes}`;
      const hit = prev.find((p) => `${p.item_id}|${[...p.option_ids].sort().join(",")}|${p.notes}` === sig);
      return hit ? prev.map((p) => (p === hit ? { ...p, quantity: Math.min(20, p.quantity + l.quantity) } : p)) : [...prev, { ...l, id: crypto.randomUUID() }];
    });
  const setQty = (id: string, q: number) => setLines((prev) => (q <= 0 ? prev.filter((p) => p.id !== id) : prev.map((p) => (p.id === id ? { ...p, quantity: q } : p))));
  const remove = (item_id: string) => setLines((prev) => prev.filter((p) => p.item_id !== item_id));
  const clear = () => setLines([]);
  const count = lines.reduce((n, l) => n + l.quantity, 0);
  const total = lines.reduce((n, l) => n + l.quantity * l.unit_minor, 0);
  return { lines, add, setQty, remove, clear, count, total };
}

export function useTableSession(slug: string) {
  const [token, setToken] = useStored<string | null>(`fm:session:${slug}`, null);
  const [data, setData] = useState<J>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!token) { setData(null); return null; }
    try {
      const d = await api(`/table-sessions/${token}`);
      setData(d); setError(null);
      return d;
    } catch (e: J) {
      if (e?.status === 404) { setToken(null); setData(null); }
      else setError(e?.message ?? "Couldn't refresh your table");
      return null;
    }
  }, [token, setToken]);

  useEffect(() => {
    refresh();
    if (!token) return;
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [token, refresh]);

  return { token, setToken, data, setData, refresh, error };
}

export function track(slug: string, event_type: string, item_id?: string) {
  api("/analytics/events", { body: { restaurant_slug: slug, event_type, item_id } }).catch(() => {});
}

export { getDemoTime };
