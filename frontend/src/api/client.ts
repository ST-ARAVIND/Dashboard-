// Thin fetch wrapper around the backend REST API.
import type {
  Breadth,
  Candle,
  MarketSentiment,
  MarketState,
  OptionChain,
  Quote,
  SearchResult,
  WatchItem,
} from "./types";

// In dev, VITE_API_BASE is empty and requests go through the Vite proxy ("/api").
// In production (Netlify), set VITE_API_BASE to the backend URL, e.g.
//   VITE_API_BASE=https://your-backend.onrender.com
export const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
const API_TOKEN = import.meta.env.VITE_API_TOKEN ?? "";

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { ...extra };
  if (API_TOKEN) h["X-API-Token"] = API_TOKEN;
  return h;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, { headers: headers() });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, { method: "DELETE", headers: headers() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => get<{ status: string; market: MarketState; angel: any; feed: any }>("/health"),
  marketState: () => get<MarketState>("/market-state"),
  authStatus: () => get<any>("/auth/status"),
  search: (q: string) => get<{ results: SearchResult[] }>(`/search?q=${encodeURIComponent(q)}`),
  expiries: (symbol: string) => get<{ expiries: string[] }>(`/expiries?symbol=${symbol}`),
  quote: (token: string) => get<Quote>(`/quote/${token}`),
  candles: (token: string, interval = "ONE_DAY", days = 90) =>
    get<{ candles: Candle[] }>(`/candles/${token}?interval=${interval}&days=${days}`),
  chain: (symbol: string, expiry?: string, strikes = 15) =>
    get<OptionChain>(
      `/chain?symbol=${symbol}${expiry ? `&expiry=${expiry}` : ""}&strikes=${strikes}`
    ),
  oi: (symbol: string, expiry?: string) =>
    get<any>(`/oi/${symbol}${expiry ? `?expiry=${expiry}` : ""}`),
  marketSentiment: () => get<MarketSentiment>("/sentiment/market"),
  symbolSentiment: (symbol: string) => get<MarketSentiment>(`/sentiment/${symbol}`),
  refreshNews: () => post<{ ingested: number }>("/sentiment/refresh"),
  breadth: () => get<Breadth>("/breadth"),
  watchlist: () => get<{ items: WatchItem[] }>("/watchlist"),
  addWatch: (item: { token: string; symbol: string; exch_seg: string }) =>
    post("/watchlist", item),
  removeWatch: (token: string) => del(`/watchlist/${token}`),
};
