# 🇮🇳 Indian Market Intelligence Dashboard

A real-time Indian equities & F&O analytics dashboard built on **Angel One SmartAPI**.
It pulls live + historical market data, **computes IV & Greeks** (Angel doesn't return
them), derives OI analytics (PCR, OI buildup, max pain, ΔOI), ingests financial news
with sentiment scoring, and renders everything in a fast dark trading-desk UI.

> Built and verified against `smartapi-python` **1.5.3**. The SDK has changed signatures
> across versions — the methods used here (`generateSession`, `getMarketData`,
> `getCandleData`, `SmartWebSocketV2`) were verified against the current source before
> wiring them up.

---

## Architecture

```
/backend                      FastAPI + Uvicorn (Python 3.11+)
  app/
    config.py                 .env-driven settings (pydantic-settings)
    main.py                   app + lifespan (DB, scrip master, auth, feed, scheduler)
    scheduler.py              APScheduler: OI snapshots, news, daily scrip refresh
    angel/                    SmartAPI session, scrip master, live websocket feed
    services/                 market_data, options_chain, iv_greeks, oi_analytics,
                              market_breadth, sentiment, ws_hub (frontend relay)
    api/                      REST + WS routers
    models/                   SQLAlchemy models (SQLite -> Postgres = URL change)
    utils/                    market hours, token-bucket rate limiter, backoff
/frontend                     React + Vite + TS + Tailwind + TanStack Query
  src/
    api/                      REST client, WS client, shared types
    components/               Layout, charts (lightweight-charts), gauge, news feed
    pages/                    Overview, OptionChain, SymbolDetail, News, Watchlist
run.sh                        boots backend + frontend together
docker-compose.yml            optional containerised run
```

**Data flow:** the browser only ever talks to the backend (REST + a `/ws` relay).
Angel One tokens never reach the browser — the backend owns the upstream websocket and
fans out normalized ticks.

---

## Quick start

```bash
# 1. Configure credentials
cp .env.example .env
#    edit .env and fill in the four Angel One values (see below)

# 2. Run everything (creates venv, installs deps, starts both servers)
./run.sh
```

- Backend → http://127.0.0.1:8000  (interactive docs at `/docs`)
- Frontend → http://localhost:5173

The app **runs without credentials in a degraded mode**: instrument search and news
sentiment work; live quotes, the option chain, breadth and the live feed return a clean
`503` until you add Angel One credentials and the session logs in.

### Manual run (without run.sh)

```bash
# backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev
```

---

## Credentials — where to get each one

Put these in `.env` (copied from `.env.example`).

| Variable | What it is | Where to get it |
|---|---|---|
| `ANGEL_API_KEY` | SmartAPI app key | Create an app at <https://smartapi.angelbroking.com/> → **Create An App** (Market Feeds / Trading). |
| `ANGEL_CLIENT_CODE` | Your Angel One login / client code | e.g. `A123456` — your trading account ID. |
| `ANGEL_MPIN` | The MPIN used for SmartAPI login | The numeric MPIN set for your account (used as the `password` arg of `generateSession`). |
| `ANGEL_TOTP_SECRET` | **Base32 TOTP secret** (not a 6-digit code) | Enable TOTP at <https://smartapi.angelbroking.com/enable-totp> and copy the long secret string. The app generates the rotating 6-digit code at runtime via `pyotp`. |

Optional:

