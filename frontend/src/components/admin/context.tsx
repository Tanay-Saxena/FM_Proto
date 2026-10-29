"use client";
import { createContext, useContext } from "react";
import type { J } from "@/lib/api";

export type AdminCtx = { me: J; rid: string; role: string; restaurant: J; can: (perm: string) => boolean; setRid: (id: string) => void };
export const AdminContext = createContext<AdminCtx | null>(null);
export const useAdmin = () => {
  const c = useContext(AdminContext);
  if (!c) throw new Error("AdminContext missing");
  return c;
};

// Mirrors backend ROLE_PERMS for hiding controls. The backend is the real gate.
const PERMS: Record<string, string[] | "*"> = {
  owner: "*",
  manager: ["menu.view", "menu.edit", "menu.publish", "availability.edit", "recommendations.edit", "tables.manage", "tables.view", "sessions.view", "sessions.manage", "orders.view", "orders.transition", "orders.cancel", "payments.view", "notifications.retry", "analytics.view", "uploads.manage", "settings.view", "staff.view", "pos.sync", "kitchen.view", "menu.availability"],
  kitchen: ["orders.view", "orders.transition", "kitchen.view", "menu.view"],
  staff: ["orders.view", "menu.view", "menu.availability", "tables.view", "sessions.view"],
};
export const roleCan = (role: string, perm: string) => PERMS[role] === "*" || (PERMS[role] as string[] | undefined)?.includes(perm) || false;
