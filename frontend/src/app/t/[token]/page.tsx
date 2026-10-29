"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, J } from "@/lib/api";
import { Button, ErrorBox } from "@/components/ui";

// QR landing: resolves the table on the server, joins/opens the table's session, then opens the menu.
export default function QrLanding() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    (async () => {
      try {
        const info = await api(`/qr/${token}`);
        const s = await api(`/qr/${token}/session`, { method: "POST" });
        try { localStorage.setItem(`fm:session:${info.restaurant_slug}`, JSON.stringify(s.session_token)); } catch {}
        router.replace(`/r/${info.restaurant_slug}`);
      } catch (e: J) { setErr(e.message); }
    })();
  }, [token, router]);
  return (
    <main className="grid min-h-dvh place-items-center bg-pine p-6 text-white">
      {err ? <div className="max-w-sm space-y-4 text-ink"><ErrorBox message={err} /><Button variant="lime" onClick={() => router.push("/")}>Back to start</Button></div> : (
        <div className="text-center"><div className="mx-auto mb-4 size-10 animate-spin rounded-full border-4 border-lime border-r-transparent" /><p className="font-display text-2xl font-semibold">Finding your table…</p></div>
      )}
    </main>
  );
}
