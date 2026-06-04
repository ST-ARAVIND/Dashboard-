import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Panel } from "../components/Panel";
import { NewsFeed } from "../components/NewsFeed";
import { SentimentGauge } from "../components/SentimentGauge";

export default function News() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["sentiment-market"],
    queryFn: api.marketSentiment,
    refetchInterval: 60000,
  });

  const refresh = useMutation({
    mutationFn: api.refreshNews,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sentiment-market"] }),
  });

  // Distribution of sentiment labels.
  const dist = (data?.articles ?? []).reduce(
    (acc, a) => {
      acc[a.sentiment_label] = (acc[a.sentiment_label] || 0) + 1;
      return acc;
    },
    { positive: 0, neutral: 0, negative: 0 } as Record<string, number>
  );
  const total = (data?.articles ?? []).length || 1;
  // Map avg sentiment (-1..1) to a 0..100 gauge.
  const avg = data?.avg_sentiment ?? 0;
  const gaugeScore = (avg + 1) * 50;
  const gaugeLabel =
    data?.avg_label === "positive" ? "bullish" : data?.avg_label === "negative" ? "bearish" : "neutral";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-1 space-y-4">
        <Panel title="Market News Sentiment">
          <SentimentGauge score={gaugeScore} label={gaugeLabel} />
          <div className="mt-3 space-y-2">
            {(["positive", "neutral", "negative"] as const).map((k) => (
              <div key={k}>
                <div className="flex justify-between text-[11px] text-muted">
                  <span className="capitalize">{k}</span>
                  <span>{dist[k]}</span>
                </div>
                <div className="h-1.5 bg-bg-soft rounded">
                  <div
                    className={`h-full rounded ${
                      k === "positive" ? "bg-bull" : k === "negative" ? "bg-bear" : "bg-slate-500"
                    }`}
                    style={{ width: `${(dist[k] / total) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Panel>
        <button
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending}
          className="w-full panel py-2 hover:border-accent text-ink"
        >
          {refresh.isPending ? "Refreshing…" : "↻ Fetch latest news"}
        </button>
        {refresh.data && (
          <div className="text-[11px] text-muted text-center">
            Ingested {refresh.data.ingested} new article(s)
          </div>
        )}
      </div>

      <div className="lg:col-span-2">
        <Panel title={`Feed (${data?.count ?? 0})`}>
          {isLoading ? (
            <div className="text-muted text-center py-8">Loading…</div>
          ) : (
            <div className="max-h-[75vh] overflow-auto">
              <NewsFeed articles={data?.articles ?? []} />
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
