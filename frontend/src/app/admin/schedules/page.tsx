"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { api, J } from "@/lib/api";
import { useAdmin } from "@/components/admin/context";
import { PageHead, Panel } from "@/components/admin/bits";
import { Badge, Button, Empty, Field, Input, Select, Sheet, Skeleton, cx } from "@/components/ui";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const t12 = (t: string) => { const [h, m] = t.split(":").map(Number); return `${((h + 11) % 12) + 1}${m ? `:${String(m).padStart(2, "0")}` : ""} ${h < 12 ? "AM" : "PM"}`; };
export function describe(r: J) {
  const days = !r.days?.length || r.days.length === 7 ? "Every day" : r.days.length === 5 && !r.days.includes(5) && !r.days.includes(6) ? "Mon–Fri" : r.days.map((d: number) => DAYS[d]).join(", ");
  const time = r.start_time && r.end_time ? `${t12(r.start_time)} – ${t12(r.end_time)}${r.start_time > r.end_time ? " (past midnight)" : ""}` : "All day";
  const dates = r.start_date ? (r.end_date && r.end_date !== r.start_date ? `${r.start_date} to ${r.end_date}` : r.start_date) : "";
  if (r.kind === "date_exception") return `${dates} · ${r.effect === "block" ? "Closed" : time}`;
  if (r.kind === "season") return `${dates} · ${days}`;
  return `${days} · ${time}${dates ? ` · ${dates}` : ""}`;
}

export default function Schedules() {
  const { rid, can } = useAdmin();
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const rules = useQuery({ queryKey: ["rules", rid], queryFn: () => api(`/restaurants/${rid}/availability-rules`) });
  const menus = useQuery({ queryKey: ["menus", rid], queryFn: () => api(`/restaurants/${rid}/menus`) });
  const live = menus.data?.find((m: J) => m.status === "published");
  const menu = useQuery({ queryKey: ["menu", rid, live?.id], queryFn: () => api(`/restaurants/${rid}/menus/${live.id}`), enabled: !!live });
  const del = useMutation({ mutationFn: (id: string) => api(`/restaurants/${rid}/availability-rules/${id}`, { method: "DELETE" }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["rules", rid] }); toast.success("Schedule removed"); } });
  const toggle = useMutation({ mutationFn: (r: J) => api(`/restaurants/${rid}/availability-rules/${r.id}`, { method: "PATCH", body: { active: !r.active } }), onSuccess: () => qc.invalidateQueries({ queryKey: ["rules", rid] }) });

  const cats: J[] = menu.data?.categories ?? [];
  const nameOf = (r: J) => r.target_type === "restaurant" ? "Whole restaurant" : r.target_type === "category" ? `Category: ${cats.find((c) => c.key === r.target_id)?.name ?? "?"}` : `Dish: ${cats.flatMap((c) => c.items).find((i: J) => i.key === r.target_id)?.name ?? "?"}`;
  const groups = [["restaurant", "Opening hours & closures", "When the kitchen takes orders."], ["category", "Category schedules", "e.g. breakfast only in the morning."], ["item", "Dish schedules", "Lunch specials, happy hour, seasonal dishes."]] as const;
  const canEdit = can("availability.edit");

  return (
    <>
      <PageHead title="Schedules" sub="Decide when things can be ordered. The same rules drive the guest menu, recommendations, the cart, and the final check when an order is sent." actions={canEdit && <Button onClick={() => setAdding(true)}><Plus className="size-4" />Add schedule</Button>} />
      <Panel className="mb-6">
        <p className="text-sm"><b>How conflicts are settled.</b> Hidden, paused or sold-out dishes are never orderable. A closure date beats everything. A special-hours date replaces the normal weekly hours that day. Otherwise a dish must be inside its own schedule <i>and</i> its category&apos;s <i>and</i> the restaurant&apos;s hours. Start times are included; end times are not (12:00–15:00 stops at 15:00).</p>
      </Panel>
      {!rules.data ? <Skeleton className="h-48" /> : (
        <div className="space-y-6">
          {groups.map(([type, title, sub]) => {
            const list = rules.data.filter((r: J) => r.target_type === type);
            return (
              <Panel key={type} title={title}>
                <p className="-mt-2 mb-3 text-sm text-muted">{sub}</p>
                {list.length === 0 ? <Empty title="Nothing scheduled" body={type === "restaurant" ? "With no hours set, the kitchen is treated as always open." : "These items follow the restaurant's hours."} /> : (
                  <ul className="divide-y divide-stone">{list.map((r: J) => (
                    <li key={r.id} className={cx("flex flex-wrap items-center justify-between gap-3 py-3", !r.active && "opacity-50")}>
                      <div><p className="font-semibold">{r.label || nameOf(r)} {r.kind === "date_exception" && <Badge tone={r.effect === "block" ? "bad" : "info"}>{r.effect === "block" ? "Closure" : "Special hours"}</Badge>} {r.kind === "season" && <Badge tone="info">Seasonal</Badge>}</p><p className="text-sm text-muted">{type !== "restaurant" && `${nameOf(r)} · `}{describe(r)}</p></div>
                      {canEdit && <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => toggle.mutate(r)}>{r.active ? "Turn off" : "Turn on"}</Button><Button size="sm" variant="ghost" aria-label={`Delete ${r.label || "schedule"}`} onClick={() => del.mutate(r.id)}><Trash2 className="size-4" /></Button></div>}
                    </li>))}</ul>
                )}
              </Panel>
            );
          })}
        </div>
      )}
      {adding && <RuleForm cats={cats} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); qc.invalidateQueries({ queryKey: ["rules", rid] }); }} />}
    </>
  );
}

