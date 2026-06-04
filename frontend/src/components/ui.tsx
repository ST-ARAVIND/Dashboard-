// Small shared UI primitives for consistent loading / empty / error / value states.
import { ReactNode, useEffect, useRef, useState } from "react";
import { fmt, pct, signClass } from "../lib/format";

/** A number that briefly flashes green/red when its value ticks up/down. */
export function FlashNum({
  value,
  dp = 2,
  className = "",
}: {
  value: number | null | undefined;
  dp?: number;
  className?: string;
}) {
  const prev = useRef<number | null | undefined>(value);
  const [flash, setFlash] = useState("");
  useEffect(() => {
    if (value != null && prev.current != null && value !== prev.current) {
      setFlash(value > prev.current ? "flash-up" : "flash-down");
      const id = setTimeout(() => setFlash(""), 600);
      prev.current = value;
      return () => clearTimeout(id);
    }
    prev.current = value;
  }, [value]);
  return <span className={`num rounded px-1 ${flash} ${className}`}>{fmt(value, dp)}</span>;
}

export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <span
      className="inline-block animate-spin rounded-full border-2 border-line border-t-accent"
      style={{ width: size, height: size }}
    />
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 text-muted py-10">
      <Spinner /> <span>{label}</span>
    </div>
  );
}

export function EmptyState({ icon = "∅", message }: { icon?: string; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-muted">
      <span className="text-2xl opacity-60">{icon}</span>
      <span className="text-center max-w-xs">{message}</span>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 py-8 text-bear">
      <span className="text-xl">⚠</span>
      <span className="text-center max-w-md text-[12px]">{message}</span>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

/** A signed change value with a directional arrow + colour. */
export function Change({
  value,
  percent,
  dp = 2,
  showArrow = true,
}: {
  value: number | null | undefined;
  percent?: number | null;
  dp?: number;
  showArrow?: boolean;
}) {
  const cls = signClass(value);
  const arrow = value == null || value === 0 ? "" : value > 0 ? "▲" : "▼";
  return (
    <span className={`num ${cls} inline-flex items-center gap-1`}>
      {showArrow && arrow && <span className="text-[9px]">{arrow}</span>}
      {fmt(value, dp)}
      {percent != null && <span className="opacity-80">({pct(percent)})</span>}
    </span>
  );
}

/** Coloured pill. variant controls the colour scheme. */
export function Badge({
  children,
  variant = "neutral",
  title,
}: {
  children: ReactNode;
  variant?: "bull" | "bear" | "neutral" | "accent" | "warn";
  title?: string;
}) {
  const map: Record<string, string> = {
    bull: "bg-bull/20 text-bull",
    bear: "bg-bear/20 text-bear",
    neutral: "bg-slate-600/20 text-slate-300",
    accent: "bg-accent/20 text-accent",
    warn: "bg-amber-500/20 text-amber-400",
  };
  return (
    <span className={`chip ${map[variant]}`} title={title}>
      {children}
    </span>
  );
}
