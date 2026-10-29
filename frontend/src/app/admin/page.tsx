"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight } from "lucide-react";
import { api, J } from "@/lib/api";
import { money } from "@/lib/format";
import { useAdmin } from "@/components/admin/context";
import { PageHead, Panel, Stat, SESSION_LABEL, OrderBadge } from "@/components/admin/bits";
import { Badge, Empty, Skeleton } from "@/components/ui";

export default function Overview() {
  const { rid, restaurant, can } = useAdmin();
  const d = useQuery({ queryKey: ["dash", rid], queryFn: () => api(`/restaurants/${rid}/dashboard`), refetchInterval: 8000 });
  const s = useQuery({ queryKey: ["sessions", rid], queryFn: () => api(`/restaurants/${rid}/sessions`), enabled: can("sessions.view"), refetchInterval: 8000 });
  const o = useQuery({ queryKey: ["orders-recent", rid], queryFn: () => api(`/restaurants/${rid}/orders?limit=6`), refetchInterval: 8000 });
  const x = d.data;
  const todo = x ? [
    x.imports_to_review > 0 && { href: "/admin/imports", text: `${x.imports_to_review} menu import${x.imports_to_review > 1 ? "s" : ""} waiting for your review` },
    x.failed_notifications > 0 && { href: "/admin/payments", text: `${x.failed_notifications} receipt message${x.failed_notifications > 1 ? "s" : ""} failed to send` },
    x.sold_out_items > 0 && { href: "/admin/menu", text: `${x.sold_out_items} dish${x.sold_out_items > 1 ? "es are" : " is"} sold out right now` },
  ].filter(Boolean) as { href: string; text: string }[] : [];

  return (
    <>
      <PageHead title={restaurant.name} sub="What's happening right now across your tables, kitchen and payments." />
      {!x ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-32" />)}</div> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Stat label="Tickets in the kitchen" value={x.active_tickets} hint="Waiting, cooking or ready to serve" tone={x.active_tickets > 6 ? "alert" : undefined} />
          <Stat label="Tables with guests" value={x.active_tables} hint={`${x.awaiting_payment} waiting to pay`} />
          <Stat label="Orders, last 24 hours" value={x.orders_24h} />
          <Stat label="Paid, last 24 hours" value={money(x.paid_24h_minor, x.currency)} hint={restaurant.is_demo ? "Includes simulated payments" : undefined} />
        </div>
      )}

      {todo.length > 0 && (
        <ul className="mt-5 space-y-2">{todo.map((t) => <li key={t.href}><Link href={t.href} className="flex items-center justify-between gap-3 rounded-2xl bg-amber-50 p-4 text-amber-950 ring-1 ring-amber-200"><span className="flex items-center gap-2 font-semibold"><AlertTriangle className="size-5" />{t.text}</span><ArrowRight className="size-5" /></Link></li>)}</ul>
      )}

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Panel title="Tables right now" actions={<Link href="/admin/orders" className="text-sm font-semibold underline">Manage</Link>}>
          {!s.data ? <Skeleton className="h-32" /> : s.data.length === 0 ? <Empty title="No guests seated" body="When someone scans a table QR and orders, the table shows up here." /> : (
            <ul className="divide-y divide-stone">{s.data.map((t: J) => (
              <li key={t.id} className="flex items-center justify-between gap-3 py-3">
                <div><p className="font-display text-lg font-bold">Table {t.table}</p><p className="text-sm text-muted">{t.guest ? t.guest.split(" ")[0] : "No name yet"} · {t.tickets} ticket{t.tickets === 1 ? "" : "s"}</p></div>
                <div className="text-right"><p className="font-semibold">{money(t.total_minor, restaurant.currency)}</p><Badge tone={t.state === "paid" ? "good" : t.state === "payment_pending" ? "warn" : "neutral"}>{SESSION_LABEL[t.state]}</Badge></div>
              </li>))}</ul>
          )}
        </Panel>
        <Panel title="Latest tickets" actions={<Link href="/kitchen" className="text-sm font-semibold underline">Kitchen display</Link>}>
          {!o.data ? <Skeleton className="h-32" /> : o.data.length === 0 ? <Empty title="No tickets yet" /> : (
            <ul className="divide-y divide-stone">{o.data.map((t: J) => (
              <li key={t.id} className="flex items-center justify-between gap-3 py-3">
                <div><p className="font-semibold">#{t.number} · Table {t.table} {t.ticket_type === "addon" && <Badge tone="lime">Add-on {t.label}</Badge>}</p><p className="text-sm text-muted">{t.items.map((i: J) => `${i.quantity}× ${i.name}`).join(", ")}</p></div>
                <OrderBadge state={t.state} />
              </li>))}</ul>
          )}
        </Panel>
      </div>
    </>
  );
}
