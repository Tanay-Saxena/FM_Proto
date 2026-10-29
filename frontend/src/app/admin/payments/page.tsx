"use client";
import { Fragment, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, J } from "@/lib/api";
import { money } from "@/lib/format";
import { useAdmin } from "@/components/admin/context";
import { PageHead, Panel } from "@/components/admin/bits";
import { Badge, Button, Empty, Field, Input, Modal, Skeleton } from "@/components/ui";

const PAY: Record<string, "good" | "warn" | "bad" | "neutral" | "info"> = { succeeded: "good", pending: "info", created: "neutral", failed: "bad", cancelled: "neutral", refund_pending: "warn", refunded: "neutral" };
const NOTE: Record<string, [("good" | "warn" | "bad" | "neutral" | "info"), string]> = { queued: ["neutral", "Queued"], sending: ["info", "Sending"], sent: ["good", "Sent"], failed: ["bad", "Failed"], retry_scheduled: ["warn", "Retrying"] };

export default function Payments() {
  const { rid, can, restaurant } = useAdmin();
  const qc = useQueryClient();
  const [openPay, setOpenPay] = useState<string | null>(null);
  const [refunding, setRefunding] = useState<J | null>(null);
  const [why, setWhy] = useState("");
  const pays = useQuery({ queryKey: ["pays", rid], queryFn: () => api(`/restaurants/${rid}/payments`), refetchInterval: 8000 });
  const notes = useQuery({ queryKey: ["notes", rid], queryFn: () => api(`/restaurants/${rid}/notifications`), refetchInterval: 8000 });
  const retry = useMutation({ mutationFn: (id: string) => api(`/notifications/${id}/retry`, { method: "POST" }), onSuccess: (r: J) => { qc.invalidateQueries({ queryKey: ["notes", rid] }); r.state === "sent" ? toast.success("Sent") : toast.error(`Still failing: ${r.last_error}`); }, onError: (e: J) => toast.error(e.message) });
  const revoke = useMutation({ mutationFn: (id: string) => api(`/restaurants/${rid}/receipts/${id}/revoke`, { method: "POST" }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["pays", rid] }); toast.success("Receipt link revoked"); }, onError: (e: J) => toast.error(e.message) });

  const refund = useMutation({
    mutationFn: () => api(`/restaurants/${rid}/payments/${refunding!.id}/refund`, { body: { reason: why } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pays", rid] }); setRefunding(null); setWhy(""); toast.success("Refund recorded"); }, onError: (e: J) => toast.error(e.message),
  });

  return (
    <>
      <PageHead title="Payments & receipts" sub="Payment status comes from the payment provider. Receipt messages are tracked separately — a failed text never changes whether a bill was paid." />
      <div className="mb-6 rounded-2xl bg-amber-50 p-4 text-sm text-amber-950 ring-1 ring-amber-200"><b>Simulated provider.</b> Payments here use the built-in mock provider and messages are written to a log, not delivered. A real UPI gateway and SMS/email provider can be plugged in once you have credentials.</div>
      <Panel title="Payments">
        {!pays.data ? <Skeleton className="h-40" /> : pays.data.length === 0 ? <Empty title="No payments yet" /> : (
          <div className="-mx-2 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-[15px]">
            <thead className="text-xs text-muted"><tr><th className="px-2 py-2 font-semibold">Table</th><th className="px-2 py-2 font-semibold">Amount</th><th className="px-2 py-2 font-semibold">Payment</th><th className="px-2 py-2 font-semibold">Reference</th><th className="px-2 py-2 font-semibold">Receipt</th><th /></tr></thead>
            <tbody className="divide-y divide-stone">{pays.data.map((p: J) => (
              <Fragment key={p.id}>
                <tr>
                  <td className="px-2 py-3 font-semibold">Table {p.table}</td>
                  <td className="px-2 py-3">{money(p.amount_minor, p.currency)}</td>
                  <td className="px-2 py-3"><Badge tone={PAY[p.state]}>{p.state.replace("_", " ")}</Badge> {p.simulated && <Badge>simulated</Badge>}{p.failure_reason && <p className="mt-0.5 text-xs text-muted">{p.failure_reason}</p>}{p.state === "refunded" && <p className="mt-0.5 text-xs text-muted">Refunded {money(p.refunded_minor, p.currency)} · {p.refund_reason}</p>}</td>
                  <td className="px-2 py-3 font-mono text-xs">{p.provider_ref}</td>
                  <td className="px-2 py-3">{p.receipt ? <a className="font-semibold underline" href={`/receipt/${p.receipt.token}`} target="_blank" rel="noreferrer">{p.receipt.number}</a> : "—"}{p.receipt?.revoked && <Badge tone="bad" className="ml-1">revoked</Badge>}</td>
                  <td className="px-2 py-3 text-right"><Button size="sm" variant="ghost" onClick={() => setOpenPay(openPay === p.id ? null : p.id)}>{openPay === p.id ? "Hide" : "Events"} ({p.events.length})</Button>{p.state === "succeeded" && can("payments.refund") && <Button size="sm" variant="ghost" onClick={() => setRefunding(p)}>Refund…</Button>}{p.receipt && !p.receipt.revoked && can("settings.edit") && <Button size="sm" variant="ghost" onClick={() => revoke.mutate(p.receipt.id)}>Revoke link</Button>}</td>
                </tr>
                {openPay === p.id && <tr key={p.id + "e"}><td colSpan={6} className="bg-black/[.03] px-4 py-3"><p className="mb-1 text-xs font-semibold text-muted">Provider events (verified, de-duplicated)</p>{p.events.length === 0 ? <p className="text-sm text-muted">None yet.</p> : <ul className="space-y-1 text-sm">{p.events.map((e: J) => <li key={e.event_id} className="flex flex-wrap gap-x-3"><span className="font-mono text-xs">{e.event_id}</span><span>{e.type}</span><Badge tone={e.outcome === "applied" ? "good" : "warn"}>{e.outcome}</Badge><span className="text-muted">{e.verified ? "signature verified" : "unverified"}</span></li>)}</ul>}</td></tr>}
              </Fragment>
            ))}</tbody></table></div>
        )}
      </Panel>
      <Panel title="Receipt messages" className="mt-6">
        {!notes.data ? <Skeleton className="h-32" /> : notes.data.length === 0 ? <Empty title="No messages yet" body="After a verified payment, the receipt link is queued by SMS and email." /> : (
          <ul className="divide-y divide-stone">{notes.data.map((n: J) => (
            <li key={n.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div><p className="font-semibold">{n.channel === "sms" ? "SMS" : "Email"} to {n.recipient} <span className="font-normal text-muted">· receipt {n.receipt_number}</span></p>
                <p className="text-sm text-muted">{n.attempts} attempt{n.attempts === 1 ? "" : "s"}{n.last_error ? ` · ${n.last_error}` : ""}{n.next_attempt_at && n.state === "retry_scheduled" ? " · retrying automatically" : ""}</p></div>
              <div className="flex items-center gap-2"><Badge tone={NOTE[n.state][0]}>{n.simulated && n.state === "sent" ? "Logged (simulated)" : NOTE[n.state][1]}</Badge>{can("notifications.retry") && n.state !== "sent" && <Button size="sm" variant="outline" loading={retry.isPending} onClick={() => retry.mutate(n.id)}>Retry now</Button>}</div>
            </li>))}</ul>
        )}
      </Panel>
      <Modal open={!!refunding} onOpenChange={(o) => !o && setRefunding(null)} title={`Refund Table ${refunding?.table}?`}>
        <p className="text-sm text-muted">The full amount ({refunding ? money(refunding.amount_minor, refunding.currency) : ""}) goes back through the payment provider and the receipt is marked refunded. This is recorded in the audit log with your name.{restaurant.is_demo && " Sample restaurant: the refund is simulated."}</p>
        <div className="mt-3"><Field label="Reason"><Input value={why} onChange={(e) => setWhy(e.target.value)} placeholder="Dish not served" autoFocus /></Field></div>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setRefunding(null)}>Cancel</Button><Button variant="danger" disabled={!why.trim()} loading={refund.isPending} onClick={() => refund.mutate()}>Refund in full</Button></div>
      </Modal>
    </>
  );
}
