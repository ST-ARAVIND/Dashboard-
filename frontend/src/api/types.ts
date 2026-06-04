// Shared API types mirroring the FastAPI response shapes.

export interface MarketState {
  is_open: boolean;
  status: "open" | "closed" | "pre_open" | "weekend" | "holiday";
  server_time_ist: string;
  open_time: string;
  close_time: string;
}

export interface SearchResult {
  token: string;
  symbol: string;
  name: string;
  expiry: string;
  strike: number;
  lotsize: number;
  instrumenttype: string;
  exch_seg: string;
  tick_size: number;
}

export interface Quote {
  token: string;
  symbol: string;
  exchange: string;
  ltp: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  oi: number | null;
  net_change: number | null;
  percent_change: number | null;
  instrument?: SearchResult;
}

export interface OptionLeg {
  token: string;
  ltp: number | null;
  oi: number | null;
  oi_change: number | null;
  volume: number | null;
  iv: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  rho: number | null;
  net_change: number | null;
  buildup: string;
  lotsize: number;
}

export interface ChainRow {
  strike: number;
  ce: OptionLeg | null;
  pe: OptionLeg | null;
}

export interface ChainAnalytics {
  pcr_oi: number | null;
  pcr_volume: number | null;
  total_ce_oi: number;
  total_pe_oi: number;
  max_pain: number | null;
  sentiment: string;
  atm_iv: number | null;
  iv_skew: number | null;
  atm_straddle: number | null;
  expected_move_pts: number | null;
  expected_move_pct: number | null;
}

export interface OptionChain {
  underlying: string;
  expiry: string;
  expiries: string[];
  spot: number | null;
  atm_strike: number | null;
  time_to_expiry_years: number;
  rows: ChainRow[];
  analytics: ChainAnalytics;
  subscribe_tokens: { token: string; exch_seg: string }[];
  error?: string;
}

export interface NewsArticle {
  id: number;
  source: string;
  title: string;
  summary: string;
  url: string;
  published_at: string | null;
  sentiment_score: number;
  sentiment_label: string;
  sentiment_model: string;
  tickers: string[];
}

export interface MarketSentiment {
  count: number;
  avg_sentiment: number | null;
  avg_label: string;
  articles: NewsArticle[];
}

export interface Breadth {
  india_vix: { value: number; net_change: number; percent_change: number } | null;
  advance_decline: {
    advances: number;
    declines: number;
    unchanged: number;
    ratio: number | null;
    sampled: number;
  };
  pcr_oi: number | null;
  pcr_sentiment: string;
  gauge: { score: number; label: string; components: Record<string, number> };
}

export interface WatchItem extends SearchResult {
  ltp?: number;
  net_change?: number;
  percent_change?: number;
  volume?: number;
  oi?: number;
}

export interface Tick {
  type: string;
  token: string;
  ltp: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  oi: number | null;
  oi_change_pct: number | null;
  ts: string | null;
}

export interface AlertRule {
  id: number;
  token: string;
  symbol: string;
  exch_seg: string;
  metric: "ltp" | "percent_change" | "oi";
  operator: "above" | "below";
  threshold: number;
  note: string;
  active: boolean;
  repeat: boolean;
  triggered_at: string | null;
  triggered_value: number | null;
  created_at: string | null;
}

export interface NewAlert {
  token: string;
  symbol: string;
  exch_seg: string;
  metric: string;
  operator: string;
  threshold: number;
  note?: string;
  repeat?: boolean;
}

export interface AlertEvent {
  type: "alert";
  id: number;
  symbol: string;
  token: string;
  metric: string;
  operator: string;
  threshold: number;
  value: number;
  note: string;
  ts: string | null;
}

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
