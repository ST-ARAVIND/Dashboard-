import { NavLink, Outlet } from "react-router-dom";
import { useFeedConnection } from "../hooks/useLiveFeed";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { SearchBar } from "./SearchBar";
import { Clock } from "./Clock";
import { AlertToaster } from "./AlertToaster";

const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/chain", label: "Option Chain" },
  { to: "/analytics", label: "Analytics" },
  { to: "/scanners", label: "Scanners" },
  { to: "/news", label: "News & Sentiment" },
  { to: "/watchlist", label: "Watchlist" },
  { to: "/alerts", label: "Alerts" },
];

// A single calm status chip. Open => "Live" (or "Connecting" if the socket is
// briefly down). Closed => a neutral "Showing last data" chip — never an
// alarming "Market closed" / "Reconnecting", since all REST data still reflects
// the last traded session.
function StatusChip({ connected }: { connected: boolean }) {
  const { data } = useQuery({
    queryKey: ["market-state"],
    queryFn: api.marketState,
    refetchInterval: 30000,
  });
  const open = data?.is_open;
  const title = `IST ${data?.server_time_ist ?? ""}`;

  if (open) {
    return connected ? (
      <span className="chip bg-bull/20 text-bull" title={title}>
        <span>●</span> Live
      </span>
    ) : (
      <span className="chip bg-amber-500/20 text-amber-600" title={title}>
        <span className="animate-pulse">●</span> Connecting
      </span>
    );
  }
  // Closed / weekend / holiday / pre-open — show last traded data, calmly.
  return (
    <span className="chip bg-ink/[0.07] text-ink-soft" title={title}>
      <span>●</span> Showing last data
    </span>
  );
}

export default function Layout() {
  const { connected } = useFeedConnection();
  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-12 border-b border-line flex items-center px-4 gap-4 bg-bg-panel sticky top-0 z-20">
        <div className="font-semibold tracking-tight text-ink">
          🇮🇳 Market<span className="text-accent">Intel</span>
        </div>
        <nav className="flex gap-1 text-muted">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded text-[13px] ${
                  isActive ? "text-ink bg-bg-soft" : "hover:text-ink"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex-1 max-w-md">
          <SearchBar />
        </div>
        <div className="flex items-center gap-3">
          <Clock />
          <StatusChip connected={connected} />
        </div>
      </header>
      <main className="flex-1 p-4">
        <Outlet />
      </main>
      <AlertToaster />
    </div>
  );
}
