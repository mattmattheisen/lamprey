/* app.js — Lamprey frontend */
"use strict";

// ── State ────────────────────────────────────────────────────────────────────
let scanning = false;

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $lastScan    = document.getElementById("last-scan-time");
const $duration    = document.getElementById("scan-duration");
const $tickerCount = document.getElementById("ticker-count");
const $body        = document.getElementById("results-body");
const $btnScan     = document.getElementById("btn-scan");
const $statusDot   = document.getElementById("status-dot");
const $statusText  = document.getElementById("status-text");
const $regimeBadge = document.getElementById("regime-badge");
const $clock       = document.getElementById("clock");
const $footerWl    = document.getElementById("footer-watchlist");

// Macro gate refs
const $gateVix      = document.getElementById("gate-vix");
const $gateMove     = document.getElementById("gate-move");
const $gateCor1m    = document.getElementById("gate-cor1m");
const $gateVixTrend = document.getElementById("gate-vix-trend");
const $gateContango = document.getElementById("gate-contango");
const $gateBreadth  = document.getElementById("gate-breadth");
const $edgeLong     = document.getElementById("edge-long");
const $edgeShort    = document.getElementById("edge-short");

// ── Clock ────────────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const et = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).format(now);
  $clock.textContent = `${et} ET`;
}
setInterval(updateClock, 1000);
updateClock();

// ── Status helpers ───────────────────────────────────────────────────────────
function setStatus(state, text) {
  $statusDot.className = "status-dot" + (state ? ` ${state}` : "");
  $statusText.textContent = text;
}

// ── Scan ─────────────────────────────────────────────────────────────────────
async function runScan() {
  if (scanning) return;
  scanning = true;
  $btnScan.disabled = true;
  setStatus("active", "SCANNING…");
  $body.innerHTML = `<div class="loading-row">▌ running scan…</div>`;

  try {
    const res = await fetch("/api/scan");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderResult(data);
    setStatus("active", "LIVE");
    setTimeout(() => setStatus("", "IDLE"), 3000);
  } catch (err) {
    console.error(err);
    setStatus("error", "ERROR");
    $body.innerHTML = `<div class="empty-state">Scan failed: ${err.message}</div>`;
  } finally {
    scanning = false;
    $btnScan.disabled = false;
  }
}

// ── Fetch latest on load ─────────────────────────────────────────────────────
async function fetchLatest() {
  try {
    const res = await fetch("/api/latest");
    if (res.status === 404) return;
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderResult(data);
    setStatus("", "CACHED");
  } catch (_) { /* silent */ }
}

// ── Fetch watchlist for footer ───────────────────────────────────────────────
async function fetchWatchlist() {
  try {
    const res = await fetch("/api/watchlist");
    const data = await res.json();
    $footerWl.textContent = "WATCHLIST: " + data.watchlist.join(" · ");
  } catch (_) {}
}

// ── Render ───────────────────────────────────────────────────────────────────
function renderResult(data) {
  const ts = new Date(data.scanned_at);
  $lastScan.textContent = ts.toLocaleTimeString("en-US", {
    timeZone: "America/New_York", hour12: false,
  }) + " ET";
  $duration.textContent  = `${data.duration_ms.toFixed(0)} ms`;
  $tickerCount.textContent = data.tickers.length;

  const m = data.macro;
  $regimeBadge.textContent = `REGIME: ${m.regime.replace(/_/g, " ").toUpperCase()}`;

  renderGate($gateVix,      "VIX",      m.vix_ok,       m.vix_ok ? "OK" : "RISK");
  renderGate($gateMove,     "MOVE",     m.move_ok,      "STUB");
  renderGate($gateCor1m,    "COR1M",    m.cor1m_ok,     "STUB");
  renderGate($gateVixTrend, "VIX TREND", m.vix_trend_ok, "STUB");
  renderGate($gateContango, "CONTANGO", m.contango_ok,  "STUB");
  renderGate($gateBreadth,  "BREADTH",  m.breadth_ok,   "STUB");

  renderEdge($edgeLong,  "LONG EDGE",  m.long_edge);
  renderEdge($edgeShort, "SHORT EDGE", m.short_edge);

  const order = { LONG: 0, SHORT: 1, WATCH: 2, FLAT: 3 };
  const sorted = [...data.tickers].sort((a, b) => {
    const od = order[a.signal] - order[b.signal];
    if (od !== 0) return od;
    return b.long_components.composite - a.long_components.composite;
  });

  $body.innerHTML = sorted.map(renderRow).join("");
}

function renderGate(el, label, ok, valText) {
  el.className = "macro-gate " + (ok ? "ok" : "fail");
  el.innerHTML = `${label} <span>${valText}</span>`;
}

function renderEdge(el, label, edge) {
  const cls = edge.replace(/_/g, "-").replace(" ", "-");
  el.className = "macro-edge";
  el.innerHTML = `${label}: <span class="${cls}">${edge.replace(/_/g, " ").toUpperCase()}</span>`;
}

function renderRow(t) {
  const sig = t.signal;
  const lc  = t.long_components;
  const sc  = t.short_components;
  const sg  = t.short_gates;

  const sigBadge = `<span class="sig sig-${sig.toLowerCase()}">${sig}</span>`;

  const borrowClass = sg.borrow_available
    ? (sg.locate_required ? "borrow-tight" : "borrow-ok")
    : "borrow-unavail";
  const borrowText = sg.borrow_available
    ? (sg.locate_required ? "LOCATE" : "AVAIL")
    : "UNAVAIL";

  return `
<div class="result-row">
  <div class="col-ticker">${escHtml(t.ticker)}</div>
  <div class="col-signal">${sigBadge}</div>
  <div class="col-composite">${compositeBar(lc.composite, "long")}</div>
  <div class="col-composite">${compositeBar(sc.composite, "short")}</div>
  <div class="col-sentiment">${fmt(lc.sentiment)}</div>
  <div class="col-volume">${fmt(lc.volume_zscore)}</div>
  <div class="col-candle">${fmt(lc.candlestick)}</div>
  <div class="col-news">${fmt(lc.news_catalyst)}</div>
  <div class="col-borrow"><span class="${borrowClass}">${borrowText}</span></div>
  <div class="col-si">${fmt(sg.short_interest_pct)}%</div>
  <div class="col-notes">${escHtml(t.notes)}</div>
</div>`;
}

function compositeBar(val, type) {
  const pct = Math.round(val * 100);
  return `<div class="comp-bar ${type}"><div class="comp-fill" style="width:${pct}%"></div><span>${val.toFixed(3)}</span></div>`;
}

function fmt(v) {
  return typeof v === "number" ? v.toFixed(3) : "—";
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ── Init ─────────────────────────────────────────────────────────────────────
$btnScan.addEventListener("click", runScan);
fetchLatest();
fetchWatchlist();
