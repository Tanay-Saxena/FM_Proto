"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, CalendarClock, ChefHat, CreditCard, FileUp, LayoutDashboard, LogOut, Menu as MenuIcon, QrCode, Settings, Sparkles, Soup, Users, ClipboardList, ShieldCheck, Star } from "lucide-react";
import { api, J } from "@/lib/api";
import { AdminContext, roleCan } from "@/components/admin/context";
import { Badge, Sheet, Skeleton, cx } from "@/components/ui";

const NAV = [
  ["/admin", "Overview", LayoutDashboard, "orders.view"],
  ["/admin/orders", "Orders & tables", ClipboardList, "orders.view"],
  ["/admin/menu", "Menu & prices", Soup, "menu.view"],
  ["/admin/schedules", "Schedules", CalendarClock, "availability.edit"],
  ["/admin/promotions", "Promotions", Sparkles, "recommendations.edit"],
  ["/admin/tables", "Tables & QR", QrCode, "tables.view"],
  ["/admin/imports", "Menu imports", FileUp, "uploads.manage"],
  ["/admin/payments", "Payments & receipts", CreditCard, "payments.view"],
  ["/admin/analytics", "Analytics", BarChart3, "analytics.view"],
  ["/admin/reviews", "Reviews", Star, "analytics.view"],
  ["/admin/team", "Team", Users, "staff.view"],
  ["/admin/settings", "Settings", Settings, "settings.view"],
] as const;

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const qc = useQueryClient();
  const [rid, setRidState] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const isLogin = path === "/admin/login";

  const me = useQuery({ queryKey: ["me"], queryFn: () => api("/auth/me"), enabled: !isLogin, retry: false });
  useEffect(() => { if (me.isError && !isLogin) router.replace(`/admin/login?next=${encodeURIComponent(path)}`); }, [me.isError, isLogin, path, router]);
  useEffect(() => { try { setRidState(localStorage.getItem("fm:rid")); } catch {} }, []);

  const memberships: J[] = me.data?.memberships ?? [];
  const current = memberships.find((m) => m.restaurant_id === rid) ?? memberships[0];
  const setRid = (id: string) => { setRidState(id); try { localStorage.setItem("fm:rid", id); } catch {} qc.invalidateQueries(); };

  const rq = useQuery({ queryKey: ["restaurant-admin", current?.restaurant_id], queryFn: () => api(`/restaurants/${current.restaurant_id}/settings`), enabled: !!current });

  const ctx = useMemo(() => (current ? { me: me.data, rid: current.restaurant_id, role: current.role, restaurant: rq.data, can: (p: string) => roleCan(current.role, p), setRid } : null), [me.data, current, rq.data]); // eslint-disable-line react-hooks/exhaustive-deps

  if (isLogin || path.startsWith("/admin/platform")) return <>{children}</>;
  if (me.isLoading || me.isError) return <main className="grid min-h-dvh place-items-center"><Skeleton className="h-24 w-64" /></main>;
  if (!current) {
    return (
      <main className="mx-auto max-w-xl p-8">
        <h1 className="font-display text-3xl font-bold">No restaurant on this account</h1>
        <p className="mt-2 text-muted">You&apos;re signed in as {me.data.email}, but you haven&apos;t been added to a restaurant.{me.data.is_platform_admin && <> Platform tools are at <Link className="font-semibold underline" href="/admin/platform">/admin/platform</Link>.</>}</p>
      </main>
    );
  }

  const visible = NAV.filter(([, , , perm]) => roleCan(current.role, perm));
  const canKitchen = roleCan(current.role, "kitchen.view");
  const logout = async () => { await api("/auth/logout", { method: "POST" }); qc.clear(); router.replace("/admin/login"); };

  const nav = (
    <nav aria-label="Dashboard" className="flex flex-col gap-1">
      {visible.map(([href, label, Icon]) => {
        const on = href === "/admin" ? path === href : path.startsWith(href);
        return (
          <Link key={href} href={href} onClick={() => setMenuOpen(false)} aria-current={on ? "page" : undefined} className={cx("group flex h-11 items-center gap-3 rounded-xl px-3 text-[15px] font-semibold transition-all duration-200", on ? "bg-lime text-ink shadow-[0_8px_24px_-8px_rgba(200,241,105,.6)]" : "text-white/80 hover:translate-x-1 hover:bg-white/10")}>
            <Icon className="size-5" />{label}
          </Link>
        );
      })}
      {canKitchen && <Link href="/kitchen" className="mt-3 flex h-11 items-center gap-3 rounded-xl border border-white/25 px-3 text-[15px] font-semibold text-white"><ChefHat className="size-5" />Kitchen display</Link>}
    </nav>
  );

  const side = (
    <div className="flex h-full flex-col gap-5 p-4">
      <p className="font-display text-2xl font-extrabold text-white">FoodMania</p>
      <div>
        {memberships.length > 1 ? (
          <select aria-label="Restaurant" value={current.restaurant_id} onChange={(e) => setRid(e.target.value)} className="h-11 w-full rounded-xl border-0 bg-white/10 px-3 font-semibold text-white">
            {memberships.map((m) => <option key={m.restaurant_id} value={m.restaurant_id} className="text-ink">{m.name}</option>)}
          </select>
        ) : <p className="font-semibold text-white">{current.name}</p>}
        <div className="mt-1 flex items-center gap-2 text-xs text-white/70"><ShieldCheck className="size-3.5" />{current.role}{rq.data?.is_demo && <Badge tone="lime">Sample data</Badge>}</div>
      </div>
      {nav}
      <div className="mt-auto text-sm text-white/70">
        <p className="truncate">{me.data.email}</p>
        <button onClick={logout} className="mt-2 flex items-center gap-2 font-semibold text-white"><LogOut className="size-4" />Sign out</button>
      </div>
    </div>
  );

  return (
    <AdminContext.Provider value={ctx!}>
      <div className="min-h-dvh lg:grid lg:grid-cols-[264px_1fr]">
        <aside className="no-print sticky top-0 hidden h-dvh bg-pine lg:block">{side}</aside>
        <header className="no-print sticky top-0 z-30 flex h-14 items-center justify-between bg-pine px-4 text-white lg:hidden">
          <p className="font-display text-xl font-extrabold">FoodMania</p>
          <p className="max-w-[40%] truncate text-sm font-semibold">{current.name}</p>
          <button aria-label="Open navigation" onClick={() => setMenuOpen(true)} className="grid size-10 place-items-center rounded-lg hover:bg-white/10"><MenuIcon className="size-6" /></button>
        </header>
        <Sheet open={menuOpen} onOpenChange={setMenuOpen} title="Menu" side="right"><div className="-mx-5 -mb-6 min-h-[70dvh] bg-pine">{side}</div></Sheet>
        <main className="min-w-0 p-4 pb-16 lg:p-8">{rq.data ? children : <Skeleton className="h-64 w-full" />}</main>
      </div>
    </AdminContext.Provider>
  );
}
