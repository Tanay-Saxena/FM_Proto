"use client";
import { useRef, useState } from "react";
import { Dices, Send, Sparkles, ShieldCheck } from "lucide-react";
import { Badge, Button, Empty, cx } from "@/components/ui";
import { DishImage } from "@/components/dish-art";
import { api, J } from "@/lib/api";
import { money } from "@/lib/format";
import { track } from "@/lib/customer";

const MOODS = [["comfort", "Comfort"], ["light", "Light & fresh"], ["celebrate", "Treat myself"], ["quick", "Quick bite"], ["adventurous", "Adventurous"]];
const DIETS = [["vegetarian", "Vegetarian"], ["vegan", "Vegan"], ["jain", "Jain"], ["eggless", "Eggless"], ["gluten_free", "Gluten-free"]];
const ALLERGENS = ["nuts", "dairy", "gluten", "egg", "soy"];
const SPICE = [[0, "Not spicy"], [1, "Mild"], [2, "Medium"], [3, "Bring heat"]] as const;

type Msg = { role: "me" | "bot"; text: string; items?: J[] };

export function DiscoverTab({ restaurant, onOpenItem, dishCount }: { restaurant: J; onOpenItem: (id: string) => void; dishCount: number }) {
  const slug = restaurant.slug;
  const [mood, setMood] = useState<string | null>(null);
  const [diets, setDiets] = useState<string[]>([]);
  const [avoid, setAvoid] = useState<string[]>([]);
  const [budget, setBudget] = useState<number | null>(null);
  const [spice, setSpice] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [res, setRes] = useState<J | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pick, setPick] = useState<J | null | undefined>(undefined);
  const [chat, setChat] = useState<Msg[]>([]);
  const [msg, setMsg] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);
  const ai = restaurant.features.ai;

  const prefs = () => ({ query: text, diets, avoid_allergens: avoid, max_price_minor: budget, max_spice: spice, mood, limit: 8 });
  const toggle = (set: React.Dispatch<React.SetStateAction<string[]>>, v: string) => set((p) => (p.includes(v) ? p.filter((x) => x !== v) : [...p, v]));

  const find = async () => {
    setBusy(true); setErr(null); setPick(undefined);
    try { const r = await api(`/restaurants/${slug}/recommendations`, { body: prefs() }); setRes(r); r.items.slice(0, 3).forEach((i: J) => track(slug, "rec_impression", i.id)); }
    catch (e: J) { setErr(e.message); } finally { setBusy(false); }
  };
  const surprise = async () => {
    setBusy(true); setErr(null);
    try { const r = await api(`/restaurants/${slug}/random-dish`, { body: prefs() }); setPick(r.item ? { ...r.item, reasons: r.reasons } : null); }
    catch (e: J) { setErr(e.message); } finally { setBusy(false); }
  };
  const ask = async (m: string) => {
    if (!m.trim()) return;
    setChat((c) => [...c, { role: "me", text: m }]); setMsg(""); setChatBusy(true);
    track(slug, "chat_question");
    try { const r = await api(`/restaurants/${slug}/chat`, { body: { message: m } }); setChat((c) => [...c, { role: "bot", text: r.answer, items: r.items }]); }
    catch (e: J) { setChat((c) => [...c, { role: "bot", text: e.message }]); }
    finally { setChatBusy(false); setTimeout(() => chatEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }), 50); }
  };

  if (!ai) return <div className="pt-6"><Empty title="Discovery is switched off" body="This restaurant hasn't enabled recommendations. Browse the menu instead." /></div>;

  const chip = (on: boolean) => cx("rounded-full px-4 py-2 text-sm font-semibold transition", on ? "bg-brand text-brand-ink" : "bg-white ring-1 ring-stone");

  return (
    <div className="space-y-8 pt-5">
      <section aria-labelledby="mood-h">
        <h2 id="mood-h" className="font-display text-[28px] font-bold leading-none">What are you in the mood for?</h2>
        <div className="mt-4 flex flex-wrap gap-2">{MOODS.map(([v, l]) => <button key={v} aria-pressed={mood === v} className={chip(mood === v)} onClick={() => setMood(mood === v ? null : v)}>{l}</button>)}</div>

        <p className="mb-2 mt-5 font-semibold">I eat</p>
        <div className="flex flex-wrap gap-2">{DIETS.map(([v, l]) => <button key={v} aria-pressed={diets.includes(v)} className={chip(diets.includes(v))} onClick={() => toggle(setDiets, v)}>{l}</button>)}</div>

        <p className="mb-2 mt-5 font-semibold">Keep these out</p>
        <div className="flex flex-wrap gap-2">{ALLERGENS.map((a) => <button key={a} aria-pressed={avoid.includes(a)} className={chip(avoid.includes(a))} onClick={() => toggle(setAvoid, a)}>{a}</button>)}</div>
        {(diets.length > 0 || avoid.length > 0) && <p className="mt-2 flex items-start gap-1.5 text-sm text-black/65"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-700" />Only dishes where the restaurant has confirmed this are shown. Unconfirmed dishes are left out, never guessed.</p>}

        <p className="mb-2 mt-5 flex justify-between font-semibold"><span>Budget per dish</span><span>{budget === null ? "Any" : `Up to ${money(budget, restaurant.currency)}`}</span></p>
        <input type="range" aria-label="Budget per dish" min={10000} max={80000} step={5000} value={budget ?? 80000} onChange={(e) => setBudget(Number(e.target.value) >= 80000 ? null : Number(e.target.value))} className="w-full accent-[var(--brand)]" />

        <p className="mb-2 mt-4 font-semibold">Spice</p>
        <div className="flex flex-wrap gap-2">{SPICE.map(([v, l]) => <button key={v} aria-pressed={spice === v} className={chip(spice === v)} onClick={() => setSpice(spice === v ? null : v)}>{l}</button>)}</div>

        <label className="mt-5 block"><span className="sr-only">Describe what you want</span>
          <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && find()} placeholder="Or say it: “creamy, vegetarian, under 300”" className="h-12 w-full rounded-2xl border border-stone bg-white px-4 text-[16px]" />
        </label>
        <div className="mt-3 flex gap-2">
          <Button variant="brand" size="lg" className="flex-1" loading={busy} onClick={find}><Sparkles className="size-5" />Find dishes</Button>
          <Button variant="outline" size="lg" onClick={surprise} disabled={busy} aria-label="Surprise me"><Dices className="size-5" />Surprise me</Button>
        </div>
        {err && <p role="alert" className="mt-3 text-sm text-chilli">{err}</p>}
      </section>

      {pick !== undefined && (
        <section aria-live="polite">
          {pick === null ? <Empty title="Nothing to surprise you with" body="Nothing orderable matches those filters right now. Loosen one and try again." /> : (
            <button onClick={() => onOpenItem(pick.id)} className="flex w-full items-center gap-4 rounded-3xl bg-brand p-5 text-left text-brand-ink">
              <DishImage image={pick.image} size={92} rounded={24} />
              <span className="min-w-0 flex-1">
                <span className="block text-sm opacity-80">Today, try</span>
                <span className="block font-display text-2xl font-bold leading-tight">{pick.name}</span>
                <span className="mt-1 block text-lg font-semibold">{money(pick.price_minor, restaurant.currency)}</span>
              </span>
            </button>
          )}
        </section>
      )}

      {res && (
        <section aria-live="polite">
          <h3 className="font-display text-2xl font-bold">{res.items.length ? `${res.items.length} that fit` : "No match yet"}</h3>
          {res.items.length === 0 ? (
            <div className="mt-3"><Empty title="Nothing fits all of that" body={`Try dropping a filter.${res.excluded.diet_unverified + res.excluded.allergen_unverified > 0 ? ` ${res.excluded.diet_unverified + res.excluded.allergen_unverified} dishes were skipped because the restaurant hasn't confirmed their diet or allergen details.` : ""}`} /></div>
          ) : (
            <ul className="mt-3 space-y-3">
              {res.items.map((i: J) => (
                <li key={i.id}>
                  <button onClick={() => { track(slug, "rec_click", i.id); onOpenItem(i.id); }} className="flex w-full gap-3 rounded-3xl bg-white p-3 text-left ring-1 ring-stone transition hover:ring-brand">
                    <DishImage image={i.image} size={76} rounded={20} />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-2"><span className="font-display text-lg font-semibold leading-tight">{i.name}</span><span className="font-semibold">{money(i.price_minor, restaurant.currency)}</span></span>
                      <span className="mt-1 flex flex-wrap gap-1.5">{i.promo && <Badge tone="lime">{i.promo.label}</Badge>}{i.reasons.slice(0, 3).map((r: string) => <Badge key={r}>{r}</Badge>)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section aria-labelledby="ask-h" className="rounded-3xl bg-white p-4 ring-1 ring-stone">
        <h2 id="ask-h" className="font-display text-2xl font-bold">Ask about the menu</h2>
        <p className="text-sm text-black/60">Answers come only from this restaurant&apos;s menu — if it isn&apos;t listed, I&apos;ll say so.</p>
        <div className="mt-3 space-y-3" aria-live="polite">
          {chat.map((m, i) => (
            <div key={i} className={cx("max-w-[92%] rounded-2xl px-4 py-2.5 text-[15px]", m.role === "me" ? "ml-auto bg-brand text-brand-ink" : "bg-black/[.05]")}>
              <p>{m.text}</p>
              {m.items && m.items.length > 0 && <div className="mt-2 flex flex-wrap gap-2">{m.items.slice(0, 4).map((it) => <button key={it.id} onClick={() => onOpenItem(it.id)} className="rounded-full bg-white px-3 py-1 text-sm font-semibold ring-1 ring-stone">{it.name} · {money(it.price_minor, restaurant.currency)}</button>)}</div>}
            </div>
          ))}
          {chatBusy && <div className="skeleton h-10 w-40" aria-label="Thinking" />}
          <div ref={chatEnd} />
        </div>
        {chat.length === 0 && dishCount > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">{["What's vegetarian under 250?", "Anything spicy?", "Does the first dish on the menu contain nuts?", "Something sweet"].map((s) => <button key={s} onClick={() => ask(s)} className="rounded-full bg-black/[.05] px-3 py-1.5 text-sm">{s}</button>)}</div>
        )}
        <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(msg); }}>
          <input value={msg} onChange={(e) => setMsg(e.target.value)} maxLength={500} aria-label="Ask a question" placeholder="Is the Dal Makhani vegan?" className="h-12 min-w-0 flex-1 rounded-2xl border border-stone px-4 text-[16px]" />
          <Button variant="brand" className="size-12 !px-0" aria-label="Send question" disabled={chatBusy || !msg.trim()}><Send className="size-5" /></Button>
        </form>
      </section>
    </div>
  );
}
