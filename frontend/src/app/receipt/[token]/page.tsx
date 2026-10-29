"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Star } from "lucide-react";
import { toast } from "sonner";
import { Download, Printer } from "lucide-react";
import { api, J } from "@/lib/api";
import { money } from "@/lib/format";
import { Confetti } from "@/components/fx";
import { Check } from "lucide-react";
import { Badge, Button, ErrorBox, Skeleton, Textarea, cx } from "@/components/ui";

function ReviewBox({ token, existing }: { token: string; existing: J | null }) {
  const qc = useQueryClient();
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState("");
  const send = useMutation({ mutationFn: () => api(`/receipts/${token}/review`, { body: { rating, comment } }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["receipt", token] }); toast.success("Thanks for the feedback!"); }, onError: (e: J) => toast.error(e.message) });
  if (existing) return (
    <section className="no-print pop mt-4 rounded-3xl bg-white p-5 text-center ring-1 ring-stone">
      <p className="font-display text-xl font-bold">Thanks for rating your visit</p>
      <div className="mt-2 flex justify-center">{[1, 2, 3, 4, 5].map((i) => <Star key={i} className={cx("size-7", i <= existing.rating ? "fill-amber text-amber" : "text-black/15")} />)}</div>
      {existing.comment && <p className="mt-2 text-sm text-muted">“{existing.comment}”</p>}
    </section>
  );
  const shown = hover || rating;
  return (
    <section className="no-print mt-4 rounded-3xl bg-white p-5 ring-1 ring-stone" aria-labelledby="rate-h">
      <h2 id="rate-h" className="font-display text-xl font-bold">How was your visit?</h2>
      <div className="mt-2 flex gap-1" role="radiogroup" aria-label="Rating" onPointerLeave={() => setHover(0)}>
        {[1, 2, 3, 4, 5].map((i) => (
          <button key={i} role="radio" aria-checked={rating === i} aria-label={`${i} star${i > 1 ? "s" : ""}`} onPointerEnter={() => setHover(i)} onClick={() => setRating(i)} className="press p-0.5">
            <Star className={cx("size-10 transition-all duration-200", i <= shown ? "scale-110 fill-amber text-amber" : "text-black/15")} />
          </button>
        ))}
      </div>
      {rating > 0 && (
        <div className="tab-in mt-3">
          <Textarea rows={3} maxLength={600} placeholder="What stood out? (optional)" value={comment} onChange={(e) => setComment(e.target.value)} aria-label="Comment" />
          <Button className="mt-3 w-full" variant="primary" size="lg" loading={send.isPending} onClick={() => send.mutate()}>Send review</Button>
        </div>
      )}
    </section>
  );
}

export default function ReceiptPage() {
  const { token } = useParams<{ token: string }>();
  const q = useQuery({ queryKey: ["receipt", token], queryFn: () => api(`/receipts/${token}`) });
  if (q.isLoading) return <main className="mx-auto max-w-md p-6"><Skeleton className="h-96 w-full" /></main>;
  if (q.isError) return <main className="mx-auto max-w-md p-6"><ErrorBox message={(q.error as J).message} /></main>;
  const r = q.data, b = r.bill, cur = b.currency;
  return (
    <main className="mx-auto max-w-md p-4 pb-16">
      {!r.refund && <Confetti count={70} />}
      <div className="no-print flex flex-col items-center pb-5 pt-6 text-center">
        <span className="relative grid size-20 place-items-center rounded-full bg-pine text-lime shadow-[0_18px_50px_-12px_rgba(18,55,42,.7)]" style={{ animation: "pop .6s cubic-bezier(.2,1.4,.4,1) both" }}>
          <span aria-hidden className="absolute inset-0 animate-ping rounded-full bg-lime/40" style={{ animationIterationCount: 2 }} />
          <Check className="relative size-10" strokeWidth={3} style={{ animation: "check-pop .6s .25s cubic-bezier(.2,1.4,.4,1) both" }} />
        </span>
        <p className="font-display mt-4 text-3xl font-extrabold">{r.refund ? <>Payment <span className="font-flair font-medium">refunded</span></> : <>Payment <span className="font-flair font-medium">received</span></>}</p>
        <p className="mt-1 text-sm text-muted">Thank you — enjoy the rest of your evening.</p>
      </div>
      <article className="tab-in rounded-[28px] bg-white p-6 shadow-sm ring-1 ring-stone" style={{ animationDelay: ".35s" }}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl font-extrabold leading-tight">{r.restaurant.name}</h1>
            <p className="text-sm text-muted">Receipt {r.number} · Table {r.table}</p>
          </div>
          {r.refund ? <Badge tone="warn">Refunded</Badge> : <Badge tone="good">Paid</Badge>}
        </div>
        {r.refund && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-900">This bill was refunded in full on {new Date(r.refund.refunded_at).toLocaleDateString("en-IN", { dateStyle: "medium" })}: {r.refund.reason}.</p>}
        {(r.payment.simulated || r.restaurant.is_demo) && <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">Demo receipt: this was a simulated payment at a sample restaurant. No money moved.</p>}
        <p className="mt-3 text-sm text-muted">{new Date(r.payment.paid_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: r.restaurant.timezone })}{r.guest_first_name ? ` · ${r.guest_first_name}` : ""}</p>

        <div className="mt-5 space-y-4">
          {b.tickets.map((t: J) => (
            <section key={t.order_id}>
              {b.tickets.length > 1 && <h2 className="mb-1 text-sm font-semibold text-muted">{t.ticket_type === "addon" ? `Add-on ${t.label}` : `Order ${t.label}`}</h2>}
              <ul className="space-y-1">{t.items.map((i: J, n: number) => <li key={n} className="flex items-baseline gap-2"><span>{i.quantity}× {i.name}</span><span className="leader" aria-hidden /><span>{money(i.line_total_minor, cur)}</span></li>)}</ul>
            </section>
          ))}
        </div>

        <dl className="mt-5 space-y-1 border-t border-stone pt-4 text-[15px]">
          <Row k="Subtotal" v={money(b.subtotal_minor, cur)} />
          {b.service_charge_minor > 0 && <Row k={`Service charge (${b.service_charge_bps / 100}%)`} v={money(b.service_charge_minor, cur)} />}
          <Row k={`${b.tax_label} (${b.tax_bps / 100}%${b.tax_inclusive ? ", included" : ""})`} v={money(b.tax_minor, cur)} />
          {b.rounding_minor !== 0 && <Row k="Rounding" v={money(b.rounding_minor, cur)} />}
          <div className="flex items-baseline justify-between pt-2"><dt className="font-display text-xl font-bold">Total paid</dt><dd className="font-display text-3xl font-extrabold">{money(b.total_minor, cur)}</dd></div>
        </dl>
        <p className="mt-4 break-all text-xs text-muted">Payment reference {r.payment.reference}</p>
      </article>
      {!r.refund && <ReviewBox token={token} existing={r.review} />}
      <div className="no-print mt-4 grid grid-cols-2 gap-2">
        <Button variant="outline" onClick={() => window.print()}><Printer className="size-4" />Print</Button>
        <a href={`/api/v1/receipts/${token}/pdf`} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-stone bg-white font-semibold"><Download className="size-4" />PDF</a>
      </div>
    </main>
  );
}
const Row = ({ k, v }: { k: string; v: string }) => <div className="flex items-baseline gap-2"><dt className="text-muted">{k}</dt><span className="leader" aria-hidden /><dd>{v}</dd></div>;
