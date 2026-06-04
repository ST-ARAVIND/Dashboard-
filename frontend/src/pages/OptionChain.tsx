import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useTicks } from "../hooks/useLiveFeed";
import { compact, fmt, signClass, BUILDUP_LABEL } from "../lib/format";

const UNDERLYINGS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"];

export default function OptionChainPage() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [expiry, setExpiry] = useState<string | undefined>(undefined);
  const [strikes, setStrikes] = useState(15);

  // Reset expiry when symbol changes.
  useEffect(() => setExpiry(undefined), [symbol]);

  const { data: chain, isLoading, error } = useQuery({
    queryKey: ["chain", symbol, expiry, strikes],
    queryFn: () => api.chain(symbol, expiry, strikes),
    refetchInterval: 15000,
  });

  // Live-subscribe the visible strike tokens.
  const subTokens = chain?.subscribe_tokens ?? [];
  const ticks = useTicks(subTokens);

  // Merge live ticks into the static chain snapshot.
  const rows = useMemo(() => {
    if (!chain?.rows) return [];
    return chain.rows.map((r) => {
      const ce = r.ce ? { ...r.ce } : null;
      const pe = r.pe ? { ...r.pe } : null;
      if (ce && ticks[ce.token]) {
        ce.ltp = ticks[ce.token].ltp ?? ce.ltp;
        ce.oi = ticks[ce.token].oi ?? ce.oi;
        ce.volume = ticks[ce.token].volume ?? ce.volume;
      }
      if (pe && ticks[pe.token]) {
        pe.ltp = ticks[pe.token].ltp ?? pe.ltp;
        pe.oi = ticks[pe.token].oi ?? pe.oi;
        pe.volume = ticks[pe.token].volume ?? pe.volume;
      }
      return { ...r, ce, pe };
    });
  }, [chain, ticks]);

  const a = chain?.analytics;

  return (
    <div className="space-y-3">
      {/* Controls + header analytics */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          className="bg-bg-soft border border-line rounded px-2 py-1.5"
        >
          {UNDERLYINGS.map((u) => (
            <option key={u}>{u}</option>
          ))}
        </select>
        <select
          value={expiry ?? ""}
          onChange={(e) => setExpiry(e.target.value || undefined)}
          className="bg-bg-soft border border-line rounded px-2 py-1.5"
        >
          {(chain?.expiries ?? []).map((ex) => (
            <option key={ex} value={ex}>
              {ex}
            </option>
          ))}
        </select>
        <div className="flex items-center gap-1 text-[12px] text-muted">
          ± strikes
          <input
            type="range"
            min={5}
            max={40}
            value={strikes}
            onChange={(e) => setStrikes(Number(e.target.value))}
          />
          <span className="num w-6">{strikes}</span>
        </div>

        <div className="flex gap-4 ml-auto num text-[13px]">
          <span>
            Spot <b>{fmt(chain?.spot ?? null)}</b>
          </span>
          <span>
            ATM <b>{fmt(chain?.atm_strike ?? null, 0)}</b>
          </span>
          <span>
            PCR(OI){" "}
            <b className={a?.sentiment === "bullish" ? "text-bull" : a?.sentiment === "bearish" ? "text-bear" : ""}>
              {a?.pcr_oi ?? "—"}
            </b>
          </span>
          <span>
            Max Pain <b>{fmt(a?.max_pain ?? null, 0)}</b>
          </span>
        </div>
      </div>

      {error && <div className="panel p-4 text-bear">Failed to load chain: {(error as Error).message}</div>}
      {isLoading && <div className="panel p-8 text-center text-muted">Building option chain…</div>}

      {!isLoading && rows.length > 0 && (
        <div className="panel overflow-auto">
          <table className="w-full text-[12px] num">
            <thead className="text-muted text-[10px] uppercase sticky top-0 bg-bg-panel">
              <tr>
                <th className="px-2 py-1.5 text-bull/80" colSpan={5}>CALLS</th>
                <th className="px-2 py-1.5 text-center">Strike</th>
                <th className="px-2 py-1.5 text-bear/80" colSpan={5}>PUTS</th>
              </tr>
              <tr className="text-[9px]">
                <th className="px-2 text-right">OI</th>
                <th className="px-2 text-right">ΔOI</th>
                <th className="px-2 text-right">Vol</th>
                <th className="px-2 text-right">IV</th>
                <th className="px-2 text-right">LTP</th>
                <th className="px-2 text-center">·</th>
                <th className="px-2 text-left">LTP</th>
                <th className="px-2 text-left">IV</th>
                <th className="px-2 text-left">Vol</th>
                <th className="px-2 text-left">ΔOI</th>
                <th className="px-2 text-left">OI</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const isATM = r.strike === chain?.atm_strike;
                return (
                  <tr
                    key={r.strike}
                    className={`border-t border-line/40 ${isATM ? "bg-accent/10" : "hover:bg-bg-soft/50"}`}
                  >
                    {/* CE side (ITM tint when strike < spot) */}
                    <Cell v={compact(r.ce?.oi)} />
                    <Cell v={compact(r.ce?.oi_change)} cls={signClass(r.ce?.oi_change)} align="right" />
                    <Cell v={compact(r.ce?.volume)} />
                    <Cell v={r.ce?.iv != null ? r.ce.iv.toFixed(1) : "—"} />
                    <Cell v={fmt(r.ce?.ltp ?? null)} cls={signClass(r.ce?.net_change)} align="right" bold />

                    <td className="px-2 py-1 text-center font-semibold bg-bg-soft/60">{r.strike}</td>

                    {/* PE side */}
                    <Cell v={fmt(r.pe?.ltp ?? null)} cls={signClass(r.pe?.net_change)} align="left" bold />
                    <Cell v={r.pe?.iv != null ? r.pe.iv.toFixed(1) : "—"} align="left" />
                    <Cell v={compact(r.pe?.volume)} align="left" />
                    <Cell v={compact(r.pe?.oi_change)} cls={signClass(r.pe?.oi_change)} align="left" />
                    <Cell v={compact(r.pe?.oi)} align="left" />
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex gap-4 text-[11px] text-muted">
        {Object.entries(BUILDUP_LABEL)
          .filter(([k]) => k !== "neutral")
          .map(([k, v]) => (
            <span key={k} className={`chip ${v.cls}`}>
              {v.text}
            </span>
          ))}
        <span>IV in %, ΔOI vs first snapshot today</span>
      </div>
    </div>
  );
}

function Cell({
  v,
  cls = "",
  align = "right",
  bold = false,
}: {
  v: any;
  cls?: string;
  align?: "left" | "right";
  bold?: boolean;
}) {
  return (
    <td className={`px-2 py-1 text-${align} ${cls} ${bold ? "font-semibold" : ""}`}>{v}</td>
  );
}
