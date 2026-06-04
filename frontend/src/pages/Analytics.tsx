import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import { Panel } from "../components/Panel";
import { compact } from "../lib/format";

const UNDERLYINGS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"];

const tooltipStyle = { background: "#111722", border: "1px solid #1f2937", fontSize: 12 };

// Background colour for an OI-change cell, scaled by magnitude vs the row-set max.
function heatColor(value: number | null, max: number): string {
  if (value == null || !max) return "transparent";
  const intensity = Math.min(Math.abs(value) / max, 1);
  const a = (0.08 + intensity * 0.55).toFixed(2);
  return value >= 0 ? `rgba(22,199,132,${a})` : `rgba(234,57,67,${a})`;
}

export default function Analytics() {
  const [symbol, setSymbol] = useState("NIFTY");

  const { data: term, isLoading: termLoading } = useQuery({
    queryKey: ["term-structure", symbol],
    queryFn: () => api.termStructure(symbol, 6),
    refetchInterval: 60000,
  });

  const { data: oi, isLoading: oiLoading, error: oiErr } = useQuery({
    queryKey: ["oi-analytics", symbol],
    queryFn: () => api.oi(symbol),
    refetchInterval: 30000,
    retry: false,
  });

  const termPoints = term?.points ?? [];
  const buildup: any[] = oi?.buildup ?? [];
  const history: any[] = oi?.oi_history ?? [];

  const maxAbsOI = Math.max(
    1,
    ...buildup.flatMap((r) => [Math.abs(r.ce?.oi_change ?? 0), Math.abs(r.pe?.oi_change ?? 0)])
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className="input w-auto">
          {UNDERLYINGS.map((u) => (
            <option key={u}>{u}</option>
          ))}
        </select>
        <span className="text-muted text-[12px]">
          {oi?.expiry ? `nearest expiry ${oi.expiry} · spot ${oi.spot ?? "—"}` : ""}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* IV term structure */}
        <Panel title="IV Term Structure (ATM)" loading={termLoading} empty={termPoints.length ? null : "No data."}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={termPoints}>
              <CartesianGrid stroke="#1f2937" />
              <XAxis dataKey="expiry" stroke="#64748b" fontSize={10} />
              <YAxis stroke="#64748b" fontSize={10} unit="%" domain={["auto", "auto"]} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="atm_iv" name="ATM IV" stroke="#3b82f6" strokeWidth={2} dot />
              <Line type="monotone" dataKey="ce_iv" name="CE IV" stroke="#16c784" dot={false} strokeDasharray="4 2" />
              <Line type="monotone" dataKey="pe_iv" name="PE IV" stroke="#ea3943" dot={false} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        </Panel>

        {/* Multi-expiry PCR */}
        <Panel title="PCR (OI) by Expiry" loading={termLoading} empty={termPoints.length ? null : "No data."}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={termPoints}>
              <CartesianGrid stroke="#1f2937" />
              <XAxis dataKey="expiry" stroke="#64748b" fontSize={10} />
              <YAxis stroke="#64748b" fontSize={10} domain={[0, "auto"]} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="pcr_oi" name="PCR (OI)" fill="#3b82f6" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="text-[10px] text-muted mt-1">PCR &gt; 1 = put-heavy (bullish bias); &lt; 1 = call-heavy.</div>
        </Panel>
      </div>

      {/* Intraday OI trend */}
      <Panel
        title="Intraday OI Trend (CE vs PE)"
        loading={oiLoading}
        error={oiErr ? (oiErr as Error).message : null}
        empty={!oiLoading && history.length === 0 ? "OI trend builds from snapshots taken every few minutes during market hours." : null}
      >
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={history}>
            <CartesianGrid stroke="#1f2937" />
            <XAxis dataKey="time" stroke="#64748b" fontSize={9} tickFormatter={(t) => (t || "").slice(11, 16)} />
            <YAxis yAxisId="oi" stroke="#64748b" fontSize={10} tickFormatter={(v) => compact(v)} />
            <YAxis yAxisId="pcr" orientation="right" stroke="#eab308" fontSize={10} domain={[0, "auto"]} />
            <Tooltip contentStyle={tooltipStyle} />
            <Area yAxisId="oi" type="monotone" dataKey="ce_oi" name="CE OI" stroke="#16c784" fill="#16c78422" />
            <Area yAxisId="oi" type="monotone" dataKey="pe_oi" name="PE OI" stroke="#ea3943" fill="#ea394322" />
            <Line yAxisId="pcr" type="monotone" dataKey="pcr_oi" name="PCR" stroke="#eab308" dot={false} strokeWidth={2} />
          </ComposedChart>
        </ResponsiveContainer>
      </Panel>

      {/* OI-change heatmap */}
      <Panel
        title="OI Change Heatmap (by strike)"
        loading={oiLoading}
        empty={!oiLoading && buildup.length === 0 ? "No chain data." : null}
      >
        <div className="overflow-auto">
          <table className="w-full text-[11px] num text-center">
            <thead className="text-muted text-[9px] uppercase">
              <tr>
                <th className="px-2 py-1">CE ΔOI</th>
                <th className="px-2 py-1">Strike</th>
                <th className="px-2 py-1">PE ΔOI</th>
              </tr>
            </thead>
            <tbody>
              {buildup.map((r) => {
                const ceC = r.ce?.oi_change ?? null;
                const peC = r.pe?.oi_change ?? null;
                const isATM = r.strike === oi?.atm_strike;
                return (
                  <tr key={r.strike} className={isATM ? "ring-1 ring-inset ring-accent/40" : ""}>
                    <td className="px-2 py-1" style={{ background: heatColor(ceC, maxAbsOI) }}>
                      {compact(ceC)}
                    </td>
                    <td className="px-2 py-1 font-semibold bg-bg-soft/60">{r.strike}</td>
                    <td className="px-2 py-1" style={{ background: heatColor(peC, maxAbsOI) }}>
                      {compact(peC)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="text-[10px] text-muted mt-2">
          Green = OI added, red = OI reduced (vs first snapshot today). Intensity scales with magnitude.
        </div>
      </Panel>
    </div>
  );
}
