"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, J } from "@/lib/api";
import { ago, clock, money } from "@/lib/format";
import { useAdmin } from "@/components/admin/context";
import { OrderBadge, PageHead, Panel, SESSION_LABEL } from "@/components/admin/bits";
import { Badge, Button, Empty, Field, Input, Modal, Select, Sheet, Skeleton } from "@/components/ui";

const NEXT: Record<string, [string, string][]> = {
  submitted: [["accepted", "Accept"]], accepted: [["preparing", "Start preparing"]], preparing: [["ready", "Mark ready"]], ready: [["served", "Mark served"]],
};

export default function Orders() {
  const { rid, can, restaurant } = useAdmin();
  const qc = useQueryClient();
  const [filter, setFilter] = useState("active");
  const [open, setOpen] = useState<J | null>(null);
  const [reason, setReason] = useState<{ order: J; to: string } | null>(null);
  const [why, setWhy] = useState("");
  const [force, setForce] = useState<J | null>(null);
  const [moving, setMoving] = useState<J | null>(null);
  const [dest, setDest] = useState("");
  const [showClosed, setShowClosed] = useState(false);
  const tables = useQuery({ queryKey: ["tables", rid], queryFn: () => api(`/restaurants/${rid}/tables`), enabled: !!moving });
  const closed = useQuery({ queryKey: ["sessions-closed", rid], queryFn: () => api(`/restaurants/${rid}/sessions?state=closed`), enabled: showClosed && can("sessions.view") });

  const orders = useQuery({ queryKey: ["orders", rid, filter], queryFn: () => api(`/restaurants/${rid}/orders${filter === "active" ? "?state=submitted,accepted,preparing,ready" : "?limit=80"}`), refetchInterval: 5000 });
  const sessions = useQuery({ queryKey: ["sessions", rid], queryFn: () => api(`/restaurants/${rid}/sessions`), enabled: can("sessions.view"), refetchInterval: 5000 });

  const move = useMutation({
    mutationFn: ({ id, to, reason }: { id: string; to: string; reason?: string }) => api(`/orders/${id}/status-transition`, { body: { to_state: to, reason: reason ?? "" } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["orders", rid] }); qc.invalidateQueries({ queryKey: ["sessions", rid] }); setReason(null); setWhy(""); setOpen(null); },
    onError: (e: J) => toast.error(e.message),
  });
  const sessAct = useMutation({
    mutationFn: ({ id, action, reason, to_table_id }: { id: string; action: string; reason?: string; to_table_id?: string }) => api(`/restaurants/${rid}/sessions/${id}/action`, { body: { action, reason, to_table_id } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["sessions", rid] }); qc.invalidateQueries({ queryKey: ["sessions-closed", rid] }); setForce(null); setMoving(null); setDest(""); setWhy(""); toast.success("Table updated"); },
    onError: (e: J) => toast.error(e.message),
  });

  return (
    <>
      <PageHead title="Orders & tables" sub="Every ticket the kitchen has received. Add-on tickets stay separate from the original order." />
      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Panel title="Tickets" actions={<div className="flex rounded-xl bg-black/5 p-1 text-sm font-semibold">{[["active", "In progress"], ["all", "Recent"]].map(([k, l]) => <button key={k} onClick={() => setFilter(k)} aria-pressed={filter === k} className={`rounded-lg px-3 py-1.5 ${filter === k ? "bg-white shadow-sm" : ""}`}>{l}</button>)}</div>}>
          {!orders.data ? <Skeleton className="h-48" /> : orders.data.length === 0 ? <Empty title="No tickets" body="New orders appear here the moment a guest sends them." /> : (
            <ul className="divide-y divide-stone">
              {orders.data.map((o: J) => (
                <li key={o.id}>
                  <button onClick={() => setOpen(o)} className="flex w-full items-start justify-between gap-3 py-3.5 text-left">
                    <div className="min-w-0">
                      <p className="font-semibold">#{o.number} · Table {o.table} {o.ticket_type === "addon" ? <Badge tone="lime">Add-on {o.label}</Badge> : <Badge>Original</Badge>}</p>
                      <p className="mt-0.5 truncate text-sm text-muted">{o.items.map((i: J) => `${i.quantity}× ${i.name}`).join(", ")}</p>
                      <p className="text-xs text-muted">{clock(o.created_at, restaurant.timezone)} · {ago(o.created_at)}</p>
                    </div>
                    <div className="text-right"><OrderBadge state={o.state} /><p className="mt-1 text-sm font-semibold">{money(o.total_minor, restaurant.currency)}</p></div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        {can("sessions.view") && (
          <Panel title="Table sessions">
            {!sessions.data ? <Skeleton className="h-48" /> : sessions.data.length === 0 ? <Empty title="No open tables" /> : (
              <ul className="divide-y divide-stone">
                {sessions.data.map((s: J) => (
                  <li key={s.id} className="py-3.5">
                    <div className="flex items-start justify-between gap-3">
                      <div><p className="font-display text-lg font-bold">Table {s.table}</p><p className="text-sm text-muted">{s.guest ? `${s.guest.split(" ")[0]} · ${s.phone_masked}` : "No contact yet"}</p></div>
                      <div className="text-right"><p className="font-semibold">{money(s.total_minor, restaurant.currency)}</p><Badge tone={s.state === "paid" ? "good" : s.state === "payment_pending" ? "warn" : "neutral"}>{SESSION_LABEL[s.state]}</Badge></div>
                    </div>
                    {can("sessions.manage") && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {s.state === "payment_pending" && <Button size="sm" variant="outline" onClick={() => sessAct.mutate({ id: s.id, action: "release_lock" })}>Release payment lock</Button>}
                        {s.state === "paid" && <Button size="sm" variant="outline" onClick={() => sessAct.mutate({ id: s.id, action: "close" })}>Close table</Button>}
                        {["open", "bill_requested"].includes(s.state) && <Button size="sm" variant="outline" onClick={() => setMoving(s)}>Move to another table…</Button>}
                        {["open", "bill_requested"].includes(s.state) && <Button size="sm" variant="ghost" onClick={() => setForce(s)}>Close without payment…</Button>}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        )}
        {can("sessions.manage") && (
          <div className="mt-4">
            <Button variant="ghost" size="sm" onClick={() => setShowClosed((v) => !v)}>{showClosed ? "Hide closed tables" : "Closed by mistake? Show closed tables"}</Button>
            {showClosed && (
              <Panel title="Recently closed" className="mt-2">
                {!closed.data ? <Skeleton className="h-20" /> : closed.data.length === 0 ? <Empty title="Nothing closed recently" /> : (
                  <ul className="divide-y divide-stone">{closed.data.slice(0, 12).map((c: J) => (
                    <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5"><span><b>Table {c.table}</b> <span className="text-sm text-muted">· {money(c.total_minor, restaurant.currency)} · {c.tickets} ticket{c.tickets === 1 ? "" : "s"}</span></span><Button size="sm" variant="outline" onClick={() => sessAct.mutate({ id: c.id, action: "reopen" })}>Re-open</Button></li>
                  ))}</ul>
                )}
              </Panel>
            )}
          </div>
        )}
      </div>

      <Sheet open={!!open} onOpenChange={(o) => !o && setOpen(null)} side="right" title={open ? `Ticket #${open.number}` : ""} description={open ? `Table ${open.table}${open.zone ? ` · ${open.zone}` : ""} · ${open.ticket_type === "addon" ? `Add-on ${open.label}` : "Original order"}` : undefined}>
        {open && (
          <div className="space-y-5 pt-2">
            <div className="flex items-center gap-2"><OrderBadge state={open.state} /><span className="text-sm text-muted">Guest: {open.guest || "—"}</span></div>
            <ul className="divide-y divide-stone rounded-2xl bg-white px-4">{open.items.map((i: J, n: number) => <li key={n} className="py-3"><p className="flex justify-between gap-3 font-semibold"><span>{i.quantity}× {i.name}</span><span>{money(i.line_total_minor, restaurant.currency)}</span></p>{i.modifiers?.length > 0 && <p className="text-sm text-muted">{i.modifiers.map((m: J) => m.name).join(", ")}</p>}{i.notes && <p className="text-sm italic">“{i.notes}”</p>}</li>)}</ul>
            {open.notes && <p className="rounded-xl bg-amber-50 p-3 text-sm">Order note: {open.notes}</p>}
            {open.reject_reason && <p className="rounded-xl bg-red-50 p-3 text-sm">Reason: {open.reject_reason}</p>}
            <div>
              <p className="mb-2 font-semibold">Timeline</p>
              <ol className="space-y-1.5 text-sm">{open.events.map((e: J, n: number) => <li key={n} className="flex justify-between gap-3"><span>{e.from ? `${e.from} → ` : ""}<b>{e.to}</b></span><span className="text-muted">{clock(e.at, restaurant.timezone)} · {e.actor}</span></li>)}</ol>
            </div>
            {can("orders.transition") && (
              <div className="flex flex-wrap gap-2">
                {(NEXT[open.state] ?? []).map(([to, label]) => <Button key={to} loading={move.isPending} onClick={() => move.mutate({ id: open.id, to })}>{label}</Button>)}
                {["submitted", "accepted"].includes(open.state) && <Button variant="outline" onClick={() => setReason({ order: open, to: "rejected" })}>Reject…</Button>}
                {can("orders.cancel") && ["accepted", "preparing", "ready"].includes(open.state) && <Button variant="danger" onClick={() => setReason({ order: open, to: "cancelled" })}>Cancel ticket…</Button>}
              </div>
            )}
          </div>
        )}
      </Sheet>

      <Modal open={!!reason} onOpenChange={(o) => !o && setReason(null)} title={reason?.to === "rejected" ? "Reject this ticket?" : "Cancel this ticket?"}>
        <p className="text-sm text-muted">The guest sees this reason and the items are removed from their bill. Stock is returned.</p>
        <div className="mt-3"><Field label="Reason"><Input value={why} onChange={(e) => setWhy(e.target.value)} placeholder="Out of paneer" autoFocus /></Field></div>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setReason(null)}>Keep ticket</Button><Button variant="danger" disabled={!why.trim()} loading={move.isPending} onClick={() => move.mutate({ id: reason!.order.id, to: reason!.to, reason: why })}>{reason?.to === "rejected" ? "Reject ticket" : "Cancel ticket"}</Button></div>
      </Modal>

      <Modal open={!!moving} onOpenChange={(o) => !o && setMoving(null)} title={`Move Table ${moving?.table}`}>
        <p className="text-sm text-muted">The party, their tickets and the bill move together. The QR code they already scanned keeps working and will show the new table.</p>
        <div className="mt-3"><Field label="New table"><Select className="w-full" value={dest} onChange={(e) => setDest(e.target.value)}><option value="">Choose a free table…</option>{(tables.data ?? []).filter((t: J) => t.status === "active" && !t.session_state && t.id !== moving?.table_id).map((t: J) => <option key={t.id} value={t.id}>Table {t.label}{t.zone ? ` · ${t.zone}` : ""}</option>)}</Select></Field></div>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setMoving(null)}>Cancel</Button><Button disabled={!dest} loading={sessAct.isPending} onClick={() => sessAct.mutate({ id: moving!.id, action: "transfer", to_table_id: dest })}>Move party</Button></div>
      </Modal>

      <Modal open={!!force} onOpenChange={(o) => !o && setForce(null)} title={`Close table ${force?.table} without payment?`}>
        <p className="text-sm text-muted">Use this only for walk-outs or comps. It&apos;s recorded in the audit log with your name. Tickets still in the kitchen must be served or cancelled first.</p>
        <div className="mt-3"><Field label="Reason"><Input value={why} onChange={(e) => setWhy(e.target.value)} placeholder="Guest left, owner comp" autoFocus /></Field></div>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setForce(null)}>Cancel</Button><Button variant="danger" disabled={!why.trim()} onClick={() => sessAct.mutate({ id: force!.id, action: "force_close", reason: why })}>Close table</Button></div>
      </Modal>
    </>
  );
}
