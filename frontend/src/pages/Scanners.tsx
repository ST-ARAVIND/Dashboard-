import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Panel, Stat } from "../components/Panel";
import { Badge, Loading } from "../components/ui";
import { fmt, pct, signClass } from "../lib/format";
import type { ScanStock } from "../api/types";

const GAP_VARIANT: Record<string, "bull" | "bear" | "neutral"> = {
  Breakaway: "bull",
  Exhaustion: "bear",
  Common: "neutral",
};

function vrocColor(v: number): string {
  if (v >= 100) return "text-accent";
  if (v >= 50) return "text-bull";
  if (v >= 0) return "text-ink-soft";
  return "text-bear";
}

export default function Scanners() {
  const [tab, setTab] = useState<"vroc" | "gaps">("vroc");
  const [sector, setSector] = useState("ALL");

  const { data, isFetching } = useQuery({
    queryKey: ["scanners"],
    queryFn: api.scanners,
    refetchInterval: (q) =>
      (q.state.data as any)?.status === "computing" ? 4000 : 60000,
  });

  const stocks = data?.stocks ?? [];
  const computing = data?.status === "computing" || (!stocks.length && isFetching);

  const sectors = useMemo(
    () => ["ALL", ...Array.from(new Set(stocks.map((s) => s.sector))).sort()],
    [stocks]
  );
  const filtered = sector === "ALL" ? stocks : stocks.filter((s) => s.sector === sector);

  const vrocList = [...filtered].sort((a, b) => b.vroc - a.vroc);
  const gapList = [...filtered]
    .filter((s) => s.gap_type !== "None")
    .sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap));

  // Stats
  const surge = stocks.filter((s) => s.vroc >= 100).length;
  const dry = stocks.filter((s) => s.vroc < 0).length;
  const breakaways = stocks.filter((s) => s.gap_type === "Breakaway").length;
  const exhaustions = stocks.filter((s) => s.gap_type === "Exhaustion").length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex border border-line rounded-md overflow-hidden text-[12px]">
          {(["vroc", "gaps"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 ${tab === t ? "bg-accent/15 text-accent" : "text-muted hover:text-ink"}`}
            >
              {t === "vroc" ? "VROC" : "Gaps"}
            </button>
          ))}
        </div>
        <select value={sector} onChange={(e) => setSector(e.target.value)} className="input w-auto">
          {sectors.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <span className="text-[11px] text-muted ml-auto num">
          {data?.generated_at ? `updated ${new Date(data.generated_at).toLocaleTimeString("en-IN")}` : ""}
          {" · "}
          {stocks.length} F&O stocks
        </span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {tab === "vroc" ? (
          <>
            <Panel><Stat label="Volume surge (>100%)" value={surge} valueClass="text-accent" /></Panel>
            <Panel><Stat label="Above average (>0%)" value={stocks.filter((s) => s.vroc >= 0).length} valueClass="text-bull" /></Panel>
            <Panel><Stat label="Volume dry (<0%)" value={dry} valueClass="text-bear" /></Panel>
            <Panel><Stat label="Universe" value={stocks.length} /></Panel>
          </>
        ) : (
          <>
            <Panel><Stat label="Total gaps" value={gapList.length} /></Panel>
            <Panel><Stat label="Breakaway" value={breakaways} valueClass="text-bull" /></Panel>
            <Panel><Stat label="Exhaustion" value={exhaustions} valueClass="text-bear" /></Panel>
            <Panel><Stat label="Common" value={stocks.filter((s) => s.gap_type === "Common").length} /></Panel>
          </>
        )}
      </div>

      <Panel
        title={tab === "vroc" ? "VROC Leaderboard (vs 14-day avg volume)" : "Gap Analysis"}
        loading={computing && !stocks.length}
        empty={!computing && (tab === "vroc" ? vrocList : gapList).length === 0 ? "No data." : null}
      >
        {computing && !stocks.length ? (
          <Loading label="Scanning F&O universe (fetching candles)…" />
        ) : tab === "vroc" ? (
          <VrocTable rows={vrocList} />
        ) : (
          <GapTable rows={gapList} />
        )}
      </Panel>

      <div className="text-[11px] text-muted">
        {tab === "vroc"
          ? "VROC = today's volume vs trailing 14-day average. >100% = unusual participation."
          : "Breakaway = gap with the trend (new move). Exhaustion = gap against the move (possible reversal). Common = likely fills."}
      </div>
    </div>
  );
}

function StockLink({ name }: { name: string }) {
  // We only have the name here; link to search isn't token-based, so just show it.
  return <span className="font-semibold text-ink">{name}</span>;
}

function VrocTable({ rows }: { rows: ScanStock[] }) {
  return (
    <div className="overflow-auto max-h-[60vh]">
      <table className="w-full text-[12px] num">
        <thead className="text-muted text-[10px] uppercase sticky top-0 bg-bg-panel">
          <tr>
            <th className="text-left px-2 py-1 font-medium">#</th>
            <th className="text-left px-2 font-medium">Stock</th>
            <th className="text-left px-2 font-medium">Sector</th>
            <th className="text-right px-2 font-medium">Price</th>
            <th className="text-right px-2 font-medium">Chg%</th>
            <th className="text-right px-2 font-medium">Vol×</th>
            <th className="text-right px-2 font-medium">VROC-14</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s, i) => (
            <tr key={s.name} className={`border-t border-line/50 ${s.vroc >= 100 ? "bg-accent/[0.05]" : ""}`}>
              <td className={`px-2 py-1 ${i < 3 ? "text-accent font-bold" : "text-muted"}`}>{i + 1}</td>
              <td className="px-2"><StockLink name={s.name} /></td>
              <td className="px-2 text-[10px] text-muted">{s.sector}</td>
              <td className="px-2 text-right">{fmt(s.price)}</td>
              <td className={`px-2 text-right ${signClass(s.chg)}`}>{pct(s.chg)}</td>
              <td className={`px-2 text-right ${s.vol_ratio > 1.5 ? "text-accent" : "text-muted"}`}>{s.vol_ratio}x</td>
              <td className={`px-2 text-right font-semibold ${vrocColor(s.vroc)}`}>
                {s.vroc > 0 ? "+" : ""}{s.vroc}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GapTable({ rows }: { rows: ScanStock[] }) {
  return (
    <div className="overflow-auto max-h-[60vh]">
      <table className="w-full text-[12px] num">
        <thead className="text-muted text-[10px] uppercase sticky top-0 bg-bg-panel">
          <tr>
            <th className="text-left px-2 py-1 font-medium">Stock</th>
            <th className="text-left px-2 font-medium">Sector</th>
            <th className="text-right px-2 font-medium">Gap%</th>
            <th className="text-center px-2 font-medium">Type</th>
            <th className="text-right px-2 font-medium">Chg%</th>
            <th className="text-right px-2 font-medium">VROC</th>
            <th className="text-right px-2 font-medium">Price</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.name} className="border-t border-line/50">
              <td className="px-2 py-1"><StockLink name={s.name} /></td>
              <td className="px-2 text-[10px] text-muted">{s.sector}</td>
              <td className={`px-2 text-right font-semibold ${signClass(s.gap)}`}>{pct(s.gap)}</td>
              <td className="px-2 text-center">
                <Badge variant={GAP_VARIANT[s.gap_type] ?? "neutral"}>{s.gap_type}</Badge>
              </td>
              <td className={`px-2 text-right ${signClass(s.chg)}`}>{pct(s.chg)}</td>
              <td className={`px-2 text-right ${vrocColor(s.vroc)}`}>{s.vroc > 0 ? "+" : ""}{s.vroc}%</td>
              <td className="px-2 text-right">{fmt(s.price)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
