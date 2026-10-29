"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { api, J } from "@/lib/api";
import { useAdmin } from "@/components/admin/context";
import { PageHead, Panel } from "@/components/admin/bits";
import { Badge, Button, Empty, Field, Input, Select, Sheet, Skeleton, cx } from "@/components/ui";
import { money } from "@/lib/format";

export default function Promotions() {
  const { rid, restaurant, can } = useAdmin();
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const rules = useQuery({ queryKey: ["recrules", rid], queryFn: () => api(`/restaurants/${rid}/recommendation-rules`) });
  const menus = useQuery({ queryKey: ["menus", rid], queryFn: () => api(`/restaurants/${rid}/menus`) });
  const live = menus.data?.find((m: J) => m.status === "published");
  const menu = useQuery({ queryKey: ["menu", rid, live?.id], queryFn: () => api(`/restaurants/${rid}/menus/${live.id}`), enabled: !!live });
  const cats: J[] = menu.data?.categories ?? [];
  const items = cats.flatMap((c) => c.items);
  const inv = () => qc.invalidateQueries({ queryKey: ["recrules", rid] });
  const patch = useMutation({ mutationFn: ({ id, body }: { id: string; body: J }) => api(`/restaurants/${rid}/recommendation-rules/${id}`, { method: "PATCH", body }), onSuccess: inv, onError: (e: J) => toast.error(e.message) });
  const del = useMutation({ mutationFn: (id: string) => api(`/restaurants/${rid}/recommendation-rules/${id}`, { method: "DELETE" }), onSuccess: () => { inv(); toast.success("Removed"); } });
  const [query, setQuery] = useState("something comforting");
  const preview = useMutation({ mutationFn: () => api(`/restaurants/${restaurant.slug}/recommendations`, { body: { query, limit: 8 } }) });
  const target = (r: J) => r.target_type === "item" ? items.find((i: J) => i.key === r.target_id)?.name ?? "(removed dish)" : cats.find((c) => c.key === r.target_id)?.name ?? "(removed category)";
  const canEdit = can("recommendations.edit");

  return (
    <>
      <PageHead title="Promotions" sub="Nudge what guests see first. A boost only reorders dishes that already pass availability, budget and diet checks — it can never make a sold-out dish orderable or show a non-vegetarian dish to a vegetarian guest." actions={canEdit && <Button onClick={() => setAdding(true)}><Plus className="size-4" />Add promotion</Button>} />
      <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <Panel title="Active rules">
          {!rules.data ? <Skeleton className="h-40" /> : rules.data.length === 0 ? <Empty title="No promotions" body="Feature a dish with a label like “Chef's pick”, or move one up or down in recommendations." /> : (
            <ul className="divide-y divide-stone">{rules.data.map((r: J) => (
              <li key={r.id} className={cx("py-3.5", !r.active && "opacity-50")}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div><p className="font-semibold">{target(r)} <span className="text-sm font-normal text-muted">({r.target_type})</span></p>
                    <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-sm">{r.weight !== 0 && <Badge tone={r.weight > 0 ? "good" : "warn"}>{r.weight > 0 ? `Boost +${r.weight}` : `Demote ${r.weight}`}</Badge>}{r.featured && <Badge tone="lime">Featured</Badge>}{r.label && <Badge>“{r.label}”</Badge>}{!r.allow_in_recommendations && <Badge tone="bad">Never recommended</Badge>}{(r.start_at || r.end_at) && <span className="text-muted">{r.start_at?.slice(0, 10) ?? "…"} → {r.end_at?.slice(0, 10) ?? "…"}</span>}</p></div>
                  {canEdit && <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => patch.mutate({ id: r.id, body: { active: !r.active } })}>{r.active ? "Turn off" : "Turn on"}</Button><Button size="sm" variant="ghost" aria-label="Delete promotion" onClick={() => del.mutate(r.id)}><Trash2 className="size-4" /></Button></div>}
                </div>
              </li>))}</ul>
          )}
        </Panel>
        <Panel title="Try the ranking">
          <p className="text-sm text-muted">See what a guest would get right now. Labels are the words you wrote — nothing is called “popular” unless real data says so.</p>
          <div className="mt-3 flex gap-2"><Input aria-label="Guest request" value={query} onChange={(e) => setQuery(e.target.value)} /><Button loading={preview.isPending} onClick={() => preview.mutate()}>Rank</Button></div>
          {preview.data && <ol className="mt-3 space-y-2">{preview.data.items.map((i: J, n: number) => <li key={i.id} className="flex items-center justify-between gap-2 rounded-xl bg-black/[.03] px-3 py-2 text-sm"><span><b>{n + 1}. {i.name}</b> <span className="text-muted">{money(i.price_minor, restaurant.currency)}</span></span><span className="flex gap-1">{i.boost !== 0 && <Badge tone={i.boost > 0 ? "good" : "warn"}>{i.boost > 0 ? "+" : ""}{i.boost}</Badge>}<Badge>score {i.score}</Badge></span></li>)}{preview.data.items.length === 0 && <p className="text-sm text-muted">Nothing eligible.</p>}</ol>}
        </Panel>
      </div>
      {adding && <Form items={items} cats={cats} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); inv(); }} />}
    </>
  );
}

