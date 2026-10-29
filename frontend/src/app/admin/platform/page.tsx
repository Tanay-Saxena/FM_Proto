"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api, J } from "@/lib/api";
import { Badge, ErrorBox, Skeleton } from "@/components/ui";
import { Panel, Stat } from "@/components/admin/bits";

export default function Platform() {
  const r = useQuery({ queryKey: ["platform-r"], queryFn: () => api("/platform/restaurants") });
  const h = useQuery({ queryKey: ["platform-h"], queryFn: () => api("/platform/health") });
  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-end justify-between"><h1 className="font-display text-4xl font-extrabold">Platform</h1><Link href="/" className="text-sm font-semibold underline">Home</Link></div>
      {(r.isError || h.isError) && <ErrorBox message="Platform administrators only. Sign in with a platform account." />}
      {h.data && <div className="grid gap-4 sm:grid-cols-3"><Stat label="Failed menu imports" value={h.data.failed_ingestion_jobs} /><Stat label="Failed receipt messages" value={h.data.failed_notifications} /><Stat label="Rejected webhooks" value={h.data.rejected_webhooks} hint={`Provider: ${h.data.payment_provider}${h.data.demo_mode ? " · demo mode ON" : ""}`} /></div>}
      <Panel title="Restaurants">{!r.data ? <Skeleton className="h-24" /> : <ul className="divide-y divide-stone">{r.data.map((x: J) => <li key={x.id} className="flex items-center justify-between py-3"><span className="font-semibold">{x.name} <span className="font-normal text-muted">/r/{x.slug}</span></span><span className="flex gap-2">{x.is_demo && <Badge tone="lime">sample</Badge>}<Badge tone={x.status === "active" ? "good" : "bad"}>{x.status}</Badge></span></li>)}</ul>}
        <p className="mt-3 text-xs text-muted">Platform administrators manage onboarding and see integration health. Tenant orders, menus and receipts are not accessible from here.</p></Panel>
    </main>
  );
}