| Variable | Default | Notes |
|---|---|---|
| `NEWS_PROVIDER` | `rss` | `rss` (free, Moneycontrol/ET/BS/Mint) or `newsapi`. |
| `NEWS_API_KEY` | — | Required only if `NEWS_PROVIDER=newsapi` (<https://newsapi.org/>). |
| `SENTIMENT_MODEL` | `vader` | `vader` (default, no download) or `finbert` (needs `pip install transformers torch`). |
| `RISK_FREE_RATE` | `0.065` | Used for Black-Scholes IV/Greeks. |
| `DATABASE_URL` | `sqlite:///./market.db` | Swap to a Postgres URL with no code changes. |
| `OI_SNAPSHOT_INTERVAL` | `180` | Seconds between intraday OI snapshots (for ΔOI / OI-trend charts). |

---

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Market state + Angel/feed status |
| GET | `/api/search?q=` | Instrument lookup |
| GET | `/api/expiries?symbol=` | Option expiries for an underlying |
| GET | `/api/quote/{token}` | FULL quote (LTP/OHLC/volume/OI) |
| GET | `/api/candles/{token}` | Historical candles (cached) |
| GET | `/api/chain?symbol=&expiry=&strikes=` | Assembled option chain + IV/Greeks/PCR/max-pain |
| GET | `/api/oi/{symbol}` | PCR, max pain, OI buildup, ΔOI history |
| GET | `/api/sentiment/market` · `/api/sentiment/{symbol}` | News + sentiment |
| POST | `/api/sentiment/refresh` | Pull latest news now |
| GET | `/api/breadth` | India VIX, advance/decline, composite gauge |
| GET/POST/DELETE | `/api/watchlist` | Manage watchlist (live quotes) |
| WS | `/ws` | Live normalized tick stream |
| POST | `/api/auth/login` · `/api/auth/logout` | Force re-login / logout |

---

## How the analytics work

- **IV & Greeks** — Angel returns no IV. Index options (NIFTY/BANKNIFTY/FINNIFTY…) are
  European → Black-Scholes via `py_vollib`. Time-to-expiry uses calendar years; the
  risk-free rate is configurable. A numba-accelerated `py_vollib_vectorized` path is
  used automatically *only if* it JITs cleanly on the installed numpy/numba (it is
  self-tested at import; otherwise the reliable scalar backend is used).
- **PCR** — put/call OI and volume ratios per expiry.
- **OI buildup** — price-vs-OI change → Long Buildup / Short Buildup / Long Unwinding /
  Short Covering.
- **Max pain** — strike minimising total option-writer payout.
- **ΔOI** — APScheduler snapshots OI to SQLite every few minutes during market hours so
  change-in-OI and OI-trend charts work.
- **Breadth / sentiment** — India VIX, a sampled large-cap advance/decline read, and a
  PCR/VIX/AD composite 0–100 gauge.

---

## Cross-cutting behaviour

- **Secrets** are never logged or sent to the browser.
- **Rate limiting** — every Angel endpoint goes through a per-endpoint token bucket with
  exponential backoff on errors.
- **Market hours** — IST 09:15–15:30, Mon–Fri, NSE holiday calendar baked in. Polling and
  OI snapshots pause when closed; the UI shows a clear *Market closed* / *Reconnecting*
  state.
- **Reconnection** — the upstream websocket auto-reconnects and re-subscribes; the browser
  WS client reconnects with backoff.

---

## Deployment (Netlify frontend + Render backend)

This is a two-part app: a static frontend (Netlify) and a long-running FastAPI
backend with a live websocket (Render). They deploy separately; both auto-redeploy
on every push to `main`.

### 1. Backend → Render

1. Render dashboard → **New + → Blueprint** → connect this repo. It reads `render.yaml`.
2. On the service's **Environment** tab, set the secrets (these are `sync:false`, never
   committed): `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_MPIN`, `ANGEL_TOTP_SECRET`,
   and `CORS_ORIGINS` = your Netlify URL (e.g. `https://your-site.netlify.app`).
   Optionally set `API_AUTH_TOKEN` to a random string.
3. Deploy. Note the service URL, e.g. `https://market-dashboard-api.onrender.com`.
   Check `https://…/api/health`.

> **Free tier caveat:** Render free web services spin down after ~15 min idle and cold-start
> (~30 s) on the next request. When you open the dashboard it wakes, logs in, and the live
> feed connects; keeping the tab open (it polls) keeps it awake. For always-on during market
> hours, use a paid instance. SQLite on free tier is **ephemeral** (resets on redeploy) — the
> scrip master re-downloads on boot and OI/news rebuild; attach a Render Disk + point
> `DATABASE_URL` at it for persistence, or switch `DATABASE_URL` to a managed Postgres.

### 2. Frontend → Netlify

1. Netlify → **Add new site → Import from Git** → pick this repo. It reads `netlify.toml`
   (base `frontend`, publish `frontend/dist`).
2. **Site settings → Environment variables:** set `VITE_API_BASE` = your Render URL
   (no trailing slash). If you set `API_AUTH_TOKEN` on the backend, also set
   `VITE_API_TOKEN` to the same value.
3. Deploy. Every push to `main` rebuilds and redeploys automatically.

### How prod differs from dev

- **Dev:** `VITE_API_BASE` empty → the Vite proxy forwards `/api` and `/ws` to `localhost:8000`.
- **Prod:** the frontend calls `VITE_API_BASE` directly for REST, and derives the websocket
  URL from it (`https://…` → `wss://…/ws`). CORS on the backend must list the Netlify origin.
- **API token** (optional): if `API_AUTH_TOKEN` is set, REST requires an `X-API-Token` header.
  Browsers can't send custom headers on a websocket, so `/ws` is not token-gated — and a token
  shipped in a public bundle is only light deterrence, not real auth. For a single-user
  dashboard the practical protections are a private URL + the built-in rate limiting.

## Notes & limitations

- Stock options are American; Black-Scholes is used as an acceptable approximation (a
  binomial model can be swapped into `services/iv_greeks.py`).
- Advance/decline is sampled from a representative large-cap basket (Angel has no direct
  A/D endpoint) — tune `BREADTH_BASKET` in `services/market_breadth.py`.
- News→ticker mapping is a keyword/entity match against the instrument master (NSE names),
  so multi-word company names that differ from the NSE symbol may not always map.
- Angel sessions expire after market hours / inactivity — the backend refreshes the JWT
  and re-logs-in automatically.
