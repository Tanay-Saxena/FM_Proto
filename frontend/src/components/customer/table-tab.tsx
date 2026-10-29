"use client";
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Check, ChefHat, CircleDot, Receipt, ScanLine, Utensils } from "lucide-react";
import { Badge, Button, Empty, Sheet, cx } from "@/components/ui";
import { api, idem, J } from "@/lib/api";
import { Confetti } from "@/components/fx";
import { clock, money, STATE_LABEL } from "@/lib/format";

const STEPS = ["submitted", "accepted", "preparing", "ready", "served"];

const STATUS_COPY: Record<string, string> = {
  submitted: "Sent. Waiting for the kitchen to accept.",
  accepted: "Accepted. The chef is getting started.",
  preparing: "🔥 Being cooked right now.",
  ready: "✨ Ready! A server is bringing it over.",
  served: "Served. Enjoy your meal!",
};

function Steps({ state }: { state: string }) {
  if (state === "rejected" || state === "cancelled") return null;
  const idx = STEPS.indexOf(state);
  return (
    <>
    <ol className="mt-3 flex items-center gap-1" aria-label={`Progress: ${STATE_LABEL[state]}`}>
      {STEPS.map((s, i) => (
        <li key={s} className="flex flex-1 items-center gap-1" aria-current={i === idx ? "step" : undefined}>
          <span className={cx("h-1.5 flex-1 rounded-full transition-all duration-700", i <= idx ? "bg-brand" : "bg-black/10", i === idx && "animate-pulse")} />
        </li>
      ))}
    </ol>
    <p key={state} className="tab-in mt-2 text-sm font-semibold text-black/70" aria-live="polite">{STATUS_COPY[state]}</p>
    </>
  );
}

const tone = (s: string) => (s === "ready" ? "good" : s === "preparing" || s === "accepted" ? "info" : s === "rejected" || s === "cancelled" ? "bad" : s === "served" ? "neutral" : "warn") as "good" | "info" | "bad" | "neutral" | "warn";

