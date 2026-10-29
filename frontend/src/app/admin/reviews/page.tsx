"use client";
import { useQuery } from "@tanstack/react-query";
import { Star } from "lucide-react";
import { api, J } from "@/lib/api";
import { useAdmin } from "@/components/admin/context";
import { PageHead, Panel } from "@/components/admin/bits";
import { Badge, Empty, Skeleton } from "@/components/ui";
import { CountUp } from "@/components/fx";

const Stars = ({ n, size = "size-5" }: { n: number; size?: string }) => (
  <span className="inline-flex" role="img" aria-label={`${n} out of 5 stars`}>{[1, 2, 3, 4, 5].map((i) => <Star key={i} className={`${size} ${i <= n ? "fill-amber text-amber" : "text-black/20"}`} />)}</span>
);

export default function Reviews() {
  const { rid } = useAdmin();
  const q = useQuery({ queryKey: ["reviews", rid], queryFn: () => api(`/restaurants/${rid}/reviews`), refetchInterval: 30000 });
  const d = q.data;
  return (
    <>
      <PageHead title="Reviews" sub="Only guests who paid and hold their receipt link can leave one — one per visit." />
      {!d ? <Skeleton className="h-48" /> : d.count === 0 ? <Empty title="No reviews yet" body="Guests are invited to rate their visit on the receipt page right after paying." /> : (
        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          <Panel title="Overall">
            <p className="font-display text-6xl font-extrabold leading-none">{d.average?.toFixed(1)}</p>
            <div className="mt-2"><Stars n={Math.round(d.average)} /></div>
            <p className="mt-1 text-sm text-muted"><CountUp to={d.count} duration={700} /> review{d.count === 1 ? "" : "s"}</p>
            <ul className="mt-4 space-y-1.5">{[5, 4, 3, 2, 1].map((n) => (
              <li key={n} className="flex items-center gap-2 text-sm"><span className="w-3 font-semibold">{n}</span><span className="h-2 flex-1 overflow-hidden rounded-full bg-black/[.07]"><span className="block h-full rounded-full bg-amber transition-all duration-700" style={{ width: `${(d.distribution[n] / d.count) * 100}%` }} /></span><span className="w-5 text-right text-muted">{d.distribution[n]}</span></li>
            ))}</ul>
          </Panel>
          <Panel title="What guests said">
            <ul className="divide-y divide-stone">{d.reviews.map((r: J) => (
              <li key={r.id} className="py-3.5">
                <div className="flex flex-wrap items-center gap-2"><Stars n={r.rating} size="size-4" /><span className="font-semibold">{r.guest || "Guest"}</span>{r.simulated && <Badge>sample</Badge>}<span className="ml-auto text-xs text-muted">{new Date(r.created_at).toLocaleDateString("en-IN", { dateStyle: "medium" })}</span></div>
                {r.comment && <p className="mt-1.5 text-[15px] text-black/80">{r.comment}</p>}
              </li>))}</ul>
          </Panel>
        </div>
      )}
    </>
  );
}
