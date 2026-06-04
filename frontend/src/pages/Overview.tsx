import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Panel, Stat } from "../components/Panel";
import { SentimentGauge } from "../components/SentimentGauge";
import { compact, fmt, pct, signClass, BUILDUP_LABEL } from "../lib/format";

function IndexCard({ symbol }: { symbol: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["chain-spot", symbol],
    queryFn: () => api.chain(symbol, undefined, 10),
    refetchInterval: 15000,
  });
  return (
    <Link to="/chain" className="panel px-3 py-2 min-w-[150px] hover:border-accent transition">
      <div className="text-[11px] text-muted uppercase">{symbol}</div>
      <div className="num text-lg">{isLoading ? "…" : fmt(data?.spot ?? null)}</div>
      <div className="text-[11px] num text-muted">
        ATM {fmt(data?.atm_strike ?? null, 0)} · PCR {data?.analytics?.pcr_oi ?? "—"}
      </div>
    </Link>
  );
}

export default function Overview() {
  const { data: breadth } = useQuery({
    queryKey: ["breadth"],
    queryFn: api.breadth,
    refetchInterval: 30000,
  });
  const { data: nifty } = useQuery({
    queryKey: ["chain-spot", "NIFTY"],
    queryFn: () => api.chain("NIFTY", undefined, 20),
    refetchInterval: 20000,
  });
  const { data: news } = useQuery({
    queryKey: ["sentiment-market-mini"],
    queryFn: api.marketSentiment,
    refetchInterval: 60000,
  });

  // Top OI movers from the NIFTY chain (largest |ΔOI| across CE/PE).
  const movers = (() => {
    if (!nifty?.rows) return [] as any[];
    const legs: any[] = [];
    nifty.rows.forEach((r) => {
      if (r.ce?.oi_change != null)
        legs.push({ strike: r.strike, type: "CE", ...r.ce });
      if (r.pe?.oi_change != null)
        legs.push({ strike: r.strike, type: "PE", ...r.pe });
    });
    return legs
      .sort((a, b) => Math.abs(b.oi_change) - Math.abs(a.oi_change))
      .slice(0, 8);
  })();

  const vix = breadth?.india_vix;
  const ad = breadth?.advance_decline;

  return (
    <div className="space-y-4">
      {/* Indices strip */}
      <div className="flex gap-3 flex-wrap">
        <IndexCard symbol="NIFTY" />
        <IndexCard symbol="BANKNIFTY" />
        <IndexCard symbol="FINNIFTY" />
        <div className="panel px-3 py-2 min-w-[150px]">
          <div className="text-[11px] text-muted uppercase">India VIX</div>
          <div className="num text-lg">{fmt(vix?.value ?? null)}</div>
          <div className={`text-[11px] num ${signClass(vix?.net_change)}`}>
            {pct(vix?.percent_change)}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Sentiment gauge */}
        <Panel title="Composite Sentiment">
          {breadth?.gauge ? (
            <div className="flex flex-col items-center gap-3">
              <SentimentGauge score={breadth.gauge.score} label={breadth.gauge.label} />
              <div className="grid grid-cols-3 gap-3 w-full text-center">
                {Object.entries(breadth.gauge.components).map(([k, v]) => (
                  <div key={k}>
                    <div className="text-[10px] text-muted uppercase">{k.replace("_", " ")}</div>
                    <div className="num">{v}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-muted text-center py-8">Loading…</div>
          )}
        </Panel>

        {/* Market breadth */}
        <Panel title="Market Breadth">
          <div className="grid grid-cols-2 gap-4">
            <Stat label="Advances" value={ad?.advances ?? "—"} valueClass="text-bull" />
            <Stat label="Declines" value={ad?.declines ?? "—"} valueClass="text-bear" />
            <Stat label="A/D Ratio" value={ad?.ratio ?? "—"} />
            <Stat label="Unchanged" value={ad?.unchanged ?? "—"} />
            <Stat
              label="NIFTY PCR (OI)"
              value={breadth?.pcr_oi ?? "—"}
              sub={<span className="text-muted">{breadth?.pcr_sentiment}</span>}
            />
            <Stat label="Max Pain" value={fmt(nifty?.analytics?.max_pain ?? null, 0)} />
          </div>
        </Panel>

        {/* Top OI movers */}
        <Panel title="NIFTY — Top OI Movers">
          {movers.length ? (
            <table className="w-full text-[12px]">
              <thead className="text-muted text-[10px] uppercase">
                <tr>
                  <th className="text-left">Strike</th>
                  <th className="text-left">Type</th>
                  <th className="text-right">ΔOI</th>
                  <th className="text-right">Buildup</th>
                </tr>
              </thead>
              <tbody className="num">
                {movers.map((m, i) => (
                  <tr key={i} className="border-t border-line/50">
                    <td>{m.strike}</td>
                    <td className={m.type === "CE" ? "text-bear" : "text-bull"}>{m.type}</td>
                    <td className={`text-right ${signClass(m.oi_change)}`}>{compact(m.oi_change)}</td>
                    <td className="text-right">
                      <span className={`chip ${BUILDUP_LABEL[m.buildup]?.cls}`}>
                        {BUILDUP_LABEL[m.buildup]?.text}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-muted text-center py-8">
              OI movers appear once snapshots accumulate (market hours).
            </div>
          )}
        </Panel>
      </div>

      {/* Recent news */}
      <Panel
        title="Market News"
        right={
          <span className={`chip ${news?.avg_label === "positive" ? "bg-bull/20 text-bull" : news?.avg_label === "negative" ? "bg-bear/20 text-bear" : "bg-slate-600/20 text-slate-400"}`}>
            avg {news?.avg_sentiment ?? "—"}
          </span>
        }
      >
        <div className="space-y-1 max-h-64 overflow-auto">
          {(news?.articles ?? []).slice(0, 8).map((a) => (
            <a key={a.id} href={a.url} target="_blank" rel="noreferrer" className="block text-slate-300 hover:text-slate-100 truncate">
              <span className={signClass(a.sentiment_score)}>●</span> {a.title}
            </a>
          ))}
          {!news?.articles?.length && (
            <div className="text-muted text-center py-4">No news — open the News tab and refresh.</div>
          )}
        </div>
      </Panel>
    </div>
  );
}
