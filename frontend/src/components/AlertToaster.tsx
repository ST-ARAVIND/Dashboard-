import { useEffect, useState } from "react";
import { liveFeed } from "../api/ws";
import type { AlertEvent } from "../api/types";

const METRIC_LABEL: Record<string, string> = {
  ltp: "LTP",
  percent_change: "% change",
  oi: "OI",
};

// Listens for fired alerts on the live feed; shows toasts + browser notifications.
export function AlertToaster() {
  const [toasts, setToasts] = useState<(AlertEvent & { _k: number })[]>([]);

  useEffect(() => {
    let k = 0;
    const off = liveFeed.onAlert((a) => {
      const item = { ...a, _k: ++k };
      setToasts((prev) => [...prev, item]);
      // Auto-dismiss after 9s.
      setTimeout(() => setToasts((prev) => prev.filter((t) => t._k !== item._k)), 9000);
      // Browser notification (best-effort; needs prior permission).
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification(`🔔 ${a.symbol}`, {
          body: `${METRIC_LABEL[a.metric] ?? a.metric} ${a.operator} ${a.threshold} — now ${a.value}`,
        });
      }
    });
    return () => {
      off();
    };
  }, []);

  if (!toasts.length) return null;
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80">
      {toasts.map((t) => (
        <div
          key={t._k}
          className="panel border-accent/50 shadow-xl p-3 animate-[flashUp_0.6s_ease] bg-bg-panel"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="font-semibold text-slate-100">🔔 {t.symbol}</div>
              <div className="text-[12px] text-slate-300 num">
                {METRIC_LABEL[t.metric] ?? t.metric} {t.operator === "above" ? "≥" : "≤"} {t.threshold} →{" "}
                <span className={t.operator === "above" ? "text-bull" : "text-bear"}>{t.value}</span>
              </div>
              {t.note && <div className="text-[11px] text-muted mt-0.5">{t.note}</div>}
            </div>
            <button
              onClick={() => setToasts((prev) => prev.filter((x) => x._k !== t._k))}
              className="text-muted hover:text-slate-200"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
