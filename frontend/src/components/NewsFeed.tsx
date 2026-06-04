import type { NewsArticle } from "../api/types";
import { sentimentColor } from "../lib/format";

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function NewsFeed({ articles }: { articles: NewsArticle[] }) {
  if (!articles.length)
    return <div className="text-muted text-center py-8">No news yet — try refreshing.</div>;
  return (
    <div className="divide-y divide-line">
      {articles.map((a) => (
        <a
          key={a.id}
          href={a.url}
          target="_blank"
          rel="noreferrer"
          className="block py-2.5 hover:bg-bg-soft px-2 -mx-2 rounded"
        >
          <div className="flex items-start gap-2">
            <span
              className={`chip mt-0.5 ${
                a.sentiment_label === "positive"
                  ? "bg-bull/20 text-bull"
                  : a.sentiment_label === "negative"
                  ? "bg-bear/20 text-bear"
                  : "bg-ink/[0.07] text-muted"
              }`}
            >
              {a.sentiment_score > 0 ? "+" : ""}
              {a.sentiment_score.toFixed(2)}
            </span>
            <div className="flex-1">
              <div className="text-ink leading-snug">{a.title}</div>
              <div className="text-[11px] text-muted mt-0.5 flex gap-2 flex-wrap">
                <span>{a.source}</span>
                <span>· {timeAgo(a.published_at)}</span>
                {a.tickers.slice(0, 4).map((t) => (
                  <span key={t} className="text-accent">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}
