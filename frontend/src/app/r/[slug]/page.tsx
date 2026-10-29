"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Compass, ListChecks, ShoppingBag, Utensils } from "lucide-react";
import { api, getDemoTime, setDemoTime, J } from "@/lib/api";
import { money, todayAtInZone } from "@/lib/format";
import { themeVars, track, useCart, useTableSession } from "@/lib/customer";
import { Badge, Button, ErrorBox, Skeleton, cx } from "@/components/ui";
import { SplitText, haptic } from "@/components/fx";
import { DishArt } from "@/components/dish-art";
import { MenuTab } from "@/components/customer/menu-tab";
import { DiscoverTab } from "@/components/customer/discover-tab";
import { TableTab } from "@/components/customer/table-tab";
import { DishSheet } from "@/components/customer/dish-sheet";
import { CartSheet } from "@/components/customer/cart-sheet";

type Tab = "menu" | "discover" | "table";

export default function RestaurantPage() {
  const { slug } = useParams<{ slug: string }>();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("menu");
  const [clockKey, setClockKey] = useState(0);
  const [openItem, setOpenItem] = useState<J | null>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const cart = useCart(slug);
  const sess = useTableSession(slug);

  const r = useQuery({ queryKey: ["restaurant", slug, clockKey], queryFn: () => api(`/restaurants/${slug}`), refetchInterval: 30_000 });
  const m = useQuery({ queryKey: ["menu", slug, clockKey], queryFn: () => api(`/restaurants/${slug}/menu`), refetchInterval: 20_000 });
  const rest = r.data;

  useEffect(() => { if (rest) track(slug, "menu_view"); }, [slug, rest?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const items = useMemo(() => Object.fromEntries((m.data?.categories ?? []).flatMap((c: J) => c.items).map((i: J) => [i.id, i])), [m.data]);
  const theme = rest?.theme;
  const canOrder = !!(rest?.features.ordering && sess.token && sess.data?.can_order);

  const addToCart = useCallback((p: { item: J; quantity: number; option_ids: string[]; option_labels: string[]; unit_minor: number; notes: string }) => {
    cart.add({ item_id: p.item.id, name: p.item.name, hue: p.item.image?.hue ?? 30, unit_minor: p.unit_minor, quantity: p.quantity, option_ids: p.option_ids, option_labels: p.option_labels, notes: p.notes });
    track(slug, "add_to_cart", p.item.id);
    toast.success(`${p.item.name} added`, { id: "cart-add", duration: 1400 });
    setOpenItem(null);
  }, [cart, slug]);

  const openById = async (id: string) => {
    const known = items[id];
    if (known) { setOpenItem(known); track(slug, "dish_view", id); return; }
    try { setOpenItem(await api(`/menu-items/${id}`)); } catch (e: J) { toast.error(e.message); }
  };

  if (r.isError) return <main className="grid min-h-dvh place-items-center p-6"><div className="max-w-sm"><ErrorBox message={(r.error as J).message ?? "Couldn't load this restaurant"} retry={() => r.refetch()} /></div></main>;
  if (!rest) return <main className="mx-auto min-h-dvh max-w-[560px] p-4"><Skeleton className="h-56 w-full !rounded-[28px]" /><Skeleton className="mt-4 h-12 w-full" /></main>;

  const status = rest.status;
  const hero = (
    <>
      <div className="flex items-center justify-between gap-2">
        {rest.is_demo ? <Badge tone="lime">Sample restaurant</Badge> : <span />}
        {sess.data && <Badge className="bg-white/20 text-brand-ink">Table {sess.data.table}{sess.data.zone ? ` · ${sess.data.zone}` : ""}</Badge>}
      </div>
      <h1 className="font-display mt-6 text-[clamp(2.6rem,11vw,4.6rem)] font-extrabold leading-[0.92]">
        {rest.name.split(" ").map((w: string, i: number) => <span key={i} className="mr-[.25em] inline-block whitespace-nowrap"><SplitText text={w} start={i * 140} step={26} /></span>)}
      </h1>
      <p className="tab-in mt-3 max-w-[24ch] text-lg opacity-90" style={{ animationDelay: ".5s" }}>{rest.tagline}</p>
      <p className="tab-in mt-5 inline-flex items-center gap-2 rounded-full bg-black/20 px-3.5 py-1.5 text-sm font-semibold" style={{ animationDelay: ".65s" }}><span className={cx("live-dot size-2.5 rounded-full", status.open ? "bg-accent text-accent" : "bg-amber text-amber")} aria-hidden />{status.message}</p>
      {rest.demo_mode && <DemoClock tz={rest.timezone} onChange={() => { setClockKey((k) => k + 1); qc.invalidateQueries(); }} />}
    </>
  );

  return (
    <div style={themeVars(theme)} className={cx(`theme-${theme.preset}`, "min-h-dvh bg-[var(--surface)] lg:grid lg:grid-cols-[1fr_560px]")}>
      <aside className="sticky top-0 hidden h-dvh flex-col justify-between bg-brand p-12 text-brand-ink lg:flex">
        <div>{hero}</div>
        <p className="max-w-xs text-sm opacity-70">This is the guest view. On a phone, guests open it by scanning the QR code on their table — no app, no sign-up.</p>
      </aside>

      <div className="relative mx-auto flex min-h-dvh w-full max-w-[560px] flex-col">
        {tab !== "menu" && (
          <header className="tab-in flex items-center justify-between gap-3 bg-brand px-5 pb-4 pt-4 text-brand-ink lg:hidden" style={{ borderBottomLeftRadius: "var(--r-lg)", borderBottomRightRadius: "var(--r-lg)" }}>
            <button onClick={() => setTab("menu")} className="press min-w-0 text-left"><p className="font-display truncate text-xl font-extrabold leading-tight">{rest.name}</p><p className="flex items-center gap-1.5 text-xs opacity-80"><span className={cx("live-dot size-2 rounded-full", status.open ? "bg-accent text-accent" : "bg-amber text-amber")} aria-hidden />{status.message}</p></button>
            {sess.data && <Badge className="shrink-0 bg-white/20 text-brand-ink">Table {sess.data.table}</Badge>}
          </header>
        )}
        <header className={cx("hero-shimmer relative overflow-hidden bg-brand px-5 pb-8 pt-5 text-brand-ink lg:hidden", tab !== "menu" && "hidden")} style={{ borderBottomLeftRadius: "var(--r-lg)", borderBottomRightRadius: "var(--r-lg)" }}>
          <div aria-hidden className="pointer-events-none absolute -right-6 top-14 opacity-90">
            {[[0, 74, 28], [1, 52, 20], [2, 40, 14]].map(([i, sz, rad]) => (
              <div key={i} className="float absolute drop-shadow-xl" style={{ ["--t" as string]: `${6 + i}s`, ["--dl" as string]: `${-i * 1.7}s`, top: i * 62, right: i % 2 ? 40 : 0, ["--r" as string]: `${i * 12 - 10}deg` }}><DishArt hue={[28, 100, 350][i]} size={sz} rounded={999} /></div>
            ))}
          </div>
          <div className="relative">{hero}</div>
        </header>

        <main className="flex-1 px-4 pb-44">
          {rest.demo_mode && !status.open && (
            <div role="status" className="tab-in mt-4 rounded-2xl bg-amber-50 p-4 text-amber-950 ring-1 ring-amber-200">
              <p className="font-semibold">The kitchen is closed right now, so ordering is switched off.</p>
              <p className="mt-0.5 text-sm">This is a demo: jump to lunch time to order, then watch the ticket appear on the kitchen screen.</p>
              <Button className="mt-3" variant="brand" size="sm" onClick={() => { setDemoTime(todayAtInZone(12, 30, rest.timezone)); setClockKey((k) => k + 1); qc.invalidateQueries(); }}>Switch to lunch time (12:30 PM)</Button>
            </div>
          )}
          <div key={tab} className="tab-in">
          {tab === "menu" && <MenuTab menu={m.data} loading={m.isLoading} error={m.isError ? (m.error as J).message : null} retry={() => m.refetch()} restaurant={rest} canOrder={canOrder}
            onOpen={(i) => { setOpenItem(i); track(slug, "dish_view", i.id); }}
            onQuickAdd={(i) => addToCart({ item: i, quantity: 1, option_ids: [], option_labels: [], unit_minor: i.price_minor, notes: "" })} />}
          {tab === "discover" && <DiscoverTab restaurant={rest} onOpenItem={openById} dishCount={Object.keys(items).length} />}
          {tab === "table" && <TableTab session={sess.data} token={sess.token} restaurant={rest} refresh={sess.refresh} onMore={() => setTab("menu")} />}
          </div>
        </main>

        <div className="sticky bottom-0 z-30 mt-auto">
          {cart.count > 0 && (
            <div className="tab-in px-4 pb-2">
              <button data-cart-target onClick={() => { haptic(); setCartOpen(true); }} className="press flex h-14 w-full items-center justify-between rounded-2xl bg-brand px-5 text-brand-ink shadow-[0_14px_40px_-10px_rgba(0,0,0,.55)]">
                <span className="flex items-center gap-2 font-semibold"><ShoppingBag className="size-5" />{sess.data?.orders?.length ? "Add-on" : "Your order"} · <span key={cart.count} className="bump inline-block">{cart.count}</span> {cart.count === 1 ? "item" : "items"}</span>
                <span key={cart.total} className="bump font-display text-lg font-bold">{money(cart.total, rest.currency)}</span>
              </button>
            </div>
          )}
          <nav aria-label="Sections" data-nav-target className="relative grid grid-cols-3 border-t border-stone bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
            <span aria-hidden className="nav-ind absolute left-0 top-0 h-1 w-1/3 px-6" style={{ transform: `translateX(${["menu", "discover", "table"].indexOf(tab) * 100}%)` }}><span className="block h-full rounded-b-full bg-brand" /></span>
            {([["menu", "Menu", Utensils], ["discover", "Discover", Compass], ["table", "My table", ListChecks]] as const).map(([k, label, Icon]) => (
              <button key={k} onClick={() => { haptic(8); setTab(k); window.scrollTo({ top: 0 }); }} aria-current={tab === k ? "page" : undefined} className={cx("press relative flex h-16 flex-col items-center justify-center gap-0.5 text-xs font-semibold transition-colors", tab === k ? "text-brand" : "text-black/55")}>
                <span key={tab === k ? "on" : "off"} className={tab === k ? "icon-hop" : ""}><Icon className="size-6" /></span>{label}
                {k === "table" && (sess.data?.orders?.some((o: J) => o.state === "ready")) && <span className="live-dot absolute right-[28%] top-2.5 size-2.5 rounded-full bg-chilli text-chilli" aria-label="An order is ready" />}
              </button>
            ))}
          </nav>
        </div>
      </div>

      <DishSheet item={openItem} currency={rest.currency} canOrder={canOrder} onClose={() => setOpenItem(null)} onAdd={addToCart} />
      <CartSheet open={cartOpen} onOpenChange={setCartOpen} cart={cart} token={sess.token} session={sess.data} currency={rest.currency} refresh={sess.refresh} onPlaced={() => { setCartOpen(false); setTab("table"); }} />
    </div>
  );
}

function DemoClock({ tz, onChange }: { tz: string; onChange: () => void }) {
  const presets: [string, string, [number, number] | null][] = [["Now", "Now", null], ["8 AM", "8:00 AM", [8, 0]], ["Lunch", "12:30 PM", [12, 30]], ["Happy hour", "5:30 PM", [17, 30]], ["Late", "10:30 PM", [22, 30]], ["Closed", "2:00 AM", [2, 0]]];
  const [val, setVal] = useState("Now");
  useEffect(() => { setVal(getDemoTime() ? "" : "Now"); }, []); // a saved custom time matches no preset
  return (
    <div className="mt-5 rounded-2xl bg-black/20 p-3">
      <p className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider opacity-80">⏱ Demo clock <span className="font-normal normal-case tracking-normal opacity-70">· time-travel the menu</span></p>
      <div role="radiogroup" aria-label="Demo clock" className="hide-scroll -mx-1 flex gap-1.5 overflow-x-auto px-1">
        {presets.map(([l, sub, t]) => (
          <button key={l} role="radio" aria-checked={val === l} onClick={() => { haptic(8); setVal(l); setDemoTime(t ? todayAtInZone(t[0], t[1], tz) : null); onChange(); }}
            className={cx("press shrink-0 rounded-xl px-3.5 py-2 text-left", val === l ? "chip-on bg-accent text-ink" : "bg-white/15 text-brand-ink")}>
            <span className="block text-sm font-bold leading-tight">{l}</span><span className="block text-[11px] opacity-70">{sub}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
