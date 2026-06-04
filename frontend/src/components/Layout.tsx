import { NavLink, Outlet } from "react-router-dom";
import { useFeedConnection } from "../hooks/useLiveFeed";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { SearchBar } from "./SearchBar";
import { Clock } from "./Clock";

const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/chain", label: "Option Chain" },
  { to: "/analytics", label: "Analytics" },
  { to: "/news", label: "News & Sentiment" },
  { to: "/watchlist", label: "Watchlist" },
];

function MarketBadge({ marketStatus }: { marketStatus?: string }) {
  const { data } = useQuery({
    queryKey: ["market-state"],
    queryFn: api.marketState,
    refetchInterval: 30000,
  });
  const status = marketStatus || data?.status || "…";
  const open = data?.is_open;
  const color = open ? "bg-bull/20 text-bull" : "bg-bear/20 text-bear";
  return (
    <span className={`chip ${color}`} title={`IST ${data?.server_time_ist ?? ""}`}>
      ● Market {status}
    </span>
  );
}

export default function Layout() {
  const { connected, marketStatus } = useFeedConnection();
  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-12 border-b border-line flex items-center px-4 gap-4 bg-bg-panel sticky top-0 z-20">
        <div className="font-semibold tracking-tight text-slate-100">
          🇮🇳 Market<span className="text-accent">Intel</span>
        </div>
        <nav className="flex gap-1 text-slate-400">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded text-[13px] ${
                  isActive ? "text-slate-100 bg-bg-soft" : "hover:text-slate-200"
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
          <MarketBadge marketStatus={marketStatus} />
          <span
            className={`chip ${connected ? "bg-bull/20 text-bull" : "bg-amber-500/20 text-amber-400"}`}
          >
            <span className={connected ? "" : "animate-pulse"}>{connected ? "●" : "○"}</span>
            {connected ? "Live" : "Reconnecting"}
          </span>
        </div>
      </header>
      <main className="flex-1 p-4">
        <Outlet />
      </main>
    </div>
  );
}