export function TableTab({ session, token, onMore, refresh, restaurant }: { session: J; token: string | null; onMore: () => void; refresh: () => Promise<J>; restaurant: J }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [split, setSplit] = useState(1);
  const [checkout, setCheckout] = useState<J | null>(null);

  if (!token || !session) {
    return (
      <div className="pt-8">
        <Empty title="You're browsing" body="Scan the QR code on your table to order, add dishes, and pay your bill from here." action={<Link href={`/`} className="inline-flex h-11 items-center gap-2 rounded-xl bg-brand px-4 font-semibold text-brand-ink"><ScanLine className="size-5" />Pick a demo table</Link>} />
      </div>
    );
  }
  const bill = session.bill;
  const cur = session.restaurant.currency;
  const paid = ["paid", "closed"].includes(session.state) && session.receipt_token;
  const act = async (name: string, fn: () => Promise<J>) => {
    setBusy(name);
    try { await fn(); await refresh(); } catch (e: J) { toast.error(e.message); } finally { setBusy(null); }
  };

  const startPay = () => act("pay", async () => {
    const r = await api(`/table-sessions/${token}/payment-session`, { body: { idempotency_key: idem() } });
    setCheckout(r.payment);
  });

  return (
    <div className="space-y-6 pt-5">
      {paid && <Confetti />}
      <div className="flex items-end justify-between">
        <div>
          <h2 className="font-display text-[34px] font-bold leading-none">Table {session.table}</h2>
          <p className="mt-1 text-sm text-black/60">{session.zone ? `${session.zone} · ` : ""}{session.contact?.name ? `Hi ${session.contact.name.split(" ")[0]}` : "Not ordered yet"}</p>
        </div>
        <Badge tone={paid ? "good" : session.state === "payment_pending" ? "warn" : "neutral"}>{{ open: "Open", bill_requested: "Bill requested", payment_pending: "Paying", paid: "Paid", closed: paid ? "Paid" : "Closed" }[session.state as string]}</Badge>
      </div>

      {session.orders.length === 0 ? (
        <Empty title="Nothing ordered yet" body="Add dishes from the menu and send them to the kitchen." action={<Button variant="brand" onClick={onMore}><Utensils className="size-4" />Browse the menu</Button>} />
      ) : (
        <ul className="space-y-3">
          {session.orders.map((o: J) => (
            <li key={o.id} className={cx("rounded-3xl bg-white p-4 ring-1", o.ticket_type === "addon" ? "ring-2 ring-accent" : "ring-stone")}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-display text-lg font-bold leading-tight">{o.ticket_type === "addon" ? `Add-on ${o.label}` : `Order ${o.label}`} <span className="font-sans text-sm font-medium text-black/50">· #{o.number} · {clock(o.created_at)}</span></p>
                </div>
                <Badge tone={tone(o.state)}>{STATE_LABEL[o.state]}</Badge>
              </div>
              <Steps state={o.state} />
              <ul className="mt-3 space-y-1 text-[15px]">
                {o.items.map((i: J, n: number) => (
                  <li key={n} className="flex items-baseline gap-2"><span>{i.quantity}× {i.name}{i.modifiers?.length ? <span className="text-black/50"> ({i.modifiers.map((m: J) => m.name).join(", ")})</span> : null}</span><span className="leader" aria-hidden /><span>{money(i.line_total_minor, cur)}</span></li>
                ))}
              </ul>
              {o.reject_reason && <p className="mt-2 rounded-xl bg-red-50 p-2.5 text-sm text-red-900">The kitchen couldn&apos;t make this: {o.reject_reason}. It&apos;s not on your bill.</p>}
            </li>
          ))}
        </ul>
      )}

      {session.orders.length > 0 && (
        <section className="rounded-3xl bg-white p-5 ring-1 ring-stone" aria-labelledby="bill-h">
          <h3 id="bill-h" className="font-display text-xl font-bold">{paid ? "Paid bill" : "Running bill"}</h3>
          <dl className="mt-3 space-y-1.5 text-[15px]">
            <Row k="Subtotal" v={money(bill.subtotal_minor, cur)} />
            {bill.service_charge_minor > 0 && <Row k={`Service charge (${bill.service_charge_bps / 100}%)`} v={money(bill.service_charge_minor, cur)} />}
            <Row k={`${bill.tax_label} (${bill.tax_bps / 100}%${bill.tax_inclusive ? ", included" : ""})`} v={money(bill.tax_minor, cur)} />
            {bill.rounding_minor !== 0 && <Row k="Rounding" v={money(bill.rounding_minor, cur)} />}
            <div className="mt-2 flex items-baseline justify-between border-t border-stone pt-3"><dt className="font-display text-xl font-bold">Total</dt><dd className="font-display text-2xl font-bold">{money(bill.total_minor, cur)}</dd></div>
          </dl>
          {!paid && bill.total_minor > 0 && (
            <div className="mt-4 rounded-2xl bg-black/[.04] p-3">
              <div className="flex items-center justify-between gap-3">
                <div><p className="text-sm font-semibold">Splitting with friends?</p><p className="text-xs text-black/55">A quick calculator. The restaurant takes one payment.</p></div>
                <div className="inline-flex items-center rounded-xl bg-white ring-1 ring-stone" role="group" aria-label="Number of people">
                  <button type="button" aria-label="Fewer people" className="press grid size-9 place-items-center text-lg font-semibold disabled:opacity-30" disabled={split <= 1} onClick={() => setSplit(split - 1)}>−</button>
                  <span className="w-7 text-center font-semibold" aria-live="polite">{split}</span>
                  <button type="button" aria-label="More people" className="press grid size-9 place-items-center text-lg font-semibold disabled:opacity-30" disabled={split >= 20} onClick={() => setSplit(split + 1)}>+</button>
                </div>
              </div>
              {split > 1 && (() => {
                const base = Math.floor(bill.total_minor / split), extra = bill.total_minor - base * split;
                return <p key={split} className="pop mt-2 text-center font-display text-2xl font-bold">{money(base + (extra ? 1 : 0), cur)} <span className="text-base font-medium text-black/55">each{extra > 0 && split - extra > 0 ? ` · ${split - extra} pay ${money(base, cur)}` : ""}</span></p>;
              })()}
            </div>
          )}
          <p className="mt-2 text-xs text-black/50">Calculated by the restaurant&apos;s system from your tickets{bill.excluded_tickets.length ? ` · ${bill.excluded_tickets.length} rejected/cancelled ticket(s) not charged` : ""}.</p>

          {session.state === "open" && (
            <div className="mt-4 grid gap-2">
              <Button variant="outline" size="lg" onClick={onMore}>Add more dishes</Button>
              <Button variant="brand" size="lg" loading={busy === "bill"} onClick={() => act("bill", () => api(`/table-sessions/${token}/bill-request`, { method: "POST" }))}><Receipt className="size-5" />Request bill</Button>
            </div>
          )}
          {session.state === "bill_requested" && (
            <div className="mt-4 grid gap-2">
              <Button variant="brand" size="lg" loading={busy === "pay"} onClick={startPay}>Pay {money(bill.total_minor, cur)}</Button>
              <Button variant="ghost" onClick={onMore}>Forgot something? Add more</Button>
            </div>
          )}
          {session.state === "payment_pending" && (
            <div className="mt-4 grid gap-2">
              <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">Payment in progress, so new items are paused. If this got stuck, ask the staff to release it.</p>
              {session.payment?.state === "pending" && <Button variant="brand" size="lg" onClick={() => setCheckout({ id: session.payment.id, amount_minor: session.payment.amount_minor, simulated: session.payment.simulated })}>Continue payment</Button>}
            </div>
          )}
          {paid && (
            <div className="mt-4 space-y-2">
              <p className="flex items-center gap-2 rounded-xl bg-emerald-50 p-3 text-emerald-900"><Check className="size-5" /><span><b>Payment confirmed.</b>{session.payment?.simulated ? " (Simulated — demo only)" : ""} We&apos;ll send the receipt link to {session.contact?.phone_masked ?? "your phone"}.</span></p>
              <Link href={`/receipt/${session.receipt_token}`} className="flex h-14 items-center justify-center gap-2 rounded-xl bg-brand font-semibold text-brand-ink"><Receipt className="size-5" />Open your receipt</Link>
              <p className="text-center text-sm text-black/55">To order again, scan the QR on your table.</p>
            </div>
          )}
          {session.payment?.state === "failed" && session.state === "bill_requested" && <p role="alert" className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-900">That payment didn&apos;t go through ({session.payment.failure_reason}). Your bill is unchanged. Try again.</p>}
        </section>
      )}

      <Checkout checkout={checkout} onClose={() => setCheckout(null)} token={token} currency={cur} refresh={refresh} />
    </div>
  );
}

const Row = ({ k, v }: { k: string; v: string }) => <div className="flex items-baseline gap-2"><dt className="text-black/70">{k}</dt><span className="leader" aria-hidden /><dd>{v}</dd></div>;

function Checkout({ checkout, onClose, token, currency, refresh }: { checkout: J | null; onClose: () => void; token: string; currency: string; refresh: () => Promise<J> }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const run = async (outcome: "success" | "failure" | "cancel") => {
    setBusy(outcome); setResult(null);
    try {
      const r = await api(`/table-sessions/${token}/payments/${checkout!.id}/simulate`, { body: { outcome } });
      await refresh();
      if (r.state === "succeeded") { toast.success("Payment confirmed"); onClose(); }
      else { toast(outcome === "failure" ? "Payment declined. Nothing was charged." : "Checkout cancelled."); onClose(); }
    } catch (e: J) { setResult(e.message); } finally { setBusy(null); }
  };
  return (
    <Sheet open={!!checkout} onOpenChange={(o) => !o && onClose()} title="Pay your bill" description="Simulated checkout — no real money moves.">
      {checkout && (
        <div className="space-y-4 pt-2">
          <div className="rounded-3xl bg-brand p-6 text-brand-ink"><p className="text-sm opacity-80">Amount due</p><p className="font-display text-4xl font-bold">{money(checkout.amount_minor, currency)}</p></div>
          <p className="rounded-2xl bg-amber-50 p-3 text-sm text-amber-900">This is a <b>demo checkout</b>. In production a UPI/payment provider confirms payment to the server by a signed message; a button on this screen never decides it. Here the button plays the provider.</p>
          <Button variant="brand" size="lg" className="w-full" loading={busy === "success"} onClick={() => run("success")}><CircleDot className="size-5" />Simulate successful payment</Button>
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outline" loading={busy === "failure"} onClick={() => run("failure")}>Simulate failure</Button>
            <Button variant="outline" loading={busy === "cancel"} onClick={() => run("cancel")}>Cancel checkout</Button>
          </div>
          {result && <p role="status" className="text-sm text-black/70">{result}</p>}
        </div>
      )}
    </Sheet>
  );
}
