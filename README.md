Lamprey — Meme Stock Momentum Scanner
> Built by Matt Mattheisen at Shomer Analytics
Lamprey generates long and short composite signals for meme stocks by combining retail sentiment, volume z-scores, candlestick patterns, and news catalysts — then gates every trade through a regime classifier adapted from the Shomer Analytics six-gate framework.
---
Stack
Layer	Technology
Backend	FastAPI + APScheduler
Frontend	Static HTML / CSS / JS (terminal aesthetic)
Deploy	Render
OHLCV	Tiingo (live)
Sentiment	Reddit/PRAW (stubbed)
Options flow	Unusual Whales (stubbed)
News	NewsAPI (stubbed)
---
Signal Weights
Signal	Weight	Notes
Sentiment	35%	VADER compound + mention velocity boost
Volume z-score	30%	vs 20-day rolling avg, capped at z=4
Candlestick	20%	pandas-ta `cdl_pattern`, normalised 0–1
News catalyst	15%	NLP headline score 0–1
Long threshold: 0.65
Short threshold: 0.75 (higher due to unlimited upside risk on meme shorts)
---
Regime → Strategy Map
Regime	Long Edge	Short Edge
Equity Trend	Strong	Weak
Rate Shock	Reduced	Strong
Vol Expansion	Suspend	Caution
Crash / Panic	Flat	Flat
Low Vol/Grind	Selective	News-gated
---
Quick Start
```bash
# 1. Clone and install
git clone <repo>
cd lamprey
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Add TIINGO_API_KEY at minimum

# 3. Run
uvicorn app.main:app --reload

# 4. Open browser
open http://localhost:8000
```
---
API Endpoints
Method	Path	Description
GET	`/api/scan`	Trigger a fresh scan
GET	`/api/latest`	Return last cached result
GET	`/api/watchlist`	Return current watchlist config
GET	`/api/scan?tickers=GME,AMC`	Scan override ticker list
---
Live vs Stubbed Data Sources
Source	Status	Env var
Tiingo OHLCV	LIVE	`TIINGO_API_KEY`
Reddit (PRAW)	STUBBED	`REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET`
Unusual Whales	STUBBED	`UNUSUAL_WHALES_API_KEY`
NewsAPI	STUBBED	`NEWSAPI_KEY`
Stubs return neutral dicts (zeros, defaults). They never raise exceptions. When a key is added to `.env`, the live fetch activates automatically.
---
Short-Specific Gates
All three must pass for a short signal:
Borrow available — status ≠ `"unavailable"`
Borrow rate < `MAX_BORROW_RATE_PCT` (default 10%)
Short interest < `MAX_SHORT_INTEREST_PCT` (default 30%)
`LOCATE` is flagged when borrow is `"tight"` but rate and SI are within limits.
---
Tests
```bash
pip install pytest pytest-asyncio
pytest
```
Tests are smoke-only — no API calls required.
---
Module Map
```
app/
  main.py               FastAPI entry + APScheduler lifespan
  config.py             Pydantic settings from .env
  state.py              In-process latest scan cache
  models/signals.py     SignalComponents · ShortGates · MacroGates · TickerResult · ScanResult
  services/
    data_feed.py        All external fetches (live + stubbed)
    signal_engine.py    compute_signals() · long_composite() · short_composite()
    regime_gate.py      get_macro_gates() · get_meme_overlay()
    short_gates.py      evaluate_short_gates() · short_gate_pass()
    scanner.py          run_scan() — orchestrator, returns ScanResult
  routers/scan.py       GET /api/scan · /api/latest · /api/watchlist
static/
  index.html · css/main.css · js/app.js
tests/
  test_signal_engine.py  Smoke tests, no API calls required
```
---
Lamprey is for research and educational purposes only. Not financial advice.
