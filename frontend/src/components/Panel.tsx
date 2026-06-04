import { ReactNode } from "react";

export function Panel({
  title,
  right,
  children,
  className = "",
}: {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || right) && (
        <div className="flex items-center justify-between px-3 py-2 border-b border-line">
          <h2 className="text-[12px] uppercase tracking-wide text-muted">{title}</h2>
          {right}
        </div>
      )}
      <div className="p-3">{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  sub,
  valueClass = "",
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  valueClass?: string;
}) {
  return (
    <div>
      <div className="text-[11px] text-muted uppercase tracking-wide">{label}</div>
      <div className={`num text-lg ${valueClass}`}>{value}</div>
      {sub && <div className="text-[11px] num">{sub}</div>}
    </div>
  );
}
