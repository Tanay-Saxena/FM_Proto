"use client";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowDown, ArrowUp, Copy, Pencil, Plus, Rocket, Search, Trash2 } from "lucide-react";
import { api, J } from "@/lib/api";
import { money } from "@/lib/format";
import { useAdmin } from "@/components/admin/context";
import { PageHead, Panel } from "@/components/admin/bits";
import { Badge, Button, Empty, Input, Modal, Select, Skeleton, cx } from "@/components/ui";
import { ItemEditor } from "@/components/admin/item-editor";

const STATE_TONE: Record<string, "good" | "warn" | "bad" | "neutral"> = { available: "good", paused: "warn", sold_out: "bad", hidden: "neutral" };

export default function MenuAdmin() {
  const { rid, can, restaurant } = useAdmin();
  const qc = useQueryClient();
  const [menuId, setMenuId] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string[]>([]);
  const [edit, setEdit] = useState<J | "new" | null>(null);
  const [catModal, setCatModal] = useState(false);
  const [catName, setCatName] = useState("");
  const [confirmPublish, setConfirmPublish] = useState(false);

  const menus = useQuery({ queryKey: ["menus", rid], queryFn: () => api(`/restaurants/${rid}/menus`) });
  const published = menus.data?.find((m: J) => m.status === "published");
  const drafts = (menus.data ?? []).filter((m: J) => m.status === "draft");
  const current = menus.data?.find((m: J) => m.id === menuId) ?? published ?? drafts[0];
  const menu = useQuery({ queryKey: ["menu", rid, current?.id], queryFn: () => api(`/restaurants/${rid}/menus/${current.id}`), enabled: !!current, refetchInterval: 15000 });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["menu", rid] }); qc.invalidateQueries({ queryKey: ["menus", rid] }); };

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: J }) => api(`/restaurants/${rid}/items/${id}`, { method: "PATCH", body }),
    onSuccess: refresh, onError: (e: J) => toast.error(e.message),
  });
  const bulk = useMutation({
    mutationFn: (body: J) => api(`/restaurants/${rid}/items/bulk`, { body: { item_ids: sel, ...body } }),
    onSuccess: (r: J) => { toast.success(`Updated ${r.updated} dish${r.updated === 1 ? "" : "es"}`); setSel([]); refresh(); }, onError: (e: J) => toast.error(e.message),
  });
  const clone = useMutation({ mutationFn: () => api(`/restaurants/${rid}/menus/${current.id}/clone`, { method: "POST" }), onSuccess: (r: J) => { setMenuId(r.id); refresh(); toast.success("Draft created. Edit freely — guests still see the live menu."); }, onError: (e: J) => toast.error(e.message) });
  const publish = useMutation({ mutationFn: () => api(`/restaurants/${rid}/menus/${current.id}/publish`, { method: "POST" }), onSuccess: () => { setConfirmPublish(false); setMenuId(null); refresh(); toast.success("Published. Guests now see this menu."); }, onError: (e: J) => toast.error(e.message) });
  const addCat = useMutation({ mutationFn: () => api(`/restaurants/${rid}/menus/${current.id}/categories`, { body: { name: catName } }), onSuccess: () => { setCatModal(false); setCatName(""); refresh(); }, onError: (e: J) => toast.error(e.message) });

  const [renameCat, setRenameCat] = useState<J | null>(null);
  const [delCat, setDelCat] = useState<J | null>(null);
  const reorder = useMutation({
    mutationFn: (body: J) => api(`/restaurants/${rid}/menus/${current.id}/reorder`, { body }),
    onSuccess: refresh, onError: (e: J) => toast.error(e.message),
  });
  const saveCat = useMutation({
    mutationFn: () => api(`/restaurants/${rid}/categories/${renameCat!.id}`, { method: "PATCH", body: { name: catName, description: renameCat!.description ?? "" } }),
    onSuccess: () => { setRenameCat(null); setCatName(""); refresh(); toast.success("Category renamed"); }, onError: (e: J) => toast.error(e.message),
  });
  const removeCat = useMutation({
    mutationFn: () => api(`/restaurants/${rid}/categories/${delCat!.id}`, { method: "DELETE" }),
    onSuccess: () => { setDelCat(null); refresh(); toast.success("Category deleted"); }, onError: (e: J) => { setDelCat(null); toast.error(e.message); },
  });
  const moveCat = (id: string, d: -1 | 1) => { const ids = cats.map((c) => c.id); const i = ids.indexOf(id), j = i + d; if (j < 0 || j >= ids.length) return; [ids[i], ids[j]] = [ids[j], ids[i]]; reorder.mutate({ kind: "categories", ids }); };
  const moveItem = (cat: J, id: string, d: -1 | 1) => { const ids = cat.items.map((x: J) => x.id); const i = ids.indexOf(id), j = i + d; if (j < 0 || j >= ids.length) return; [ids[i], ids[j]] = [ids[j], ids[i]]; reorder.mutate({ kind: "items", category_id: cat.id, ids }); };
  const cats: J[] = menu.data?.categories ?? [];
  const term = q.trim().toLowerCase();
  const shown = useMemo(() => cats.map((c) => ({ ...c, items: c.items.filter((i: J) => !i.archived && (!term || i.name.toLowerCase().includes(term))) })).filter((c) => c.items.length || !term), [cats, term]);
  const isLive = current?.status === "published";
  const canEdit = can("menu.edit"), canAvail = can("menu.availability") || canEdit;
  const toggleSel = (id: string) => setSel((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const [priceDraft, setPriceDraft] = useState<Record<string, string>>({});

  return (
    <>
      <PageHead title="Menu & prices" sub={isLive ? "Price and availability changes apply to the live menu immediately and are recorded in the audit log." : "You're editing a draft. Guests keep seeing the live menu until you publish."}
        actions={<>
          {current && <Select aria-label="Menu version" value={current.id} onChange={(e) => setMenuId(e.target.value)}>{(menus.data ?? []).filter((m: J) => m.status !== "archived").map((m: J) => <option key={m.id} value={m.id}>v{m.version} · {m.status === "published" ? "Live" : "Draft"}</option>)}</Select>}
          {canEdit && isLive && <Button variant="outline" loading={clone.isPending} onClick={() => clone.mutate()}><Copy className="size-4" />Create draft</Button>}
          {can("menu.publish") && current?.status === "draft" && <Button variant="lime" onClick={() => setConfirmPublish(true)}><Rocket className="size-4" />Publish draft</Button>}
        </>} />

      {!current ? <Skeleton className="h-64" /> : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <div className="relative min-w-[220px] flex-1"><Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-black/40" /><Input className="pl-10" placeholder="Search dishes" aria-label="Search dishes" value={q} onChange={(e) => setQ(e.target.value)} /></div>
            {canEdit && <><Button variant="outline" onClick={() => setCatModal(true)}>Add category</Button><Button onClick={() => setEdit("new")} disabled={!cats.length}><Plus className="size-4" />Add dish</Button></>}
          </div>
          {sel.length > 0 && (
            <div role="region" aria-label="Bulk actions" className="sticky top-2 z-10 mb-4 flex flex-wrap items-center gap-2 rounded-2xl bg-ink p-3 text-white">
              <span className="px-2 font-semibold">{sel.length} selected</span>
              <Button size="sm" variant="lime" onClick={() => bulk.mutate({ state: "sold_out" })}>Mark sold out</Button>
              <Button size="sm" variant="outline" onClick={() => bulk.mutate({ state: "available" })}>Make available</Button>
              <Button size="sm" variant="outline" onClick={() => bulk.mutate({ state: "paused" })}>Pause</Button>
              {canEdit && <Button size="sm" variant="outline" onClick={() => bulk.mutate({ state: "hidden" })}>Hide</Button>}
              {canEdit && <Button size="sm" variant="danger" onClick={() => bulk.mutate({ archived: true })}>Archive</Button>}
              <Button size="sm" variant="ghost" className="ml-auto text-white hover:bg-white/10" onClick={() => setSel([])}>Clear</Button>
            </div>
          )}
          {menu.isLoading ? <Skeleton className="h-64" /> : shown.length === 0 ? <Empty title="No dishes" body={term ? "Nothing matches your search." : "Add a category, then your first dish — or import a PDF or photo of your menu."} /> : (
            <div className="space-y-6">
              {shown.map((c) => (
                <Panel key={c.id} title={c.name} actions={canEdit && !term ? (
                  <div className="flex gap-1">
                    <Button size="sm" variant="ghost" aria-label={`Move ${c.name} up`} disabled={cats[0]?.id === c.id} onClick={() => moveCat(c.id, -1)}><ArrowUp className="size-4" /></Button>
                    <Button size="sm" variant="ghost" aria-label={`Move ${c.name} down`} disabled={cats[cats.length - 1]?.id === c.id} onClick={() => moveCat(c.id, 1)}><ArrowDown className="size-4" /></Button>
                    <Button size="sm" variant="ghost" aria-label={`Rename ${c.name}`} onClick={() => { setRenameCat(c); setCatName(c.name); }}><Pencil className="size-4" /></Button>
                    <Button size="sm" variant="ghost" aria-label={`Delete ${c.name}`} onClick={() => setDelCat(c)}><Trash2 className="size-4" /></Button>
                  </div>) : undefined}>
                  <div className="-mx-2 overflow-x-auto">
                    <table className="w-full min-w-[640px] text-left text-[15px]">
                      <caption className="sr-only">{c.name}</caption>
                      <thead className="text-xs text-muted"><tr><th className="w-10 px-2 py-2"><span className="sr-only">Select</span></th><th className="px-2 py-2 font-semibold">Dish</th><th className="px-2 py-2 font-semibold">Price</th><th className="px-2 py-2 font-semibold">Status</th><th className="px-2 py-2 font-semibold">Ordering now</th><th className="px-2 py-2" /></tr></thead>
                      <tbody className="divide-y divide-stone">
                        {c.items.map((i: J) => (
                          <tr key={i.id} className={cx(sel.includes(i.id) && "bg-lime/20")}>
                            <td className="px-2 py-2.5"><input aria-label={`Select ${i.name}`} type="checkbox" className="size-5 accent-[var(--pine)]" checked={sel.includes(i.id)} onChange={() => toggleSel(i.id)} /></td>
                            <td className="px-2 py-2.5"><button className="text-left font-semibold hover:underline" onClick={() => setEdit(i)}>{i.name}</button>{i.stock_remaining != null && <span className="ml-2 text-xs text-muted">{i.stock_remaining} left</span>}</td>
                            <td className="px-2 py-2.5">
                              {canEdit ? (
                                <label className="inline-flex items-center gap-1"><span className="text-muted">{restaurant.currency === "INR" ? "₹" : ""}</span>
                                  <input aria-label={`Price of ${i.name}`} inputMode="decimal" className="h-9 w-20 rounded-lg border border-transparent bg-black/[.04] px-2 text-right font-semibold hover:border-stone focus:border-pine focus:bg-white"
                                    value={priceDraft[i.id] ?? String(i.price_minor / 100)} onChange={(e) => setPriceDraft({ ...priceDraft, [i.id]: e.target.value })}
                                    onBlur={() => { const v = priceDraft[i.id]; if (v === undefined) return; const minor = Math.round(parseFloat(v) * 100); setPriceDraft(({ [i.id]: _, ...rest }) => rest); if (Number.isFinite(minor) && minor >= 0 && minor !== i.price_minor) patch.mutate({ id: i.id, body: { price_minor: minor } }); }}
                                    onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} /></label>
                              ) : money(i.price_minor, restaurant.currency)}
                            </td>
                            <td className="px-2 py-2.5">
                              {canAvail ? <select aria-label={`Status of ${i.name}`} value={i.state} onChange={(e) => patch.mutate({ id: i.id, body: { state: e.target.value } })} className="h-9 rounded-lg border border-stone bg-white px-2 text-sm font-semibold"><option value="available">Available</option><option value="paused">Paused</option><option value="sold_out">Sold out</option><option value="hidden">Hidden</option></select> : <Badge tone={STATE_TONE[i.state]}>{i.state}</Badge>}
                            </td>
                            <td className="px-2 py-2.5">{i.availability.orderable ? <Badge tone="good">Yes</Badge> : <Badge tone={i.availability.status === "scheduled" || i.availability.status === "closed" ? "warn" : "bad"}>{i.availability.message || i.availability.status}</Badge>}</td>
                            <td className="px-2 py-2.5 text-right">{canEdit && !term && <span className="mr-1 inline-flex"><Button size="sm" variant="ghost" aria-label={`Move ${i.name} up`} onClick={() => moveItem(c, i.id, -1)}><ArrowUp className="size-4" /></Button><Button size="sm" variant="ghost" aria-label={`Move ${i.name} down`} onClick={() => moveItem(c, i.id, 1)}><ArrowDown className="size-4" /></Button></span>}{canAvail && i.state !== "sold_out" && <Button size="sm" variant="outline" onClick={() => patch.mutate({ id: i.id, body: { state: "sold_out" } })}>Sold out</Button>}{i.state === "sold_out" && <Button size="sm" variant="outline" onClick={() => patch.mutate({ id: i.id, body: { state: "available" } })}>Back on</Button>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Panel>
              ))}
            </div>
          )}
        </>
      )}

      {edit && current && <ItemEditor key={edit === "new" ? "new" : edit.id} item={edit === "new" ? null : edit} menuId={current.id} categories={cats} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); refresh(); }} readOnly={!canEdit} />}

      <Modal open={catModal} onOpenChange={setCatModal} title="New category">
        <Input autoFocus placeholder="Starters" value={catName} onChange={(e) => setCatName(e.target.value)} aria-label="Category name" />
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setCatModal(false)}>Cancel</Button><Button disabled={!catName.trim()} loading={addCat.isPending} onClick={() => addCat.mutate()}>Add category</Button></div>
      </Modal>
      <Modal open={!!renameCat} onOpenChange={(o) => !o && setRenameCat(null)} title="Rename category">
        <Input autoFocus value={catName} onChange={(e) => setCatName(e.target.value)} aria-label="Category name" />
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setRenameCat(null)}>Cancel</Button><Button disabled={!catName.trim()} loading={saveCat.isPending} onClick={() => saveCat.mutate()}>Save</Button></div>
      </Modal>
      <Modal open={!!delCat} onOpenChange={(o) => !o && setDelCat(null)} title={`Delete “${delCat?.name ?? ""}”?`}>
        <p className="text-sm text-muted">Only empty categories can be deleted. Move or archive its dishes first.</p>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setDelCat(null)}>Keep it</Button><Button variant="danger" loading={removeCat.isPending} onClick={() => removeCat.mutate()}>Delete category</Button></div>
      </Modal>
      <Modal open={confirmPublish} onOpenChange={setConfirmPublish} title="Publish this draft?">
        <p className="text-sm text-muted">Guests will see this menu right away. The current live menu is archived, and open tables keep their existing tickets and prices.</p>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setConfirmPublish(false)}>Not yet</Button><Button variant="lime" loading={publish.isPending} onClick={() => publish.mutate()}>Publish menu</Button></div>
      </Modal>
    </>
  );
}
