"use strict";

/* Edge AI Predictive Maintenance - single-screen dashboard.
 *
 * State arrives as server-sent events (/events) twice a second, carrying only
 * the readings and health scores that are new since the last message. The
 * page keeps up to 15 minutes of history and draws it with the small canvas
 * LineChart below (no chart library, so it works offline on the Jetson).
 */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const HISTORY = 15 * 60;
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

let state = null;
let samples = [];             // [t, vib, temp, current, speed]
let scores = [];              // [t, health, distance]
let clockOffset = 0;          // server time - local time, seconds
let range = 300;
let hoverT = null;            // crosshair time shared by every chart
const bootAt = performance.now();
const serverNow = () => Date.now() / 1000 + clockOffset;

// ─── Helpers ────────────────────────────────────────────
async function api(path, body) {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify(body ?? {}) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

let toastTimer;
function toast(msg, kind = "") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast show ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

const fmtClock = (t) => new Date(t * 1000).toLocaleTimeString([], { hour12: false });
function fmtNum(v, digits = 1) {
  return v === null || v === undefined || Number.isNaN(v) ? "—" : Number(v).toFixed(digits);
}
function fmtDuration(s) {
  if (s < 60) return "< 1 min";
  if (s < 3600) return `~${Math.round(s / 60)} min`;
  return `~${Math.floor(s / 3600)} h ${String(Math.round(s / 60) % 60).padStart(2, "0")} min`;
}

// ─── Line chart ─────────────────────────────────────────
/* One series per chart (each sensor has its own unit, so no shared axis).
 * Spec: 2px line, hairline solid grid, end dot with a 2px surface ring,
 * value labelled at the line end only, crosshair + tooltip on hover. */
class LineChart {
  constructor(card, opts) {
    this.card = card;
    this.canvas = $("canvas", card);
    this.tip = $(".tooltip", card);
    this.valueEl = $('[data-role="value"]', card);
    this.ctx = this.canvas.getContext("2d");
    Object.assign(this, { digits: 1, fixed: null, band: null, thresholds: [], area: false }, opts);

    this.canvas.addEventListener("pointermove", (e) => {
      const r = this.canvas.getBoundingClientRect();
      const x = e.clientX - r.left;
      if (x < this.L || x > r.width - this.R) { hoverT = null; this.hovered = false; return; }
      hoverT = this.t0 + (x - this.L) / this.xs;
      this.hovered = true;
      this.pointerY = e.clientY - r.top;
    });
    this.canvas.addEventListener("pointerleave", () => { hoverT = null; this.hovered = false; });
  }

  points(from) {
    const out = [];
    for (const row of this.source()) {
      const v = row[this.index];
      if (row[0] >= from && v !== null && !Number.isNaN(v)) out.push([row[0], v]);
    }
    return out;
  }

  draw(now) {
    const dpr = window.devicePixelRatio || 1;
    const W = this.canvas.clientWidth, H = this.canvas.clientHeight;
    if (!W || !H) return;
    if (this.canvas.width !== Math.round(W * dpr) || this.canvas.height !== Math.round(H * dpr)) {
      this.canvas.width = Math.round(W * dpr);
      this.canvas.height = Math.round(H * dpr);
    }
    const ctx = this.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    const L = (this.L = 40), R = (this.R = 58), T = 8, B = 20;
    const t0 = (this.t0 = now - range);
    const xs = (this.xs = (W - L - R) / range);
    const X = (t) => L + (t - t0) * xs;
    const pts = this.points(t0 - 2);
    const band = this.band && this.band();

    // Y domain
    let lo, hi;
    if (this.fixed) [lo, hi] = this.fixed;
    else {
      const vals = pts.map((p) => p[1]);
      if (band) vals.push(band[0], band[1]);
      if (!vals.length) vals.push(0, 1);
      lo = Math.min(...vals); hi = Math.max(...vals);
      const pad = (hi - lo || Math.abs(hi) || 1) * 0.12;
      lo -= pad; hi += pad;
      if (this.zeroFloor) lo = Math.max(0, lo);
    }
    const ticks = niceTicks(lo, hi, 4);
    if (!this.fixed) { lo = Math.min(lo, ticks[0]); hi = Math.max(hi, ticks[ticks.length - 1]); }
    const Y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);

    // Threshold zones (health chart only) sit under everything else.
    for (const th of this.thresholds) {
      if (!th.zone) continue;
      ctx.fillStyle = th.zone;
      const y0 = Y(Math.min(th.value(), hi)), y1 = Y(th.below ? th.below() : lo);
      ctx.fillRect(L, y0, W - L - R, y1 - y0);
    }

    // Grid + y labels
    ctx.lineWidth = 1;
    ctx.strokeStyle = css("--grid");
    ctx.fillStyle = css("--faint");
    ctx.font = "11px ui-monospace, Menlo, Consolas, monospace";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (const v of ticks) {
      if (v < lo - 1e-9 || v > hi + 1e-9) continue;
      const y = Math.round(Y(v)) + 0.5;
      ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(W - R, y); ctx.stroke();
      ctx.fillText(fmtTick(v), L - 8, y);
    }
    // X labels
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    const step = [10, 15, 30, 60, 120, 180, 300].find((s) => range / s <= 5) || 300;
    for (let t = Math.ceil(t0 / step) * step; t <= now; t += step) {
      ctx.fillText(fmtClock(t).slice(range > 120 ? 0 : 3, range > 120 ? 5 : 8), X(t), H - 4);
    }

    // Normal band
    if (band) {
      const y0 = Y(band[1]), y1 = Y(band[0]);
      ctx.fillStyle = "rgba(232, 236, 244, .05)";
      ctx.fillRect(L, y0, W - L - R, y1 - y0);
      ctx.strokeStyle = "rgba(232, 236, 244, .14)";
      ctx.beginPath();
      ctx.moveTo(L, Math.round(y0) + 0.5); ctx.lineTo(W - R, Math.round(y0) + 0.5);
      ctx.moveTo(L, Math.round(y1) + 0.5); ctx.lineTo(W - R, Math.round(y1) + 0.5);
      ctx.stroke();
      ctx.fillStyle = css("--faint");
      ctx.textAlign = "left";
      ctx.textBaseline = "top";
      if (y1 - y0 > 14) ctx.fillText("normal", L + 6, y0 + 3);
    }

    // Threshold lines + labels
    for (const th of this.thresholds) {
      const y = Math.round(Y(th.value())) + 0.5;
      ctx.strokeStyle = th.color;
      ctx.globalAlpha = 0.7;
      ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(W - R, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillStyle = css("--muted");
      ctx.textAlign = "left";
      ctx.textBaseline = "bottom";
      ctx.fillText(`${th.label} ${th.value()}`, L + 6, y - 3);
    }

    if (!pts.length) {
      ctx.fillStyle = css("--faint");
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = "13px Inter, Segoe UI, sans-serif";
      ctx.fillText(this.empty || "Waiting for data…", (L + W - R) / 2, (T + H - B) / 2);
      this.setValue(null);
      this.tip.classList.remove("show");
      return;
    }

    // Line, decimated to min/max per pixel column so spikes survive.
    const path = decimate(pts, X);
    ctx.save();
    ctx.beginPath();
    ctx.rect(L, 0, W - L - R + 1, H);
    ctx.clip();
    if (this.area) {
      ctx.beginPath();
      path.forEach(([x, v], i) => (i ? ctx.lineTo(x, Y(v)) : ctx.moveTo(x, Y(v))));
      ctx.lineTo(path[path.length - 1][0], Y(lo));
      ctx.lineTo(path[0][0], Y(lo));
      ctx.closePath();
      ctx.fillStyle = withAlpha(this.color(), 0.06);
      ctx.fill();
    }
    ctx.beginPath();
    path.forEach(([x, v], i) => (i ? ctx.lineTo(x, Y(v)) : ctx.moveTo(x, Y(v))));
    ctx.strokeStyle = this.color();
    ctx.lineWidth = 2;
    ctx.lineJoin = ctx.lineCap = "round";
    ctx.stroke();
    ctx.restore();

    // End dot + end label
    const last = pts[pts.length - 1];
    dot(ctx, X(last[0]), Y(last[1]), this.color());
    ctx.fillStyle = css("--text");
    ctx.font = "600 12px ui-monospace, Menlo, Consolas, monospace";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(fmtNum(last[1], this.digits), X(last[0]) + 9, Math.min(H - B - 6, Math.max(T + 6, Y(last[1]))));

    // Crosshair (shared across charts) + tooltip (only on the hovered chart)
    if (hoverT !== null && hoverT >= t0 && hoverT <= now) {
      const near = nearest(pts, hoverT);
      const x = Math.round(X(near[0])) + 0.5;
      ctx.strokeStyle = "rgba(232, 236, 244, .35)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, T); ctx.lineTo(x, H - B); ctx.stroke();
      dot(ctx, X(near[0]), Y(near[1]), this.color());
      this.setValue(near[1]);
      if (this.hovered) {
        this.tip.replaceChildren();
        const strong = document.createElement("strong");
        strong.textContent = `${fmtNum(near[1], this.digits)} ${this.unit}`;
        const key = document.createElement("span");
        key.className = "key";
        key.style.background = this.color();
        const label = document.createTextNode(`${this.label} · ${fmtClock(near[0])}`);
        this.tip.append(strong, key, label);
        const tw = this.tip.offsetWidth;
        const left = x + 14 + tw > W ? x - 14 - tw : x + 14;
        this.tip.style.left = `${left}px`;
        this.tip.style.top = `${Math.max(0, Math.min(H - 52, (this.pointerY ?? 20) - 26))}px`;
        this.tip.classList.add("show");
      } else {
        this.tip.classList.remove("show");
      }
    } else {
      this.setValue(last[1]);
      this.tip.classList.remove("show");
    }
  }

  setValue(v) {
    const text = fmtNum(v, this.digits);
    if (this.valueEl.textContent !== text) this.valueEl.textContent = text;
  }
}

function dot(ctx, x, y, color) {
  ctx.beginPath();
  ctx.arc(x, y, 6, 0, Math.PI * 2);
  ctx.fillStyle = css("--panel");          // 2px surface ring
  ctx.fill();
  ctx.beginPath();
  ctx.arc(x, y, 4, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

function decimate(pts, X) {
  const out = [];
  let col = null, min = null, max = null;
  const flush = () => {
    if (!min) return;
    if (min === max) out.push([X(min[0]), min[1]]);
    else if (min[0] < max[0]) out.push([X(min[0]), min[1]], [X(max[0]), max[1]]);
    else out.push([X(max[0]), max[1]], [X(min[0]), min[1]]);
  };
  for (const p of pts) {
    const c = Math.floor(X(p[0]));
    if (c !== col) { flush(); col = c; min = max = p; continue; }
    if (p[1] < min[1]) min = p;
    if (p[1] > max[1]) max = p;
  }
  flush();
  return out;
}

function nearest(pts, t) {
  let lo = 0, hi = pts.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (pts[mid][0] < t) lo = mid; else hi = mid;
  }
  return Math.abs(pts[lo][0] - t) < Math.abs(pts[hi][0] - t) ? pts[lo] : pts[hi];
}

function niceTicks(lo, hi, count) {
  const span = hi - lo || 1;
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const ticks = [];
  for (let v = Math.floor(lo / step) * step; v <= hi + step * 0.5; v += step) ticks.push(+v.toFixed(10));
  return ticks;
}

function fmtTick(v) {
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(v % 1000 ? 2 : 0)}K`;
  return Number.isInteger(v) ? String(v) : v.toFixed(Math.abs(v) < 1 ? 2 : 1);
}

function withAlpha(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

const featureBand = (key) => () => {
  const f = state?.features?.find((x) => x.key === key);
  return f && f.normal && f.normal[0] !== null ? f.normal : null;
};

const charts = [
  new LineChart($('[data-chart="health"]'), {
    label: "Health", unit: "/ 100", digits: 0, fixed: [0, 100], area: true,
    source: () => scores, index: 1, color: () => css("--s-health"),
    empty: "The health index appears once the baseline has been learned",
    thresholds: [
      { label: "Warning", value: () => state?.settings.warn_health ?? 70, color: css("--warning"),
        zone: "rgba(250, 178, 25, .05)", below: () => state?.settings.critical_health ?? 35 },
      { label: "Critical", value: () => state?.settings.critical_health ?? 35, color: css("--critical"),
        zone: "rgba(208, 59, 59, .08)" },
    ],
  }),
  new LineChart($('[data-chart="vib"]'), {
    label: "Vibration", unit: "mm/s", digits: 2, zeroFloor: true,
    source: () => samples, index: 1, color: () => css("--s-vib"), band: featureBand("vib_rms"),
  }),
  new LineChart($('[data-chart="temp"]'), {
    label: "Temperature", unit: "°C", digits: 1,
    source: () => samples, index: 2, color: () => css("--s-temp"), band: featureBand("temp"),
  }),
  new LineChart($('[data-chart="current"]'), {
    label: "Current", unit: "A", digits: 2, zeroFloor: true,
    source: () => samples, index: 3, color: () => css("--s-current"), band: featureBand("current"),
  }),
  new LineChart($('[data-chart="speed"]'), {
    label: "Speed", unit: "rpm", digits: 0,
    source: () => samples, index: 4, color: () => css("--s-speed"), band: featureBand("speed"),
    empty: "No speed sensor reported",
  }),
];

// Clear the shared crosshair whenever the pointer is anywhere but a chart.
document.addEventListener("pointermove", (e) => {
  if (hoverT !== null && !e.target.closest?.(".chart-body")) {
    hoverT = null;
    for (const c of charts) c.hovered = false;
  }
});

// ─── Live state ─────────────────────────────────────────
function connect() {
  const es = new EventSource("/events");
  es.addEventListener("state", (e) => onState(JSON.parse(e.data)));
  es.addEventListener("log", (e) => addLog(JSON.parse(e.data)));
  es.onerror = () => {
    $("#splashSub").textContent = "Reconnecting to the engine…";
    // A reconnect replays the full history, so start clean.
    samples = []; scores = [];
  };
}

function onState(s) {
  if (!state) {
    const wait = Math.max(0, 900 - (performance.now() - bootAt));
    setTimeout(() => document.body.classList.remove("booting"), wait);
  }
  state = s;
  clockOffset = s.server_time - Date.now() / 1000;

  samples.push(...s.samples);
  scores.push(...s.scores);
  const cutoff = s.server_time - HISTORY;
  if (samples.length && samples[0][0] < cutoff) samples = samples.filter((r) => r[0] >= cutoff);
  if (scores.length && scores[0][0] < cutoff) scores = scores.filter((r) => r[0] >= cutoff);

  document.body.classList.toggle("source-serial", s.source === "serial");
  $$("#sourceSwitch button").forEach((b) => b.classList.toggle("active", b.dataset.source === s.source));

  const link = $("#linkPill");
  link.classList.toggle("ok", s.connected && s.running);
  link.classList.toggle("bad", !s.connected || !s.running);
  $("#linkText").textContent = !s.running ? "stopped"
    : s.source === "simulator" ? "simulator" : s.connected ? (s.port || "").replace("/dev/", "") : "no board";
  $("#modelText").textContent = s.learning ? `Learning ${Math.round(s.learning.progress * 100)}%`
    : s.model.ready ? "Model ready" : "No model";

  updateHealth(s);
  updateRul(s);
  updateDiagnosis(s);
  updateSim(s);
  if (document.body.classList.contains("view-table")) renderTable();
}

const STATUS = {
  starting: ["Starting", "Waiting for data"],
  learning: ["Learning", "Building the normal baseline"],
  healthy:  ["Healthy", "Operating normally"],
  warning:  ["Degrading", "Plan maintenance soon"],
  critical: ["Critical", "Stop for maintenance"],
  offline:  ["No data", "Sensor board not sending"],
  stopped:  ["Stopped", "Monitoring is off"],
};

const GAUGE_LEN = Math.PI * 90;
let shownHealth = 0;

function updateHealth(s) {
  const card = $("#healthCard");
  card.dataset.status = s.status;
  const [label, sub] = STATUS[s.status] || STATUS.starting;
  $("#statusText").textContent = label;
  $("#healthSub").textContent = sub;
  if (s.learning) {
    const pct = Math.round(s.learning.progress * 100);
    $("#learnPct").textContent = `${pct}%`;
    $("#learnFill").style.width = `${pct}%`;
    $("#learnLeft").textContent = `${Math.ceil(s.learning.remaining)} s left.`;
  }
  placeTick($("#tickWarn"), s.settings.warn_health);
  placeTick($("#tickCrit"), s.settings.critical_health);
}

function placeTick(el, v) {
  const a = Math.PI * (1 - v / 100);
  const c = Math.cos(a), sn = Math.sin(a);
  el.setAttribute("x1", 110 + c * 80); el.setAttribute("y1", 112 - sn * 80);
  el.setAttribute("x2", 110 + c * 100); el.setAttribute("y2", 112 - sn * 100);
}

function updateRul(s) {
  const value = $("#rulValue"), trend = $("#rulTrend");
  trend.classList.remove("down");
  if (!s.model.ready || s.learning) {
    value.textContent = "Learning…";
    trend.textContent = "Available once the baseline is learned";
  } else if (s.health === null) {
    value.textContent = "—";
    trend.textContent = "Waiting for data";
  } else if (s.rul_seconds === 0) {
    value.textContent = "Now";
    trend.textContent = "Health is at or below the critical level";
    trend.classList.add("down");
  } else if (s.rul_seconds === null) {
    value.textContent = "No issue";
    trend.textContent = s.trend_per_min === null ? "Collecting trend data"
      : `Health steady (${s.trend_per_min >= 0 ? "+" : "−"}${Math.abs(s.trend_per_min).toFixed(1)} pts/min)`;
  } else {
    value.textContent = fmtDuration(s.rul_seconds);
    trend.textContent = `▼ ${Math.abs(s.trend_per_min).toFixed(1)} pts/min over the last ${Math.round(s.settings.trend_seconds / 60)} min`;
    trend.classList.add("down");
  }
}

function updateDiagnosis(s) {
  const d = s.diagnosis;
  $("#diagCard").classList.toggle("fault", !!d);
  $("#diagName").textContent = d ? d.name : s.model.ready ? "No fault detected" : "Learning baseline";
  $("#diagAction").textContent = d ? d.action
    : s.model.ready ? "All features are inside their normal range." : "Diagnosis starts once the model is ready.";
  $("#diagConf").textContent = d ? `${Math.round(d.confidence * 100)}% of the deviation` : "";

  const box = $("#contrib");
  const feats = (s.features || []).filter((f) => f.z !== undefined);
  if (box.children.length !== feats.length) {
    box.replaceChildren(...feats.map((f) => {
      const row = document.createElement("div");
      row.className = "contrib-row";
      const name = document.createElement("span");
      name.textContent = f.label;
      const track = document.createElement("div");
      track.className = "bar-track";
      track.innerHTML = '<span class="mark3" style="left:30%"></span><span class="bar"></span>';
      const val = document.createElement("span");
      val.className = "val";
      row.append(name, track, val);
      return row;
    }));
  }
  const zs = feats.map((f) => Math.abs(f.z ?? 0));
  const top = zs.indexOf(Math.max(...zs));
  feats.forEach((f, i) => {
    const row = box.children[i];
    const z = zs[i];
    row.classList.toggle("top", i === top && z >= 3);
    $(".bar", row).style.width = `${Math.min(z, 10) * 10}%`;
    $(".val", row).textContent = `${z.toFixed(1)}σ`;
  });
}

function updateSim(s) {
  $$(".fault").forEach((b) => b.classList.toggle("on", s.sim.active.includes(b.dataset.fault)));
  for (const row of $$(".wear-row")) {
    const w = s.sim.wear[row.dataset.wear] || 0;
    $(".meter span", row).style.width = `${(w * 100).toFixed(0)}%`;
    $(".mono", row).textContent = `${Math.round(w * 100)}%`;
  }
  const badge = $("#simBadge");
  const map = { healthy: ["RUNNING", ""], warning: ["DEGRADING", "warning"], critical: ["CRITICAL", "critical"],
                learning: ["LEARNING", ""], offline: ["NO DATA", "warning"], stopped: ["STOPPED", "warning"] };
  const [text, cls] = map[s.status] || ["RUNNING", ""];
  badge.textContent = text;
  badge.className = `badge ${cls}`;
}

// ─── Table view (every charted value, without hovering) ─
function renderTable() {
  const body = $("#tableBody");
  const rows = samples.slice(-60).reverse();
  let si = scores.length - 1;
  body.replaceChildren(...rows.map((r) => {
    while (si > 0 && scores[si][0] > r[0]) si--;
    const h = scores[si] && Math.abs(scores[si][0] - r[0]) < 1 ? scores[si][1] : null;
    const tr = document.createElement("tr");
    for (const text of [fmtClock(r[0]), fmtNum(r[1], 2), fmtNum(r[2], 1), fmtNum(r[3], 2),
                        fmtNum(r[4], 0), h === null ? "—" : fmtNum(h, 0)]) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.append(td);
    }
    return tr;
  }));
}

// ─── Event log ──────────────────────────────────────────
const seenLogs = new Set();
function addLog(ev) {
  const key = `${ev.id}:${ev.t}`;
  if (seenLogs.has(key)) return;
  seenLogs.add(key);
  const list = $("#log");
  list.querySelector(".log-empty")?.remove();
  const li = document.createElement("li");
  const time = document.createElement("time");
  time.textContent = fmtClock(ev.t);
  const dotEl = document.createElement("span");
  dotEl.className = `lv lv-${ev.level}`;
  const msg = document.createElement("span");
  msg.textContent = ev.msg;
  li.append(time, dotEl, msg);
  list.prepend(li);
  while (list.children.length > 120) list.lastChild.remove();
}
function emptyLog() { $("#log").innerHTML = '<li class="log-empty">No events yet</li>'; }
$("#clearLogBtn").addEventListener("click", emptyLog);

// ─── Controls ───────────────────────────────────────────
function segmented(sel, attr, onPick, initial) {
  const buttons = $$(`${sel} button`);
  const pick = (val) => buttons.forEach((b) => b.classList.toggle("active", b.dataset[attr] === String(val)));
  buttons.forEach((b) => b.addEventListener("click", () => { pick(b.dataset[attr]); onPick(b.dataset[attr]); }));
  pick(initial);
}

let savedRange = 300;
try { savedRange = Number(localStorage.getItem("pm-range")) || 300; } catch (_) {}
range = savedRange;
segmented("#rangeSwitch", "range", (v) => {
  range = Number(v);
  try { localStorage.setItem("pm-range", v); } catch (_) {}
}, range);
segmented("#viewSwitch", "view", (v) => {
  document.body.classList.toggle("view-table", v === "table");
  if (v === "table") renderTable();
}, "charts");

$$("#sourceSwitch button").forEach((b) => b.addEventListener("click", async () => {
  if (state && b.dataset.source === state.source) return;
  try {
    await api("/api/settings", { source: b.dataset.source });
    toast(b.dataset.source === "serial" ? "Reading the sensor board" : "Simulator on");
  } catch (err) { toast(err.message, "error"); }
}));

$$("[data-fault]").forEach((b) => b.addEventListener("click", async () => {
  try {
    await api("/api/sim", { fault: b.dataset.fault });
    toast(b.dataset.fault === "repair" ? "Machine repaired" : `${b.textContent.trim()} fault injected`);
  } catch (err) { toast(err.message, "error"); }
}));

const learnBtn = $("#learnBtn");
learnBtn.addEventListener("click", async () => {
  // Learning on a faulty machine would teach the model that the fault is normal.
  if (!learnBtn.dataset.armed) {
    learnBtn.dataset.armed = "1";
    learnBtn.lastChild.textContent = " Tap again: machine is healthy";
    learnBtn._t = setTimeout(() => { delete learnBtn.dataset.armed; learnBtn.lastChild.textContent = " Re-learn baseline"; }, 3500);
    return;
  }
  clearTimeout(learnBtn._t);
  delete learnBtn.dataset.armed;
  learnBtn.lastChild.textContent = " Re-learn baseline";
  try { await api("/api/learn"); toast("Learning a new baseline"); } catch (err) { toast(err.message, "error"); }
});

$("#fullscreenBtn").addEventListener("click", () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen?.();
});
setInterval(() => { $("#clock").textContent = new Date().toLocaleTimeString([], { hour12: false }); }, 1000);

// ─── Settings drawer ────────────────────────────────────
const form = $("#settingsForm");
async function openDrawer() {
  if (!state) return;
  const s = state.settings;
  let ports = [];
  try { ports = (await (await fetch("/api/serial/ports")).json()).ports; } catch (_) {}
  const sel = $("#portSelect");
  sel.replaceChildren();
  for (const p of ["auto", ...new Set([...ports, ...(s.serial_port !== "auto" ? [s.serial_port] : [])])]) {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p === "auto" ? "Auto-detect" : p + (ports.includes(p) ? "" : " (not found)");
    sel.append(opt);
  }
  for (const el of form.elements) if (el.name && el.name in s) el.value = String(s[el.name]);
  syncOutputs();
  document.body.classList.add("drawer-open");
}
const closeDrawer = () => document.body.classList.remove("drawer-open");
function syncOutputs() {
  $("#warnOut").textContent = form.warn_health.value;
  $("#critOut").textContent = form.critical_health.value;
}
form.addEventListener("input", syncOutputs);
form.addEventListener("submit", (e) => e.preventDefault());
$("#settingsBtn").addEventListener("click", openDrawer);
$("#closeDrawerBtn").addEventListener("click", closeDrawer);
$("#cancelSettingsBtn").addEventListener("click", closeDrawer);
$("#drawerBackdrop").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
$("#saveSettingsBtn").addEventListener("click", async () => {
  const data = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    data[el.name] = el.name === "serial_port" ? el.value : Number(el.value);
  }
  if (data.critical_health >= data.warn_health) { toast("Critical level must be below the warning level", "error"); return; }
  try { await api("/api/settings", data); closeDrawer(); toast("Settings saved"); }
  catch (err) { toast(err.message, "error"); }
});

// ─── Animation: gauge, motor, charts ────────────────────
let lastFrame = performance.now(), lastCharts = 0, fanAngle = 0;
function animate(ts) {
  const dt = Math.min(0.1, (ts - lastFrame) / 1000);
  lastFrame = ts;

  // Gauge eases toward the latest health value
  const target = state && state.health !== null && !state.learning ? state.health : 0;
  shownHealth += (target - shownHealth) * (1 - Math.exp(-dt * 4));
  const fill = $("#gaugeFill");
  fill.style.strokeDasharray = `${GAUGE_LEN}`;
  fill.style.strokeDashoffset = `${GAUGE_LEN * (1 - shownHealth / 100)}`;
  $("#healthValue").textContent = state && state.health !== null && !state.learning ? Math.round(shownHealth) : "—";

  // Motor: fan speed from rpm, shake from vibration, glow from temperature, bolt from current
  const last = samples[samples.length - 1];
  if (last && state?.running) {
    const [, vib, temp, cur, spd] = last;
    fanAngle += ((Number.isFinite(spd) ? spd : 1450) / 1480) * 900 * dt;
    $("#fan").setAttribute("transform", `rotate(${fanAngle % 360})`);
    $("#coupling").setAttribute("transform", `rotate(${(fanAngle * 0.5) % 360})`);
    $("#impeller").setAttribute("transform", `rotate(${(fanAngle * 0.7) % 360})`);
    const amp = Math.max(0, Math.min(1, (vib - 3) / 6)) * 3.2;
    $("#shaker").setAttribute("transform", `translate(${(Math.random() - 0.5) * amp} ${(Math.random() - 0.5) * amp})`);
    $("#heat").setAttribute("opacity", Math.max(0, Math.min(0.9, (temp - 54) / 28)).toFixed(2));
    const load = Math.max(0, Math.min(1, (cur - 12.5) / 5));
    $("#bolt").setAttribute("opacity", (0.25 + load * 0.75 * (0.6 + 0.4 * Math.random())).toFixed(2));
  }

  if (ts - lastCharts > 66) {             // charts at ~15 fps is plenty
    lastCharts = ts;
    if (!document.body.classList.contains("view-table")) {
      const now = serverNow();
      for (const c of charts) c.draw(now);
    }
  }
  requestAnimationFrame(animate);
}

emptyLog();
connect();
requestAnimationFrame(animate);
