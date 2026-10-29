"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, BellRing, ChefHat, CreditCard, LayoutDashboard, QrCode, ScanLine, ShieldCheck, Sparkles, Receipt } from "lucide-react";
import { api, J } from "@/lib/api";
import { Skeleton } from "@/components/ui";
import { DishArt } from "@/components/dish-art";
import { CountUp, Magnetic, Marquee, Reveal, SplitText, Spotlight, Tilt } from "@/components/fx";

const LOGINS = [
  ["Owner", "owner@spiceroute.demo"],
  ["Manager", "manager@spiceroute.demo"],
  ["Kitchen", "kitchen@spiceroute.demo"],
  ["Floor staff", "staff@spiceroute.demo"],
  ["Platform", "platform@foodmania.demo"],
];

const STEPS = [
  { icon: QrCode, t: "Scan", d: "A table QR opens the live menu. No app, no sign-up." },
  { icon: Sparkles, t: "Discover", d: "Ask for “spicy, vegetarian, under ₹400”. Allergen answers come only from facts the kitchen confirmed." },
  { icon: BellRing, t: "Order & add more", d: "Add-ons become their own kitchen ticket while the first one is still cooking." },
  { icon: CreditCard, t: "Pay", d: "One running bill, UPI-ready checkout, split-proof totals in exact paise." },
  { icon: Receipt, t: "Receipt", d: "The instant it's paid: a receipt page, PDF, SMS and email." },
];

const FLOATERS = [
  { hue: 28, size: 120, top: "6%", left: "58%", r: "-12deg", t: "8s", dl: "0s" },
  { hue: 100, size: 84, top: "40%", left: "88%", r: "14deg", t: "6.5s", dl: "-2s" },
  { hue: 350, size: 100, top: "72%", left: "52%", r: "-6deg", t: "9s", dl: "-4s" },
  { hue: 45, size: 70, top: "18%", left: "93%", r: "20deg", t: "7s", dl: "-1s" },
];

const TICKER = ["Live availability", "Honest allergen facts", "Add-on tickets", "UPI-ready checkout", "Instant receipts", "Kitchen display", "Multi-restaurant", "Deterministic AI picks"];

