import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useTicks } from "../hooks/useLiveFeed";
import { compact, fmt, signClass, BUILDUP_LABEL } from "../lib/format";
import { Loading, ErrorState } from "../components/ui";
import { OIProfile } from "../components/OIProfile";

const UNDERLYINGS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"];

export default function OptionChainPage() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [expiry, setExpiry] = useState<string | undefined>(undefined);
  const [strikes, setStrikes] = useState(15);
  const [view, setView] = useState<"table" | "profile">("table");

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

        {/* Table / OI-profile view toggle */}
        <div className="flex border border-line rounded-md overflow-hidden text-[11px]">
          {(["table", "profile"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-2.5 py-1 ${view === v ? "bg-accent/15 text-accent" : "text-muted hover:text-ink"}`}
            >
              {v === "table" ? "Table" : "OI Profile"}
            </button>
          ))}
        </div>
      </div>

      {/* Metrics strip */}
      <div className="panel px-3 py-2 flex flex-wrap gap-x-6 gap-y-1 num text-[12px]">
        <span>Spot <b>{fmt(chain?.spot ?? null)}</b></span>
        <span>ATM <b>{fmt(chain?.atm_strike ?? null, 0)}</b></span>
        <span>
          PCR(OI){" "}
          <b className={a?.sentiment === "bullish" ? "text-bull" : a?.sentiment === "bearish" ? "text-bear" : ""}>
            {a?.pcr_oi ?? "—"}
          </b>
        </span>
        <span>Max Pain <b>{fmt(a?.max_pain ?? null, 0)}</b></span>
        <span className="text-muted">|</span>
        <span>ATM IV <b>{a?.atm_iv != null ? `${a.atm_iv}%` : "—"}</b></span>
        <span title="OTM put IV − OTM call IV; >0 = downside (put) skew">
          Skew{" "}
          <b className={(a?.iv_skew ?? 0) > 0 ? "text-bear" : "text-bull"}>
            {a?.iv_skew != null ? `${a.iv_skew > 0 ? "+" : ""}${a.iv_skew}%` : "—"}
          </b>
        </span>
        <span>Straddle <b>₹{fmt(a?.atm_straddle ?? null, 0)}</b></span>
        <span title="~1σ expected move to expiry (≈ ATM straddle)">
          Exp. Move{" "}
          <b className="text-accent">
            {a?.expected_move_pct != null ? `±${a.expected_move_pct}%` : "—"}
            {a?.expected_move_pts != null ? ` (±${fmt(a.expected_move_pts, 0)})` : ""}
          </b>
        </span>
      </div>

      {error && <div className="panel"><ErrorState message={`Failed to load chain: ${(error as Error).message}`} /></div>}
      {isLoading && <div className="panel"><Loading label="Building option chain…" /></div>}

      {!isLoading && !error && rows.length > 0 && view === "profile" && (
        <div className="panel p-4">
          <OIProfile rows={rows} atmStrike={chain?.atm_strike ?? null} />
        </div>
      )}

      {!isLoading && !error && rows.length > 0 && view === "table" && (
        <div className="panel overflow-auto">
          <table className="w-full text-[12px] num">
            <thead className="text-muted text-[10px] uppercase sticky top-0 bg-bg-panel z-10">
              <tr className="border-b border-line">
                <th className="px-2 py-1.5 text-bull/80 text-left" colSpan={5}>CALLS</th>
                <th className="px-2 py-1.5 text-center">Strike</th>
                <th className="px-2 py-1.5 text-bear/80 text-right" colSpan={5}>PUTS</th>
              </tr>
              <tr className="text-[9px]">
                <th className="px-2 text-right font-medium">OI</th>
                <th className="px-2 text-right font-medium">ΔOI</th>
                <th className="px-2 text-right font-medium">Vol</th>
                <th className="px-2 text-right font-medium">IV</th>
                <th className="px-2 text-right font-medium">LTP</th>
                <th className="px-2 text-center font-medium"></th>
                <th className="px-2 text-left font-medium">LTP</th>
                <th className="px-2 text-left font-medium">IV</th>
                <th className="px-2 text-left font-medium">Vol</th>
                <th className="px-2 text-left font-medium">ΔOI</th>
                <th className="px-2 text-left font-medium">OI</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const isATM = r.strike === chain?.atm_strike;
                const spot = chain?.spot ?? null;
                // CE in-the-money when strike < spot; PE ITM when strike > spot.
                const ceItm = spot != null && r.strike < spot ? "bg-bull/[0.06]" : "";
                const peItm = spot != null && r.strike > spot ? "bg-bear/[0.06]" : "";
                return (
                  <tr
                    key={r.strike}
                    className={`border-t border-line/40 ${isATM ? "bg-accent/10 ring-1 ring-inset ring-accent/30" : "hover:bg-bg-soft/50"}`}
                  >
                    <Cell v={compact(r.ce?.oi)} cls={ceItm} />
                    <Cell v={compact(r.ce?.oi_change)} cls={`${signClass(r.ce?.oi_change)} ${ceItm}`} align="right" />
                    <Cell v={compact(r.ce?.volume)} cls={ceItm} />
                    <Cell v={r.ce?.iv != null ? r.ce.iv.toFixed(1) : "—"} cls={ceItm} />
                    <Cell v={fmt(r.ce?.ltp ?? null)} cls={`${signClass(r.ce?.net_change)} ${ceItm}`} align="right" bold />

                    <td className="px-2 py-1 text-center font-semibold bg-bg-soft/60">{r.strike}</td>

                    <Cell v={fmt(r.pe?.ltp ?? null)} cls={`${signClass(r.pe?.net_change)} ${peItm}`} align="left" bold />
                    <Cell v={r.pe?.iv != null ? r.pe.iv.toFixed(1) : "—"} cls={peItm} align="left" />
                    <Cell v={compact(r.pe?.volume)} cls={peItm} align="left" />
                    <Cell v={compact(r.pe?.oi_change)} cls={`${signClass(r.pe?.oi_change)} ${peItm}`} align="left" />
                    <Cell v={compact(r.pe?.oi)} cls={peItm} align="left" />
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
