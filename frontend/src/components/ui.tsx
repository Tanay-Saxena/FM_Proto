"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import clsx from "clsx";
import { forwardRef } from "react";

export const cx = clsx;

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "outline" | "danger" | "brand" | "lime"; size?: "sm" | "md" | "lg"; loading?: boolean };
export const Button = forwardRef<HTMLButtonElement, BtnProps>(function Button({ variant = "primary", size = "md", loading, className, children, disabled, ...p }, ref) {
  const v = {
    primary: "bg-pine text-white hover:bg-pine-2",
    brand: "bg-brand text-brand-ink hover:brightness-110",
    lime: "bg-lime text-ink hover:brightness-95",
    ghost: "bg-transparent text-ink hover:bg-black/5",
    outline: "border border-stone bg-white text-ink hover:bg-black/[.03]",
    danger: "bg-chilli text-white hover:brightness-110",
  }[variant];
  const s = { sm: "h-9 px-3 text-sm", md: "h-11 px-4 text-[15px]", lg: "h-14 px-6 text-base" }[size];
  return (
    <button ref={ref} disabled={disabled || loading} className={cx("inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition active:scale-[.98] disabled:opacity-50 disabled:pointer-events-none select-none", v, s, className)} {...p}>
      {loading && <span className="size-4 rounded-full border-2 border-current border-r-transparent animate-spin" aria-hidden />}
      {children}
    </button>
  );
});

export function Badge({ tone = "neutral", children, className }: { tone?: "neutral" | "good" | "warn" | "bad" | "info" | "lime"; children: React.ReactNode; className?: string }) {
  const t = {
    neutral: "bg-black/[.06] text-ink",
    good: "bg-emerald-100 text-emerald-900",
    warn: "bg-amber-100 text-amber-900",
    bad: "bg-red-100 text-red-900",
    info: "bg-sky-100 text-sky-900",
    lime: "bg-lime text-ink",
  }[tone];
  return <span className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap", t, className)}>{children}</span>;
}

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }>(function Input({ className, invalid, ...p }, ref) {
  return <input ref={ref} className={cx("h-11 w-full rounded-xl border bg-white px-3.5 text-[15px] placeholder:text-black/40 focus:border-pine", invalid ? "border-chilli" : "border-stone", className)} {...p} />;
});
export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...p }, ref) {
  return <textarea ref={ref} className={cx("w-full rounded-xl border border-stone bg-white px-3.5 py-2.5 text-[15px] placeholder:text-black/40", className)} {...p} />;
});
export function Select({ className, ...p }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cx("h-11 rounded-xl border border-stone bg-white px-3 text-[15px]", className)} {...p} />;
}

export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-chilli" role="alert">{error}</span>}
    </label>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} aria-hidden />;
}

export function Empty({ title, body, action }: { title: string; body?: string; action?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-stone bg-white/60 p-8 text-center">
      <p className="font-display text-xl font-semibold">{title}</p>
      {body && <p className="mx-auto mt-1 max-w-sm text-sm text-muted">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBox({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      <p className="font-semibold">{message}</p>
      {retry && <button onClick={retry} className="mt-2 font-semibold underline">Try again</button>}
    </div>
  );
}

export function Sheet({ open, onOpenChange, title, description, children, side = "bottom", wide }: { open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: string; children: React.ReactNode; side?: "bottom" | "right"; wide?: boolean }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay fixed inset-0 z-40 bg-black/45" />
        <Dialog.Content
          aria-describedby={description ? undefined : undefined}
          className={cx(
            side === "right" && "sheet-right", "sheet-content fixed z-50 flex flex-col bg-[var(--surface)] text-ink shadow-2xl focus:outline-none",
            side === "bottom" ? "inset-x-0 bottom-0 mx-auto max-h-[92dvh] w-full max-w-[520px] rounded-t-[28px]" : cx("right-0 top-0 h-dvh w-full", wide ? "max-w-[720px]" : "max-w-[480px]"),
          )}
        >
          <div className="flex items-start justify-between gap-4 px-5 pb-2 pt-5">
            <div>
              <Dialog.Title className="font-display text-2xl font-bold leading-tight">{title}</Dialog.Title>
              {description && <Dialog.Description className="mt-1 text-sm text-muted">{description}</Dialog.Description>}
            </div>
            <Dialog.Close className="grid size-10 shrink-0 place-items-center rounded-full bg-black/5 hover:bg-black/10" aria-label="Close"><X className="size-5" /></Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-6">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function Modal({ open, onOpenChange, title, children }: { open: boolean; onOpenChange: (o: boolean) => void; title: string; children: React.ReactNode }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay fixed inset-0 z-40 bg-black/45" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-32px)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-3xl bg-white p-6 shadow-2xl focus:outline-none">
          <Dialog.Title className="font-display text-xl font-bold">{title}</Dialog.Title>
          <div className="mt-3">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function Stepper({ value, onChange, min = 0, max = 20, label }: { value: number; onChange: (n: number) => void; min?: number; max?: number; label: string }) {
  return (
    <div className="inline-flex items-center rounded-xl border border-stone bg-white" role="group" aria-label={label}>
      <button type="button" className="grid size-11 place-items-center text-xl font-semibold disabled:opacity-30" disabled={value <= min} onClick={() => onChange(value - 1)} aria-label={`Decrease ${label}`}>−</button>
      <span className="w-8 text-center font-semibold" aria-live="polite">{value}</span>
      <button type="button" className="grid size-11 place-items-center text-xl font-semibold disabled:opacity-30" disabled={value >= max} onClick={() => onChange(value + 1)} aria-label={`Increase ${label}`}>+</button>
    </div>
  );
}
