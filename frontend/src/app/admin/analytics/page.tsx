"use client";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, J } from "@/lib/api";
import { useAdmin } from "@/components/admin/context";
import { PageHead, Panel, Stat } from "@/components/admin/bits";
import { Badge, Skeleton } from "@/components/ui";

export default function Analytics() {
  const { rid } = useAdmin();
  const q = useQuery({ queryKey: ["analytics", rid], queryFn: () => api(`/restaurants/${rid}/analytics`) });
  const d = q.data;
  const ev = d?.engagement ?? {};
  const ctr = ev.rec_impression ? Math.round(((ev.rec_click ?? 0) / ev.rec_impression) * 100) : null;
  const axis = { fontSize: 12, fill: "#5a6b60" };
  return (
    <>
      <PageHead title="Analytics" sub="Last 14 days. Counts only — no guest names, phone numbers or emails." actions={d?.includes_demo_data && <Badge tone="lime">Includes sample demo data</Badge>} />
      {!d ? <Skeleton className="h-96" /> : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat label="Menu views" value={ev.menu_view ?? 0} /><Stat label="Dish views" value={ev.dish_view ?? 0} /><Stat label="Added to order" value={ev.add_to_cart ?? 0} />
            <Stat label="Recommendation click rate" value={ctr === null ? "—" : `${ctr}%`} hint={`${ev.rec_click ?? 0} clicks / ${ev.rec_impression ?? 0} shown`} />
          </div>
          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Orders per day">
              <div className="h-64" role="img" aria-label="Bar chart of orders per day"><ResponsiveContainer><BarChart data={d.orders_by_day} margin={{ left: -20 }}><CartesianGrid vertical={false} stroke="#dce2d6" /><XAxis dataKey="day" tickFormatter={(v: string) => v.slice(5)} tick={axis} tickLine={false} axisLine={false} /><YAxis allowDecimals={false} tick={axis} tickLine={false} axisLine={false} /><Tooltip cursor={{ fill: "#0000000a" }} /><Bar dataKey="orders" fill="#12372a" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div>
            </Panel>
            <Panel title="Busiest hours (local time)">
              <div className="h-64" role="img" aria-label="Bar chart of orders by hour"><ResponsiveContainer><BarChart data={d.orders_by_hour} margin={{ left: -20 }}><CartesianGrid vertical={false} stroke="#dce2d6" /><XAxis dataKey="hour" tick={axis} tickLine={false} axisLine={false} /><YAxis allowDecimals={false} tick={axis} tickLine={false} axisLine={false} /><Tooltip cursor={{ fill: "#0000000a" }} labelFormatter={(h) => `${h}:00`} /><Bar dataKey="orders" fill="#12372a" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div>
            </Panel>
          </div>
          <Panel title="Top dishes by quantity ordered">
            {d.top_items.length === 0 ? <p className="text-sm text-muted">No orders yet.</p> : (
              <div style={{ height: d.top_items.length * 44 + 20 }} role="img" aria-label="Bar chart of top dishes"><ResponsiveContainer><BarChart data={d.top_items} layout="vertical" margin={{ left: 40, right: 20 }}><XAxis type="number" hide /><YAxis type="category" dataKey="name" width={170} tick={{ ...axis, fill: "#0e1a13" }} tickLine={false} axisLine={false} /><Tooltip cursor={{ fill: "#0000000a" }} /><Bar dataKey="quantity" fill="#12372a" radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></div>
            )}
            <p className="mt-2 text-xs text-muted">Ranked from real orders. “Chef&apos;s pick”-style labels are set by you and are not popularity claims.</p>
          </Panel>
        </div>
      )}
    </>
  );
}
