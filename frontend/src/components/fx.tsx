"use client";
import { useEffect, useRef, useState } from "react";
import { cx } from "@/components/ui";

/** Fades/blur-rises its children into view once scrolled to. */
export function Reveal({ children, delay = 0, className, as: T = "div" }: { children: React.ReactNode; delay?: number; className?: string; as?: React.ElementType }) {
  const ref = useRef<HTMLElement | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") { setSeen(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect(); } }, { threshold: 0.12 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return <T ref={ref} className={cx("reveal", seen && "in", className)} style={{ ["--d" as string]: `${delay}ms` }}>{children}</T>;
}

/** Headline whose letters slide up one by one. */
export function SplitText({ text, className, start = 0, step = 28, palette }: { text: string; className?: string; start?: number; step?: number; palette?: string[] }) {
  return (
    <span className={className} aria-label={text}>
      {Array.from(text).map((c, i) => (
        <span key={i} className="char" aria-hidden>
          <span style={{ ["--d" as string]: `${start + i * step}ms`, color: palette ? palette[i % palette.length] : undefined }}>{c === " " ? " " : c}</span>
        </span>
      ))}
    </span>
  );
}

/** 3D hover tilt that follows the pointer, with a glare. */
export function Tilt({ children, className, max = 9 }: { children: React.ReactNode; className?: string; max?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (e: React.PointerEvent) => {
    const el = ref.current;
    if (!el || e.pointerType === "touch") return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(800px) rotateY(${x * max}deg) rotateX(${-y * max}deg) translateZ(0) scale(1.015)`;
  };
  const leave = () => { if (ref.current) ref.current.style.transform = ""; };
  return <div ref={ref} onPointerMove={move} onPointerLeave={leave} className={cx("tilt", className)}>{children}</div>;
}

/** Element drifts toward the cursor like a magnet. */
export function Magnetic({ children, className }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const move = (e: React.PointerEvent) => {
    const el = ref.current;
    if (!el || e.pointerType === "touch") return;
    const r = el.getBoundingClientRect();
    el.style.transform = `translate(${(e.clientX - r.left - r.width / 2) * 0.22}px, ${(e.clientY - r.top - r.height / 2) * 0.28}px)`;
  };
  return <span ref={ref} onPointerMove={move} onPointerLeave={() => { if (ref.current) ref.current.style.transform = ""; }} className={cx("inline-block transition-transform duration-200 ease-out", className)}>{children}</span>;
}

/** Number that counts up when it scrolls into view. */
export function CountUp({ to, suffix = "", duration = 1400 }: { to: number; suffix?: string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [v, setV] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setV(to); return; }
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const t0 = performance.now();
      const tick = (t: number) => {
        const p = Math.min(1, (t - t0) / duration);
        setV(Math.round(to * (1 - Math.pow(1 - p, 4))));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    io.observe(el);
    return () => io.disconnect();
  }, [to, duration]);
  return <span ref={ref}>{v.toLocaleString("en-IN")}{suffix}</span>;
}

/** Infinite horizontal ticker. */
export function Marquee({ items, className, speed = 38 }: { items: React.ReactNode[]; className?: string; speed?: number }) {
  const row = items.map((it, i) => <span key={i} className="mx-5 inline-flex items-center gap-5 whitespace-nowrap">{it}</span>);
  return (
    <div className={cx("overflow-hidden", className)} aria-hidden>
      <div className="marquee" style={{ ["--t" as string]: `${speed}s` }}>{row}{row}</div>
    </div>
  );
}

/** Mouse-follow spotlight for a section. */
export function Spotlight({ children, className }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div
      ref={ref}
      className={cx("spot relative", className)}
      onPointerMove={(e) => {
        const el = ref.current;
        if (!el) return;
        const r = el.getBoundingClientRect();
        el.style.setProperty("--mx", `${e.clientX - r.left}px`);
        el.style.setProperty("--my", `${e.clientY - r.top}px`);
      }}
    >{children}</div>
  );
}

const COLORS = ["#c8f169", "#f0b429", "#ff7a59", "#ffffff", "#8be0c2", "#d62839"];
/** One-shot confetti burst; mount it to fire. */
export function Confetti({ count = 90 }: { count?: number }) {
  const [bits] = useState(() =>
    Array.from({ length: count }, (_, i) => ({
      left: Math.random() * 100, x: `${(Math.random() - 0.5) * 240}px`, rot: `${360 + Math.random() * 900}deg`,
      dur: 2.2 + Math.random() * 2.2, delay: Math.random() * 0.5, c: COLORS[i % COLORS.length],
      w: 6 + Math.random() * 6, h: 8 + Math.random() * 10, round: Math.random() > 0.6,
    })),
  );
  const [on, setOn] = useState(true);
  useEffect(() => { const t = setTimeout(() => setOn(false), 5200); return () => clearTimeout(t); }, []);
  if (!on) return null;
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-[100] overflow-hidden">
      {bits.map((b, i) => (
        <span key={i} style={{ position: "absolute", top: 0, left: `${b.left}%`, width: b.w, height: b.h, background: b.c, borderRadius: b.round ? 99 : 2, animation: `confetti-fall ${b.dur}s cubic-bezier(.3,.5,.5,1) ${b.delay}s forwards`, ["--x" as string]: b.x, ["--rot" as string]: b.rot }} />
      ))}
    </div>
  );
}

/** Tiny tactile buzz on supporting phones. */
export function haptic(ms = 12) {
  try { if (typeof navigator !== "undefined" && "vibrate" in navigator) navigator.vibrate(ms); } catch { /* not supported */ }
}

/** A dot that arcs from the tapped button into the cart bar (or the bottom nav when the bar isn't up yet). */
export function flyToCart(from: Element | null) {
  if (!from || typeof document === "undefined") return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const target = document.querySelector("[data-cart-target]") ?? document.querySelector("[data-nav-target]");
  if (!target) return;
  const a = from.getBoundingClientRect(), b = target.getBoundingClientRect();
  const dot = document.createElement("span");
  const x0 = a.left + a.width / 2 - 11, y0 = a.top + a.height / 2 - 11;
  const dx = b.left + 38 - x0, dy = b.top + b.height / 2 - 11 - y0;
  Object.assign(dot.style, { position: "fixed", left: `${x0}px`, top: `${y0}px`, width: "22px", height: "22px", borderRadius: "999px", background: "var(--accent, #c8f169)", border: "2px solid var(--brand, #12372a)", zIndex: "90", pointerEvents: "none", boxShadow: "0 6px 20px rgba(0,0,0,.35)" });
  document.body.appendChild(dot);
  const anim = dot.animate([
    { transform: "translate(0,0) scale(1)", opacity: 1, offset: 0 },
    { transform: `translate(${dx * 0.45}px, ${dy * 0.45 - 90}px) scale(1.25)`, opacity: 1, offset: 0.45 },
    { transform: `translate(${dx}px, ${dy}px) scale(.3)`, opacity: 0.4, offset: 1 },
  ], { duration: 650, easing: "cubic-bezier(.4,0,.2,1)" });
  anim.onfinish = () => { dot.remove(); target.classList.remove("bump"); void (target as HTMLElement).offsetWidth; target.classList.add("bump"); };
}
