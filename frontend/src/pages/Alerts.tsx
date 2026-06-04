import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Panel } from "../components/Panel";
import { Badge } from "../components/ui";
import type { SearchResult } from "../api/types";

const METRICS = [
  { v: "ltp", label: "Last price (LTP)" },
  { v: "percent_change", label: "% change" },
  { v: "oi", label: "Open interest" },
];

export default function Alerts() {
  const qc = useQueryClient();
  const [picked, setPicked] = useState<SearchResult | null>(null);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [metric, setMetric] = useState("ltp");
  const [operator, setOperator] = useState("above");
  const [threshold, setThreshold] = useState("");
  const [note, setNote] = useState("");
  const [repeat, setRepeat] = useState(false);

  const { data } = useQuery({ queryKey: ["alerts"], queryFn: api.alerts, refetchInterval: 10000 });
  const alerts = data?.alerts ?? [];

  const create = useMutation({
    mutationFn: () =>
      api.createAlert({
        token: picked!.token,
        symbol: picked!.symbol,
        exch_seg: picked!.exch_seg,
        metric,
        operator,
        threshold: Number(threshold),
        note,
        repeat,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
      setPicked(null);
      setQ("");
      setThreshold("");
      setNote("");
    },
  });
  const del = useMutation({
    mutationFn: (id: number) => api.deleteAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) => api.toggleAlert(id, active),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const doSearch = async (val: string) => {
    setQ(val);
    setPicked(null);
    if (val.trim().length < 1) return setResults([]);
    const r = await api.search(val.trim());
    setResults(r.results.slice(0, 8));
  };

  const notifyPerm = "Notification" in window ? Notification.permission : "unsupported";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Create */}
      <Panel title="New Alert" className="lg:col-span-1">
        <div className="space-y-3">
          <div className="relative">
            <label className="text-[11px] text-muted uppercase">Instrument</label>
            <input
              value={picked ? picked.symbol : q}
              onChange={(e) => doSearch(e.target.value)}
              placeholder="Search symbol…"
              className="input mt-1"
            />
            {!picked && results.length > 0 && (
              <div className="absolute z-20 mt-1 w-full bg-bg-panel border border-line rounded max-h-60 overflow-auto">
                {results.map((r) => (
                  <button
                    key={`${r.token}-${r.exch_seg}`}
                    onClick={() => {
                      setPicked(r);
                      setResults([]);
                    }}
                    className="w-full text-left px-3 py-1.5 hover:bg-bg-soft flex justify-between"
                  >
                    <span className="num">{r.symbol}</span>
                    <span className="text-[11px] text-muted">{r.exch_seg}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] text-muted uppercase">Metric</label>
              <select value={metric} onChange={(e) => setMetric(e.target.value)} className="input mt-1">
                {METRICS.map((m) => (
                  <option key={m.v} value={m.v}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] text-muted uppercase">Condition</label>
              <select value={operator} onChange={(e) => setOperator(e.target.value)} className="input mt-1">
                <option value="above">crosses above</option>
                <option value="below">crosses below</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-[11px] text-muted uppercase">Threshold</label>
            <input
              type="number"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              placeholder={metric === "percent_change" ? "e.g. 2 (=+2%)" : "e.g. 24000"}
              className="input mt-1 num"
            />
          </div>

          <div>
            <label className="text-[11px] text-muted uppercase">Note (optional)</label>
            <input value={note} onChange={(e) => setNote(e.target.value)} className="input mt-1" />
          </div>

          <label className="flex items-center gap-2 text-[12px] text-slate-300">
            <input type="checkbox" checked={repeat} onChange={(e) => setRepeat(e.target.checked)} />
            Repeat (don't auto-disable after firing)
          </label>

          <button
            disabled={!picked || !threshold || create.isPending}
            onClick={() => create.mutate()}
            className="btn w-full"
          >
            {create.isPending ? "Creating…" : "Create alert"}
          </button>

          {notifyPerm !== "granted" && notifyPerm !== "unsupported" && (
            <button onClick={() => Notification.requestPermission()} className="btn w-full text-[12px]">
              Enable browser notifications
            </button>
          )}
        </div>
      </Panel>

      {/* List */}
      <Panel
        title={`Alerts (${alerts.length})`}
        className="lg:col-span-2"
        empty={alerts.length ? null : "No alerts yet — create one on the left. Alerts evaluate against live ticks."}
      >
        <div className="divide-y divide-line">
          {alerts.map((a) => (
            <div key={a.id} className="py-2 flex items-center gap-3">
              <Badge variant={a.active ? "accent" : a.triggered_at ? "bull" : "neutral"}>
                {a.active ? "armed" : a.triggered_at ? "fired" : "off"}
              </Badge>
              <div className="flex-1">
                <div className="num text-slate-200">
                  {a.symbol}{" "}
                  <span className="text-muted">
                    {a.metric === "ltp" ? "LTP" : a.metric === "oi" ? "OI" : "% chg"}{" "}
                    {a.operator === "above" ? "≥" : "≤"} {a.threshold}
                  </span>
                  {a.repeat && <span className="chip bg-slate-600/20 text-slate-400 ml-2">repeat</span>}
                </div>
                <div className="text-[11px] text-muted">
                  {a.note && <span>{a.note} · </span>}
                  {a.triggered_at
                    ? `fired @ ${a.triggered_value} (${new Date(a.triggered_at).toLocaleString("en-IN")})`
                    : "waiting…"}
                </div>
              </div>
              <button
                onClick={() => toggle.mutate({ id: a.id, active: !a.active })}
                className="text-[11px] text-muted hover:text-accent"
              >
                {a.active ? "disarm" : "re-arm"}
              </button>
              <button onClick={() => del.mutate(a.id)} className="text-muted hover:text-bear" title="Delete">
                ✕
              </button>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