function RuleForm({ cats, onClose, onSaved }: { cats: J[]; onClose: () => void; onSaved: () => void }) {
  const { rid, restaurant } = useAdmin();
  const [f, setF] = useState({ target_type: "restaurant", target_id: "", kind: "weekly", effect: "allow", label: "", days: [] as number[], start_time: "12:00", end_time: "15:00", allDay: false, start_date: "", end_date: "" });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const save = useMutation({
    mutationFn: () => api(`/restaurants/${rid}/availability-rules`, { body: {
      target_type: f.target_type, target_id: f.target_type === "restaurant" ? null : f.target_id, kind: f.kind, effect: f.kind === "date_exception" ? f.effect : "allow", label: f.label,
      days: f.kind === "weekly" ? f.days : [], start_time: f.allDay || (f.kind === "date_exception" && f.effect === "block" && f.allDay) || f.kind === "season" ? null : f.start_time, end_time: f.allDay || f.kind === "season" ? null : f.end_time,
      start_date: f.start_date || null, end_date: f.end_date || f.start_date || null } }),
    onSuccess: () => { toast.success("Schedule added"); onSaved(); }, onError: (e: J) => toast.error(e.message),
  });
  const items = cats.flatMap((c) => c.items.map((i: J) => ({ ...i, cat: c.name })));
  const needsTarget = f.target_type !== "restaurant";
  const needsDates = f.kind !== "weekly";
  const ok = (!needsTarget || f.target_id) && (!needsDates || f.start_date) && (f.kind === "season" ? f.end_date : true);
  return (
    <Sheet open onOpenChange={(o) => !o && onClose()} side="right" title="Add a schedule" description={`Times are in ${restaurant.timezone}.`}>
      <div className="space-y-4 pt-2">
        <Field label="What kind of schedule?">
          <Select className="w-full" value={f.kind} onChange={(e) => set({ kind: e.target.value })}>
            <option value="weekly">Weekly hours (days and times)</option><option value="date_exception">One-off date (holiday, closure, special hours)</option><option value="season">Seasonal window (start and end dates)</option>
          </Select>
        </Field>
        <Field label="Applies to">
          <Select className="w-full" value={f.target_type} onChange={(e) => set({ target_type: e.target.value, target_id: "" })}><option value="restaurant">Whole restaurant</option><option value="category">A category</option><option value="item">A dish</option></Select>
        </Field>
        {f.target_type === "category" && <Field label="Category"><Select className="w-full" value={f.target_id} onChange={(e) => set({ target_id: e.target.value })}><option value="">Choose…</option>{cats.map((c) => <option key={c.key} value={c.key}>{c.name}</option>)}</Select></Field>}
        {f.target_type === "item" && <Field label="Dish"><Select className="w-full" value={f.target_id} onChange={(e) => set({ target_id: e.target.value })}><option value="">Choose…</option>{items.map((i: J) => <option key={i.key} value={i.key}>{i.name} ({i.cat})</option>)}</Select></Field>}
        {f.kind === "date_exception" && <Field label="On that date"><Select className="w-full" value={f.effect} onChange={(e) => set({ effect: e.target.value })}><option value="block">Closed — nothing can be ordered</option><option value="allow">Open with special hours</option></Select></Field>}
        {f.kind === "weekly" && (
          <div><p className="mb-1.5 text-sm font-semibold">Days <span className="font-normal text-muted">(none ticked = every day)</span></p>
            <div className="flex flex-wrap gap-2">{DAYS.map((d, i) => <button type="button" key={d} aria-pressed={f.days.includes(i)} onClick={() => set({ days: f.days.includes(i) ? f.days.filter((x) => x !== i) : [...f.days, i] })} className={cx("h-10 w-12 rounded-xl text-sm font-semibold", f.days.includes(i) ? "bg-pine text-white" : "bg-white ring-1 ring-stone")}>{d}</button>)}</div></div>
        )}
        {needsDates && <div className="grid grid-cols-2 gap-3"><Field label={f.kind === "season" ? "First day" : "Date"}><Input type="date" value={f.start_date} onChange={(e) => set({ start_date: e.target.value })} /></Field><Field label={f.kind === "season" ? "Last day" : "Until (optional)"}><Input type="date" value={f.end_date} onChange={(e) => set({ end_date: e.target.value })} /></Field></div>}
        {f.kind !== "season" && !(f.kind === "date_exception" && f.effect === "block" && f.allDay) && (
          <>
            {(f.kind === "weekly" || f.effect === "block") && <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-5 accent-[var(--pine)]" checked={f.allDay} onChange={(e) => set({ allDay: e.target.checked })} />All day</label>}
            {!f.allDay && <div className="grid grid-cols-2 gap-3"><Field label="From"><Input type="time" value={f.start_time} onChange={(e) => set({ start_time: e.target.value })} /></Field><Field label="To" hint="Earlier than “From” means past midnight."><Input type="time" value={f.end_time} onChange={(e) => set({ end_time: e.target.value })} /></Field></div>}
          </>
        )}
        <Field label="Label (optional)"><Input value={f.label} onChange={(e) => set({ label: e.target.value })} placeholder="Lunch special" maxLength={80} /></Field>
        <Button className="w-full" size="lg" disabled={!ok} loading={save.isPending} onClick={() => save.mutate()}>Add schedule</Button>
      </div>
    </Sheet>
  );
}
