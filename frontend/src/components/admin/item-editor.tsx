"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { api, J } from "@/lib/api";
import { useAdmin } from "./context";
import { Button, Field, Input, Select, Sheet, Textarea, cx } from "@/components/ui";
import { DishImage } from "@/components/dish-art";
import { ImagePlus, Trash } from "lucide-react";

const DIETS = ["vegetarian", "vegan", "jain", "eggless", "gluten_free"];
const ALLERGENS = ["nuts", "dairy", "gluten", "egg", "soy", "fish", "shellfish", "sesame", "mustard"];
const TASTES = ["sweet", "savory", "tangy", "creamy", "crunchy", "smoky", "spicy", "rich", "fresh", "bitter", "buttery", "soft", "crisp"];
const MEALS = ["breakfast", "lunch", "dinner", "snack", "dessert", "drink"];

const vals = (item: J | null, key: string) => (item?.attributes ?? []).filter((a: J) => a.key === key).map((a: J) => a.value);
const verifiedDiets = (item: J | null) => (item?.attributes ?? []).filter((a: J) => a.key === "diet" && a.verified).map((a: J) => a.value);

export function ItemEditor({ item, menuId, categories, onClose, onSaved, readOnly }: { item: J | null; menuId: string; categories: J[]; onClose: () => void; onSaved: () => void; readOnly: boolean }) {
  const { rid, restaurant } = useAdmin();
  const [f, setF] = useState(() => ({
    name: item?.name ?? "", description: item?.description ?? "", price: item ? String(item.price_minor / 100) : "", category_id: item?.category_id ?? categories[0]?.id,
    state: item?.state ?? "available", stock: item?.stock_remaining != null ? String(item.stock_remaining) : "",
    diets: verifiedDiets(item), spice: vals(item, "spice")[0] ?? "", tastes: vals(item, "taste"), meals: vals(item, "meal"), tags: vals(item, "tag").join(", "),
    allergensVerified: item?.allergens?.verified ?? false, allergens: item?.allergens?.list ?? [] as string[],
    ingVerified: item?.ingredients?.verified ?? false, ingredients: (item?.ingredients?.list ?? []).join(", "),
    hue: item?.image?.hue ?? 30, provenance: item?.image?.provenance ?? "Sample illustration generated for demo",
    groups: (item?.modifier_groups ?? []) as J[],
  }));
  const [photo, setPhoto] = useState<J | null>(item?.image?.url ? item.image : null);
  const upload = useMutation({
    mutationFn: (file: File) => { const form = new FormData(); form.append("file", file); return api(`/restaurants/${rid}/items/${item!.id}/image`, { form }); },
    onSuccess: (r: J) => { setPhoto(r.image); onSaved(); toast.success("Photo saved"); }, onError: (e: J) => toast.error(e.message),
  });
  const removePhoto = useMutation({
    mutationFn: () => api(`/restaurants/${rid}/items/${item!.id}/image`, { method: "DELETE" }),
    onSuccess: () => { setPhoto(null); onSaved(); toast.success("Photo removed"); }, onError: (e: J) => toast.error(e.message),
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const tog = (arr: string[], v: string) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  const save = useMutation({
    mutationFn: () => {
      const attributes = [
        ...f.diets.map((d: string) => ({ key: "diet", value: d, source: "restaurant_confirmed", verified: true })),
        ...(f.spice !== "" ? [{ key: "spice", value: String(f.spice), source: "restaurant_confirmed", verified: true }] : []),
        ...f.tastes.map((t: string) => ({ key: "taste", value: t, source: "restaurant_confirmed", verified: true })),
        ...f.meals.map((t: string) => ({ key: "meal", value: t, source: "restaurant_confirmed", verified: true })),
        ...f.tags.split(",").map((t: string) => t.trim().toLowerCase()).filter(Boolean).map((t: string) => ({ key: "tag", value: t, source: "restaurant_confirmed", verified: true })),
      ];
      const minor = Math.round(parseFloat(f.price) * 100);
      const body: J = {
        name: f.name.trim(), description: f.description.trim(), price_minor: minor, category_id: f.category_id, state: f.state, attributes,
        allergens: { verified: f.allergensVerified, list: f.allergensVerified ? f.allergens : [] },
        ingredients: { verified: f.ingVerified, list: f.ingVerified ? f.ingredients.split(",").map((s: string) => s.trim()).filter(Boolean) : [] },
        ...(item?.image?.kind === "photo" ? {} : { image: { kind: "illustration", hue: f.hue, provenance: f.provenance } }),
        modifier_groups: f.groups.map((g: J, i: number) => ({ id: g.id || `g${i}-${Date.now()}`, name: g.name, min: g.min, max: Math.max(1, g.max), options: g.options.map((o: J, n: number) => ({ id: o.id || `${g.id || "g" + i}-${n}`, name: o.name, price_minor: Math.round(Number(o.price) * 100 || o.price_minor || 0) })) })),
      };
      if (!item) { body.stock_remaining = f.stock === "" ? null : Number(f.stock); return api(`/restaurants/${rid}/menus/${menuId}/items`, { body }); }
      if (f.stock === "") body.clear_stock = true; else body.stock_remaining = Number(f.stock);
      return api(`/restaurants/${rid}/items/${item.id}`, { method: "PATCH", body });
    },
    onSuccess: () => { toast.success(item ? "Dish saved" : "Dish added"); onSaved(); },
    onError: (e: J) => toast.error(e.message),
  });

  const valid = f.name.trim() && f.price !== "" && Number.isFinite(parseFloat(f.price)) && parseFloat(f.price) >= 0 && f.category_id;
  const chip = (on: boolean) => cx("rounded-full px-3.5 py-1.5 text-sm font-semibold", on ? "bg-pine text-white" : "bg-white ring-1 ring-stone");

  return (
    <Sheet open onOpenChange={(o) => !o && onClose()} side="right" wide title={item ? item.name : "New dish"} description={item ? "Changes are saved to the audit log." : "Add a dish to this menu."}>
      <div className="space-y-5 pt-2">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name"><Input value={f.name} onChange={(e) => set({ name: e.target.value })} disabled={readOnly} /></Field>
          <Field label={`Price (${restaurant.currency})`}><Input inputMode="decimal" value={f.price} onChange={(e) => set({ price: e.target.value })} disabled={readOnly} /></Field>
        </div>
        <Field label="Description"><Textarea rows={3} value={f.description} onChange={(e) => set({ description: e.target.value })} disabled={readOnly} /></Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Category"><Select className="w-full" value={f.category_id} onChange={(e) => set({ category_id: e.target.value })} disabled={readOnly}>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
          <Field label="Status"><Select className="w-full" value={f.state} onChange={(e) => set({ state: e.target.value })}><option value="available">Available</option><option value="paused">Paused</option><option value="sold_out">Sold out</option><option value="hidden">Hidden</option></Select></Field>
          <Field label="Stock limit" hint="Blank = unlimited"><Input inputMode="numeric" value={f.stock} onChange={(e) => set({ stock: e.target.value.replace(/\D/g, "") })} /></Field>
        </div>

        <fieldset className="rounded-2xl bg-white p-4 ring-1 ring-stone">
          <legend className="px-1 font-semibold">Diet &amp; taste</legend>
          <p className="text-sm text-muted">Guests&apos; diet filters only match what you tick here. Leave it unticked if you&apos;re not sure.</p>
          <div className="mt-2 flex flex-wrap gap-2">{DIETS.map((d) => <button type="button" key={d} aria-pressed={f.diets.includes(d)} className={chip(f.diets.includes(d))} onClick={() => set({ diets: tog(f.diets, d) })}>{d.replace("_", " ")}</button>)}</div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label="Spice level"><Select className="w-full" value={f.spice} onChange={(e) => set({ spice: e.target.value })}><option value="">Not set</option><option value="0">Not spicy</option><option value="1">Mild</option><option value="2">Medium</option><option value="3">Hot</option></Select></Field>
            <Field label="Extra tags" hint="Comma-separated, e.g. comfort, shareable"><Input value={f.tags} onChange={(e) => set({ tags: e.target.value })} /></Field>
          </div>
          <p className="mb-1.5 mt-4 text-sm font-semibold">Tastes</p>
          <div className="flex flex-wrap gap-2">{TASTES.map((t) => <button type="button" key={t} aria-pressed={f.tastes.includes(t)} className={chip(f.tastes.includes(t))} onClick={() => set({ tastes: tog(f.tastes, t) })}>{t}</button>)}</div>
          <p className="mb-1.5 mt-4 text-sm font-semibold">Served as</p>
          <div className="flex flex-wrap gap-2">{MEALS.map((t) => <button type="button" key={t} aria-pressed={f.meals.includes(t)} className={chip(f.meals.includes(t))} onClick={() => set({ meals: tog(f.meals, t) })}>{t}</button>)}</div>
        </fieldset>

        <fieldset className="rounded-2xl bg-white p-4 ring-1 ring-stone">
          <legend className="px-1 font-semibold">Allergens &amp; ingredients</legend>
          <label className="flex items-start gap-3"><input type="checkbox" className="mt-1 size-5 accent-[var(--pine)]" checked={f.allergensVerified} onChange={(e) => set({ allergensVerified: e.target.checked })} /><span><b>I have verified this dish&apos;s allergen list.</b><br /><span className="text-sm text-muted">If unticked, guests see “not confirmed” — an empty list is never shown as allergen-free.</span></span></label>
          {f.allergensVerified && <div className="mt-3 flex flex-wrap gap-2">{ALLERGENS.map((a) => <button type="button" key={a} aria-pressed={f.allergens.includes(a)} className={chip(f.allergens.includes(a))} onClick={() => set({ allergens: tog(f.allergens, a) })}>{a}</button>)}</div>}
          <label className="mt-4 flex items-start gap-3"><input type="checkbox" className="mt-1 size-5 accent-[var(--pine)]" checked={f.ingVerified} onChange={(e) => set({ ingVerified: e.target.checked })} /><span><b>I have verified the ingredient list.</b></span></label>
          {f.ingVerified && <div className="mt-3"><Input value={f.ingredients} onChange={(e) => set({ ingredients: e.target.value })} placeholder="paneer, curd, spices" aria-label="Ingredients" /></div>}
        </fieldset>

        <fieldset className="rounded-2xl bg-white p-4 ring-1 ring-stone">
          <legend className="px-1 font-semibold">Options guests can choose</legend>
          {f.groups.map((g, gi) => (
            <div key={gi} className="mt-3 rounded-xl bg-black/[.03] p-3">
              <div className="flex flex-wrap items-end gap-2">
                <Field label="Group"><Input value={g.name} onChange={(e) => set({ groups: f.groups.map((x, i) => (i === gi ? { ...x, name: e.target.value } : x)) })} placeholder="Milk" /></Field>
                <Field label="Min"><Input className="w-16" inputMode="numeric" value={g.min} onChange={(e) => set({ groups: f.groups.map((x, i) => (i === gi ? { ...x, min: Number(e.target.value.replace(/\D/g, "")) || 0 } : x)) })} /></Field>
                <Field label="Max"><Input className="w-16" inputMode="numeric" value={g.max} onChange={(e) => set({ groups: f.groups.map((x, i) => (i === gi ? { ...x, max: Number(e.target.value.replace(/\D/g, "")) || 1 } : x)) })} /></Field>
                <Button type="button" size="sm" variant="ghost" aria-label="Remove group" onClick={() => set({ groups: f.groups.filter((_, i) => i !== gi) })}><Trash2 className="size-4" /></Button>
              </div>
              {g.options.map((o: J, oi: number) => (
                <div key={oi} className="mt-2 flex gap-2">
                  <Input aria-label="Option name" value={o.name} placeholder="Oat" onChange={(e) => set({ groups: f.groups.map((x, i) => (i === gi ? { ...x, options: x.options.map((y: J, n: number) => (n === oi ? { ...y, name: e.target.value } : y)) } : x)) })} />
                  <Input aria-label="Extra price" className="w-24" inputMode="decimal" value={o.price ?? o.price_minor / 100} onChange={(e) => set({ groups: f.groups.map((x, i) => (i === gi ? { ...x, options: x.options.map((y: J, n: number) => (n === oi ? { ...y, price: e.target.value } : y)) } : x)) })} />
                  <Button type="button" size="sm" variant="ghost" aria-label="Remove option" onClick={() => set({ groups: f.groups.map((x, i) => (i === gi ? { ...x, options: x.options.filter((_: J, n: number) => n !== oi) } : x)) })}><Trash2 className="size-4" /></Button>
                </div>
              ))}
              <Button type="button" size="sm" variant="outline" className="mt-2" onClick={() => set({ groups: f.groups.map((x, i) => (i === gi ? { ...x, options: [...x.options, { id: "", name: "", price: "0" }] } : x)) })}><Plus className="size-4" />Add option</Button>
            </div>
          ))}
          <Button type="button" size="sm" variant="outline" className="mt-3" onClick={() => set({ groups: [...f.groups, { id: "", name: "", min: 0, max: 1, options: [{ id: "", name: "", price: "0" }] }] })}><Plus className="size-4" />Add option group</Button>
        </fieldset>

        <fieldset className="flex items-center gap-4 rounded-2xl bg-white p-4 ring-1 ring-stone">
          <DishImage image={photo ?? { hue: f.hue }} size={72} />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">Picture</p>
            {photo ? (
              <>
                <p className="text-sm text-muted">Your photo is shown to guests. It is re-encoded and its location data removed.</p>
                {!readOnly && <Button type="button" size="sm" variant="outline" className="mt-2" loading={removePhoto.isPending} onClick={() => removePhoto.mutate()}><Trash className="size-4" />Remove photo</Button>}
              </>
            ) : (
              <>
                <p className="text-sm text-muted">{item ? "Upload a JPEG, PNG or WebP photo (up to 5 MB). Until then guests see a labelled illustration." : "Save the dish first, then add a photo."}</p>
                {item && !readOnly && (
                  <label className="mt-2 inline-flex h-9 cursor-pointer items-center gap-2 rounded-xl border border-stone bg-white px-3 text-sm font-semibold hover:bg-black/[.03]">
                    <ImagePlus className="size-4" />{upload.isPending ? "Uploading…" : "Upload photo"}
                    <input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" aria-label="Upload dish photo" disabled={upload.isPending} onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
                  </label>
                )}
                <input aria-label="Illustration colour" type="range" min={0} max={360} value={f.hue} onChange={(e) => set({ hue: Number(e.target.value) })} className="mt-3 w-full accent-[var(--pine)]" />
                <Input className="mt-2" aria-label="Image source" value={f.provenance} onChange={(e) => set({ provenance: e.target.value })} />
              </>
            )}
          </div>
        </fieldset>

        <div className="sticky -mx-5 bottom-0 flex justify-end gap-2 border-t border-stone bg-[var(--surface)] px-5 py-3">
          <Button variant="ghost" onClick={onClose}>Close</Button>
          <Button disabled={!valid} loading={save.isPending} onClick={() => save.mutate()}>{item ? "Save dish" : "Add dish"}</Button>
        </div>
      </div>
    </Sheet>
  );
}
