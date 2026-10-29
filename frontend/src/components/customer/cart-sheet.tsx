"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { Button, Field, Input, Sheet, Stepper, Textarea } from "@/components/ui";
import { api, ApiError, idem, J } from "@/lib/api";
import { money } from "@/lib/format";
import type { useCart } from "@/lib/customer";

type Cart = ReturnType<typeof useCart>;

export function CartSheet({ open, onOpenChange, cart, token, session, currency, onPlaced, refresh }: { open: boolean; onOpenChange: (o: boolean) => void; cart: Cart; token: string | null; session: J; currency: string; onPlaced: () => void; refresh: () => Promise<J> }) {
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<{ message: string; items: J[] } | null>(null);
  const [key, setKey] = useState(idem());
  const [c, setC] = useState({ name: "", phone: "", email: "", consent: false });
  const [errs, setErrs] = useState<Record<string, string>>({});

  const needsContact = session?.contact_required && !session?.contact?.has_contact;
  const isAddon = (session?.orders?.length ?? 0) > 0;

  const validate = () => {
    const e: Record<string, string> = {};
    if (needsContact) {
      if (c.name.trim().length < 1) e.name = "Enter your name";
      if (!/^\+?\d[\d\s-]{6,17}$/.test(c.phone.trim())) e.phone = "Enter a valid mobile number";
      if (c.email && !/^\S+@\S+\.\S+$/.test(c.email)) e.email = "That email doesn't look right";
      if (!c.consent) e.consent = "Please agree so we can send your receipt";
    }
    setErrs(e);
    return Object.keys(e).length === 0;
  };

  const submit = async () => {
    if (!token || !validate()) return;
    setBusy(true); setProblem(null);
    try {
      if (needsContact) await api(`/table-sessions/${token}/contact`, { body: { name: c.name.trim(), phone: c.phone.trim(), email: c.email.trim() || null, consent: c.consent } });
      await api(`/table-sessions/${token}/orders`, { body: { idempotency_key: key, notes, lines: cart.lines.map((l) => ({ item_id: l.item_id, quantity: l.quantity, modifier_option_ids: l.option_ids, notes: l.notes })) } });
      toast.success(isAddon ? "Add-on sent to the kitchen" : "Order sent to the kitchen");
      setNotes(""); setKey(idem());
      await refresh();
      onPlaced();
      setTimeout(() => cart.clear(), 450); // let the sheet finish sliding away before it empties
    } catch (e) {
      const err = e as ApiError;
      if (err.code === "items_unavailable" || err.code === "insufficient_stock") setProblem({ message: err.message, items: err.detail ?? [] });
      else toast.error(err.message);
    } finally { setBusy(false); }
  };

  const dropUnavailable = () => { problem?.items.forEach((i) => cart.remove(i.item_id)); setProblem(null); setKey(idem()); };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={isAddon ? "Add to your table" : "Your order"} description={session ? `Table ${session.table}${isAddon ? " · goes to the kitchen as a new ticket" : ""}` : undefined}>
      {cart.lines.length === 0 ? (
        <p className="py-10 text-center text-black/60">Nothing here yet. Add dishes from the menu.</p>
      ) : (
        <div className="space-y-5">
          <ul className="divide-y divide-stone rounded-2xl bg-white px-4">
            {cart.lines.map((l) => (
              <li key={l.id} className="flex items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold leading-tight">{l.name}</p>
                  {l.option_labels.length > 0 && <p className="text-sm text-black/60">{l.option_labels.join(", ")}</p>}
                  {l.notes && <p className="text-sm italic text-black/60">“{l.notes}”</p>}
                  <p className="text-sm text-black/60">{money(l.unit_minor, currency)} each</p>
                </div>
                <Stepper value={l.quantity} onChange={(q) => cart.setQty(l.id, q)} min={0} label={l.name} />
                <button aria-label={`Remove ${l.name}`} onClick={() => cart.setQty(l.id, 0)} className="grid size-10 place-items-center rounded-full text-black/50 hover:bg-black/5"><Trash2 className="size-4" /></button>
              </li>
            ))}
          </ul>

          {problem && (
            <div role="alert" className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
              <p className="font-semibold">{problem.message}</p>
              <ul className="mt-1 list-disc pl-5">{problem.items.map((i) => <li key={i.item_id}>{i.name}{i.message ? ` — ${i.message}` : i.available != null ? ` — ${i.available} left` : ""}</li>)}</ul>
              <Button size="sm" variant="outline" className="mt-3" onClick={dropUnavailable}>Remove these and continue</Button>
            </div>
          )}

          {needsContact && (
            <div className="space-y-3 rounded-2xl bg-white p-4">
              <div>
                <p className="font-semibold">Where should we send your receipt?</p>
                <p className="text-sm text-black/60">We use these only to serve your table and send your receipt link.</p>
              </div>
              <Field label="Name" error={errs.name}><Input autoComplete="name" value={c.name} onChange={(e) => setC({ ...c, name: e.target.value })} invalid={!!errs.name} /></Field>
              <Field label="Mobile number" error={errs.phone} hint="Your receipt link is sent here."><Input inputMode="tel" autoComplete="tel" placeholder="+91 98765 43210" value={c.phone} onChange={(e) => setC({ ...c, phone: e.target.value })} invalid={!!errs.phone} /></Field>
              <Field label="Email (optional)" error={errs.email}><Input type="email" inputMode="email" autoComplete="email" value={c.email} onChange={(e) => setC({ ...c, email: e.target.value })} invalid={!!errs.email} /></Field>
              <label className="flex items-start gap-3 text-sm">
                <input type="checkbox" className="mt-0.5 size-5 accent-[var(--brand)]" checked={c.consent} onChange={(e) => setC({ ...c, consent: e.target.checked })} />
                <span>I agree to share these details with {session?.restaurant?.name} for my order and receipt. {errs.consent && <span className="block text-chilli">{errs.consent}</span>}</span>
              </label>
            </div>
          )}
          {!needsContact && session?.contact?.has_contact && <p className="text-sm text-black/60">Receipt goes to {session.contact.phone_masked}{session.contact.email_masked ? ` and ${session.contact.email_masked}` : ""}.</p>}

          <Field label="Note for the whole order (optional)"><Textarea rows={2} maxLength={300} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Bring starters first" /></Field>

          <div className="sticky -mx-5 bottom-0 border-t border-stone bg-[var(--surface)] px-5 pb-1 pt-3">
            <div className="mb-2 flex justify-between text-sm"><span className="text-black/60">Items total · tax and charges added at billing</span><span className="font-semibold">{money(cart.total, currency)}</span></div>
            <Button variant="brand" size="lg" className="w-full" loading={busy} onClick={submit} disabled={!token}>{isAddon ? "Send add-on to kitchen" : "Send to kitchen"}</Button>
            {!token && <p className="mt-2 text-center text-sm text-black/60">Scan your table&apos;s QR code to place an order.</p>}
          </div>
        </div>
      )}
    </Sheet>
  );
}
