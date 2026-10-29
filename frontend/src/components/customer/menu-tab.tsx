"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { Button, Badge, Empty, Sheet, Skeleton, cx } from "@/components/ui";
import { money } from "@/lib/format";
import type { J } from "@/lib/api";
import { Reveal } from "@/components/fx";
import { DishRow, hasVerifiedDiet } from "./dish";

const DIETS = ["vegetarian", "vegan", "jain", "eggless", "gluten_free"];

export function MenuTab({ menu, loading, error, retry, restaurant, canOrder, onOpen, onQuickAdd }: { menu: J; loading: boolean; error: string | null; retry: () => void; restaurant: J; canOrder: boolean; onOpen: (i: J) => void; onQuickAdd: (i: J) => void }) {
  const [q, setQ] = useState("");
  const [diets, setDiets] = useState<string[]>([]);
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [onlyAvail, setOnlyAvail] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [active, setActive] = useState<string | null>(null);
  const sections = useRef<Record<string, HTMLElement | null>>({});

  const cats: J[] = menu?.categories ?? [];
  const maxSeen = useMemo(() => Math.max(100_00, ...cats.flatMap((c) => c.items.map((i: J) => i.price_minor))), [cats]);
  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return cats
      .map((c) => ({
        ...c,
        items: c.items.filter((i: J) => {
          if (term && !`${i.name} ${i.description} ${i.attributes.map((a: J) => a.value).join(" ")}`.toLowerCase().includes(term)) return false;
          if (diets.some((d) => !hasVerifiedDiet(i, d))) return false;
          if (maxPrice !== null && i.price_minor > maxPrice) return false;
          if (onlyAvail && !i.availability.orderable) return false;
          return true;
        }),
      }))
      .filter((c) => c.items.length);
  }, [cats, q, diets, maxPrice, onlyAvail]);

  useEffect(() => {
    if (!filtered.length) return;
    const io = new IntersectionObserver((entries) => {
      const vis = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (vis) setActive(vis.target.getAttribute("data-cat"));
    }, { rootMargin: "-130px 0px -70% 0px" });
    Object.values(sections.current).forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, [filtered]);

  const pillRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  useEffect(() => { if (active) pillRefs.current[active]?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" }); }, [active]);
  const nFilters = diets.length + (maxPrice !== null ? 1 : 0) + (onlyAvail ? 1 : 0);

  return (
    <div>
      <div className="sticky top-0 z-20 -mx-4 bg-[var(--surface)]/95 px-4 pb-2 pt-3 backdrop-blur-none">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 size-5 -translate-y-1/2 text-black/45" />
            <input value={q} onChange={(e) => setQ(e.target.value)} type="search" aria-label="Search the menu" placeholder="Search dishes, tastes…" className="h-12 w-full rounded-2xl border border-stone bg-white pl-11 pr-10 text-[16px]" />
            {q && <button onClick={() => setQ("")} aria-label="Clear search" className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-full hover:bg-black/5"><X className="size-4" /></button>}
          </div>
          <button onClick={() => setFiltersOpen(true)} aria-label={`Filters${nFilters ? `, ${nFilters} active` : ""}`} className="relative grid size-12 shrink-0 place-items-center rounded-2xl border border-stone bg-white">
            <SlidersHorizontal className="size-5" />
            {nFilters > 0 && <span className="absolute -right-1 -top-1 grid size-5 place-items-center rounded-full bg-brand text-[11px] font-bold text-brand-ink">{nFilters}</span>}
          </button>
        </div>
        {!loading && filtered.length > 1 && (
          <nav aria-label="Categories" className="hide-scroll -mx-4 mt-2 flex gap-2 overflow-x-auto px-4 pb-1">
            {filtered.map((c) => (
              <button key={c.id} ref={(el) => { pillRefs.current[c.id] = el; }} onClick={() => sections.current[c.id]?.scrollIntoView({ behavior: "smooth", block: "start" })}
                className={cx("press shrink-0 rounded-full px-4 py-2 text-sm font-semibold transition-all duration-300", active === c.id ? "scale-105 bg-brand text-brand-ink shadow-md" : "bg-white text-ink ring-1 ring-stone")}>{c.name}</button>
            ))}
          </nav>
        )}
      </div>

      {error && <div role="alert" className="mt-4 rounded-2xl bg-red-50 p-4 text-sm text-red-900"><p className="font-semibold">{error}</p><button className="mt-1 underline" onClick={retry}>Try again</button></div>}

      {loading ? (
        <div className="mt-4 space-y-5">{[0, 1, 2, 3].map((i) => <div key={i} className="flex gap-3"><div className="flex-1 space-y-2"><Skeleton className="h-6 w-3/4" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-1/2" /></div><Skeleton className="size-24 !rounded-[18px]" /></div>)}</div>
      ) : filtered.length === 0 ? (
        <div className="mt-6"><Empty title={cats.length ? "Nothing matches" : "The menu is empty"} body={cats.length ? "Try a different word or clear the filters. Dishes without confirmed diet details are left out of diet filters." : "This restaurant hasn't published any dishes yet."} action={nFilters || q ? <Button variant="outline" onClick={() => { setQ(""); setDiets([]); setMaxPrice(null); setOnlyAvail(false); }}>Clear search and filters</Button> : undefined} /></div>
      ) : (
        filtered.map((c) => (
          <section key={c.id} data-cat={c.id} ref={(el) => { sections.current[c.id] = el; }} className="scroll-mt-32 pt-5">
            <Reveal><h2 className="font-display text-[30px] font-extrabold leading-none">{c.name}<span className="ml-1 font-flair text-[22px] font-medium opacity-40">{c.items.length}</span></h2></Reveal>
            {(c.description || c.note) && <p className="mt-1 text-sm text-black/60">{[c.description, c.note].filter(Boolean).join(" · ")}</p>}
            <ul className="divide-y divide-stone/70">
              {c.items.map((i: J) => (
                <DishRow key={i.id} item={i} currency={restaurant.currency} density={restaurant.card_density} canOrder={canOrder} onOpen={() => onOpen(i)} onQuickAdd={() => onQuickAdd(i)} />
              ))}
            </ul>
          </section>
        ))
      )}

      <Sheet open={filtersOpen} onOpenChange={setFiltersOpen} title="Filters" description="Diet filters only match dishes the restaurant has confirmed.">
        <div className="space-y-6 pt-2">
          <div>
            <p className="mb-2 font-semibold">Diet</p>
            <div className="flex flex-wrap gap-2">
              {DIETS.map((d) => <button key={d} aria-pressed={diets.includes(d)} onClick={() => setDiets((p) => p.includes(d) ? p.filter((x) => x !== d) : [...p, d])} className={cx("rounded-full px-4 py-2 text-sm font-semibold", diets.includes(d) ? "bg-brand text-brand-ink" : "bg-white ring-1 ring-stone")}>{d.replace("_", " ")}</button>)}
            </div>
          </div>
          <div>
            <p className="mb-2 flex justify-between font-semibold"><span>Max price</span><span>{maxPrice === null ? "Any" : money(maxPrice, restaurant.currency)}</span></p>
            <input type="range" aria-label="Maximum price" min={5000} max={maxSeen} step={5000} value={maxPrice ?? maxSeen} onChange={(e) => setMaxPrice(Number(e.target.value) >= maxSeen ? null : Number(e.target.value))} className="w-full accent-[var(--brand)]" />
          </div>
          <label className="flex items-center justify-between gap-3 rounded-2xl bg-white p-4"><span className="font-semibold">Only dishes I can order now</span><input type="checkbox" className="size-6 accent-[var(--brand)]" checked={onlyAvail} onChange={(e) => setOnlyAvail(e.target.checked)} /></label>
          <div className="flex gap-3"><Button variant="outline" className="flex-1" onClick={() => { setDiets([]); setMaxPrice(null); setOnlyAvail(false); }}>Reset</Button><Button variant="brand" className="flex-1" onClick={() => setFiltersOpen(false)}>Show dishes</Button></div>
        </div>
      </Sheet>
    </div>
  );
}
