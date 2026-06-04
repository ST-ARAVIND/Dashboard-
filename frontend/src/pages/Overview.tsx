import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Panel, Stat } from "../components/Panel";
import { SentimentGauge } from "../components/SentimentGauge";
import { compact, fmt, signClass, BUILDUP_LABEL } from "../lib/format";
import { Badge, Change, Skeleton } from "../components/ui";

function IndexCard({ symbol }: { symbol: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["chain-spot", symbol],
    queryFn: () => api.chain(symbol, undefined, 10),
    refetchInterval: 15000,
  });
  const sentiment = data?.analytics?.sentiment;
  return (
    <Link to="/chain" className="panel card-hover px-3 py-2 min-w-[160px] flex-1">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-muted uppercase tracking-wide">{symbol}</span>
        {sentiment && (
          <Badge variant={sentiment === "bullish" ? "bull" : sentiment === "bearish" ? "bear" : "neutral"}>
            {sentiment}
          </Badge>
        )}
      </div>
      {isLoading ? (
        <Skeleton className="h-6 w-24 my-1" />
      ) : (
        <div className="num text-xl">{fmt(data?.spot ?? null)}</div>
      )}
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

  // Top OI movers from the NIFTY chain. Prefer largest |ΔOI| (intraday); when
  // ΔOI isn't available yet (e.g. before snapshots accumulate / off-hours), fall
  // back to the highest absolute OI strikes so the panel always shows last data.
  const { movers, moversByDelta } = (() => {
    if (!nifty?.rows) return { movers: [] as any[], moversByDelta: false };
    const legs: any[] = [];
    nifty.rows.forEach((r) => {
      if (r.ce) legs.push({ strike: r.strike, type: "CE", ...r.ce });
      if (r.pe) legs.push({ strike: r.strike, type: "PE", ...r.pe });
    });
    const withDelta = legs.filter((l) => l.oi_change != null);
    if (withDelta.length) {
      return {
        movers: withDelta.sort((a, b) => Math.abs(b.oi_change) - Math.abs(a.oi_change)).slice(0, 8),
        moversByDelta: true,
      };
    }
    return {
      movers: legs.filter((l) => l.oi != null).sort((a, b) => (b.oi ?? 0) - (a.oi ?? 0)).slice(0, 8),
      moversByDelta: false,
    };
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
        <div className="panel card-hover px-3 py-2 min-w-[160px] flex-1">
          <div className="text-[11px] text-muted uppercase tracking-wide">India VIX</div>
          {vix ? (
            <>
              <div className="num text-xl">{fmt(vix.value)}</div>
              <div className="text-[11px]">
                <Change value={vix.net_change} percent={vix.percent_change} />
              </div>
            </>
          ) : (
            <Skeleton className="h-6 w-20 my-1" />
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Sentiment gauge */}
        <Panel title="Composite Sentiment" loading={!breadth?.gauge}>
          {breadth?.gauge && (
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
          )}
        </Panel>

        {/* Market breadth */}
        <Panel title="Market Breadth" loading={!breadth}>
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

        {/* Top OI movers (by ΔOI intraday, else by absolute OI) */}
        <Panel
          title={moversByDelta ? "NIFTY — Top OI Movers (ΔOI)" : "NIFTY — Top OI (open interest)"}
          empty={movers.length ? null : "No chain data."}
        >
          <table className="w-full text-[12px]">
            <thead className="text-muted text-[10px] uppercase">
              <tr>
                <th className="text-left font-medium pb-1">Strike</th>
                <th className="text-left font-medium">Type</th>
                <th className="text-right font-medium">{moversByDelta ? "ΔOI" : "OI"}</th>
                <th className="text-right font-medium">Buildup</th>
              </tr>
            </thead>
            <tbody className="num">
              {movers.map((m, i) => (
                <tr key={i} className="border-t border-line/50">
                  <td className="py-0.5">{m.strike}</td>
                  <td className={m.type === "CE" ? "text-bear" : "text-bull"}>{m.type}</td>
                  <td className={`text-right ${moversByDelta ? signClass(m.oi_change) : ""}`}>
                    {compact(moversByDelta ? m.oi_change : m.oi)}
                  </td>
                  <td className="text-right">
                    <span className={`chip ${BUILDUP_LABEL[m.buildup]?.cls}`}>
                      {BUILDUP_LABEL[m.buildup]?.text}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>

      {/* Recent news */}
      <Panel
        title="Market News"
        right={
          <Badge variant={news?.avg_label === "positive" ? "bull" : news?.avg_label === "negative" ? "bear" : "neutral"}>
            avg {news?.avg_sentiment ?? "—"}
          </Badge>
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
