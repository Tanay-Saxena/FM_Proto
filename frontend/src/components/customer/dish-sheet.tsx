"use client";
import { useState } from "react";
import { Info } from "lucide-react";
import { Button, Badge, Sheet, Stepper, Textarea, cx } from "@/components/ui";
import { DishImage } from "@/components/dish-art";
import { money } from "@/lib/format";
import type { J } from "@/lib/api";
import { DietChips, Spice, spiceOf, tastesOf } from "./dish";

export function DishSheet({ item, currency, canOrder, onClose, onAdd }: { item: J | null; currency: string; canOrder: boolean; onClose: () => void; onAdd: (payload: { item: J; quantity: number; option_ids: string[]; option_labels: string[]; unit_minor: number; notes: string }) => void }) {
  return (
    <Sheet open={!!item} onOpenChange={(o) => !o && onClose()} title={item?.name ?? ""}>
      {item && <Body key={item.id} item={item} currency={currency} canOrder={canOrder} onAdd={onAdd} />}
    </Sheet>
  );
}

function Body({ item, currency, canOrder, onAdd }: { item: J; currency: string; canOrder: boolean; onAdd: (p: J) => void }) {
  const [qty, setQty] = useState(1);
  const [picked, setPicked] = useState<Record<string, string[]>>({});
  const [notes, setNotes] = useState("");
  const av = item.availability;
  const spice = spiceOf(item);
  const groups: J[] = item.modifier_groups;

  const toggle = (g: J, id: string) =>
    setPicked((p) => {
      const cur = p[g.id] ?? [];
      if (g.max === 1) return { ...p, [g.id]: [id] };
      return { ...p, [g.id]: cur.includes(id) ? cur.filter((x) => x !== id) : cur.length < g.max ? [...cur, id] : cur };
    });

  const chosen = groups.flatMap((g) => (picked[g.id] ?? []).map((id) => g.options.find((o: J) => o.id === id)).filter(Boolean));
  const unit = item.price_minor + chosen.reduce((n: number, o: J) => n + o.price_minor, 0);
  const missing = groups.find((g) => (picked[g.id]?.length ?? 0) < g.min);
  const allergens = item.allergens, ingredients = item.ingredients;

  return (
    <div>
      <div className="relative -mx-5 mb-4 grid place-items-center bg-black/[.03] py-5">
        <div className="pop"><div className="float" style={{ ["--t" as string]: "5s" }}><DishImage image={item.image} size={168} rounded={item.image?.url ? 36 : 999} label={`${item.name} ${item.image?.url ? "photo" : "illustration"}`} /></div></div>
        <p className="mt-2 text-[11px] text-black/50">{item.image?.provenance ?? "Illustration"}</p>
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <p className="font-display text-3xl font-bold">{money(item.price_minor, currency)}</p>
        {item.promo && <Badge tone="lime">{item.promo.label}</Badge>}
      </div>
      {item.description && <p className="mt-2 text-[15px] leading-relaxed text-black/75">{item.description}</p>}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <DietChips item={item} />
        {spice !== null && <span className="inline-flex items-center gap-1 text-sm"><Spice level={spice} /> {["Not spicy", "Mild", "Medium", "Hot"][spice]}</span>}
        {tastesOf(item).map((t) => <Badge key={t}>{t}</Badge>)}
      </div>

      <dl className="mt-4 space-y-2 rounded-2xl bg-white p-4 text-sm">
        <div>
          <dt className="font-semibold">Allergens</dt>
          <dd className="text-black/70">{allergens.verified ? (allergens.list.length ? `Contains ${allergens.list.join(", ")} · confirmed by the restaurant` : "None listed · confirmed by the restaurant. Cross-contact is still possible.") : "Not confirmed by the restaurant yet. Please ask the staff if you have an allergy."}</dd>
        </div>
        <div>
          <dt className="font-semibold">Ingredients</dt>
          <dd className="text-black/70">{ingredients.verified && ingredients.list.length ? ingredients.list.join(", ") : "Not listed on the menu."}</dd>
        </div>
      </dl>

      {!av.orderable && (
        <p className="mt-4 flex items-start gap-2 rounded-2xl bg-amber-50 p-3 text-sm text-amber-900"><Info className="mt-0.5 size-4 shrink-0" />{av.message || "Not available right now"}.</p>
      )}

      {groups.map((g) => (
        <fieldset key={g.id} className="mt-5">
          <legend className="font-semibold">{g.name} <span className="text-sm font-normal text-black/55">{g.min > 0 ? "· required" : g.max > 1 ? `· up to ${g.max}` : "· optional"}</span></legend>
          <div className="mt-2 space-y-2">
            {g.options.map((o: J) => {
              const on = (picked[g.id] ?? []).includes(o.id);
              return (
                <button key={o.id} type="button" role={g.max === 1 ? "radio" : "checkbox"} aria-checked={on} onClick={() => toggle(g, o.id)}
                  className={cx("flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left text-[15px] transition", on ? "border-brand bg-white ring-2 ring-brand" : "border-stone bg-white")}>
                  <span>{o.name}</span>
                  <span className="text-black/60">{o.price_minor ? `+${money(o.price_minor, currency)}` : "Included"}</span>
                </button>
              );
            })}
          </div>
        </fieldset>
      ))}

      {canOrder && av.orderable && (
        <>
          <div className="mt-5">
            <p className="mb-1.5 text-sm font-semibold">Note for the kitchen</p>
            <Textarea rows={2} maxLength={200} placeholder="Less spicy, no onion…" value={notes} onChange={(e) => setNotes(e.target.value)} />
            <p className="mt-1 text-xs text-black/50">Notes can&apos;t change what&apos;s on the menu or the price.</p>
          </div>
          <div className="sticky -mx-5 bottom-0 mt-5 flex items-center gap-3 border-t border-stone bg-[var(--surface)] px-5 py-3">
            <Stepper value={qty} onChange={setQty} min={1} max={20} label="quantity" />
            <Button variant="brand" size="lg" className="flex-1" disabled={!!missing} onClick={() => onAdd({ item, quantity: qty, option_ids: chosen.map((o: J) => o.id), option_labels: chosen.map((o: J) => o.name), unit_minor: unit, notes })}>
              {missing ? `Choose ${missing.name.toLowerCase()}` : `Add · ${money(unit * qty, currency)}`}
            </Button>
          </div>
        </>
      )}
      {!canOrder && av.orderable && <p className="mt-5 rounded-2xl bg-white p-4 text-sm text-black/70">To order, scan the QR code on your table.</p>}
    </div>
  );
}
