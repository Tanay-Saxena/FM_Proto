"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Printer, RefreshCw } from "lucide-react";
import { api, J } from "@/lib/api";
import { useAdmin } from "@/components/admin/context";
import { PageHead } from "@/components/admin/bits";
import { Badge, Button, Field, Input, Modal, Skeleton } from "@/components/ui";
import { SESSION_LABEL } from "@/components/admin/bits";

export default function Tables() {
  const { rid, can, restaurant } = useAdmin();
  const qc = useQueryClient();
  const [add, setAdd] = useState(false);
  const [label, setLabel] = useState("");
  const [zone, setZone] = useState("");
  const [rotate, setRotate] = useState<J | null>(null);
  const t = useQuery({ queryKey: ["tables", rid], queryFn: () => api(`/restaurants/${rid}/tables`), refetchInterval: 10000 });
  const inv = () => qc.invalidateQueries({ queryKey: ["tables", rid] });
  const create = useMutation({ mutationFn: () => api(`/restaurants/${rid}/tables`, { body: { label, zone } }), onSuccess: () => { setAdd(false); setLabel(""); setZone(""); inv(); toast.success("Table added with a new QR code"); }, onError: (e: J) => toast.error(e.message) });
  const rot = useMutation({ mutationFn: (id: string) => api(`/restaurants/${rid}/tables/${id}/qr-codes`, { method: "POST" }), onSuccess: () => { setRotate(null); inv(); toast.success("New QR code issued. Print and replace the old one."); }, onError: (e: J) => toast.error(e.message) });
  const canManage = can("tables.manage");

  return (
    <>
      <PageHead title="Tables & QR codes" sub="Each table has its own QR code. The code never changes when you edit the menu — only if you replace it." actions={<>
        <Button variant="outline" onClick={() => window.print()} className="no-print"><Printer className="size-4" />Print all</Button>
        {canManage && <Button onClick={() => setAdd(true)} className="no-print"><Plus className="size-4" />Add table</Button>}</>} />
      {!t.data ? <Skeleton className="h-64" /> : (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 print:grid-cols-3">
          {t.data.map((x: J) => (
            <li key={x.id} className="break-inside-avoid rounded-3xl bg-white p-5 text-center ring-1 ring-stone">
              <p className="font-display text-3xl font-extrabold">Table {x.label}</p>
              {x.zone && <p className="text-sm text-muted">{x.zone}</p>}
              {x.qr_id ? <img src={`/api/v1/restaurants/${rid}/qr-codes/${x.qr_id}/image.svg`} alt={`QR code for table ${x.label}`} className="mx-auto my-3 size-44" /> : <p className="my-6 text-sm text-muted">No active QR code</p>}
              <p className="text-xs text-muted">Scan to see the {restaurant.name} menu</p>
              <div className="no-print mt-3 flex flex-wrap justify-center gap-2">
                {x.session_state && <Badge tone={x.session_state === "open" ? "info" : "warn"}>{SESSION_LABEL[x.session_state]}</Badge>}
                {x.qr_token && <a className="text-sm font-semibold underline" href={`/t/${x.qr_token}`} target="_blank" rel="noreferrer">Open as guest</a>}
                {canManage && <button className="inline-flex items-center gap-1 text-sm font-semibold text-muted" onClick={() => setRotate(x)}><RefreshCw className="size-3.5" />Replace QR</button>}
              </div>
            </li>
          ))}
        </ul>
      )}
      <Modal open={add} onOpenChange={setAdd} title="Add a table">
        <div className="space-y-3"><Field label="Table name or number"><Input autoFocus value={label} onChange={(e) => setLabel(e.target.value)} placeholder="13" /></Field><Field label="Section (optional)"><Input value={zone} onChange={(e) => setZone(e.target.value)} placeholder="Terrace" /></Field></div>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setAdd(false)}>Cancel</Button><Button disabled={!label.trim()} loading={create.isPending} onClick={() => create.mutate()}>Add table</Button></div>
      </Modal>
      <Modal open={!!rotate} onOpenChange={(o) => !o && setRotate(null)} title={`Replace the QR code for table ${rotate?.label}?`}>
        <p className="text-sm text-muted">The old printed code stops working immediately. Use this if a code was damaged, copied or leaked.</p>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setRotate(null)}>Keep current</Button><Button variant="danger" loading={rot.isPending} onClick={() => rot.mutate(rotate!.id)}>Replace QR code</Button></div>
      </Modal>
    </>
  );
}
