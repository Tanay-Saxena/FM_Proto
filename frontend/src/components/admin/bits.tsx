"use client";
import { Badge } from "@/components/ui";
import { STATE_LABEL } from "@/lib/format";

export function PageHead({ title, sub, actions }: { title: string; sub?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="font-display text-[34px] font-extrabold leading-none">{title}</h1>
        {sub && <p className="mt-1.5 max-w-2xl text-[15px] text-muted">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({ title, children, actions, className = "" }: { title?: string; children: React.ReactNode; actions?: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-3xl bg-white p-5 ring-1 ring-stone ${className}`}>
      {(title || actions) && <div className="mb-3 flex items-center justify-between gap-2">{title && <h2 className="font-display text-xl font-bold">{title}</h2>}{actions}</div>}
      {children}
    </section>
  );
}

export const orderTone = (s: string) => (s === "ready" ? "good" : s === "preparing" || s === "accepted" ? "info" : s === "rejected" || s === "cancelled" ? "bad" : s === "served" ? "neutral" : "warn") as "good" | "info" | "bad" | "neutral" | "warn";
export const OrderBadge = ({ state }: { state: string }) => <Badge tone={orderTone(state)}>{STATE_LABEL[state] ?? state}</Badge>;

import { CountUp } from "@/components/fx";
export function Stat({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: string; tone?: "alert" }) {
  return (
    <div className={`tab-in group rounded-3xl p-5 ring-1 transition duration-300 hover:-translate-y-1 hover:shadow-[0_18px_40px_-18px_rgba(18,55,42,.45)] ${tone === "alert" ? "bg-chilli text-white ring-chilli" : "bg-white ring-stone"}`}>
      <p className={`text-sm font-semibold ${tone === "alert" ? "text-white/85" : "text-muted"}`}>{label}</p>
      <p className="font-display mt-1 text-4xl font-extrabold leading-none">{typeof value === "number" ? <CountUp to={value} duration={900} /> : value}</p>
      {hint && <p className={`mt-2 text-xs ${tone === "alert" ? "text-white/80" : "text-muted"}`}>{hint}</p>}
    </div>
  );
}

export const SESSION_LABEL: Record<string, string> = { open: "Ordering", bill_requested: "Bill requested", payment_pending: "Paying", paid: "Paid", closed: "Closed" };
