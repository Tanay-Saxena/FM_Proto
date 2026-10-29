"use client";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { api, J } from "@/lib/api";
import { Button, Field, Input } from "@/components/ui";
import { DishArt } from "@/components/dish-art";
import { SplitText } from "@/components/fx";

function Form() {
  const router = useRouter();
  const next = useSearchParams().get("next") || "/admin";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const go = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      const me = await api("/auth/login", { body: { email, password } });
      router.replace(me.is_platform_admin && !me.memberships.length ? "/admin/platform" : next);
    } catch (e: J) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <form onSubmit={go} className="pop relative w-full max-w-sm space-y-4 rounded-[28px] bg-paper p-7 text-ink shadow-[0_40px_100px_-30px_rgba(0,0,0,.7)]">
      <h1 className="font-display text-3xl font-extrabold"><SplitText text="Welcome" step={34} /> <span className="font-flair font-medium"><SplitText text="back" start={300} /></span></h1>
      <p className="-mt-2 text-sm text-muted">Pick a demo account below, or type your own.</p>
      <Field label="Email"><Input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus /></Field>
      <Field label="Password"><Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></Field>
      {err && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-900">{err}</p>}
      <Button className="w-full" size="lg" loading={busy}>Sign in</Button>
      <div className="rounded-xl bg-white p-3 text-sm text-muted ring-1 ring-stone">
        <p className="font-semibold text-ink">Demo accounts</p>
        {[["owner@spiceroute.demo", "Owner"], ["kitchen@spiceroute.demo", "Kitchen"], ["manager@spiceroute.demo", "Manager"]].map(([e, r]) => (
          <button type="button" key={e} onClick={() => { setEmail(e); setPassword("demo1234"); }} aria-pressed={email === e} className={`press mt-1 flex w-full justify-between gap-2 rounded-lg px-2 py-1.5 text-left transition ${email === e ? "bg-lime/60 text-ink" : "hover:bg-black/5"}`}><span className="font-semibold">{r}</span><span className="font-mono text-xs">{e}</span></button>
        ))}
      </div>
    </form>
  );
}
export default function Login() {
  return (
    <main className="relative grid min-h-dvh place-items-center overflow-hidden bg-pine p-5">
      <div aria-hidden className="blob absolute -left-24 -top-24 size-[420px] bg-lime/25" />
      <div aria-hidden className="blob absolute -bottom-32 -right-24 size-[460px] bg-[#ff7a59]/25" style={{ animationDelay: "-5s" }} />
      <div aria-hidden className="float absolute left-[8%] top-[62%] hidden md:block" style={{ ["--r" as string]: "-10deg" }}><DishArt hue={28} size={110} rounded={999} /></div>
      <div aria-hidden className="float absolute right-[10%] top-[14%] hidden md:block" style={{ ["--t" as string]: "9s", ["--r" as string]: "12deg" }}><DishArt hue={100} size={90} rounded={999} /></div>
      <Suspense><Form /></Suspense>
    </main>
  );
}
