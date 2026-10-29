"use client";
import Link from "next/link";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileUp, RotateCw } from "lucide-react";
import { api, J } from "@/lib/api";
import { money } from "@/lib/format";
import { useAdmin } from "@/components/admin/context";
import { PageHead, Panel } from "@/components/admin/bits";
import { Badge, Button, Empty, Input, Sheet, Skeleton, cx } from "@/components/ui";

const STATUS: Record<string, ["neutral" | "info" | "warn" | "good" | "bad", string]> = { queued: ["neutral", "Waiting"], processing: ["info", "Reading…"], review: ["warn", "Ready to review"], approved: ["good", "Draft created"], failed: ["bad", "Couldn't read"] };
const FLAG: Record<string, string> = { price_missing: "No price found", price_ambiguous: "Two prices", duplicate: "Possible duplicate", low_confidence: "Low confidence", price_outlier: "Unusual price" };

export default function Imports() {
  const { rid, can } = useAdmin();
  const qc = useQueryClient();
  const file = useRef<HTMLInputElement>(null);
  const [review, setReview] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const jobs = useQuery({ queryKey: ["jobs", rid], queryFn: () => api(`/restaurants/${rid}/ingestion-jobs`), refetchInterval: (q) => (q.state.data?.some((j: J) => ["queued", "processing"].includes(j.status)) ? 1500 : 8000) });
  const up = useMutation({
    mutationFn: (f: File) => { const fd = new FormData(); fd.append("file", f); return api(`/restaurants/${rid}/menu-uploads`, { form: fd }); },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["jobs", rid] }); toast.success("Uploaded. Reading your menu…"); }, onError: (e: J) => toast.error(e.message),
  });
  const retry = useMutation({ mutationFn: (id: string) => api(`/restaurants/${rid}/ingestion-jobs/${id}/process`, { method: "POST" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs", rid] }), onError: (e: J) => toast.error(e.message) });
  const pick = (fl: FileList | null) => { const f = fl?.[0]; if (f) up.mutate(f); };

  return (
    <>
      <PageHead title="Menu imports" sub="Upload a PDF or a photo of your menu. We read it, you check it, and nothing reaches guests until you approve and publish a draft." />
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files); }}
        className={cx("mb-6 rounded-3xl border-2 border-dashed p-8 text-center transition", drag ? "border-pine bg-lime/20" : "border-stone bg-white")}>
        <FileUp className="mx-auto size-8 text-pine" />
        <p className="mt-2 font-display text-xl font-bold">Drop a menu here</p>
        <p className="text-sm text-muted">PDF, JPEG, PNG or WebP · up to 10 MB · PDFs up to 20 pages. Text PDFs are read directly; photos and scans use OCR.</p>
        <input ref={file} type="file" hidden accept="application/pdf,image/png,image/jpeg,image/webp" onChange={(e) => { pick(e.target.files); e.target.value = ""; }} aria-label="Choose a menu file" />
        <Button className="mt-4" loading={up.isPending} disabled={!can("uploads.manage")} onClick={() => file.current?.click()}>Choose a file</Button>
      </div>
      <Panel title="Recent imports">
        {!jobs.data ? <Skeleton className="h-32" /> : jobs.data.length === 0 ? <Empty title="No imports yet" /> : (
          <ul className="divide-y divide-stone">{jobs.data.map((j: J) => (
            <li key={j.id} className="flex flex-wrap items-center justify-between gap-3 py-3.5">
              <div className="min-w-0"><p className="truncate font-semibold">{j.filename}</p><p className="text-sm text-muted">{(j.size_bytes / 1024).toFixed(0)} KB{j.method ? ` · read by ${j.method === "ocr" ? "OCR" : "PDF text"}` : ""} · attempt {j.attempts}</p>{j.error && <p className="mt-1 text-sm text-chilli">{j.error}</p>}</div>
              <div className="flex items-center gap-2"><Badge tone={STATUS[j.status][0]}>{STATUS[j.status][1]}</Badge>
                {["review", "approved"].includes(j.status) && <Button size="sm" onClick={() => setReview(j.id)}>{j.status === "review" ? "Review dishes" : "View"}</Button>}
                {j.status === "failed" && <Button size="sm" variant="outline" loading={retry.isPending} onClick={() => retry.mutate(j.id)}><RotateCw className="size-4" />Try again</Button>}</div>
            </li>))}</ul>
        )}
      </Panel>
      {review && <Review jobId={review} onClose={() => setReview(null)} />}
    </>
  );
}

