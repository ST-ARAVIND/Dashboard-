import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import { useTicks } from "../hooks/useLiveFeed";
import { Panel, Stat } from "../components/Panel";
import { PriceChart } from "../components/PriceChart";
import { NewsFeed } from "../components/NewsFeed";
import { compact, fmt, pct, signClass } from "../lib/format";

export default function SymbolDetail() {
  const { token } = useParams<{ token: string }>();

  const { data: quote } = useQuery({
    queryKey: ["quote", token],
    queryFn: () => api.quote(token!),
    enabled: !!token,
    refetchInterval: 15000,
  });

  const inst = quote?.instrument;
  const underlying = inst?.name || quote?.symbol || "";
  const exch = inst?.exch_seg || "NSE";

  const { data: candleData } = useQuery({
    queryKey: ["candles", token],
    queryFn: () => api.candles(token!, "ONE_DAY", 120),
    enabled: !!token,
  });

  const { data: news } = useQuery({
    queryKey: ["sentiment", underlying],
    queryFn: () => api.symbolSentiment(underlying),
    enabled: !!underlying,
  });

  // Options analytics for the underlying (IV smile + buildup), best-effort.
  const { data: oi } = useQuery({
    queryKey: ["oi", underlying],
    queryFn: () => api.oi(underlying),
    enabled: !!underlying,
    retry: false,
  });

  const live = useTicks(token ? [{ token, exch_seg: exch }] : []);
  const tick = token ? live[token] : undefined;
  const ltp = tick?.ltp ?? quote?.ltp ?? null;

  // Build IV smile + buildup datasets from the chain.
  const { data: chain } = useQuery({
    queryKey: ["chain-detail", underlying],
    queryFn: () => api.chain(underlying, undefined, 15),
    enabled: !!oi && !oi.error,
    retry: false,
  });

  const ivSmile =
    chain?.rows
      ?.map((r) => ({
        strike: r.strike,
        CE: r.ce?.iv ?? null,
        PE: r.pe?.iv ?? null,
      }))
      .filter((d) => d.CE != null || d.PE != null) ?? [];

  const buildup =
    chain?.rows?.map((r) => ({
      strike: r.strike,
      CE_OI: r.ce?.oi ?? 0,
      PE_OI: r.pe?.oi ?? 0,
    })) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-6 flex-wrap">
        <div>
          <div className="text-xl font-semibold">{quote?.symbol || token}</div>
          <div className="text-[11px] text-muted">
            {exch} · {inst?.instrumenttype || "EQ"} · token {token}
          </div>
        </div>
        <Stat label="LTP" value={fmt(ltp)} valueClass={signClass(quote?.net_change)} />
        <Stat
          label="Change"
          value={<span className={signClass(quote?.net_change)}>{fmt(quote?.net_change ?? null)}</span>}
          sub={<span className={signClass(quote?.net_change)}>{pct(quote?.percent_change)}</span>}
        />
        <Stat label="Open" value={fmt(quote?.open ?? null)} />
        <Stat label="High" value={fmt(quote?.high ?? null)} />
        <Stat label="Low" value={fmt(quote?.low ?? null)} />
        <Stat label="Volume" value={compact(quote?.volume)} />
        {quote?.oi != null && <Stat label="OI" value={compact(quote.oi)} />}
      </div>

      <Panel title="Price (Daily)">
        {candleData?.candles?.length ? (
          <PriceChart candles={candleData.candles} />
        ) : (
          <div className="text-muted text-center py-12">No candle data (needs Angel session).</div>
        )}
      </Panel>

      {chain && !chain.error && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Panel title={`IV Smile — ${underlying} ${chain.expiry}`}>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={ivSmile}>
                <CartesianGrid stroke="#1f2937" />
                <XAxis dataKey="strike" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} unit="%" />
                <Tooltip contentStyle={{ background: "#111722", border: "1px solid #1f2937" }} />
                <Line type="monotone" dataKey="CE" stroke="#16c784" dot={false} />
                <Line type="monotone" dataKey="PE" stroke="#ea3943" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Panel>
          <Panel title="OI by Strike">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={buildup}>
                <CartesianGrid stroke="#1f2937" />
                <XAxis dataKey="strike" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} tickFormatter={(v) => compact(v)} />
                <Tooltip contentStyle={{ background: "#111722", border: "1px solid #1f2937" }} />
                <Bar dataKey="CE_OI" fill="#16c784" />
                <Bar dataKey="PE_OI" fill="#ea3943" />
              </BarChart>
            </ResponsiveContainer>
          </Panel>
        </div>
      )}

      <Panel
        title={`News — ${underlying}`}
        right={news?.avg_sentiment != null ? <span className="chip num">avg {news.avg_sentiment}</span> : undefined}
      >
        <NewsFeed articles={news?.articles ?? []} />
      </Panel>
    </div>
  );
}
