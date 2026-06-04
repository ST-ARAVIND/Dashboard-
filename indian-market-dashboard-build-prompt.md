# Build Prompt — Indian Market Intelligence Dashboard (Angel One SmartAPI)

> Paste everything below the line into Claude Code. It is written as a single, complete specification. Build it in phases (the phases are numbered). Ask me for any credential the moment you reach a step that needs it — do not invent or stub keys.

---

## ROLE & GOAL

You are building a **real-time Indian equities & F&O analytics dashboard** that pulls live and historical data from **Angel One SmartAPI**, computes derived analytics (IV, Greeks, PCR, OI buildup), ingests financial news with sentiment scoring, and renders everything in a fast web UI.

Build it as a production-quality local app first (single command to run both backend and frontend), structured so it can later be deployed.

## TECH STACK (use exactly this)

- **Backend:** Python 3.11+, FastAPI, Uvicorn, `smartapi-python` SDK, `SmartWebSocketV2` for live feed, `pyotp`, `py_vollib` / `py_vollib_vectorized` (IV + Greeks), `pandas`, `httpx`, `apscheduler` (scheduled refresh), `vaderSentiment` (default) with optional `transformers`+FinBERT.
- **Frontend:** React + Vite + TypeScript, TailwindCSS, `lightweight-charts` (TradingView) for price/OI charts, `recharts` for analytics, TanStack Query for data fetching, a WebSocket client for live ticks.
- **Storage:** SQLite via SQLAlchemy (schema written so swapping to Postgres is a connection-string change). Use it for: instrument master cache, historical candles cache, news + sentiment, user watchlists, and snapshot logging of OI/IV over the day.
- **Caching/throttle:** in-memory + on-disk cache; a token-bucket rate limiter that respects Angel One's published per-endpoint limits.

Project layout:
```
/backend
  /app
    main.py
    config.py          # loads .env
    /angel             # SmartAPI auth, session, websocket, scrip master
    /services          # options_chain, iv_greeks, oi_analytics, sentiment, market_breadth
    /api               # FastAPI routers
    /models            # SQLAlchemy models
  requirements.txt
/frontend
  (vite react-ts app)
.env.example
README.md
docker-compose.yml     # optional, for later deploy
run.sh                 # boots backend + frontend together
```

## PHASE 1 — ANGEL ONE AUTH & SESSION

Implement the SmartAPI login flow. Angel One requires **API key + client code + MPIN + TOTP**.

- Use `from SmartApi import SmartConnect`.
- Generate TOTP at runtime with `pyotp.TOTP(TOTP_SECRET).now()` — never hardcode a code.
- `obj = SmartConnect(api_key=API_KEY); session = obj.generateSession(CLIENT_CODE, MPIN, totp)`.
- Persist `jwtToken`, `refreshToken`, and `feedToken`. Implement automatic **token refresh** and a re-login path if the session expires (sessions die after market hours / inactivity).
- **Verify the exact method names and the SDK package name against the current Angel One SmartAPI docs before relying on them — the SDK has changed signatures across versions. If a method differs, adapt and tell me.**

**Credentials to ask me for in this phase:** `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_MPIN`, `ANGEL_TOTP_SECRET`. (The TOTP secret is the base32 string from enabling TOTP in the Angel One account — not a one-time code.)

## PHASE 2 — INSTRUMENT MASTER

- On startup, download Angel One's scrip master (the OpenAPI scrip master JSON, default URL: `https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json` — verify it's current). Cache it to SQLite, refresh once daily.
- Build lookup helpers: symbol/name → token, segment (NSE, BSE, NFO, MCX), instrument type (EQ, FUTIDX, OPTIDX, FUTSTK, OPTSTK), strike, expiry, lot size.
- Expose a search endpoint so the frontend can resolve "NIFTY", "BANKNIFTY", "RELIANCE" etc. to tradable tokens.

## PHASE 3 — MARKET DATA (REST)

Wrap these into clean service functions with the rate limiter applied:
- **LTP / OHLC / FULL quote** via the market-data endpoint. FULL mode returns LTP, OHLC, volume traded, and **open interest (`opnInterest`)** — capture all of it.
- **Historical candles** (`getCandleData`) for intraday + daily intervals; cache results.
- Handle the documented per-second / per-minute rate limits with backoff; never hammer the API.

## PHASE 4 — LIVE FEED (WEBSOCKET)

