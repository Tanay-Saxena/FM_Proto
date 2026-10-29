"use client";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, J } from "@/lib/api";
import { useAdmin } from "@/components/admin/context";
import { PageHead, Panel } from "@/components/admin/bits";
import { Button, Field, Input, Select, Skeleton, Textarea, cx } from "@/components/ui";
import { themeVars } from "@/lib/customer";
import { DishArt } from "@/components/dish-art";
import { ago } from "@/lib/format";

const PRESETS = [
  { name: "Pine", brand: "#12372A", accent: "#C8F169", surface: "#F6F8F4" },
  { name: "Oxblood", brand: "#7A1F2B", accent: "#F2B705", surface: "#FBF7F6" },
  { name: "Ink blue", brand: "#1F3A5F", accent: "#A8E0B5", surface: "#F4F7F9" },
  { name: "Night", brand: "#14202B", accent: "#E08A4B", surface: "#F3F5F7" },
];

export default function Settings() {
  const { rid, restaurant, can } = useAdmin();
  const qc = useQueryClient();
  const edit = can("settings.edit");
  const [f, setF] = useState<J>(null);
  useEffect(() => { if (restaurant) setF({ name: restaurant.name, tagline: restaurant.tagline, cuisine: restaurant.cuisine, timezone: restaurant.timezone, theme: restaurant.theme, config: restaurant.config }); }, [restaurant]);
  const audit = useQuery({ queryKey: ["audit", rid], queryFn: () => api(`/restaurants/${rid}/audit`) });
  const save = useMutation({
    mutationFn: () => api(`/restaurants/${rid}`, { method: "PATCH", body: { name: f.name, tagline: f.tagline, cuisine: f.cuisine, timezone: f.timezone, theme: f.theme, config: f.config } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["restaurant-admin", rid] }); qc.invalidateQueries({ queryKey: ["audit", rid] }); toast.success("Settings saved"); }, onError: (e: J) => toast.error(e.message),
  });
  if (!f) return <Skeleton className="h-96" />;
  const set = (p: J) => setF({ ...f, ...p });
  const th = (p: J) => set({ theme: { ...f.theme, ...p } });
  const cfg = (path: string[], v: J) => { const c = structuredClone(f.config); let o = c; path.slice(0, -1).forEach((k) => (o = o[k])); o[path[path.length - 1]] = v; set({ config: c }); };
  const Tog = ({ label, hint, path }: { label: string; hint?: string; path: string[] }) => {
    const val = path.reduce((o: J, k) => o[k], f.config);
    return <label className="flex items-start justify-between gap-4 py-2.5"><span><b>{label}</b>{hint && <span className="block text-sm text-muted">{hint}</span>}</span><input disabled={!edit} type="checkbox" className="mt-1 size-6 shrink-0 accent-[var(--pine)]" checked={!!val} onChange={(e) => cfg(path, e.target.checked)} /></label>;
  };

  return (
    <>
      <PageHead title="Settings" sub="Branding, taxes, ordering rules and features. No code changes needed." actions={edit && <Button loading={save.isPending} onClick={() => save.mutate()}>Save changes</Button>} />
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Restaurant">
          <div className="space-y-3">
            <Field label="Name"><Input disabled={!edit} value={f.name} onChange={(e) => set({ name: e.target.value })} /></Field>
            <Field label="Tagline"><Input disabled={!edit} value={f.tagline} onChange={(e) => set({ tagline: e.target.value })} /></Field>
            <Field label="Cuisine"><Input disabled={!edit} value={f.cuisine} onChange={(e) => set({ cuisine: e.target.value })} /></Field>
            <Field label="Timezone" hint="All schedules run on this clock, including daylight-saving changes."><Input disabled={!edit} value={f.timezone} onChange={(e) => set({ timezone: e.target.value })} /></Field>
            <p className="text-sm text-muted">Public address: <b>/r/{restaurant.slug}</b> · Currency: <b>{restaurant.currency}</b></p>
          </div>
        </Panel>

        <Panel title="Look & feel">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-3">
              <div><p className="mb-1.5 text-sm font-semibold">Start from</p><div className="flex flex-wrap gap-2">{PRESETS.map((p) => <button key={p.name} disabled={!edit} onClick={() => th({ brand: p.brand, accent: p.accent, surface: p.surface })} className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm font-semibold ring-1 ring-stone"><span className="size-4 rounded-full" style={{ background: p.brand }} />{p.name}</button>)}</div></div>
              {([["brand", "Brand colour"], ["accent", "Accent colour"], ["surface", "Page background"]] as const).map(([k, l]) => <label key={k} className="flex items-center justify-between gap-3 text-sm font-semibold">{l}<input disabled={!edit} type="color" value={f.theme[k]} onChange={(e) => th({ [k]: e.target.value.toUpperCase() })} className="size-10 rounded-lg border border-stone" aria-label={l} /></label>)}
              <Field label="Heading style"><Select disabled={!edit} className="w-full" value={f.theme.preset} onChange={(e) => th({ preset: e.target.value })}><option value="modern">Modern grotesque</option><option value="classic">Classic serif</option><option value="friendly">Friendly</option></Select></Field>
              <Field label="Corners"><Select disabled={!edit} className="w-full" value={f.theme.radius} onChange={(e) => th({ radius: e.target.value })}><option value="sharp">Sharp</option><option value="soft">Soft</option><option value="round">Round</option></Select></Field>
              <Field label="Menu density"><Select disabled={!edit} className="w-full" value={f.config.card_density} onChange={(e) => cfg(["card_density"], e.target.value)}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></Select></Field>
            </div>
            <div style={themeVars(f.theme)} className={`theme-${f.theme.preset} rounded-3xl bg-[var(--surface)] p-3 ring-1 ring-stone`} aria-label="Preview">
              <div className="rounded-[var(--r-lg)] bg-brand p-4 text-brand-ink"><p className="font-display text-2xl font-extrabold leading-none">{f.name}</p><p className="mt-1 text-xs opacity-80">{f.tagline}</p></div>
              <div className="mt-3 flex items-end gap-2 text-ink"><DishArt hue={30} size={52} /><span className="flex flex-1 items-end gap-2"><span className="font-display font-semibold">Dal Makhani</span><span className="leader" /><span className="font-display font-semibold">₹290</span></span></div>
              <button className="mt-3 h-9 rounded-full bg-brand px-4 text-sm font-bold text-brand-ink" style={{ borderRadius: "var(--r)" }}>Add</button> <span className="ml-2 rounded-full px-2.5 py-1 text-xs font-bold" style={{ background: f.theme.accent }}>Chef&apos;s pick</span>
            </div>
          </div>
        </Panel>

        <Panel title="Tax & charges">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Tax label"><Input disabled={!edit} value={f.config.tax.label} onChange={(e) => cfg(["tax", "label"], e.target.value)} /></Field>
            <Field label="Tax rate (%)"><Input disabled={!edit} inputMode="decimal" value={f.config.tax.gst_bps / 100} onChange={(e) => cfg(["tax", "gst_bps"], Math.round((parseFloat(e.target.value) || 0) * 100))} /></Field>
            <Field label="Service charge (%)"><Input disabled={!edit} inputMode="decimal" value={f.config.service_charge_bps / 100} onChange={(e) => cfg(["service_charge_bps"], Math.round((parseFloat(e.target.value) || 0) * 100))} /></Field>
          </div>
          <Tog label="Menu prices already include tax" hint="Tax is shown on the bill but not added on top." path={["tax", "inclusive"]} />
          <Tog label="Round the total to a whole rupee" path={["round_to_rupee"]} />
          <p className="mt-1 text-xs text-muted">Service charge is calculated on the subtotal; tax on subtotal plus service charge. Rounded half-up to the paisa.</p>
        </Panel>

        <Panel title="Ordering rules">
          <div className="divide-y divide-stone">
            <Tog label="Accepting orders" hint="Turn off to pause all ordering instantly." path={["ordering", "accepting_orders"]} />
            <Tog label="Allow orders outside kitchen hours" path={["ordering", "allow_outside_hours"]} />
            <Tog label="Ask for name and mobile before the first order" hint="Needed to send receipts." path={["ordering", "contact_required"]} />
            <Tog label="Lock new items once the bill is requested" path={["ordering", "lock_on_bill_request"]} />
            <Tog label="Close the table automatically after payment" path={["ordering", "auto_close_after_payment"]} />
          </div>
        </Panel>

        <Panel title="Features">
          <div className="divide-y divide-stone">
            <Tog label="Order from the table" path={["features", "ordering"]} />
            <Tog label="AI discovery and ask-a-dish" path={["features", "ai"]} />
            <Tog label="Weather-aware suggestions" hint="Optional ranking signal. Off by default." path={["features", "weather"]} />
            <Tog label="Promotions and labels" path={["features", "promotions"]} />
          </div>
        </Panel>

        <Panel title="Receipt messages">
          <div className="space-y-3">
            <Field label="SMS text" hint="Use {restaurant} and {link}. Keep amounts and personal details out of texts."><Textarea disabled={!edit} rows={2} value={f.config.templates.sms} onChange={(e) => cfg(["templates", "sms"], e.target.value)} /></Field>
            <Field label="Email subject"><Input disabled={!edit} value={f.config.templates.email_subject} onChange={(e) => cfg(["templates", "email_subject"], e.target.value)} /></Field>
            <Field label="Email body"><Textarea disabled={!edit} rows={3} value={f.config.templates.email_body} onChange={(e) => cfg(["templates", "email_body"], e.target.value)} /></Field>
          </div>
        </Panel>

        <Panel title="Recent changes">
          {!audit.data ? <Skeleton className="h-40" /> : (
            <ul className="max-h-96 divide-y divide-stone overflow-y-auto text-sm">{audit.data.map((a: J, i: number) => <li key={i} className="py-2"><p><b>{a.action}</b> <span className="text-muted">· {a.actor}</span></p><p className="text-xs text-muted">{ago(a.at)}{a.detail && Object.keys(a.detail).length ? ` · ${JSON.stringify(a.detail).slice(0, 110)}` : ""}</p></li>)}</ul>
          )}
        </Panel>
      </div>
    </>
  );
}
