import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useTicks } from "../hooks/useLiveFeed";
import { Panel } from "../components/Panel";
import { FlashNum } from "../components/ui";
import { compact, fmt, pct, signClass } from "../lib/format";
import type { SearchResult } from "../api/types";

export default function Watchlist() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);

  const { data } = useQuery({
    queryKey: ["watchlist"],
    queryFn: api.watchlist,
    refetchInterval: 20000,
  });

  const items = data?.items ?? [];
  const ticks = useTicks(items.map((i) => ({ token: i.token, exch_seg: i.exch_seg })));

  const add = useMutation({
    mutationFn: (r: SearchResult) =>
      api.addWatch({ token: r.token, symbol: r.symbol, exch_seg: r.exch_seg }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      setQ("");
      setResults([]);
    },
  });
  const remove = useMutation({
    mutationFn: (token: string) => api.removeWatch(token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const doSearch = async (val: string) => {
    setQ(val);
    if (val.trim().length < 1) return setResults([]);
    const r = await api.search(val.trim());
    setResults(r.results.slice(0, 8));
  };

  return (
    <div className="space-y-4">
      <Panel title="Add to Watchlist">
        <div className="relative">
          <input
            value={q}
            onChange={(e) => doSearch(e.target.value)}
            placeholder="Search a symbol to add…"
            className="w-full bg-bg-soft border border-line rounded px-3 py-1.5 outline-none focus:border-accent"
          />
          {results.length > 0 && (
            <div className="absolute z-20 mt-1 w-full bg-bg-panel border border-line rounded max-h-72 overflow-auto">
              {results.map((r) => (
                <button
                  key={`${r.token}-${r.exch_seg}`}
                  onClick={() => add.mutate(r)}
                  className="w-full text-left px-3 py-1.5 hover:bg-bg-soft flex justify-between"
                >
                  <span className="num">{r.symbol}</span>
                  <span className="text-[11px] text-muted">
                    {r.exch_seg} · {r.instrumenttype || "EQ"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </Panel>

      <Panel title={`Watchlist (${items.length})`}>
        {items.length === 0 ? (
          <div className="text-muted text-center py-8">Empty — search above to add instruments.</div>
        ) : (
          <table className="w-full text-[13px]">
            <thead className="text-muted text-[10px] uppercase">
              <tr>
                <th className="text-left px-2 py-1">Symbol</th>
                <th className="text-right px-2">LTP</th>
                <th className="text-right px-2">Change</th>
                <th className="text-right px-2">%</th>
                <th className="text-right px-2">Volume</th>
                <th className="text-right px-2">OI</th>
                <th className="px-2"></th>
              </tr>
            </thead>
            <tbody className="num">
              {items.map((it) => {
                const t = ticks[it.token];
                const ltp = t?.ltp ?? it.ltp ?? null;
                const chg = it.net_change ?? null;
                return (
                  <tr key={it.token} className="border-t border-line/40 hover:bg-bg-soft/50">
                    <td className="px-2 py-1.5">
                      <Link to={`/symbol/${it.token}`} className="hover:text-accent">
                        {it.symbol}
                      </Link>
                      <span className="text-[10px] text-muted ml-1">{it.exch_seg}</span>
                    </td>
                    <td className="text-right px-2"><FlashNum value={ltp} /></td>
                    <td className={`text-right px-2 ${signClass(chg)}`}>{fmt(chg)}</td>
                    <td className={`text-right px-2 ${signClass(chg)}`}>{pct(it.percent_change)}</td>
                    <td className="text-right px-2">{compact(t?.volume ?? it.volume)}</td>
                    <td className="text-right px-2">{compact(t?.oi ?? it.oi)}</td>
                    <td className="text-right px-2">
                      <button
                        onClick={() => remove.mutate(it.token)}
                        className="text-muted hover:text-bear"
                        title="Remove"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