function Form({ items, cats, onClose, onSaved }: { items: J[]; cats: J[]; onClose: () => void; onSaved: () => void }) {
  const { rid } = useAdmin();
  const [f, setF] = useState({ target_type: "item", target_id: "", weight: 2, featured: false, label: "", allow: true, start: "", end: "" });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const save = useMutation({
    mutationFn: () => api(`/restaurants/${rid}/recommendation-rules`, { body: { target_type: f.target_type, target_id: f.target_id, weight: f.weight, featured: f.featured, label: f.label, allow_in_recommendations: f.allow, start_at: f.start ? new Date(f.start).toISOString() : null, end_at: f.end ? new Date(f.end).toISOString() : null } }),
    onSuccess: () => { toast.success("Promotion added"); onSaved(); }, onError: (e: J) => toast.error(e.message),
  });
  return (
    <Sheet open onOpenChange={(o) => !o && onClose()} side="right" title="Add a promotion">
      <div className="space-y-4 pt-2">
        <Field label="Promote"><Select className="w-full" value={f.target_type} onChange={(e) => set({ target_type: e.target.value, target_id: "" })}><option value="item">A dish</option><option value="category">A whole category</option></Select></Field>
        <Field label={f.target_type === "item" ? "Dish" : "Category"}>
          <Select className="w-full" value={f.target_id} onChange={(e) => set({ target_id: e.target.value })}><option value="">Choose…</option>{(f.target_type === "item" ? items : cats).map((x: J) => <option key={x.key} value={x.key}>{x.name}</option>)}</Select>
        </Field>
        <Field label={`Ranking nudge: ${f.weight > 0 ? "+" : ""}${f.weight}`} hint="−5 pushes it down, +5 pulls it up. Bounded so guest preferences still matter.">
          <input type="range" min={-5} max={5} value={f.weight} onChange={(e) => set({ weight: Number(e.target.value) })} className="w-full accent-[var(--pine)]" aria-label="Ranking nudge" />
        </Field>
        <Field label="Label shown to guests (optional)" hint="e.g. Chef's pick, New this week"><Input maxLength={60} value={f.label} onChange={(e) => set({ label: e.target.value })} /></Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-5 accent-[var(--pine)]" checked={f.featured} onChange={(e) => set({ featured: e.target.checked })} />Mark as featured</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="size-5 accent-[var(--pine)]" checked={f.allow} onChange={(e) => set({ allow: e.target.checked })} />Allow in recommendations <span className="text-muted">(untick to keep it out of suggestions)</span></label>
        <div className="grid grid-cols-2 gap-3"><Field label="Starts (optional)"><Input type="datetime-local" value={f.start} onChange={(e) => set({ start: e.target.value })} /></Field><Field label="Ends (optional)"><Input type="datetime-local" value={f.end} onChange={(e) => set({ end: e.target.value })} /></Field></div>
        <Button className="w-full" size="lg" disabled={!f.target_id} loading={save.isPending} onClick={() => save.mutate()}>Add promotion</Button>
      </div>
    </Sheet>
  );
}
