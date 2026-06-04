// Number / display formatting helpers.

export const fmt = (v: number | null | undefined, dp = 2): string =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : v.toLocaleString("en-IN", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });

export const fmtInt = (v: number | null | undefined): string =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : Math.round(v).toLocaleString("en-IN");

// Compact Indian-style abbreviation (K / L / Cr) for OI & volume.
export const compact = (v: number | null | undefined): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e7) return (v / 1e7).toFixed(2) + "Cr";
  if (abs >= 1e5) return (v / 1e5).toFixed(2) + "L";
  if (abs >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return String(Math.round(v));
};

export const signClass = (v: number | null | undefined): string =>
  v === null || v === undefined || v === 0 ? "text-slate-300" : v > 0 ? "text-bull" : "text-bear";

export const pct = (v: number | null | undefined): string =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;

export const BUILDUP_LABEL: Record<string, { text: string; cls: string }> = {
  long_buildup: { text: "Long Buildup", cls: "bg-bull/20 text-bull" },
  short_buildup: { text: "Short Buildup", cls: "bg-bear/20 text-bear" },
  short_covering: { text: "Short Covering", cls: "bg-bull/10 text-bull/80" },
  long_unwinding: { text: "Long Unwinding", cls: "bg-bear/10 text-bear/80" },
  neutral: { text: "—", cls: "text-muted" },
};

export const sentimentColor = (label: string): string =>
  label === "bullish" || label === "positive"
    ? "text-bull"
    : label === "bearish" || label === "negative"
    ? "text-bear"
    : "text-slate-300";
