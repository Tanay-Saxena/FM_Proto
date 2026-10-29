"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { api, J } from "@/lib/api";
import { useAdmin } from "@/components/admin/context";
import { PageHead, Panel } from "@/components/admin/bits";
import { Badge, Button, Field, Input, Modal, Select, Skeleton } from "@/components/ui";

const ROLE_HELP: Record<string, string> = {
  owner: "Everything, including team and settings.",
  manager: "Menu, prices, schedules, orders, payments and analytics.",
  kitchen: "Kitchen display and ticket status only.",
  staff: "View orders and tables; mark dishes sold out.",
};

export default function Team() {
  const { rid, can } = useAdmin();
  const qc = useQueryClient();
  const [add, setAdd] = useState(false);
  const [f, setF] = useState({ email: "", name: "", password: "", role: "kitchen" });
  const q = useQuery({ queryKey: ["staff", rid], queryFn: () => api(`/restaurants/${rid}/staff`) });
  const inv = () => qc.invalidateQueries({ queryKey: ["staff", rid] });
  const create = useMutation({ mutationFn: () => api(`/restaurants/${rid}/staff`, { body: { ...f, password: f.password || null } }), onSuccess: () => { setAdd(false); setF({ email: "", name: "", password: "", role: "kitchen" }); inv(); toast.success("Added"); }, onError: (e: J) => toast.error(e.message) });
  const del = useMutation({ mutationFn: (id: string) => api(`/restaurants/${rid}/staff/${id}`, { method: "DELETE" }), onSuccess: () => { inv(); toast.success("Access removed"); }, onError: (e: J) => toast.error(e.message) });
  const owner = can("staff.manage");
  return (
    <>
      <PageHead title="Team" sub="Choose what each person can do. Permissions are enforced on the server, not just hidden in the menu." actions={owner && <Button onClick={() => setAdd(true)}><Plus className="size-4" />Add person</Button>} />
      <Panel>
        {!q.data ? <Skeleton className="h-32" /> : (
          <ul className="divide-y divide-stone">{q.data.map((m: J) => (
            <li key={m.id} className="flex flex-wrap items-center justify-between gap-3 py-3.5"><div><p className="font-semibold">{m.name || m.email}</p><p className="text-sm text-muted">{m.email}</p></div><div className="flex items-center gap-2"><Badge tone={m.role === "owner" ? "lime" : "neutral"}>{m.role}</Badge>{owner && m.role !== "owner" && <Button size="sm" variant="ghost" aria-label={`Remove ${m.email}`} onClick={() => del.mutate(m.id)}><Trash2 className="size-4" /></Button>}</div></li>))}</ul>
        )}
      </Panel>
      <Panel title="What each role can do" className="mt-6"><dl className="grid gap-2 sm:grid-cols-2">{Object.entries(ROLE_HELP).map(([r, h]) => <div key={r}><dt className="font-semibold capitalize">{r}</dt><dd className="text-sm text-muted">{h}</dd></div>)}</dl></Panel>
      <Modal open={add} onOpenChange={setAdd} title="Add a person">
        <div className="space-y-3">
          <Field label="Email"><Input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} autoFocus /></Field>
          <Field label="Name"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <Field label="Role" hint={ROLE_HELP[f.role]}><Select className="w-full" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}><option value="manager">Manager</option><option value="kitchen">Kitchen</option><option value="staff">Floor staff</option></Select></Field>
          <Field label="Starting password" hint="Only needed for a new account. At least 8 characters."><Input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="new-password" /></Field>
        </div>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setAdd(false)}>Cancel</Button><Button disabled={!f.email} loading={create.isPending} onClick={() => create.mutate()}>Add person</Button></div>
      </Modal>
    </>
  );
}
