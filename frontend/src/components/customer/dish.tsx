"use client";
import { useState } from "react";
import { Plus, Leaf, Flame, Check } from "lucide-react";
import { Reveal, flyToCart, haptic } from "@/components/fx";
import { Badge, cx } from "@/components/ui";
import { DishImage } from "@/components/dish-art";
import { money } from "@/lib/format";
import type { J } from "@/lib/api";

export const hasVerifiedDiet = (item: J, d: string) =>
  item.attributes.some((a: J) => a.key === "diet" && a.verified && (a.value === d || (d === "vegetarian" && a.value === "vegan")));
export const spiceOf = (item: J): number | null => {
  const a = item.attributes.find((x: J) => x.key === "spice");
  return a ? Number(a.value) : null;
};
export const tastesOf = (item: J): string[] => item.attributes.filter((a: J) => a.key === "taste").map((a: J) => a.value);

export function VegMark({ item }: { item: J }) {
  const veg = hasVerifiedDiet(item, "vegetarian");
  if (!veg) return null;
  return (
    <span title="Vegetarian — confirmed by the restaurant" aria-label="Vegetarian, confirmed by the restaurant" className="mt-1 inline-grid size-[18px] shrink-0 self-start place-items-center rounded-[4px] border-2 border-emerald-700">
      <span className="size-2 rounded-full bg-emerald-700" />
    </span>
  );
}

export function Spice({ level }: { level: number }) {
  return (
    <span className="inline-flex items-center gap-0.5 text-chilli" title={`Spice level ${level} of 3`} aria-label={`Spice level ${level} of 3`}>
      {[1, 2, 3].map((i) => <Flame key={i} className={cx("size-3.5", i <= level ? "fill-current" : "opacity-20")} />)}
    </span>
  );
}

export function DishRow({ item, currency, density, onOpen, onQuickAdd, canOrder }: { item: J; currency: string; density: string; onOpen: () => void; onQuickAdd: () => void; canOrder: boolean }) {
  const av = item.availability;
  const spice = spiceOf(item);
  const tastes = tastesOf(item).slice(0, 3);
  const needsChoice = item.modifier_groups.some((g: J) => g.min > 0);
  const [added, setAdded] = useState(false);
  const quick = (el: Element) => { flyToCart(el); haptic(); onQuickAdd(); setAdded(true); setTimeout(() => setAdded(false), 1100); };
  return (
    <Reveal as="li" className={cx("group relative list-none", !av.orderable && "opacity-70")}>
      <div className={cx("flex w-full gap-3 text-left", density === "compact" ? "py-3" : "py-4")}>
        <button onClick={onOpen} className="min-w-0 flex-1 text-left" aria-label={`${item.name}, ${money(item.price_minor, currency)}. Open details`}>
          <span className="flex items-end gap-2">
            <VegMark item={item} />
            <span className="font-display text-[19px] font-semibold leading-tight">{item.name}</span>
            <span className="leader" aria-hidden />
            <span className="font-display text-[19px] font-semibold">{money(item.price_minor, currency)}</span>
          </span>
          {item.description && <span className="mt-1 line-clamp-2 block text-[14px] leading-snug text-black/65">{item.description}</span>}
          <span className="mt-2 flex flex-wrap items-center gap-1.5">
            {item.promo && <Badge tone="lime">{item.promo.label}</Badge>}
            {!av.orderable && <Badge tone={av.status === "sold_out" ? "bad" : "warn"}>{av.message || "Not available"}</Badge>}
            {item.stock_remaining != null && av.orderable && <Badge tone="warn">Only {item.stock_remaining} left</Badge>}
            {spice !== null && spice > 0 && <Spice level={spice} />}
            {tastes.map((t) => <span key={t} className="text-xs text-black/55">{t}</span>)}
          </span>
        </button>
        <div className="relative shrink-0">
          <button onClick={onOpen} tabIndex={-1} aria-hidden>
            <DishImage image={item.image} size={density === "compact" ? 84 : 96} rounded={18} />
          </button>
          {canOrder && (
            <button
              onClick={(e) => (needsChoice ? onOpen() : quick(e.currentTarget))}
              disabled={!av.orderable}
              aria-label={needsChoice ? `Choose options for ${item.name}` : `Add ${item.name} to order`}
              className="absolute -bottom-2 left-1/2 inline-flex h-9 -translate-x-1/2 items-center gap-1 rounded-full bg-brand px-3.5 text-sm font-bold text-brand-ink shadow-md press hover:shadow-lg disabled:bg-black/20 disabled:text-black/40 disabled:shadow-none"
            >
              {added ? <Check key="c" className="size-4" style={{ animation: "check-pop .4s both" }} /> : <Plus className="size-4 transition-transform group-hover:rotate-90" />} {added ? "Added" : needsChoice ? "Choose" : "Add"}
            </button>
          )}
        </div>
      </div>
    </Reveal>
  );
}

export function DietChips({ item }: { item: J }) {
  const diets = item.attributes.filter((a: J) => a.key === "diet" && a.verified).map((a: J) => a.value);
  if (!diets.length) return <Badge>Diet details not confirmed</Badge>;
  return <>{diets.map((d: string) => <Badge key={d} tone="good"><Leaf className="size-3" />{d.replace("_", " ")}</Badge>)}</>;
}