function Review({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const { rid, restaurant } = useAdmin();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cands", jobId], queryFn: () => api(`/restaurants/${rid}/ingestion-jobs/${jobId}/candidates`) });
  const inv = () => qc.invalidateQueries({ queryKey: ["cands", jobId] });
  const patch = useMutation({ mutationFn: ({ id, body }: { id: string; body: J }) => api(`/restaurants/${rid}/ingestion-candidates/${id}`, { method: "PATCH", body }), onSuccess: inv, onError: (e: J) => toast.error(e.message) });
  const bulk = useMutation({ mutationFn: (body: J) => api(`/restaurants/${rid}/ingestion-jobs/${jobId}/bulk`, { body }), onSuccess: inv });
  const approve = useMutation({ mutationFn: () => api(`/restaurants/${rid}/ingestion-jobs/${jobId}/approve`, { method: "POST" }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["jobs", rid] }); qc.invalidateQueries({ queryKey: ["menus", rid] }); toast.success("Draft menu created — publish it from Menu & prices."); onClose(); }, onError: (e: J) => toast.error(e.message) });
  const cands: J[] = q.data?.candidates ?? [];
  const approved = cands.filter((c) => c.review_state === "approved").length;
  const done = q.data?.job.status === "approved";
  const [price, setPrice] = useState<Record<string, string>>({});
  const [name, setName] = useState<Record<string, string>>({});

  return (
    <Sheet open onOpenChange={(o) => !o && onClose()} side="right" wide title="Check the dishes we found" description="Fix names and prices, tick the ones to import. We never fill in ingredients, allergens or diets for you.">
      {!q.data ? <Skeleton className="h-64" /> : (
        <div className="pt-2">
          {!done && <div className="mb-3 flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => bulk.mutate({ review_state: "approved", only_unflagged: true })}>Approve all without warnings</Button><Button size="sm" variant="ghost" onClick={() => bulk.mutate({ review_state: "pending" })}>Reset</Button></div>}
          <ul className="space-y-2">
            {cands.map((c) => (
              <li key={c.id} className={cx("rounded-2xl p-3 ring-1", c.review_state === "approved" ? "bg-lime/20 ring-pine/30" : c.review_state === "rejected" ? "opacity-50 ring-stone" : "bg-white ring-stone")}>
                <div className="flex flex-wrap items-center gap-2">
                  <Input aria-label="Dish name" className="min-w-[160px] flex-1" disabled={done} value={name[c.id] ?? c.name} onChange={(e) => setName({ ...name, [c.id]: e.target.value })} onBlur={() => name[c.id] !== undefined && name[c.id] !== c.name && patch.mutate({ id: c.id, body: { name: name[c.id] } })} />
                  <label className="flex items-center gap-1"><span className="text-muted">{restaurant.currency === "INR" ? "₹" : ""}</span><Input aria-label="Price" inputMode="decimal" className="w-24" disabled={done} invalid={c.price_minor == null} value={price[c.id] ?? (c.price_minor != null ? String(c.price_minor / 100) : "")} onChange={(e) => setPrice({ ...price, [c.id]: e.target.value })} onBlur={() => { const v = price[c.id]; if (v === undefined) return; const m = Math.round(parseFloat(v) * 100); if (Number.isFinite(m) && m !== c.price_minor) patch.mutate({ id: c.id, body: { price_minor: m } }); }} /></label>
                  {!done && <><Button size="sm" variant={c.review_state === "approved" ? "primary" : "outline"} onClick={() => patch.mutate({ id: c.id, body: { review_state: c.review_state === "approved" ? "pending" : "approved" } })}>{c.review_state === "approved" ? "Approved" : "Approve"}</Button><Button size="sm" variant="ghost" onClick={() => patch.mutate({ id: c.id, body: { review_state: c.review_state === "rejected" ? "pending" : "rejected" } })}>{c.review_state === "rejected" ? "Restore" : "Skip"}</Button></>}
                </div>
                <p className="mt-1.5 text-xs text-muted">{c.category}{c.description ? ` · ${c.description}` : ""} · page {c.source.page} · {Math.round(c.confidence * 100)}% sure{c.source.alt_prices?.length ? ` · other price seen: ${money(c.source.alt_prices[0], restaurant.currency)}` : ""}</p>
                {c.flags.length > 0 && <p className="mt-1 flex flex-wrap gap-1">{c.flags.map((f: string) => <Badge key={f} tone="warn">{FLAG[f] ?? f}</Badge>)}</p>}
              </li>
            ))}
          </ul>
          {done ? <p className="mt-4 rounded-xl bg-emerald-50 p-3 text-sm">This import became a draft menu. <Link href="/admin/menu" className="font-semibold underline">Open Menu &amp; prices</Link> to publish it.</p> : (
            <div className="sticky -mx-5 bottom-0 mt-4 flex items-center justify-between gap-3 border-t border-stone bg-[var(--surface)] px-5 py-3">
              <p className="text-sm"><b>{approved}</b> of {cands.length} approved · goes to a draft, not live</p>
              <Button disabled={approved === 0} loading={approve.isPending} onClick={() => approve.mutate()}>Create draft menu</Button>
            </div>
          )}
        </div>
      )}
    </Sheet>
  );
}