export default function Home() {
  const q = useQuery({ queryKey: ["directory"], queryFn: () => api("/demo/directory") });
  return (
    <main className="min-h-dvh overflow-x-clip bg-pine text-white">
      {/* HERO */}
      <Spotlight className="grain relative isolate overflow-hidden">
        <div aria-hidden className="blob absolute -left-32 -top-24 -z-10 size-[520px] bg-lime/25" />
        <div aria-hidden className="blob absolute -bottom-40 right-[-8rem] -z-10 size-[560px] bg-[#ff7a59]/25" style={{ animationDelay: "-6s" }} />
        <div aria-hidden className="absolute inset-0 -z-10 hidden lg:block">
          {FLOATERS.map((f, i) => (
            <div key={i} className="float absolute drop-shadow-2xl" style={{ top: f.top, left: f.left, ["--r" as string]: f.r, ["--t" as string]: f.t, ["--dl" as string]: f.dl }}>
              <DishArt hue={f.hue} size={f.size} rounded={999} />
            </div>
          ))}
        </div>

        <div className="mx-auto max-w-6xl px-5 pb-20 pt-8 lg:pb-28">
          <nav className="flex items-center justify-between">
            <p className="font-display text-xl font-extrabold tracking-tight sm:text-2xl"><span className="inline-block animate-[wiggle_3s_ease-in-out_infinite]">🍽️</span> FoodMania</p>
            <div className="flex gap-2 text-sm font-semibold">
              <Link href="/kitchen" className="hidden rounded-full px-4 py-2 sm:inline-flex ring-1 ring-white/25 transition hover:bg-white/10">Kitchen</Link>
              <Link href="/admin/login" className="rounded-full bg-lime px-4 py-2 text-ink transition hover:brightness-95">Dashboard</Link>
            </div>
          </nav>

          <div className="mt-14 max-w-3xl lg:mt-24">
            <p className="pop mb-5 inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-1.5 text-sm font-semibold ring-1 ring-white/20 backdrop-blur" style={{ animationDelay: ".1s" }}>
              <span className="size-2 animate-ping rounded-full bg-lime" /> Live demo · 3 restaurants · real kitchen flow
            </p>
            <h1 className="font-display text-[clamp(3.4rem,10.5vw,7.6rem)] font-extrabold leading-[.88] tracking-tight">
              <SplitText text="Scan." /><br />
              <SplitText text="Discover." start={180} /><br />
              <SplitText text="Order." start={360} className="font-flair font-medium" /><br />
              <SplitText text="Add more." start={540} palette={["#c8f169", "#d9e85f", "#f0b429", "#ff9a4d", "#ff7a59"]} /><br />
              <SplitText text="Pay." start={760} />
            </h1>
            <p className="reveal in mt-8 max-w-[46ch] text-lg text-white/80" style={{ transitionDelay: "1s" }}>
              QR menus that tell the truth: availability straight from the kitchen&apos;s schedule, recommendations that never guess an allergen, add-on tickets mid-meal, and a receipt the second the bill is paid.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <Magnetic className="block sm:inline-block"><a href="#tables" className="btn-glow flex h-14 justify-center sm:inline-flex items-center gap-2 rounded-2xl bg-lime px-7 text-lg font-bold text-ink transition"><ScanLine className="size-5" />Sit at a table</a></Magnetic>
              <Magnetic className="block sm:inline-block"><Link href="/admin/login" className="flex h-14 items-center justify-center gap-2 rounded-2xl border sm:inline-flex border-white/30 px-6 font-bold backdrop-blur transition hover:bg-white/10"><LayoutDashboard className="size-5" />Owner dashboard</Link></Magnetic>
              <Magnetic className="block sm:inline-block"><Link href="/kitchen" className="flex h-14 items-center justify-center gap-2 rounded-2xl border sm:inline-flex border-white/30 px-6 font-bold backdrop-blur transition hover:bg-white/10"><ChefHat className="size-5" />Kitchen display</Link></Magnetic>
            </div>
          </div>
        </div>
      </Spotlight>

      <Marquee className="border-y border-white/15 bg-black/20 py-4 font-display text-xl font-bold text-white/80" items={TICKER.map((t) => <>{t}<span className="text-lime">✦</span></>)} />

      {/* STATS */}
      <section className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-5 py-16 md:grid-cols-4">
        {[[48, "", "tests passing"], [5, "", "staff roles, scoped"], [100, "%", "money in exact paise"], [0, "", "guessed allergens"]].map(([n, s, l], i) => (
          <Reveal key={String(l)} delay={i * 90}>
            <p className="font-display text-6xl font-extrabold text-lime"><CountUp to={n as number} suffix={s as string} /></p>
            <p className="mt-1 text-sm text-white/70">{l}</p>
          </Reveal>
        ))}
      </section>

      {/* HOW IT WORKS */}
      <section className="mx-auto max-w-6xl px-5 pb-20">
        <Reveal><h2 className="font-display text-4xl font-extrabold md:text-6xl">From QR to receipt, <span className="font-flair text-lime">no friction</span>.</h2></Reveal>
        <ol className="mt-12 grid gap-4 md:grid-cols-5">
          {STEPS.map((s, i) => (
            <Reveal as="li" key={s.t} delay={i * 110} className="list-none">
              <Tilt className="h-full rounded-3xl bg-white/[.07] p-5 ring-1 ring-white/15 backdrop-blur">
                <span className="grid size-12 place-items-center rounded-2xl bg-lime text-ink"><s.icon className="size-6" /></span>
                <p className="mt-4 font-display text-sm font-bold text-lime">0{i + 1}</p>
                <h3 className="font-display text-2xl font-bold">{s.t}</h3>
                <p className="mt-2 text-sm text-white/75">{s.d}</p>
              </Tilt>
            </Reveal>
          ))}
        </ol>
      </section>

      {/* DEMO TABLES */}
      <section id="tables" aria-labelledby="demo-h" className="mx-auto max-w-6xl scroll-mt-6 px-5 pb-24">
        <div className="rounded-[40px] bg-paper p-6 text-ink shadow-[0_40px_120px_-30px_rgba(0,0,0,.6)] lg:p-10">
          <Reveal>
            <h2 id="demo-h" className="font-display text-4xl font-extrabold leading-tight md:text-5xl">Sit at a sample table</h2>
            <p className="mt-1 text-muted">Three venues. Each chip is the exact link a printed table QR would open.</p>
          </Reveal>
          <div className="mt-8 grid gap-5 lg:grid-cols-3">
            {q.isLoading && [0, 1, 2].map((i) => <Skeleton key={i} className="h-56 w-full" />)}
            {q.isError && <p role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-900 lg:col-span-3">The demo server isn&apos;t reachable. Start the API (see README) and refresh.</p>}
            {q.data?.map((r: J, i: number) => (
              <Reveal key={r.slug} delay={i * 120}>
                <Tilt className="shine h-full rounded-3xl bg-white p-5 ring-1 ring-stone" max={6}>
                  <div className="mb-3 h-2 w-16 rounded-full" style={{ background: r.theme.brand }} />
                  <Link href={`/r/${r.slug}`} className="group flex items-start justify-between gap-2 font-display text-2xl font-extrabold leading-tight" style={{ color: r.theme.brand }}>
                    {r.name}<ArrowUpRight className="mt-1 size-5 shrink-0 transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                  </Link>
                  <p className="mt-1 text-sm text-muted">{r.cuisine}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {r.tables.slice(0, 12).map((t: J) => (
                      <Link key={t.qr_token} href={`/t/${t.qr_token}`} title={t.zone || undefined} className="inline-flex h-10 items-center gap-1.5 rounded-full bg-paper px-4 text-sm font-semibold ring-1 ring-stone transition hover:-translate-y-0.5 hover:text-white hover:ring-0" onMouseEnter={(e) => (e.currentTarget.style.background = r.theme.brand)} onMouseLeave={(e) => (e.currentTarget.style.background = "")}>
                        <ScanLine className="size-4" />Table {t.label}
                      </Link>
                    ))}
                  </div>
                </Tilt>
              </Reveal>
            ))}
          </div>
          <Reveal className="mt-8 rounded-2xl bg-white p-5 text-sm ring-1 ring-stone">
            <p className="flex items-center gap-2 font-semibold"><ShieldCheck className="size-4 text-emerald-700" />Staff sign-ins · shared demo password <code className="rounded bg-black/5 px-1.5 py-0.5">demo1234</code></p>
            <ul className="mt-3 grid gap-x-8 gap-y-1 sm:grid-cols-2">{LOGINS.map(([role, email]) => <li key={email} className="flex flex-wrap justify-between gap-x-3"><span className="text-muted">{role}</span><span className="font-mono text-[12.5px] break-all">{email}</span></li>)}</ul>
            <p className="mt-3 text-xs text-muted">Sample data only. Payments, SMS and email are simulated and labelled as such.</p>
          </Reveal>
        </div>
      </section>
      <footer className="border-t border-white/10 py-8 text-center text-sm text-white/50">FoodMania · built for the restaurants that tell the truth</footer>
    </main>
  );
}
