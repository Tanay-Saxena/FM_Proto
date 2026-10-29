"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bell, BellOff, LogOut, Wifi, WifiOff } from "lucide-react";
import { api, J } from "@/lib/api";
import { minutesSince, clock, dur } from "@/lib/format";
import { Button, Field, Input, Modal, Skeleton, cx } from "@/components/ui";

const COLS: [string, string, string[]][] = [
  ["new", "New", ["submitted"]],
  ["cooking", "In the kitchen", ["accepted", "preparing"]],
  ["ready", "Ready to serve", ["ready"]],
];
const ACTION: Record<string, [string, string]> = { submitted: ["accepted", "Accept"], accepted: ["preparing", "Start cooking"], preparing: ["ready", "Mark ready"], ready: ["served", "Served"] };

function beep() {
  try {
    const ctx = new (window.AudioContext || (window as J).webkitAudioContext)();
    [880, 1175].forEach((f, i) => { const o = ctx.createOscillator(), g = ctx.createGain(); o.frequency.value = f; o.connect(g); g.connect(ctx.destination); g.gain.setValueAtTime(0.15, ctx.currentTime + i * 0.18); g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.18 + 0.16); o.start(ctx.currentTime + i * 0.18); o.stop(ctx.currentTime + i * 0.18 + 0.17); });
  } catch {}
}