- Use `SmartWebSocketV2` with the `feedToken`.
- Subscribe to **snapquote mode** for watchlist + active option strikes — it streams LTP, best-5 depth, volume, and OI.
- Backend WebSocket relay: FastAPI exposes a `/ws` endpoint that fans out normalized ticks to connected frontend clients (don't expose Angel tokens to the browser).
- Auto-resubscribe on reconnect; gracefully handle market-closed state.

## PHASE 5 — OPTIONS CHAIN

Angel One has **no single "option chain" endpoint** — build it:
1. From the scrip master, filter NFO options for the chosen underlying + expiry → list all strikes (CE & PE).
2. Batch-fetch FULL market data for those tokens to get LTP, volume, and OI per strike.
3. Assemble a chain table: strike | CE (LTP, OI, ΔOI, volume, IV, Greeks) | PE (same). Center on ATM.
4. Subscribe the visible strikes to the live websocket so the chain updates in real time.

## PHASE 6 — IV & GREEKS (COMPUTED)

Angel One does **not** return IV — compute it.
- Index options (NIFTY, BANKNIFTY, FINNIFTY, etc.) are **European** → use Black-Scholes via `py_vollib` / `py_vollib_vectorized`:
  - Inputs: option market price, spot (underlying LTP), strike, time-to-expiry (in years, account for market hours), risk-free rate (make configurable, default ~6.5%).
  - Output: implied volatility, delta, gamma, theta, vega, rho per strike.
- Stock options are American — note this; BS is an acceptable approximation, or use a binomial model if I ask.
- Vectorize across the whole chain for speed.

## PHASE 7 — OI & SENTIMENT ANALYTICS

- **PCR** (Put-Call Ratio) by OI and by volume, per expiry.
- **OI buildup classification** per strike using price-vs-OI change: Long Buildup / Short Buildup / Long Unwinding / Short Covering.
- **Max Pain** calculation for the expiry.
- **Change-in-OI** intraday: snapshot OI to SQLite on a schedule (e.g., every 3–5 min during market hours) so ΔOI and OI trend charts work.
- **Market breadth / sentiment:** India VIX level + change, advance/decline if available, PCR-based sentiment read. Render a simple composite "sentiment gauge."

## PHASE 8 — NEWS SENTIMENT (PLUGGABLE)

Angel One has no news. Build a provider-agnostic news module:
- Default provider: a news API (e.g., NewsAPI) **or** RSS feeds from Indian financial outlets (Moneycontrol, Economic Times, Business Standard). Make the provider swappable via config.
- Map headlines to tickers (simple keyword/entity match against the instrument master).
- Sentiment scoring: default **VADER** (fast, no model download); optional **FinBERT** via `transformers` for finance-tuned scoring (toggle in config).
- Store articles + scores in SQLite; expose per-symbol and overall market news-sentiment feeds.

**Credential to ask me for in this phase:** `NEWS_API_KEY` (only if I choose the API provider over RSS).

## PHASE 9 — BACKEND API SURFACE

Expose clean REST + WS endpoints, e.g.:
- `GET /api/search?q=` — instrument lookup
- `GET /api/quote/{token}` — full quote
- `GET /api/chain?symbol=&expiry=` — assembled option chain with IV/Greeks/OI analytics
- `GET /api/oi/{symbol}` — PCR, max pain, OI buildup, ΔOI history
- `GET /api/sentiment/market` and `GET /api/sentiment/{symbol}` — news + sentiment
- `GET /api/breadth` — VIX, advance/decline, composite gauge
- `WS /ws` — live tick stream
- `GET/POST /api/watchlist` — manage watchlist

## PHASE 10 — FRONTEND

Dark, dense, trading-desk aesthetic. Pages/panels:
- **Overview:** indices strip (NIFTY/BANKNIFTY/SENSEX), India VIX, sentiment gauge, market breadth, top OI movers.
- **Option Chain:** live chain table (CE/PE with OI, ΔOI, volume, IV, Greeks), ATM highlight, expiry + strike-range selectors, PCR/Max-Pain header.
- **Symbol detail:** price chart (lightweight-charts) + OI overlay, IV chart, OI-buildup chart, news+sentiment feed for that symbol.
- **News & Sentiment:** scrollable feed with sentiment tags and a market-wide sentiment trend.
- **Watchlist:** live LTP/change/volume/OI, click-through to detail.

All live panels driven by the `/ws` relay via TanStack Query + a WS client. Show clear "market closed" and "reconnecting" states.

## CONFIG (.env.example)

```
ANGEL_API_KEY=
ANGEL_CLIENT_CODE=
ANGEL_MPIN=
ANGEL_TOTP_SECRET=
NEWS_PROVIDER=rss          # rss | newsapi
NEWS_API_KEY=
SENTIMENT_MODEL=vader      # vader | finbert
RISK_FREE_RATE=0.065
DATABASE_URL=sqlite:///./market.db
```

## CROSS-CUTTING REQUIREMENTS

- **Never log or expose secrets or Angel tokens to the frontend.**
- Token-bucket rate limiting on every Angel endpoint; exponential backoff on errors.
- Graceful handling of **market hours** (IST 09:15–15:30, Mon–Fri) and holidays — pause polling/feed and show closed state outside hours.
- Robust reconnection for the websocket.
- Type hints + docstrings on backend; TypeScript types shared via generated schema if practical.
- A `README.md` with exact setup steps and where to get each credential.
- A `run.sh` that installs deps and starts backend + frontend together.

## BUILD ORDER

Do Phases 1→10 in order. After each phase, run it, show me it working (or the test output), and pause for the credentials that phase needs before continuing. Flag any place where the live Angel One SmartAPI docs differ from this spec and adapt rather than guessing.