export default function Kitchen() {
  const router = useRouter();
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api("/auth/me"), retry: false });
  useEffect(() => { if (me.isError) router.replace("/admin/login?next=/kitchen"); }, [me.isError, router]);
  const ms: J[] = (me.data?.memberships ?? []).filter((m: J) => ["owner", "manager", "kitchen"].includes(m.role));
  const [rid, setRid] = useState<string | null>(null);
  useEffect(() => { try { setRid(localStorage.getItem("fm:rid")); } catch {} }, []);
  const cur = ms.find((m) => m.restaurant_id === rid) ?? ms[0];

  const [sound, setSound] = useState(false);
  const seen = useRef<Set<string> | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [reject, setReject] = useState<J | null>(null);
  const [why, setWhy] = useState("");
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);

  const q = useQuery({ queryKey: ["kds", cur?.restaurant_id], queryFn: () => api(`/restaurants/${cur.restaurant_id}/kitchen/queue`), enabled: !!cur, refetchInterval: 2000, refetchIntervalInBackground: true, refetchOnWindowFocus: true, staleTime: 0 });
  const tickets: J[] = q.data?.tickets ?? [];

  useEffect(() => {
    if (!q.data) return;
    const ids = new Set(tickets.map((t) => t.id));
    if (seen.current) {
      const added = tickets.filter((t) => !seen.current!.has(t.id) && t.state === "submitted").map((t) => t.id);
      if (added.length) { setFresh(new Set(added)); if (sound) beep(); setTimeout(() => setFresh(new Set()), 8000); }
    }
    seen.current = ids;
  }, [q.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const move = useMutation({
    mutationFn: ({ id, to, reason }: { id: string; to: string; reason?: string }) => api(`/orders/${id}/status-transition`, { body: { to_state: to, reason: reason ?? "" } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["kds"] }); setReject(null); setWhy(""); },
    onError: (e: J) => { toast.error(e.message); qc.invalidateQueries({ queryKey: ["kds"] }); },
  });

  const byTable = useMemo(() => { const m: Record<string, number> = {}; tickets.filter((t) => t.state !== "served").forEach((t) => (m[t.table] = (m[t.table] ?? 0) + 1)); return m; }, [tickets]);
  const logout = async () => { await api("/auth/logout", { method: "POST" }); qc.clear(); router.replace("/admin/login"); };

  if (me.isLoading || me.isError) return <main className="grid min-h-dvh place-items-center bg-ink"><Skeleton className="h-24 w-64 !bg-white/10" /></main>;
  if (!cur) return <main className="grid min-h-dvh place-items-center bg-ink p-6 text-white"><p>Your account doesn&apos;t have kitchen access. <Link className="underline" href="/admin">Back</Link></p></main>;

  const online = !q.isError;
  return (
    <div className="flex min-h-dvh flex-col bg-ink text-white">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-3">
        <div className="flex items-center gap-4">
          <h1 className="font-display text-2xl font-extrabold">Kitchen</h1>
          {ms.length > 1 ? <select aria-label="Restaurant" value={cur.restaurant_id} onChange={(e) => { setRid(e.target.value); try { localStorage.setItem("fm:rid", e.target.value); } catch {} seen.current = null; }} className="h-10 rounded-lg border-0 bg-white/10 px-3 font-semibold">{ms.map((m) => <option className="text-ink" key={m.restaurant_id} value={m.restaurant_id}>{m.name}</option>)}</select> : <span className="font-semibold text-white/80">{cur.name}</span>}
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className={cx("inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 font-semibold", online ? "bg-white/10 text-lime" : "bg-chilli")} role="status">{online ? <Wifi className="size-4" /> : <WifiOff className="size-4" />}{online ? `Live · updated ${Math.max(0, Math.round((now - q.dataUpdatedAt) / 1000))}s ago` : "Reconnecting…"}</span>
          <button onClick={() => { setSound(!sound); if (!sound) beep(); }} aria-pressed={sound} className="inline-flex h-10 items-center gap-2 rounded-lg bg-white/10 px-3 font-semibold">{sound ? <Bell className="size-4" /> : <BellOff className="size-4" />}New-order sound {sound ? "on" : "off"}</button>
          <Link href="/admin" className="inline-flex h-10 items-center rounded-lg bg-white/10 px-3 font-semibold">Dashboard</Link>
          <button onClick={logout} aria-label="Sign out" className="grid size-10 place-items-center rounded-lg bg-white/10"><LogOut className="size-4" /></button>
        </div>
      </header>

      <div className="grid flex-1 gap-4 p-4 lg:grid-cols-3">
        {COLS.map(([key, title, states]) => {
          const list = tickets.filter((t) => states.includes(t.state)).sort((a, b) => +new Date(a.created_at) - +new Date(b.created_at));
          return (
            <section key={key} aria-label={title} className="flex min-h-[40dvh] flex-col rounded-3xl bg-white/[.04] p-3">
              <h2 className="mb-3 flex items-center justify-between px-2 font-display text-xl font-bold">{title}<span className="grid size-8 place-items-center rounded-full bg-white/10 text-base">{list.length}</span></h2>
              <ul className="flex flex-1 flex-col gap-3">
                {!q.data && [0, 1].map((i) => <Skeleton key={i} className="h-40 !bg-white/10" />)}
                {q.data && list.length === 0 && <li className="grid flex-1 place-items-center text-white/40">{key === "new" ? "No new tickets" : "Nothing here"}</li>}
                {list.map((t) => {
                  const mins = minutesSince(t.created_at) + (now ? 0 : 0);
                  const late = t.state !== "ready" && mins >= 20, warn = t.state !== "ready" && mins >= 10;
                  const act = ACTION[t.state];
                  return (
                    <li key={t.id} className={cx("overflow-hidden rounded-2xl bg-white text-ink", "tab-in", fresh.has(t.id) && "new-ticket")}>
                      {t.ticket_type === "addon" && <div className="flex items-center justify-between bg-chilli px-4 py-1.5 text-sm font-extrabold text-white"><span>ADD-ON {t.label}</span><span className="font-semibold opacity-90">after #{t.follows_number}</span></div>}
                      <div className="p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div><p className="font-display text-[44px] font-extrabold leading-none">T{t.table}</p><p className="mt-1 text-sm font-semibold text-muted">#{t.number}{t.zone ? ` · ${t.zone}` : ""}{t.guest ? ` · ${t.guest}` : ""}</p></div>
                          <div className="text-right"><p className={cx("rounded-full px-3 py-1 text-lg font-extrabold tabular-nums", late ? "bg-chilli text-white" : warn ? "bg-amber text-ink" : "bg-black/[.06]")} aria-label={`${mins} minutes waiting`}>{dur(mins)}</p><p className="mt-1 text-xs text-muted">{clock(t.created_at)}</p>{byTable[t.table] > 1 && <p className="mt-1 text-xs font-bold text-chilli">{byTable[t.table]} tickets open</p>}</div>
                        </div>
                        <ul className="mt-3 space-y-1.5">
                          {t.items.map((i: J, n: number) => (
                            <li key={n} className="text-[22px] font-bold leading-tight"><span className="mr-2 inline-grid min-w-9 place-items-center rounded-lg bg-ink px-2 py-0.5 text-white">{i.quantity}</span>{i.name}
                              {i.modifiers?.length > 0 && <span className="block pl-12 text-base font-semibold text-muted">{i.modifiers.map((m: J) => m.name).join(" · ")}</span>}
                              {i.notes && <span className="block pl-12 text-base font-semibold text-chilli">“{i.notes}”</span>}</li>
                          ))}
                        </ul>
                        {t.notes && <p className="mt-3 rounded-xl bg-amber/30 p-2.5 font-semibold">Note: {t.notes}</p>}
                        <div className="mt-4 flex gap-2">
                          {act && <Button size="lg" variant={t.state === "ready" ? "outline" : "primary"} className="h-16 flex-1 text-lg" loading={move.isPending && move.variables?.id === t.id} onClick={() => move.mutate({ id: t.id, to: act[0] })}>{act[1]}</Button>}
                          {["submitted", "accepted"].includes(t.state) && <Button size="lg" variant="outline" className="h-16" onClick={() => setReject(t)}>Can&apos;t make</Button>}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>

      <Modal open={!!reject} onOpenChange={(o) => !o && setReject(null)} title={`Can't make ticket #${reject?.number}?`}>
        <p className="text-sm text-muted">The guest is told why and isn&apos;t charged for these items.</p>
        <div className="mt-3 flex flex-wrap gap-2">{["Out of stock", "Kitchen closing", "Item unavailable"].map((r) => <button key={r} onClick={() => setWhy(r)} className="rounded-full bg-black/[.06] px-3 py-1.5 text-sm font-semibold">{r}</button>)}</div>
        <div className="mt-3"><Field label="Reason"><Input autoFocus value={why} onChange={(e) => setWhy(e.target.value)} /></Field></div>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setReject(null)}>Keep ticket</Button><Button variant="danger" disabled={!why.trim()} loading={move.isPending} onClick={() => move.mutate({ id: reject!.id, to: "rejected", reason: why })}>Reject ticket</Button></div>
      </Modal>
    </div>
  );
}
