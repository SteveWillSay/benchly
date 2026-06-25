/* Benchly — frontend application logic. */
"use strict";

/* ================= API bridge ================= */
const api = new Proxy({}, {
  get: (_t, method) => (...args) =>
    apiReady.then(() => window.pywebview.api[method](...args)),
});
const apiReady = new Promise(resolve => {
  if (window.pywebview && window.pywebview.api) resolve();
  else window.addEventListener("pywebviewready", () => resolve());
});

/* ================= helpers ================= */
const $ = sel => document.querySelector(sel);
const $$ = sel => [...document.querySelectorAll(sel)];

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
const ico = (name, cls = "ic") => `<svg class="${cls}"><use href="#i-${name}"/></svg>`;

function fmtBytes(n, dp = 1) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0; n = Number(n);
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n >= 100 || i === 0 ? 0 : dp)} ${units[i]}`;
}
const fmtRate = n => n === undefined ? "—" : fmtBytes(n) + "/s";
function fmtDur(secs) {
  const d = Math.floor(secs / 86400), h = Math.floor(secs % 86400 / 3600), m = Math.floor(secs % 3600 / 60);
  return d > 0 ? `${d}d ${h}h ${m}m` : h > 0 ? `${h}h ${m}m` : `${m}m`;
}
function toast(msg, kind = "info", ms = 3800) {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<span class="t-dot"></span><span>${esc(msg)}</span>`;
  $("#toasts").appendChild(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 180); }, ms);
}
function confirmModal(title, body, verb = "Confirm", details = null) {
  if ($("#modal-veil").classList.contains("open")) return Promise.resolve(false);
  return new Promise(resolve => {
    $("#modalTitle").textContent = title;
    $("#modalBody").textContent = body;
    $("#modalOk").textContent = verb;
    const det = $("#modalDetails");
    if (details) { det.textContent = details; det.style.display = ""; }
    else det.style.display = "none";
    const veil = $("#modal-veil");
    veil.classList.add("open");
    const done = val => { veil.classList.remove("open"); resolve(val); };
    $("#modalOk").onclick = () => done(true);
    $("#modalCancel").onclick = () => done(false);
    veil.onclick = e => { if (e.target === veil) done(false); };
  });
}
const pill = (status, text) => `<span class="pill ${status}">${esc(text)}</span>`;
const emptyState = (icon, title, hint = "") => `
  <div class="empty">${ico(icon)}<div>${esc(title)}</div>${hint ? `<div class="hint">${esc(hint)}</div>` : ""}</div>`;

/* click-to-copy for identifiers */
document.addEventListener("click", e => {
  const el = e.target.closest(".copy");
  if (!el || window.getSelection().toString()) return;
  navigator.clipboard.writeText(el.textContent.trim()).then(() =>
    toast(`Copied "${el.textContent.trim().slice(0, 50)}"`, "info", 1800));
});

/* ================= navigation ================= */
const loadedPages = new Set(["dashboard"]);
let currentPage = "dashboard";
function showPage(name) {
  if (!$(`#page-${name}`)) return;
  currentPage = name;
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.page === name));
  $$(".page").forEach(p => p.classList.toggle("active", p.id === `page-${name}`));
  if (!loadedPages.has(name)) {
    loadedPages.add(name);
    // A Map (not a plain object) so a page name can only ever resolve to one of these
    // known loaders — never an inherited prop like "constructor" or "hasOwnProperty".
    const loaders = new Map([
      ["system", loadSystem], ["storage", loadStorage], ["network", loadNetwork],
      ["software", loadSoftware], ["health", loadHealth], ["events", loadEvents],
      ["devices", loadDevices], ["toolbox", loadToolbox], ["security", loadSecurity],
      ["fleet", loadFleet], ["fixit", loadFixit], ["cleanup", loadCleanup],
      ["workplace", loadWorkplace],
    ]);
    const loader = loaders.get(name);
    if (typeof loader === "function") Promise.resolve(loader()).then(() => labelInputs()).catch(err => {
      loadedPages.delete(name);   // allow retry by re-navigating
      toast(`Failed to load ${name}: ${err}`, "bad", 6000);
    });
  }
  if (name === "processes") startProcLoop(); else stopProcLoop();
}
$$(".nav-item").forEach(b => b.addEventListener("click", () => showPage(b.dataset.page)));

/* a11y: give every text input an accessible name from its placeholder when it lacks one,
   so screen readers announce a real label (placeholder alone isn't a reliable name). */
function labelInputs(root = document) {
  root.querySelectorAll("input[placeholder]:not([aria-label]):not([aria-labelledby])")
    .forEach(i => i.setAttribute("aria-label", i.placeholder));
}
labelInputs();

const PAGES = ["dashboard", "system", "storage", "network", "processes", "software",
               "devices", "health", "events", "toolbox", "security", "fleet", "fixit", "helper", "cleanup", "workplace"];
document.addEventListener("keydown", e => {
  if (e.key === "k" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); openPalette(); return; }
  if (e.key === "Escape" && e.target.tagName === "INPUT") {
    e.target.value = ""; e.target.dispatchEvent(new Event("input")); return;
  }
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  if ($("#modal-veil").classList.contains("open") || $("#palette-veil").classList.contains("open")) return;
  if (e.key === "/") {
    const search = $(`#page-${currentPage} input.search, #page-${currentPage} input.input`);
    if (search) { e.preventDefault(); search.focus(); }
    return;
  }
  if (e.key === "0") { showPage("toolbox"); return; }
  const idx = parseInt(e.key, 10) - 1;
  if (idx >= 0 && idx < 9) showPage(PAGES[idx]);
});
$("#dashAuditLink").onclick = () => showPage("health");
$("#dashProcLink").onclick = () => showPage("processes");

/* ================= theme & appearance ================= */
const BG_PRESETS = [
  { name: "Indigo", c: ["#6a3df0", "#2e1c66", "#29184f"] },
  { name: "Ocean", c: ["#0a84ff", "#1b3a6e", "#0a1f3a"] },
  { name: "Sunset", c: ["#ff6f61", "#b5277d", "#3a1b5e"] },
  { name: "Forest", c: ["#1aa64b", "#0f5e3a", "#0a2e22"] },
  { name: "Rose", c: ["#ff5a8a", "#a83a7a", "#3a1b3e"] },
  { name: "Slate", c: ["#3a4a6e", "#222a40", "#14161f"] },
];
const hexRgb = h => {
  const n = parseInt(h.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const mixHex = (a, b, t) => {
  const [r1, g1, b1] = hexRgb(a), [r2, g2, b2] = hexRgb(b);
  const m = (x, y) => Math.round(x + (y - x) * t);
  return `#${[m(r1, r2), m(g1, g2), m(b1, b2)].map(v => v.toString(16).padStart(2, "0")).join("")}`;
};
function applyTheme(name) {
  // "icloud" kept as a back-compat alias for the renamed Frosted Glass theme
  if (name === "frost" || name === "icloud") document.documentElement.dataset.theme = "frost";
  else delete document.documentElement.dataset.theme;
}
function applyBackground(c) {
  const root = document.documentElement.style;
  root.setProperty("--ic-bg1", c[0]);
  root.setProperty("--ic-bg2", c[1]);
  root.setProperty("--ic-bg3", c[2]);
  root.setProperty("--ic-glow", hexRgb(c[0]).join(", "));
}
// Synchronous launch-flag theme to avoid a flash (#…,frost).
if (location.hash.includes("frost") || location.hash.includes("icloud")) applyTheme("frost");

function renderSwatches(selected) {
  $("#bgSwatches").innerHTML = BG_PRESETS.map((p, i) =>
    `<button class="swatch-btn ${selected === i ? "sel" : ""}" data-bg="${i}" title="${p.name}"
       style="background:linear-gradient(160deg, ${p.c[0]}, ${p.c[2]})"></button>`).join("");
}
function syncAppearanceUI() {
  const theme = document.documentElement.dataset.theme === "frost" ? "frost" : "graphite";
  $$("#themeSeg button").forEach(b => b.classList.toggle("on", b.dataset.themeChoice === theme));
  $("#bgPicker").style.display = theme === "frost" ? "" : "none";
}
$("#btnTheme").onclick = () => {
  const pop = $("#appearance-pop");
  if (pop.hidden) { syncAppearanceUI(); renderSwatches(loadedBgIndex); }
  pop.hidden = !pop.hidden;
};
document.addEventListener("click", e => {
  if (!$("#appearance-pop").hidden && !e.target.closest("#appearance-pop") && !e.target.closest("#btnTheme"))
    $("#appearance-pop").hidden = true;
});
$$("#themeSeg button").forEach(b => b.addEventListener("click", async () => {
  const next = b.dataset.themeChoice;
  applyTheme(next);
  syncAppearanceUI();
  await api.set_setting("theme", next);
}));
let loadedBgIndex = 0;
$("#bgSwatches").addEventListener("click", async e => {
  const b = e.target.closest("[data-bg]");
  if (!b) return;
  const i = +b.dataset.bg;
  loadedBgIndex = i;
  applyBackground(BG_PRESETS[i].c);
  renderSwatches(i);
  await api.set_setting("frost_bg", BG_PRESETS[i].c);
});
$("#bgApplyCustom").onclick = async () => {
  const c1 = $("#bgC1").value, c2 = $("#bgC2").value;
  const c = [c1, mixHex(c1, c2, 0.55), c2];
  loadedBgIndex = -1;
  applyBackground(c);
  renderSwatches(-1);
  await api.set_setting("frost_bg", c);
};

/* ================= boot ================= */
let isAdmin = false;
async function boot() {
  if (!location.hash.includes("frost") && !location.hash.includes("icloud")) {   // honour the saved choice
    try { applyTheme((await api.get_setting("theme")) || "graphite"); } catch { /* default */ }
  }
  try {
    const savedBg = (await api.get_setting("frost_bg")) || (await api.get_setting("icloud_bg"));
    if (Array.isArray(savedBg) && savedBg.length === 3) {
      applyBackground(savedBg);
      loadedBgIndex = BG_PRESETS.findIndex(p => p.c[0] === savedBg[0] && p.c[2] === savedBg[2]);
      $("#bgC1").value = savedBg[0]; $("#bgC2").value = savedBg[2];
    }
  } catch { /* default gradient */ }
  const info = await api.app_info();
  isAdmin = info.is_admin;
  const ver = $("#appVersion");
  ver.textContent = `v${info.version}`;
  ver.classList.add("clickable");
  ver.title = "What's new";
  ver.onclick = openChangelog;
  api.get_setting("last_seen_version").then(seen => {
    if (seen !== CHANGELOG[0].v) ver.insertAdjacentHTML("afterend", `<span class="ver-dot" id="verDot" title="New in this version"></span>`);
  }).catch(() => {});
  $("#tbHost").textContent = info.hostname;
  $("#tbSub").textContent = info.os_quick;
  const priv = $("#tbPriv");
  priv.textContent = isAdmin ? "Elevated" : "Standard";
  priv.classList.add(isAdmin ? "ok" : "warn");
  if (!isAdmin) {
    const btn = $("#btnElevate");
    btn.style.display = "";
    btn.onclick = async () => {
      const r = await api.relaunch_as_admin(currentPage);
      if (!r.ok) toast(r.error, "bad");
    };
  }
  startMetricsLoop();
  loadDashboardStatic();
  setInterval(() => { $("#footClock").textContent = new Date().toLocaleTimeString(); }, 1000);
}

/* Self-chaining poll: the next tick is scheduled only AFTER the current one
   settles, so a slow bridge call can never let ticks overlap and pile up.
   Skips work while the window is hidden. `#turbo` compresses every interval
   20× for soak-testing (90 s ≈ 30 min of normal cadence). */
const TURBO = location.hash.includes("turbo") ? 20 : 1;
function pollLoop(ms, fn) {
  const delay = Math.max(20, Math.round(ms / TURBO));
  let stopped = false;
  const tick = async () => {
    if (stopped) return;
    if (!document.hidden) {
      try { await fn(); } catch (e) { console.error("pollLoop", e); }
    }
    if (!stopped) setTimeout(tick, delay);
  };
  tick();   // first run immediately, then self-chain
  return () => { stopped = true; };
}
/** Write innerHTML only when the content actually changed. */
function setHTML(el, html) {
  if (el._last !== html) { el._last = html; el.innerHTML = html; }
}

/* ================= dashboard: live loop ================= */
const charts = {};
let coreEls = null;
function startMetricsLoop() {
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  charts.cpu = new Sparkline($("#chCpu"), { color: css("--cpu") });
  charts.ram = new Sparkline($("#chRam"), { color: css("--ram") });
  charts.disk = new Sparkline($("#chDisk"), { color: css("--dsk"), max: null });
  charts.net = new Sparkline($("#chNet"), { color: css("--net"), max: null });
  pollLoop(1000, tickMetrics);
}
async function tickMetrics() {
  let m;
  try { m = await api.get_metrics(); } catch { return; }

  $("#stCpu").innerHTML = `${m.cpu.toFixed(0)}<small>%</small>`;
  $("#stCpuMeta").textContent = m.cpu_mhz ? `${(m.cpu_mhz / 1000).toFixed(2)} GHz · ${m.proc_count} processes` : `${m.proc_count} processes`;
  charts.cpu.push(m.cpu);

  $("#stRam").innerHTML = `${m.ram.percent.toFixed(0)}<small>%</small>`;
  $("#stRamMeta").textContent = `${fmtBytes(m.ram.used)} of ${fmtBytes(m.ram.total)}`;
  charts.ram.push(m.ram.percent);

  const dio = m.rates.disk_read + m.rates.disk_write;
  $("#stDisk").innerHTML = `${fmtBytes(dio)}<small>/s</small>`;
  $("#stDiskMeta").textContent = `Read ${fmtRate(m.rates.disk_read)} · Write ${fmtRate(m.rates.disk_write)}`;
  charts.disk.push(dio);

  const nio = m.rates.net_up + m.rates.net_down;
  $("#stNet").innerHTML = `${fmtBytes(nio)}<small>/s</small>`;
  $("#stNetMeta").textContent = `Down ${fmtRate(m.rates.net_down)} · Up ${fmtRate(m.rates.net_up)}`;
  charts.net.push(nio);

  // per-core grid
  const cores = m.cpu_per_core;
  if (!coreEls || coreEls.length !== cores.length) {
    $("#coreGrid").innerHTML = cores.map(() =>
      `<div class="core"><div class="fill"></div><div class="pct"></div></div>`).join("");
    $("#coreCount").textContent = `${cores.length} threads`;
    coreEls = $$("#coreGrid .core");
  }
  cores.forEach((v, i) => {
    coreEls[i].querySelector(".fill").style.height = v >= 1 ? `${v}%` : "0";
    coreEls[i].querySelector(".pct").textContent = v >= 1 ? Math.round(v) : "";
  });

  $("#tbUptimeVal").textContent = fmtDur(Date.now() / 1000 - m.boot_time);
  if (m.battery) {
    $("#tbBattery").style.display = "";
    $("#tbBatteryVal").textContent = `${m.battery.percent}%${m.battery.plugged ? " · mains" : ""}`;
  }
  updateQuickVitals(m);
}

/* ---- vitals strip ---- */
const vitalState = { quick: {}, audit: {} };
function updateQuickVitals(m) {
  const up = (Date.now() / 1000 - m.boot_time) / 86400;
  vitalState.quick.uptime = { cls: up < 14 ? "ok" : "warn", html: `Uptime <b>${fmtDur(Date.now() / 1000 - m.boot_time)}</b>` };
  if (m.sys_disk) {
    const freePct = 100 - m.sys_disk.percent;
    vitalState.quick.disk = {
      cls: freePct >= 15 ? "ok" : freePct >= 8 ? "warn" : "crit",
      html: `C: free <b>${fmtBytes(m.sys_disk.total - m.sys_disk.used)}</b>`,
    };
  }
  vitalState.quick.ram = { cls: m.ram.percent < 85 ? "ok" : "warn", html: `Memory <b>${m.ram.percent.toFixed(0)}%</b>` };
  renderVitals();
}
function setAuditVitals(h) {
  const find = id => h.checks.find(c => c.id === id);
  const map = [["av_rt", "Antivirus"], ["smart", "Disks"], ["updates", "Updates"], ["reboot", "Reboot"]];
  for (const [id, label] of map) {
    const c = find(id);
    if (!c) continue;
    const cls = { good: "ok", warn: "warn", bad: "crit", unknown: "unk" }[c.status];
    const word = { good: "OK", warn: "attention", bad: "action needed", unknown: "unknown" }[c.status];
    vitalState.audit[id] = { cls, html: `${esc(label)} <b>${word}</b>` };
  }
  renderVitals();
}
function renderVitals() {
  const items = [...Object.values(vitalState.quick), ...Object.values(vitalState.audit)];
  setHTML($("#vitals"), items.map(v =>
    `<span class="vital ${v.cls}"><span class="dot"></span>${v.html}</span>`).join(""));
}

/* dashboard top processes */
async function refreshDashProcs() {
  if (!$("#page-dashboard").classList.contains("active")) return;
  try {
    const procs = await api.get_processes();
    $("#dashTopProcs").className = "";
    setHTML($("#dashTopProcs"), `<table class="mini-table"><tbody>` + procs.slice(0, 6).map(p => `
      <tr><td class="strong">${esc(p.name)}</td>
      <td class="num" style="width:64px">${p.cpu.toFixed(1)}%</td>
      <td class="num" style="width:84px">${fmtBytes(p.mem)}</td></tr>`).join("") + `</tbody></table>`);
  } catch { /* window closing */ }
}

/* dashboard static cards */
async function loadDashboardStatic() {
  pollLoop(3000, refreshDashProcs);

  api.get_health().then(h => {
    setRing($("#dashRing"), h.score, h.grade);
    setAuditVitals(h);
    const worst = h.checks.filter(c => c.status === "bad").concat(h.checks.filter(c => c.status === "warn")).slice(0, 3);
    $("#dashHealthSummary").className = "";
    $("#dashHealthSummary").innerHTML = worst.length
      ? worst.map(c => `<div style="margin-bottom:8px">${pill(c.status === "bad" ? "bad" : "warn", c.status === "bad" ? "Fail" : "Warn")} <span style="font-size:12px">${esc(c.label)}</span></div>`).join("")
      : `<div>${pill("good", "All clear")} <span style="font-size:12px">No failed checks</span></div>`;
  }).catch(() => { $("#dashHealthSummary").className = ""; $("#dashHealthSummary").innerHTML = emptyState("bang", "Couldn't load health"); });

  api.get_inventory().then(inv => {
    $("#tbSub").textContent = `${inv.os.name ?? "Windows"} · build ${inv.os.build ?? "?"} · ${inv.system.manufacturer ?? ""} ${inv.system.model ?? ""}`;
    const cpu = inv.cpus[0] || {};
    const gpus = inv.gpus.filter(g => g.name && !/virtual|basic/i.test(g.name));
    $("#dashGlance").innerHTML = [
      ["Machine", `${inv.system.manufacturer ?? "—"} ${inv.system.model ?? ""}`],
      ["OS", `${inv.os.name ?? "—"} (${inv.os.arch ?? "?"})`],
      ["CPU", cpu.name ? `${cpu.name} — ${cpu.cores}C/${cpu.threads}T` : "—"],
      ["Memory", `${fmtBytes(inv.ram_total)} · ${inv.ram_modules.length} module(s)`],
      ["GPU", gpus.map(g => g.name).join(", ") || (inv.gpus[0]?.name ?? "—")],
      ["BIOS", `${inv.bios.vendor ?? "—"} ${inv.bios.version ?? ""} (${inv.bios.date ?? "?"})`],
      ["Domain", inv.system.domain ?? "—"],
    ].map(([k, v]) => `<dt>${k}</dt><dd class="copy">${esc(v)}</dd>`).join("");
  }).catch(() => { $("#dashGlance").innerHTML = `<dt class="muted">Couldn't load inventory</dt><dd></dd>`; });

  api.get_storage().then(st => {
    $("#dashVolumes").className = "";
    $("#dashVolumes").innerHTML = st.volumes.map(v => volBar(v, true)).join("")
      || emptyState("drive", "No volumes found");
  }).catch(() => { $("#dashVolumes").className = ""; $("#dashVolumes").innerHTML = emptyState("drive", "Couldn't load volumes"); });
}

function volBar(v, clickable = false) {
  const cls = v.percent >= 92 ? "bad" : v.percent >= 80 ? "warn" : "";
  const attrs = clickable ? ` class="vol-link" data-drive="${esc(v.letter)}" style="cursor:pointer"` : "";
  return `<div${attrs} style="margin-bottom:12px${clickable ? ";cursor:pointer" : ""}">
    <div class="row" style="justify-content:space-between; margin-bottom:5px; font-size:12px">
      <span class="strong" style="color:var(--text-1)">${esc(v.letter)}: ${esc(v.label || "")}</span>
      <span class="muted">${fmtBytes(v.free)} free of ${fmtBytes(v.size)}</span>
    </div>
    <div class="bar"><div class="fill ${cls}" style="width:${v.percent}%"></div></div>
  </div>`;
}
$("#dashVolumes").addEventListener("click", e => {
  const link = e.target.closest(".vol-link");
  if (!link) return;
  showPage("storage");
  analyzePath(`${link.dataset.drive}:\\`);
});

/* ================= SYSTEM page ================= */
async function loadSystem(refresh = false) {
  startSensorsLoop();
  loadBatteryTrend();
  const body = $("#systemBody");
  if (refresh) body.innerHTML = `<div class="card"><div class="skel-block"><div class="skel"></div><div class="skel" style="width:80%"></div></div></div>`;
  const inv = await api.get_inventory(refresh);
  const cpu = inv.cpus[0] || {};
  const kv = rows => `<dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd class="copy">${esc(v ?? "—")}</dd>`).join("")}</dl>`;

  body.innerHTML = `
  <div class="grid cols-2">
    <div class="card"><h3>Machine</h3>${kv([
      ["Manufacturer", inv.system.manufacturer], ["Model", inv.system.model],
      ["Family", inv.system.family], ["Chassis type", inv.system.type],
      ["Domain / Workgroup", inv.system.domain],
      ["Domain joined", inv.system.domain_joined === true ? "Yes" : inv.system.domain_joined === false ? "No" : "—"],
    ])}</div>
    <div class="card"><h3>Operating system</h3>${kv([
      ["Edition", inv.os.name], ["Version / Build", `${inv.os.version ?? "?"} (build ${inv.os.build ?? "?"})`],
      ["Architecture", inv.os.arch], ["Installed", inv.os.installed], ["Product serial", inv.os.serial],
    ])}</div>
    <div class="card"><h3>Processor</h3>${kv([
      ["Model", cpu.name], ["Cores / Threads", cpu.cores ? `${cpu.cores} cores / ${cpu.threads} threads` : null],
      ["Max clock", cpu.max_mhz ? `${(cpu.max_mhz / 1000).toFixed(2)} GHz` : null],
      ["L2 / L3 cache", cpu.l2_kb ? `${cpu.l2_kb / 1024} MB / ${(cpu.l3_kb / 1024).toFixed(0)} MB` : null],
      ["Socket", cpu.socket],
      ["Virtualization (fw)", cpu.virtualization === true ? "Enabled" : cpu.virtualization === false ? "Disabled" : "—"],
    ])}</div>
    <div class="card"><h3>Board &amp; firmware</h3>${kv([
      ["Motherboard", `${inv.board.manufacturer ?? "—"} ${inv.board.product ?? ""}`],
      ["Board serial", inv.board.serial],
      ["BIOS / UEFI", `${inv.bios.vendor ?? "—"} ${inv.bios.version ?? ""}`],
      ["BIOS date", inv.bios.date], ["System serial", inv.bios.serial],
      ["Secure Boot", inv.secure_boot === true ? "Enabled" : inv.secure_boot === false ? "Disabled" : "Unknown (needs admin)"],
      ["TPM", inv.tpm ? `${inv.tpm.enabled ? "Enabled" : "Present, disabled"} — spec ${esc(String(inv.tpm.spec ?? "?")).split(",")[0]}` : "Unknown (needs admin)"],
    ])}</div>
  </div>

  <div class="card mt"><h3>Memory — ${fmtBytes(inv.ram_total)} in ${inv.ram_modules.length} module(s)</h3>
    <div class="table-wrap" style="max-height:none"><table>
      <thead><tr><th>Slot</th><th class="num">Capacity</th><th>Type</th><th class="num">Speed</th><th>Manufacturer</th><th>Part number</th></tr></thead>
      <tbody>${inv.ram_modules.map(m => `<tr>
        <td class="strong">${esc(m.slot)}</td><td class="num">${fmtBytes(m.capacity)}</td>
        <td>${esc(m.type ?? "—")}</td><td class="num">${m.speed ?? "—"} MT/s</td>
        <td>${esc(m.manufacturer || "—")}</td><td class="mono copy">${esc(m.part || "—")}</td></tr>`).join("")}
      </tbody></table></div>
  </div>

  <div class="grid cols-2 mt">
    <div class="card"><h3>Graphics</h3>${inv.gpus.map(g => kv([
      ["Adapter", g.name], ["Driver", g.driver], ["Driver date", g.driver_date],
      ["Active mode", g.resolution], ["Status", g.status],
    ])).join("<hr style='border:none;border-top:1px solid var(--border-1);margin:12px 0'>")}</div>
    <div class="card"><h3>Monitors</h3>${inv.monitors.length ? inv.monitors.map(m => kv([
      ["Display", m.name], ["Serial", m.serial || "—"], ["Manufactured", m.year || "—"],
    ])).join("<hr style='border:none;border-top:1px solid var(--border-1);margin:12px 0'>") : emptyState("q", "No EDID data available")}</div>
  </div>`;
}
$("#btnSysRefresh").onclick = () => loadSystem(true);

/* ================= STORAGE page ================= */
async function loadStorage(refresh = false) {
  const body = $("#storageBody");
  if (refresh) body.innerHTML = `<div class="card"><div class="skel-block"><div class="skel"></div></div></div>`;
  const st = await api.get_storage(refresh);

  const smartChip = d => {
    if (!d.health) return pill("unknown", "Unknown");
    return d.health === "Healthy" ? pill("good", "Healthy") : pill("bad", d.health);
  };
  const needsAdmin = `<span class="muted">${isAdmin ? "not reported" : "needs admin"}</span>`;

  body.innerHTML = `
  <div class="grid cols-2">${st.disks.map(d => `
    <div class="card disk-card">
      <div class="head">
        <div class="dico">${ico("drive")}</div>
        <div style="flex:1; min-width:0">
          <div class="name">${esc(d.name)}</div>
          <div class="sub">${esc(d.media ?? "?")} · ${esc(d.bus ?? "?")} · ${fmtBytes(d.size)}${d.rpm ? ` · ${d.rpm} RPM` : ""}</div>
        </div>
        ${smartChip(d)}
      </div>
      <dl class="kv tight">
        <dt>Serial</dt><dd class="mono copy" style="font-size:11px">${esc(d.serial || "—")}</dd>
        <dt>Firmware</dt><dd class="copy">${esc(d.firmware || "—")}</dd>
        <dt>Temperature</dt><dd>${d.temp_c ? d.temp_c + " °C" : needsAdmin}</dd>
        <dt>Wear</dt><dd>${d.wear_pct !== null && d.wear_pct !== undefined ? d.wear_pct + " %" : needsAdmin}</dd>
        <dt>Power-on hours</dt><dd>${d.power_on_hours ? d.power_on_hours.toLocaleString() + " h" : needsAdmin}</dd>
      </dl>
    </div>`).join("")}
  </div>
  <div class="card mt"><h3>Volumes</h3>${st.volumes.map(v => volBar(v)).join("")}</div>
  <div class="card mt"><h3>SMART attributes <span class="right"><button class="btn small" id="btnSmart">Show</button></span></h3>
    <p class="muted" style="font-size:12.5px; line-height:1.5; margin-bottom:8px">
      The raw drive self-monitoring counters — reallocated, pending and uncorrectable sectors are the
      early warning signs of a failing disk. Mostly SATA/ATA drives; NVMe rarely exposes them, and reading needs admin.</p>
    <div id="smartBody"></div></div>`;
  const smartBtn = $("#btnSmart");
  if (smartBtn) smartBtn.onclick = async () => {
    $("#smartBody").innerHTML = `<div class="muted" style="font-size:12.5px">Reading SMART data…</div>`;
    const s = await api.smart_attributes();
    if (!s || !s.disks) { $("#smartBody").innerHTML = emptyState("bang", "Couldn't read SMART data"); return; }
    const avail = s.disks.filter(d => d.available);
    if (!avail.length) { $("#smartBody").innerHTML = `<div class="muted" style="font-size:12.5px">${esc(s.note || "No SMART attributes available (NVMe, or needs admin).")}</div>`; return; }
    $("#smartBody").innerHTML = avail.map(d => `
      <div style="margin-bottom:10px"><div class="strong" style="margin-bottom:4px">${esc(d.disk)}</div>
        <div class="table-wrap" style="max-height:260px"><table>
          <thead><tr><th>ID</th><th>Attribute</th><th class="num">Current</th><th class="num">Worst</th><th class="num">Raw</th></tr></thead>
          <tbody>${d.attributes.map(a => `<tr${a.concern ? ' style="color:var(--crit)"' : ''}>
            <td class="mono">${a.id}</td><td>${esc(a.name)}</td>
            <td class="num">${a.current}</td><td class="num">${a.worst}</td><td class="num mono">${a.raw}</td></tr>`).join("")}</tbody>
        </table></div></div>`).join("");
  };
}
$("#btnStorRefresh").onclick = () => loadStorage(true);

/* ---- space analyzer ---- */
let anBusy = false;
async function initDriveChips() {
  const drives = await api.list_drives();
  $("#anDrives").innerHTML = drives.map(d =>
    `<button class="btn small" data-drive="${d}">${d}:</button>`).join("");
  $("#anDrives").addEventListener("click", e => {
    const b = e.target.closest("[data-drive]");
    if (b) analyzePath(`${b.dataset.drive}:\\`);
  });
}
function renderCrumbs(path) {
  const parts = path.replace(/\\+$/, "").split("\\");
  let acc = "";
  $("#anCrumbs").innerHTML = parts.map((p, i) => {
    acc += (i ? "\\" : "") + p;
    const target = i === 0 ? p + "\\" : acc;
    return `<button data-path="${esc(target)}">${esc(p || "?")}</button>`;
  }).join(`<span class="sep">${ico("chev", "ic sm")}</span>`);
}
$("#anCrumbs").addEventListener("click", e => {
  const b = e.target.closest("[data-path]");
  if (b) analyzePath(b.dataset.path);
});
async function analyzePath(path) {
  if (anBusy) return;
  anBusy = true;
  $("#anPath").value = path;
  $("#anStatus").innerHTML = `<span class="spin"></span>`;
  $("#btnAnalyze").disabled = true;
  try {
    const r = await api.analyze_folder(path);
    if (!r.ok) { $("#anStatus").textContent = ""; toast(r.error, "bad"); return; }
    renderCrumbs(r.path);
    $("#anStatus").textContent = `${fmtBytes(r.total)} total`;
    const max = r.entries[0]?.size || 1;
    $("#anResult").innerHTML = r.entries.map(e => `
      <div class="an-row">
        ${ico(e.kind === "dir" ? "folder" : "file", "ic sm")}
        <span class="nm ${e.kind}" ${e.kind === "dir" ? `data-dir="${esc(e.name)}"` : ""} title="${esc(e.name)}">${esc(e.name)}</span>
        <div class="bar" style="flex:1"><div class="fill" style="width:${Math.max(0.6, e.size / max * 100)}%"></div></div>
        <span class="sz">${fmtBytes(e.size)}</span>
        <button class="btn ghost small row-action" data-open="${esc(e.name)}" title="Reveal in Explorer">${ico("open", "ic sm")}</button>
      </div>`).join("") || emptyState("folder", "Empty folder");
    $("#anResult").dataset.base = r.path;
  } finally { anBusy = false; $("#btnAnalyze").disabled = false; }
}
$("#anResult").addEventListener("click", e => {
  const base = $("#anResult").dataset.base || "";
  const open = e.target.closest("[data-open]");
  if (open) { api.open_path(base.replace(/\\+$/, "") + "\\" + open.dataset.open); return; }
  const dir = e.target.closest("[data-dir]");
  if (dir) analyzePath(base.replace(/\\+$/, "") + "\\" + dir.dataset.dir);
});
$("#btnAnalyze").onclick = () => analyzePath($("#anPath").value.trim() || "C:\\");
$("#anPath").addEventListener("keydown", e => { if (e.key === "Enter") $("#btnAnalyze").click(); });

/* ================= NETWORK page ================= */
async function loadNetwork() {
  const wrap = $("#netAdapters");
  const net = await api.get_network_info();
  const cards = net.adapters.filter(a => a.status === "Up" || a.ipv4).map(a => `
    <div class="card">
      <h3>${esc(a.alias)} <span class="right">${a.status === "Up" ? pill("good", "Up") : pill("unknown", esc(a.status ?? "Down"))}</span></h3>
      <dl class="kv tight">
        <dt>Adapter</dt><dd class="copy">${esc(a.desc ?? "—")}</dd>
        <dt>IPv4</dt><dd class="mono copy" style="font-size:12px">${esc(a.ipv4 || "—")}</dd>
        <dt>Gateway</dt><dd class="mono copy" style="font-size:12px">${esc(a.gateway || "—")}</dd>
        <dt>DNS</dt><dd class="mono copy" style="font-size:12px">${esc(a.dns || "—")}</dd>
        <dt>MAC</dt><dd class="mono copy" style="font-size:12px">${esc(a.mac ?? "—")}</dd>
        <dt>Link / DHCP</dt><dd>${esc(a.speed ?? "—")} · DHCP ${esc(String(a.dhcp ?? "?"))}</dd>
      </dl>
    </div>`);
  if (net.wifi) {
    const w = net.wifi;
    cards.push(`<div class="card"><h3>Wi-Fi <span class="right">${pill("info", esc(w.signal ?? "?"))}</span></h3>
      <dl class="kv tight">
        <dt>SSID</dt><dd class="copy">${esc(w.ssid ?? "—")}</dd>
        <dt>Radio / Band</dt><dd>${esc(w.radio ?? "—")} · ${esc(w.band ?? "—")} · ch ${esc(w.channel ?? "?")}</dd>
        <dt>Rates</dt><dd>Down ${esc(w.rx_rate ?? "?")} Mbps · Up ${esc(w.tx_rate ?? "?")} Mbps</dd>
        <dt>Security</dt><dd>${esc(w.auth ?? "—")}</dd>
      </dl></div>`);
  }
  wrap.innerHTML = cards.join("") || `<div class="card">${emptyState("q", "No active adapters")}</div>`;
  initSubnetChips();

  // quick-target chips from live adapter data
  const up = net.adapters.find(a => a.status === "Up" && a.gateway);
  const targets = [];
  if (up?.gateway) targets.push(["Gateway", up.gateway.split(",")[0].trim()]);
  if (up?.dns) targets.push(["DNS", up.dns.split(",")[0].trim()]);
  targets.push(["Cloudflare", "1.1.1.1"], ["Google", "8.8.8.8"]);
  const seen = new Set();
  $("#netTargets").innerHTML = targets.filter(([, ip]) => ip && !seen.has(ip) && seen.add(ip))
    .map(([label, ip]) => `<button class="btn small" data-ip="${esc(ip)}" title="${esc(ip)}">${esc(label)}</button>`).join("");
}
$("#netTargets").addEventListener("click", e => {
  const b = e.target.closest("[data-ip]");
  if (b) { $("#netHost").value = b.dataset.ip; $("#netHost").focus(); }
});
$("#btnNetRefresh").onclick = () => loadNetwork();
$("#btnPublicIp").onclick = async () => {
  $("#btnPublicIp").disabled = true;
  const r = await api.get_public_ip();
  $("#btnPublicIp").disabled = false;
  if (r.ok) { $("#btnPublicIp").textContent = r.ip; toast(`Public IP ${r.ip}`, "good"); }
  else toast(r.error, "bad");
};

/* tool console */
let curTool = "ping";
$$("#netTabs .tab").forEach(t => t.addEventListener("click", () => {
  curTool = t.dataset.tool;
  $$("#netTabs .tab").forEach(x => x.classList.toggle("active", x === t));
  $("#netPort").style.display = curTool === "port" ? "" : "none";
  $("#btnPortProfile").style.display = curTool === "port" ? "" : "none";
  $("#netHost").style.display = (curTool === "conns" || curTool === "speed") ? "none" : "";
  $("#netTargets").style.display = (curTool === "conns" || curTool === "speed") ? "none" : "";
  $("#netHost").placeholder = {
    ping: "Hostname or IP", trace: "Destination host or IP",
    dns: "Name to resolve", port: "Host",
  }[curTool] || "";
}));
function consoleLog(html) {
  const c = $("#netConsole");
  if (c.dataset.used !== "1") { c.textContent = ""; c.dataset.used = "1"; }
  c.innerHTML += (c.innerHTML ? "\n\n" : "") + html;
  c.scrollTop = c.scrollHeight;
}
const padCol = (s, n) => esc((String(s ?? "") + " ".repeat(n)).slice(0, n));
$("#btnNetRun").onclick = async () => {
  const host = $("#netHost").value.trim();
  const btn = $("#btnNetRun");
  btn.disabled = true;
  const stamp = new Date().toLocaleTimeString();
  try {
    if (curTool === "ping") {
      consoleLog(`<span class="ok">[${stamp}] ping ${esc(host)}</span>`);
      const r = await api.run_ping(host, 4);
      consoleLog(r.ok ? esc(r.output) : `<span class="err">${esc(r.error)}</span>`);
      if (r.ok && r.summary && r.summary.loss_pct !== null)
        toast(`Ping ${host}: ${r.summary.loss_pct}% loss, avg ${r.summary.avg_ms ?? "?"} ms`,
              r.summary.loss_pct === 0 ? "good" : "bad");
    } else if (curTool === "trace") {
      consoleLog(`<span class="ok">[${stamp}] tracert ${esc(host)} (up to ~60 s)</span>`);
      const r = await api.run_traceroute(host);
      consoleLog(r.ok ? esc(r.output) : `<span class="err">${esc(r.error)}</span>`);
    } else if (curTool === "dns") {
      consoleLog(`<span class="ok">[${stamp}] resolve ${esc(host)}</span>`);
      const r = await api.dns_lookup(host);
      consoleLog(r.ok
        ? r.records.map(x => `${padCol(x.type, 6)} ${padCol(x.name, 42)} ${esc(x.value)}   (ttl ${x.ttl})`).join("\n")
        : `<span class="err">${esc(r.error)}</span>`);
    } else if (curTool === "port") {
      const port = $("#netPort").value.trim();
      consoleLog(`<span class="ok">[${stamp}] test ${esc(host)}:${esc(port)}</span>`);
      const r = await api.port_test(host, port);
      if (!r.ok) consoleLog(`<span class="err">${esc(r.error)}</span>`);
      else consoleLog(r.open
        ? `<span class="ok">OPEN</span> — TCP connect in ${r.ms} ms`
        : `<span class="err">CLOSED</span> — ${esc(r.reason)}`);
    } else if (curTool === "conns") {
      consoleLog(`<span class="ok">[${stamp}] active connections</span>`);
      const r = await api.get_connections();
      if (!r.ok) consoleLog(`<span class="err">${esc(r.error)}</span>`);
      else consoleLog(r.connections.map(x =>
        `${x.proto}  ${padCol(x.laddr, 28)} → ${padCol(x.raddr, 28)} ${padCol(x.status, 13)} ${esc(x.process)}`).join("\n")
        + `\n(${r.total} total, showing ${r.connections.length})`);
    } else if (curTool === "speed") {
      consoleLog(`<span class="ok">[${stamp}] speed test via speed.cloudflare.com</span>\nMeasuring latency, then ~40 MB of transfer — 15–30 s on most links…`);
      const r = await api.run_speedtest();
      if (!r.ok) consoleLog(`<span class="err">${esc(r.error)}</span>`);
      else {
        consoleLog(`<div class="speed-row">
          <div class="speed-kpi"><div class="v">${r.down_mbps}<small> Mbps</small></div><div class="l">Download</div></div>
          <div class="speed-kpi"><div class="v">${r.up_mbps}<small> Mbps</small></div><div class="l">Upload</div></div>
          <div class="speed-kpi"><div class="v">${r.latency_ms}<small> ms</small></div><div class="l">Latency</div></div>
        </div>`);
        toast(`Speed test: ${r.down_mbps} down / ${r.up_mbps} up Mbps`, "good");
      }
    }
  } finally { btn.disabled = false; }
};
$("#netHost").addEventListener("keydown", e => { if (e.key === "Enter") $("#btnNetRun").click(); });
async function flushDns() {
  const r = await api.flush_dns();
  toast(r.ok ? "DNS resolver cache flushed" : "Flush failed: " + (r.error || ""), r.ok ? "good" : "bad");
}
$("#btnFlushDns").onclick = flushDns;
$("#btnNetCopy").onclick = () => {
  navigator.clipboard.writeText($("#netConsole").innerText).then(() => toast("Session log copied", "info", 1800));
};

/* ---- Sharing & firewall (Bundle G) ---- */
const shLoaded = { profile: false, firewall: false, creds: false, dns: false };
$("#btnSharing").onclick = () => { shLoaded.profile = false; loadShProfile(); };
$$("#shTabs .tab").forEach(t => t.addEventListener("click", () => {
  $$("#shTabs .tab").forEach(x => x.classList.toggle("active", x === t));
  const w = t.dataset.sh;
  for (const [k, id] of [["profile", "shProfile"], ["firewall", "shFirewall"], ["creds", "shCreds"], ["dns", "shDns"]])
    $("#" + id).style.display = w === k ? "" : "none";
  if (w === "profile" && !shLoaded.profile) loadShProfile();
  if (w === "firewall" && !shLoaded.firewall) loadShFirewall();
  if (w === "creds" && !shLoaded.creds) loadShCreds();
  if (w === "dns" && !shLoaded.dns) loadShDns();
}));
async function loadShProfile() {
  shLoaded.profile = true;
  const el = $("#shProfile");
  el.innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Reading network profile…</span></div>`;
  const r = await api.network_profiles().catch(() => null);
  if (!r || !r.ok || !r.profiles.length) { el.innerHTML = emptyState("bang", "No active network profile"); return; }
  el.innerHTML = r.profiles.map(p => `<div class="dom-sec">
    <div class="dr"><span class="dk strong">${esc(p.interface)}</span><span class="dv">
      ${p.is_public ? pill("warn", "Public") : pill("good", esc(p.category))}
      ${p.is_public ? `<button class="btn small primary" style="margin-left:8px" data-mkpriv="${esc(p.interface)}">Set Private</button>` : ""}</span></div>
    ${p.is_public ? `<div class="muted" style="font-size:11.5px; margin-top:4px">On Public, Windows hides this PC and blocks file/printer sharing &amp; discovery. If this is a home or work network, set it Private.</div>` : ""}
    </div>`).join("");
  $$("#shProfile [data-mkpriv]").forEach(b => b.onclick = async () => {
    if (!confirm("Set this network to Private? It enables network discovery and file/printer sharing on this connection.")) return;
    b.disabled = true;
    const res = await api.set_network_category(b.dataset.mkpriv, "Private");
    toast(res.ok ? res.where : (res.error || "Couldn't change it"), res.ok ? "good" : "bad", 3500);
    if (res.ok) loadShProfile();
  });
}
async function loadShFirewall() {
  shLoaded.firewall = true;
  const el = $("#shFirewall");
  el.innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Reading firewall rules…</span></div>`;
  const [ov, ib] = await Promise.all([api.firewall_overview().catch(() => null), api.firewall_inbound().catch(() => null)]);
  if (!ov || !ov.ok) { el.innerHTML = emptyState("bang", "Couldn't read the firewall"); return; }
  const prof = `<div class="dom-sec"><h4>Profiles</h4>${ov.profiles.map(p =>
    `<div class="dr"><span class="dk">${esc(p.name)}</span><span class="dv">${p.enabled ? pill("good", "on") : pill("bad", "OFF")} · inbound ${esc(p.inbound_default)}</span></div>`).join("")}</div>`;
  let rules = "";
  if (ib && ib.ok) {
    const head = ib.flagged
      ? `<div class="dom-flag warn">${ico("bang")}<span>${ib.flagged} inbound allow rule(s) worth a look — flagged below.</span></div>`
      : `<div class="dom-flag good">${ico("check")}<span>${ib.total} inbound allow rules; nothing unusual.</span></div>`;
    rules = head + `<div class="table-wrap" style="max-height:320px; margin-top:8px"><table>
      <thead><tr><th>Rule</th><th>Program / port</th><th>Scope</th><th></th></tr></thead><tbody>
      ${ib.rules.slice(0, 120).map(r => `<tr>
        <td class="strong" style="max-width:220px">${esc(r.name)}</td>
        <td class="mono" style="max-width:260px; font-size:11px">${esc(r.program !== "Any" ? r.program : (r.proto + " " + r.port))}</td>
        <td>${r.public_any ? pill("info", "any / public") : esc(r.profiles)}</td>
        <td>${r.flags.length ? `<span title="${esc(r.flags.join("; "))}">${pill("warn", "review")}</span>` : ""}</td>
      </tr>`).join("")}</tbody></table></div>`;
  }
  el.innerHTML = prof + rules;
}
async function loadShCreds() {
  shLoaded.creds = true;
  const el = $("#shCreds");
  el.innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Reading drives &amp; credentials…</span></div>`;
  const [d, c] = await Promise.all([api.mapped_drives().catch(() => null), api.stored_credentials().catch(() => null)]);
  const drives = (d && d.ok && d.drives.length)
    ? `<div class="dom-sec"><h4>Mapped drives${d.stale ? ` ${pill("warn", d.stale + " stale")}` : ""}</h4>${d.drives.map(x =>
        `<div class="dr"><span class="dk strong">${esc(x.local)} → ${esc(x.remote)}</span><span class="dv">${x.stale ? pill("warn", esc(x.status)) : pill("good", esc(x.status))}</span></div>`).join("")}</div>`
    : `<div class="dom-sec"><h4>Mapped drives</h4><div class="muted" style="font-size:12px">No network drives mapped.</div></div>`;
  const creds = (c && c.ok && c.credentials.length)
    ? `<div class="dom-sec"><h4>Saved credentials (${c.total}) <span class="muted" style="font-size:11px">names only — no passwords are ever read</span></h4>
        <div class="table-wrap" style="max-height:260px"><table><thead><tr><th>Target</th><th>Type</th><th>User</th></tr></thead><tbody>
        ${c.credentials.map(x => `<tr><td class="copy" style="max-width:280px">${esc(x.display)}</td><td class="muted">${esc(x.type)}</td><td class="muted">${esc(x.user)}</td></tr>`).join("")}
        </tbody></table></div></div>`
    : `<div class="dom-sec"><h4>Saved credentials</h4><div class="muted" style="font-size:12px">None stored.</div></div>`;
  el.innerHTML = `<div class="dom-grid">${drives}${creds}</div>`;
}
async function loadShDns() {
  shLoaded.dns = true;
  const el = $("#shDns");
  el.innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Reading DNS cache &amp; Winsock…</span></div>`;
  const [d, w] = await Promise.all([api.dns_cache().catch(() => null), api.winsock_catalog().catch(() => null)]);
  const dns = (d && d.ok)
    ? `<div class="dom-sec"><h4>DNS resolver cache (${d.total})</h4>
        <div class="table-wrap" style="max-height:280px"><table><thead><tr><th>Name</th><th>Data</th></tr></thead><tbody>
        ${d.entries.map(e => `<tr><td class="copy" style="max-width:240px">${esc(e.name)}</td><td class="mono" style="max-width:240px; font-size:11px">${esc(e.data)}</td></tr>`).join("")}
        </tbody></table></div></div>`
    : `<div class="dom-sec"><h4>DNS resolver cache</h4>${emptyState("check", "Cache empty")}</div>`;
  const win = (w && w.ok)
    ? `<div class="dom-sec"><h4>Winsock / LSP providers ${w.third_party ? pill("warn", w.third_party + " third-party") : pill("good", "all built-in")}</h4>
        ${w.providers.map(p => `<div class="dr"><span class="dk">${esc(p.description)}</span><span class="dv">${p.third_party ? pill("warn", "3rd-party") : `<span class="muted">built-in</span>`}</span></div>`).join("")}</div>`
    : "";
  el.innerHTML = `<div class="dom-grid">${dns}${win}</div>`;
}

/* ================= Bundle H: power / storage / runtime forensics ================= */
$("#btnBatteryReport").onclick = async () => {
  $("#powerReportBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Reading battery report…</span></div>`;
  const r = await api.battery_report().catch(() => null);
  if (!r || !r.ok) { $("#powerReportBody").innerHTML = `<div class="muted">Couldn't read the battery report.</div>`; return; }
  if (!r.has_battery) { $("#powerReportBody").innerHTML = `<div class="muted" style="font-size:12.5px">${esc(r.message)}</div>`; return; }
  const wearLvl = r.wear_pct == null ? "info" : r.wear_pct >= 30 ? "warn" : "good";
  $("#powerReportBody").innerHTML = `<div class="dom-sec">
    ${r.wear_pct != null ? `<div class="dr"><span class="dk">Battery wear</span><span class="dv">${pill(wearLvl, r.wear_pct + "%")}</span></div>` : ""}
    ${r.full_mwh ? `<div class="dr"><span class="dk">Full charge / design</span><span class="dv mono">${r.full_mwh} / ${r.design_mwh} mWh</span></div>` : ""}
    ${r.cycles != null ? `<div class="dr"><span class="dk">Cycle count</span><span class="dv mono">${r.cycles}</span></div>` : ""}
  </div>`;
};
$("#btnEnergyReport").onclick = async () => {
  const b = $("#btnEnergyReport"); b.disabled = true;
  $("#powerReportBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Running a ~30s power trace…</span></div>`;
  const r = await api.energy_report(30).catch(() => null);
  b.disabled = false;
  if (!r || !r.ok) { $("#powerReportBody").innerHTML = `<div class="muted">Couldn't run the energy trace.</div>`; return; }
  if (r.needs_admin) { $("#powerReportBody").innerHTML = `<div class="dom-flag warn">${ico("bang")}<span>${esc(r.note)}</span></div>`; return; }
  const counts = `<div class="row" style="gap:6px; margin-bottom:8px">
    ${pill(r.errors ? "bad" : "good", (r.errors || 0) + " errors")}
    ${pill(r.warnings ? "warn" : "good", (r.warnings || 0) + " warnings")}
    ${pill("info", (r.info || 0) + " info")}</div>`;
  const issues = r.issues.length ? `<div class="dom-sec">${r.issues.map(i =>
    `<div class="dom-flag ${i.level === "error" ? "bad" : "warn"}">${ico("bang")}<span>${esc(i.text)}</span></div>`).join("")}</div>`
    : `<div class="muted" style="font-size:12px">No efficiency problems reported.</div>`;
  $("#powerReportBody").innerHTML = counts + issues;
};
$("#btnEnvAudit").onclick = async () => {
  $("#envBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Auditing PATH…</span></div>`;
  const r = await api.env_audit().catch(() => null);
  if (!r || !r.ok) { $("#envBody").innerHTML = `<div class="muted">Couldn't read the environment.</div>`; return; }
  const head = r.problem_count
    ? `<div class="dom-flag warn">${ico("bang")}<span>${r.problem_count} PATH entr${r.problem_count === 1 ? "y has" : "ies have"} a problem (highlighted below).</span></div>`
    : `<div class="dom-flag good">${ico("check")}<span>PATH is clean — every entry exists, no duplicates.</span></div>`;
  const rows = r.entries.map(e => `<div class="dr">
    <span class="dk mono" style="font-size:11px; ${e.ok ? "" : "color:var(--warn,#d98a3a)"}">${esc(e.value)}</span>
    <span class="dv">${e.ok ? `<span class="muted">${esc(e.scope)}</span>` : pill("warn", esc(e.problems.join(", ")))}</span></div>`).join("");
  const vw = r.var_warnings.length ? `<div class="dom-sec"><h4>Variables pointing at a missing folder</h4>${
    r.var_warnings.map(v => `<div class="dr"><span class="dk strong">${esc(v.name)}</span><span class="dv mono" style="font-size:11px">${esc(v.value)}</span></div>`).join("")}</div>` : "";
  const clean = r.problem_count ? `<div class="row" style="margin-top:8px">
    <button class="btn small primary" data-clean-path="User">Clean User PATH</button>
    <button class="btn small ghost" data-clean-path="Machine">Clean Machine PATH (admin)</button>
    <span class="muted" style="font-size:11px">Removes broken &amp; duplicate entries; backs up the prior value.</span></div>` : "";
  $("#envBody").innerHTML = head + `<div class="dom-sec" style="margin-top:8px">${rows}</div>` + vw + clean;
  $$("#envBody [data-clean-path]").forEach(b => b.onclick = async () => {
    if (!confirm("Remove broken and duplicate entries from this PATH? The prior value is backed up.")) return;
    b.disabled = true;
    const res = await api.clean_path(b.dataset.cleanPath);
    toast(res.ok ? (res.message || res.where || "PATH cleaned") : (res.error || "Couldn't clean PATH"), res.ok ? "good" : "bad", 3500);
    if (res.ok && res.changed) $("#btnEnvAudit").click();
  });
};
$("#btnRuntimes").onclick = async () => {
  $("#runtimesBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Reading runtimes…</span></div>`;
  const r = await api.runtimes_inventory().catch(() => null);
  if (!r || !r.ok) { $("#runtimesBody").innerHTML = `<div class="muted">Couldn't read runtimes.</div>`; return; }
  const list = (title, arr) => `<div class="dom-sec"><h4>${title}</h4>${
    arr.length ? arr.map(x => `<div class="dr"><span class="dk strong">${esc(x)}</span></div>`).join("") : `<div class="muted" style="font-size:12px">None found.</div>`}</div>`;
  const vc = `<div class="dom-sec"><h4>Visual C++ redistributables</h4>${
    r.vcredist.length ? r.vcredist.map(v => `<div class="dr"><span class="dk">${esc(v.name)}</span><span class="dv mono">${esc(v.version)}</span></div>`).join("") : `<div class="muted" style="font-size:12px">None found.</div>`}</div>`;
  $("#runtimesBody").innerHTML = `<div class="dom-grid">
    ${list(".NET Framework", r.dotnet_framework)}
    ${list(".NET (Core / 5+)", r.dotnet_core)}
    ${vc}
    <div class="dom-sec"><h4>DirectX</h4><div class="dr"><span class="dk strong">${esc(r.directx.label)}</span><span class="dv mono">${esc(r.directx.ddi || "")}</span></div></div>
  </div>`;
};
$("#btnStorageDeep").onclick = async () => {
  $("#storageDeepBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Reading deep storage health…</span></div>`;
  const r = await api.storage_deep().catch(() => null);
  if (!r || !r.ok) { $("#storageDeepBody").innerHTML = `<div class="muted">Couldn't read storage health.</div>`; return; }
  const trimPill = r.trim_enabled == null ? pill("info", "unknown") : r.trim_enabled ? pill("good", "enabled") : pill("warn", "disabled");
  const top = `<div class="dom-sec"><h4>Filesystem</h4>
    <div class="dr"><span class="dk">TRIM (SSD)</span><span class="dv">${trimPill}</span></div>
    <div class="dr"><span class="dk">C: dirty bit</span><span class="dv">${r.c_dirty ? pill("warn", "set — chkdsk wanted") : pill("good", "clean")}</span></div></div>`;
  const spaces = (r.pools.length || r.vdisks.length) ? `<div class="dom-sec"><h4>Storage Spaces</h4>
    ${r.pools.map(p => `<div class="dr"><span class="dk strong">${esc(p.FriendlyName)} (${p.Size} GB)</span><span class="dv">${esc(p.Health || "")}</span></div>`).join("")}
    ${r.vdisks.map(v => `<div class="dr"><span class="dk">${esc(v.FriendlyName)} · ${esc(v.Resiliency || "")}</span><span class="dv">${esc(v.Health || "")}</span></div>`).join("")}</div>` : "";
  const rel = r.reliability.length ? `<div class="dom-sec"><h4>Reliability counters${r.reliability.every(x => x.wear == null) ? ` ${pill("info", "wear/temp need admin")}` : ""}</h4>
    ${r.reliability.map(x => `<div class="dr"><span class="dk strong">${esc(x.name)}</span><span class="dv">${
      x.wear != null ? `wear ${x.wear}% · ` : ""}${x.temp != null ? `${x.temp}°C · ` : ""}${x.read_err != null ? `rd-err ${x.read_err} · wr-err ${x.write_err}` : (x.wear == null ? "—" : "")}</span></div>`).join("")}</div>` : "";
  const vss = r.vss.length ? `<div class="dom-sec"><h4>Shadow-copy storage (System Restore)</h4>
    ${r.vss.map(v => `<div class="dr"><span class="dk strong">${esc(v.volume)}</span><span class="dv mono" style="font-size:11px">used ${esc(v.used || "—")} / max ${esc(v.max || "—")}</span></div>`).join("")}</div>`
    : (r.vss_needs_admin ? `<div class="dom-sec"><h4>Shadow-copy storage</h4><div class="muted" style="font-size:12px">Run as admin to see restore-point space usage.</div></div>` : "");
  $("#storageDeepBody").innerHTML = `<div class="dom-grid">${top}${spaces}${rel}${vss}</div>`;
};
$("#btnAudioCheck").onclick = async () => {
  $("#audioBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Reading audio devices…</span></div>`;
  const r = await api.audio_status().catch(() => null);
  if (!r || !r.ok) { $("#audioBody").innerHTML = `<div class="muted">Couldn't read audio devices.</div>`; return; }
  const notes = r.notes.map(n => `<div class="dom-flag warn">${ico("bang")}<span>${esc(n)}</span></div>`).join("");
  const eps = r.endpoints.filter(e => e.present || e.status === "active");
  const list = eps.length ? `<div class="table-wrap" style="max-height:260px"><table>
    <thead><tr><th>Device</th><th>Kind</th><th>State</th></tr></thead><tbody>
    ${eps.map(e => `<tr><td class="strong">${esc(e.name)}</td><td class="muted">${esc(e.kind)}</td>
      <td>${e.status === "active" ? pill("good", "active") : e.concern ? pill("bad", esc(e.status)) : pill("info", esc(e.status))}</td></tr>`).join("")}
    </tbody></table></div>` : emptyState("bang", "No audio endpoints found");
  const svc = `<div class="row" style="gap:6px; margin-top:8px">${r.services.map(s =>
    s.concern ? pill("warn", `${esc(s.name)}: ${esc(s.status)}`) : pill("good", `${esc(s.name)}: ${esc(s.status)}`)).join("")}
    <button class="btn small ghost" id="btnAudioRestart" title="Restart the audio services">Restart audio</button></div>`;
  $("#audioBody").innerHTML = notes + list + svc;
  const rb = $("#btnAudioRestart");
  if (rb) rb.onclick = async () => {
    rb.disabled = true;
    const res = await api.restart_audio();
    toast(res.ok ? "Audio service restarted" : (res.error || "Couldn't restart"), res.ok ? "good" : "bad");
    rb.disabled = false;
    if (res.ok) $("#btnAudioCheck").click();
  };
};
$("#btnNetClear").onclick = () => {
  const c = $("#netConsole");
  c.dataset.used = "";
  c.innerHTML = `<span class="console-empty">Enter a target and press Run. The session log accumulates here.</span>`;
};

/* ---- Domain & website lookup ---- */
const domDate = s => s ? esc(String(s).slice(0, 10)) : "—";
const domRow = (k, v) => (v == null || v === "") ? "" :
  `<div class="dr"><span class="dk">${esc(k)}</span><span class="dv">${v}</span></div>`;

function renderDomain(r) {
  const sec = (title, rows) => {
    const body = rows.filter(Boolean).join("");
    return body ? `<div class="dom-sec"><h4>${esc(title)}</h4>${body}</div>` : "";
  };

  // Verdict
  const flags = (r.flags || []).map(f => {
    const i = f.level === "good" ? "check" : f.level === "warn" ? "bang" : "q";
    return `<div class="dom-flag ${esc(f.level)}">${ico(i)}<span>${esc(f.text)}</span></div>`;
  }).join("");
  const verdict = `<div class="dom-verdict">${flags ||
    `<div class="dom-flag info">${ico("q")}<span>No specific signals — review the details below.</span></div>`}</div>`;

  // Registration (WHOIS/RDAP)
  const rd = r.rdap;
  const whois = rd ? sec("Registration · WHOIS", [
    domRow("Registrar", esc(rd.registrar || "—")),
    domRow("Registered", domDate(rd.created)),
    domRow("Updated", domDate(rd.updated)),
    domRow("Expires", domDate(rd.expires)),
    domRow("Age", rd.age_days != null ? esc(rd.age_days >= 365
      ? `${Math.floor(rd.age_days / 365)} yr ${rd.age_days % 365} d` : `${rd.age_days} days`) : ""),
    domRow("Registrant", rd.registrant_org ? esc(rd.registrant_org) : `<span class="muted">redacted / private</span>`),
    domRow("Abuse", rd.abuse_email ? `<span class="mono copy">${esc(rd.abuse_email)}</span>` : ""),
    rd.statuses && rd.statuses.length ? domRow("Status",
      rd.statuses.map(s => pill("unk", s)).join(" ")) : "",
    rd.nameservers && rd.nameservers.length ? domRow("Nameservers",
      `<span class="mono">${esc(rd.nameservers.slice(0, 4).join("\n"))}</span>`) : "",
  ]) : sec("Registration · WHOIS", [
    `<div class="muted" style="font-size:12px">${esc(r.rdap_error || "No registration data.")}</div>`]);

  // DNS
  const d = r.dns || {};
  const mxView = (d.mx || []).length
    ? ((d.mx[0].host === ".") ? `<span class="muted">Null MX — accepts no email</span>`
       : `<span class="mono">${esc(d.mx.slice(0, 4).map(m => `${m.pref ?? ""} ${m.host}`.trim()).join("\n"))}</span>`)
    : "";
  const dns = sec("DNS records", [
    domRow("A", d.a && d.a.length ? `<span class="mono copy">${esc(d.a.slice(0, 4).join("\n"))}</span>` : ""),
    domRow("AAAA", d.aaaa && d.aaaa.length ? `<span class="mono">${esc(d.aaaa.slice(0, 2).join("\n"))}</span>` : ""),
    domRow("NS", d.ns && d.ns.length ? `<span class="mono">${esc(d.ns.slice(0, 4).join("\n"))}</span>` : ""),
    domRow("MX", mxView),
    domRow("Email auth", `${d.spf ? pill("good", "SPF") : pill("warn", "no SPF")} ${d.dmarc ? pill("good", "DMARC") : pill("warn", "no DMARC")}`),
  ]);

  // Hosting (IP)
  const ip = r.ip;
  const hosting = ip ? sec("Hosting", [
    domRow("IP address", `<span class="mono copy">${esc(ip.addr || "—")}</span>`),
    domRow("Reverse DNS", ip.ptr ? `<span class="mono">${esc(ip.ptr)}</span>` : `<span class="muted">none</span>`),
    domRow("Network / org", esc(ip.org || ip.network || "—")),
    domRow("Country", esc(ip.country || "—")),
  ]) : "";

  // TLS certificate
  const t = r.tls || {};
  let tls;
  if (t.ok) {
    const vpill = t.verified ? pill("good", "Valid & trusted") : pill("warn", "Not validated");
    const dl = t.days_left;
    const dlView = dl == null ? "—" : dl < 0 ? pill("bad", `expired ${-dl} d ago`)
      : dl < 14 ? pill("warn", `${dl} days left`) : esc(`${dl} days left`);
    tls = sec("TLS certificate", [
      domRow("Status", vpill + (t.verify_error && !t.verified ? ` <span class="muted">${esc(t.verify_error)}</span>` : "")),
      domRow("Issuer", esc(t.issuer || "—")),
      domRow("Subject", t.subject_cn ? `<span class="mono">${esc(t.subject_cn)}</span>` : ""),
      domRow("Valid until", `${domDate(t.not_after)} · ${dlView}`),
      domRow("Covers", t.san_count ? esc(`${t.san_count} name(s): ${t.sans.slice(0, 4).join(", ")}${t.san_count > 4 ? "…" : ""}`) : ""),
    ]);
  } else {
    tls = sec("TLS certificate", [
      `<div class="dom-flag warn">${ico("bang")}<span>No HTTPS on port 443${t.error ? ` — ${esc(t.error)}` : ""}</span></div>`]);
  }

  // Reputation (VirusTotal)
  let rep = "";
  const vt = r.vt;
  if (vt && vt.found && vt.error == null) {
    const verdictPill = vt.malicious ? pill("bad", `${vt.malicious} malicious`)
      : vt.suspicious ? pill("warn", `${vt.suspicious} suspicious`) : pill("good", "clean");
    rep = sec("Reputation · VirusTotal", [
      domRow("Verdict", verdictPill),
      domRow("Detections", esc(`${vt.malicious} malicious · ${vt.suspicious} suspicious · ${vt.harmless} harmless`)),
      vt.reputation != null ? domRow("Community score", esc(String(vt.reputation))) : "",
      domRow("Report", `<a href="${esc(vt.link)}" class="lnk" data-ext="1">Open on VirusTotal</a>`),
    ]);
  } else if (vt && vt.error) {
    rep = sec("Reputation · VirusTotal", [`<div class="muted" style="font-size:12px">${esc(vt.error)}</div>`]);
  } else if (vt == null) {
    rep = sec("Reputation · VirusTotal", [
      `<div class="muted" style="font-size:12px">Add a VirusTotal API key in Security → VirusTotal to include domain reputation here.</div>`]);
  }

  return `${verdict}<div class="dom-grid">${whois}${dns}${hosting}${tls}${rep}</div>`;
}

async function runDomainLookup() {
  const q = $("#domHost").value.trim();
  if (!q) return;
  const btn = $("#btnDomLookup");
  btn.disabled = true;
  $("#domStatus").innerHTML = `<span class="spin"></span> looking up…`;
  $("#domResult").innerHTML = "";
  try {
    const r = await api.lookup_domain(q);
    if (!r.ok) { $("#domStatus").innerHTML = pill("bad", r.error); return; }
    $("#domStatus").innerHTML = `<span class="muted mono">${esc(r.domain)}</span>`;
    $("#domResult").innerHTML = renderDomain(r);
  } catch (e) {
    $("#domStatus").innerHTML = pill("bad", "Lookup failed");
  } finally { btn.disabled = false; }
}
$("#btnDomLookup").onclick = runDomainLookup;
$("#domHost").addEventListener("keydown", e => { if (e.key === "Enter") runDomainLookup(); });
// open VirusTotal report links externally
$("#domResult").addEventListener("click", e => {
  const a = e.target.closest('a[data-ext="1"]');
  if (a) { e.preventDefault(); api.open_in_browser(a.getAttribute("href")); }
});

/* ---- URL / redirect unmasker ---- */
async function runUrlUnmask() {
  const q = $("#urlInput").value.trim();
  if (!q) return;
  $("#btnUrlUnmask").disabled = true;
  $("#urlStatus").innerHTML = `<span class="spin"></span> tracing…`;
  $("#urlResult").innerHTML = "";
  try {
    const r = await api.unmask_url(q);
    if (!r.ok) { $("#urlStatus").innerHTML = pill("bad", r.error); return; }
    $("#urlStatus").textContent = "";
    const flags = (r.flags || []).map(f => {
      const i = f.level === "good" ? "check" : f.level === "warn" ? "bang" : "q";
      return `<div class="dom-flag ${esc(f.level)}">${ico(i)}<span>${esc(f.text)}</span></div>`;
    }).join("");
    const chain = r.hops.map((h, i) => {
      const tag = h.shortener ? pill("info", "shortener") : "";
      const extra = h.redirects_to ? `<span class="muted"> → ${esc(h.redirects_to)}</span>`
        : h.meta_refresh ? `<span class="muted"> ⟳ meta-refresh → ${esc(h.meta_refresh)}</span>`
        : h.js_redirect ? `<span class="muted"> ⟳ JavaScript redirect (not followed)</span>`
        : h.error ? `<span style="color:var(--crit)">${esc(h.error)}</span>` : "";
      return `<div class="dr"><span class="dk">${i + 1}${h.status ? " · " + h.status : ""}</span>
        <span class="dv mono" style="font-size:11.5px; word-break:break-all">${esc(h.url)} ${tag}${extra}</span></div>`;
    }).join("");
    $("#urlResult").innerHTML = `<div class="dom-verdict">${flags}</div>
      <div class="dom-sec"><h4>Redirect chain (${r.hop_count} hop${r.hop_count === 1 ? "" : "s"})</h4>${chain}</div>`;
  } finally { $("#btnUrlUnmask").disabled = false; }
}
$("#btnUrlUnmask").onclick = runUrlUnmask;
$("#urlInput").addEventListener("keydown", e => { if (e.key === "Enter") runUrlUnmask(); });

/* ---- Wi-Fi analyzer ---- */
function signalBars(pct) {
  if (pct == null) return "";
  const cls = pct >= 67 ? "good" : pct >= 40 ? "warn" : "bad";
  return `<span class="pill ${cls}">${pct}%${" · " + (Math.round(pct / 2 - 100))} dBm</span>`;
}
$("#btnWifiScan").onclick = async () => {
  $("#wifiBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Scanning…</span></div>`;
  const r = await api.scan_wifi();
  if (!r.ok) { $("#wifiBody").innerHTML = `<div class="muted">${esc(r.error)}</div>`; return; }
  if (!r.available) {
    let cta = "";
    if (r.reason === "location_off") cta = `<button class="btn small mt" id="btnWifiLoc">Open Location settings</button>`;
    $("#wifiBody").innerHTML = `<div class="dom-flag info">${ico("q")}<span>${esc(r.message)}</span></div>${cta}`;
    $("#btnWifiLoc") && ($("#btnWifiLoc").onclick = () => api.open_settings("ms-settings:privacy-location"));
    return;
  }
  const cong = r.congestion_24 || {};
  const congLine = (cong[1] || cong[6] || cong[11])
    ? `<div class="muted" style="font-size:11.5px; margin-bottom:8px">2.4 GHz congestion — ch 1: ${cong[1] || 0} · ch 6: ${cong[6] || 0} · ch 11: ${cong[11] || 0} networks (use the least busy of 1/6/11)</div>`
    : "";
  const cur = r.current;
  const curLine = cur ? `<div class="dom-flag good" style="margin-bottom:10px">${ico("check")}<span>Connected to <b>${esc(cur.ssid || "?")}</b> · ${esc(cur.signal || "")} · ${esc(cur.band || "")} ch ${esc(cur.channel || "?")} · ${esc(cur.rx || "?")}/${esc(cur.tx || "?")} Mbps</span></div>` : "";
  $("#wifiBody").innerHTML = curLine + congLine + `<div class="table-wrap" style="max-height:340px"><table>
    <thead><tr><th>Network</th><th>Signal</th><th>Band</th><th>Ch</th><th>Radio</th><th>Security</th></tr></thead><tbody>
    ${r.aps.map(a => `<tr>
      <td class="strong">${esc(a.ssid)}<div class="muted mono" style="font-size:10.5px">${esc(a.bssid)}</div></td>
      <td>${signalBars(a.signal)}</td>
      <td class="muted">${esc(a.band || "—")}</td>
      <td class="mono">${esc(a.channel ?? "—")}</td>
      <td class="muted" style="font-size:11px">${esc(a.radio || "")}</td>
      <td class="muted" style="font-size:11px">${esc(a.auth || "")}</td>
    </tr>`).join("")}</tbody></table></div>`;
};

/* ================= PROCESSES page ================= */
let procStop = null, procPaused = false, procData = [];
let procSort = { key: "cpu", dir: -1 };
function startProcLoop() {
  if (procStop) return;   // re-selecting the page must not stack loops
  procStop = pollLoop(3000, async () => { if (!procPaused) await refreshProcs(); });
}
function stopProcLoop() { if (procStop) { procStop(); procStop = null; } }
async function refreshProcs() {
  try { procData = await api.get_processes(); renderProcs(); } catch { /* closing */ }
}
function renderProcs() {
  const q = $("#procSearch").value.trim().toLowerCase();
  const { key, dir } = procSort;
  const rows = procData
    .filter(p => !q || p.name.toLowerCase().includes(q) || p.user.toLowerCase().includes(q) || String(p.pid).includes(q))
    .sort((a, b) => {
      const av = a[key], bv = b[key];
      return (typeof av === "string" ? av.localeCompare(bv) : av - bv) * dir;
    });
  $$("#page-processes th.sortable").forEach(th => {
    th.querySelector(".arr").textContent = th.dataset.k === key ? (dir === 1 ? "↑" : "↓") : "";
  });
  $("#procBody").innerHTML = rows.slice(0, 120).map(p => `
    <tr data-pid="${p.pid}" class="proc-row" style="cursor:pointer">
      <td class="strong">${esc(p.name)}</td><td class="mono num">${p.pid}</td>
      <td>${esc(p.user || "—")}</td>
      <td class="num" style="color:${p.cpu > 25 ? "var(--warn)" : "inherit"}">${p.cpu.toFixed(1)}</td>
      <td class="num">${fmtBytes(p.mem)}</td><td>${esc(p.status)}</td>
      <td style="width:40px"><button class="btn ghost small row-action kill" title="End task">${ico("x", "ic sm")}</button></td>
    </tr>`).join("") || `<tr><td colspan="7">${emptyState("inbox", q ? `No results for "${q}"` : "No processes", q ? "Press Esc to clear the filter" : "")}</td></tr>`;
}
$$("#page-processes th.sortable").forEach(th => th.addEventListener("click", () => {
  const k = th.dataset.k;
  if (procSort.key === k) procSort.dir *= -1;
  else procSort = { key: k, dir: k === "name" || k === "user" || k === "status" ? 1 : -1 };
  renderProcs();
}));
$("#procSearch").addEventListener("input", renderProcs);
$("#btnProcPause").onclick = () => {
  procPaused = !procPaused;
  $("#btnProcPause").innerHTML = procPaused
    ? `${ico("play")}<span>Resume</span>` : `${ico("pause")}<span>Pause</span>`;
};
$("#procBody").addEventListener("click", async e => {
  const tr = e.target.closest("tr.proc-row");
  if (!tr) return;
  const pid = +tr.dataset.pid;
  if (!e.target.closest(".kill")) { openProcDrawer(pid); return; }
  const name = tr.querySelector("td").textContent;
  if (!await confirmModal("End task?", `Terminate "${name}" (PID ${pid})? Unsaved data in that program will be lost.`, "End process")) return;
  const r = await api.kill_process(pid);
  toast(r.ok ? `Ended ${r.name} (${pid})` : r.error, r.ok ? "good" : "bad");
  refreshProcs();
});

/* ================= SOFTWARE page ================= */
const swCache = {};
let curSw = "installed";
async function loadSoftware() {
  await switchSw("installed");
  api.get_startup().then(d => { swCache.startup = d; $("#cntStartup").textContent = d.length; });
  api.get_services().then(d => { swCache.services = d; $("#cntServices").textContent = d.length; });
  api.get_hotfixes().then(d => { swCache.hotfixes = d; $("#cntHotfixes").textContent = d.length; });
  api.get_scheduled_tasks().then(d => { swCache.tasks = d; $("#cntTasks").textContent = d.length; });
  api.get_extensions().then(d => { swCache.extensions = d; $("#cntExtensions").textContent = d.length; });
}
async function switchSw(kind) {
  curSw = kind;
  $$("#swTabs .tab").forEach(t => t.classList.toggle("active", t.dataset.sw === kind));
  if (kind === "appupdates") { renderAppUpdates(); return; }            // winget, on-demand
  if (kind === "updates" && !swCache.updates) { renderSw(); return; }   // on-demand, it's slow
  if (!swCache[kind]) {
    $("#swBody").innerHTML = `<div class="card"><div class="skel-block"><div class="skel"></div><div class="skel" style="width:80%"></div></div></div>`;
    swCache[kind] = await { installed: api.get_installed, startup: api.get_startup,
                            services: api.get_services, hotfixes: api.get_hotfixes,
                            tasks: api.get_scheduled_tasks, extensions: api.get_extensions }[kind]();
    if (kind === "installed") $("#cntInstalled").textContent = swCache[kind].length;
  }
  renderSw();
}
async function checkUpdates() {
  $("#swBody").innerHTML = `<div class="card"><div class="row"><span class="spin"></span>
    <span class="muted">Querying the Windows Update service — this can take up to a minute…</span></div></div>`;
  const r = await api.get_pending_updates();
  if (!r.ok) {
    $("#swBody").innerHTML = `<div class="card">${emptyState("bang", "Update search failed", r.error)}</div>`;
    return;
  }
  swCache.updates = r.updates;
  $("#cntUpdates").textContent = r.updates.length;
  renderSw();
}
$$("#swTabs .tab").forEach(t => t.addEventListener("click", () => switchSw(t.dataset.sw)));
$("#swSearch").addEventListener("input", renderSw);
function renderSw() {
  const q = $("#swSearch").value.trim().toLowerCase();
  const data = (swCache[curSw] || []).filter(x => !q || JSON.stringify(x).toLowerCase().includes(q));
  const empty = `<tr><td colspan="6">${emptyState("inbox", q ? `No results for "${q}"` : "Nothing here")}</td></tr>`;
  const tbl = (head, rows) => `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${rows || empty}</tbody></table></div>`;
  if (curSw === "installed") {
    $("#swBody").innerHTML = tbl(`<th>Application</th><th>Version</th><th>Publisher</th><th>Installed</th><th class="num">Size</th>`,
      data.map(a => `<tr><td class="strong copy">${esc(a.name)}</td><td class="mono">${esc(a.version)}</td>
        <td>${esc(a.publisher)}</td><td>${esc(a.installed)}</td><td class="num">${a.size ? fmtBytes(a.size) : "—"}</td></tr>`).join(""));
  } else if (curSw === "startup") {
    const impactPill = i => i === "High" ? pill("warn", "High") : i === "Medium" ? pill("info", "Medium") : `<span class="muted" style="font-size:11px">Low</span>`;
    $("#swBody").innerHTML = tbl(`<th>Name</th><th>State</th><th>Impact (est.)</th><th>Command</th><th>Source</th>`,
      data.map(s => `<tr><td class="strong copy">${esc(s.name)}</td>
        <td>${s.enabled === false ? pill("unknown", "Disabled") : pill("good", "Enabled")}</td>
        <td>${impactPill(s.impact)}</td>
        <td class="mono copy" style="max-width:440px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap" title="${esc(s.command)}">${esc(s.command)}</td>
        <td>${esc(s.source)}</td></tr>`).join(""));
  } else if (curSw === "services") {
    $("#swBody").innerHTML = tbl(`<th>Service</th><th>Name</th><th>Status</th><th>Start type</th><th class="num">PID</th>`,
      data.map(s => `<tr><td class="strong copy">${esc(s.display)}</td><td class="mono copy">${esc(s.name)}</td>
        <td>${s.status === "running" ? pill("good", "Running") : s.start === "automatic" ? pill("warn", "Stopped") : pill("unknown", esc(s.status))}</td>
        <td>${esc(s.start)}</td><td class="num">${s.pid ?? ""}</td></tr>`).join(""));
  } else if (curSw === "hotfixes") {
    $("#swBody").innerHTML = tbl(`<th>Hotfix</th><th>Type</th><th>Installed</th>`,
      data.map(h => `<tr><td class="strong mono copy">${esc(h.id)}</td><td>${esc(h.desc)}</td><td>${esc(h.installed ?? "—")}</td></tr>`).join(""));
  } else if (curSw === "tasks") {
    $("#swBody").innerHTML = tbl(`<th>Task</th><th>State</th><th>Last result</th><th>Last run</th><th>Action</th><th>Author</th>`,
      data.map(t => `<tr>
        <td class="strong copy">${esc(t.path === "\\" ? t.name : t.path + t.name)}</td>
        <td>${t.state === "Running" ? pill("info", "Running") : t.state === "Disabled" ? pill("unknown", "Disabled") : esc(t.state)}</td>
        <td>${t.result_ok === false ? pill("bad", t.result) : t.result_ok === true ? pill("good", t.result) : `<span class="muted">${esc(t.result)}</span>`}</td>
        <td class="mono">${esc(t.last_run ?? "—")}</td>
        <td class="mono copy" style="max-width:380px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap" title="${esc(t.action)}">${esc(t.action)}</td>
        <td class="muted">${esc(t.author)}</td></tr>`).join(""));
  } else if (curSw === "extensions") {
    $("#swBody").innerHTML = tbl(`<th>Extension</th><th>Browser</th><th>Profile</th><th>Version</th><th>State</th><th>Permissions</th>`,
      data.map(x => `<tr>
        <td class="strong copy">${esc(x.name)}</td><td>${esc(x.browser)}</td><td>${esc(x.profile)}</td>
        <td class="mono">${esc(x.version)}</td>
        <td>${x.enabled === true ? pill("good", "Enabled") : x.enabled === false ? pill("unknown", "Disabled") : `<span class="muted">—</span>`}</td>
        <td class="muted" style="max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap" title="${esc(x.permissions)}">${esc(x.permissions)}</td></tr>`).join(""));
  } else if (curSw === "updates") {
    if (!swCache.updates) {
      $("#swBody").innerHTML = `<div class="card">
        <p class="muted" style="font-size:12.5px; margin-bottom:12px">Lists pending updates from the Windows Update
        service. Benchly doesn't install them — use the deep link to finish in Settings.</p>
        <div class="row">
          <button class="btn primary" id="btnCheckUpdates">Check for updates</button>
          <button class="btn" id="btnOpenWU">Open Windows Update${ico("open", "ic sm")}</button>
        </div></div>`;
      $("#btnCheckUpdates").onclick = checkUpdates;
      $("#btnOpenWU").onclick = () => api.open_settings("ms-settings:windowsupdate");
      return;
    }
    const sevPill = s => s === "Critical" ? pill("bad", s) : s === "Important" ? pill("warn", s) : s ? pill("info", s) : `<span class="muted">—</span>`;
    $("#swBody").innerHTML = (data.length ? tbl(`<th>Update</th><th>Severity</th><th>Downloaded</th><th class="num">Size</th><th>Category</th>`,
      data.map(u => `<tr>
        <td class="strong copy" style="max-width:520px">${esc(u.title)}</td>
        <td>${sevPill(u.severity)}</td>
        <td>${u.downloaded ? pill("good", "Yes") : `<span class="muted">No</span>`}</td>
        <td class="num">${u.size_mb ? u.size_mb + " MB" : "—"}</td>
        <td class="muted">${esc(u.categories.split(",")[0] || "")}</td></tr>`).join(""))
      : `<div class="card">${emptyState("check", "No pending updates", "This machine is fully patched.")}</div>`)
      + `<div class="row mt"><button class="btn" id="btnOpenWU2">Install via Windows Update${ico("open", "ic sm")}</button>
         <button class="btn ghost" id="btnRecheckUpdates">Re-check</button></div>`;
    $("#btnOpenWU2").onclick = () => api.open_settings("ms-settings:windowsupdate");
    $("#btnRecheckUpdates").onclick = () => { swCache.updates = null; checkUpdates(); };
  }
}

/* ---- App updates (winget) ---- */
let appUpdates = null;
let appUpdateJob = null;
function renderAppUpdates() {
  if (appUpdates === null) {
    $("#swBody").innerHTML = `<div class="card">
      <p class="muted" style="font-size:12.5px; margin-bottom:12px">Finds installed apps with a newer version available
      via the Windows Package Manager (winget) and updates them — individually or all at once.</p>
      <button class="btn primary" id="btnAppScan">Check for app updates</button></div>`;
    $("#btnAppScan").onclick = scanAppUpdates;
    return;
  }
  if (appUpdates.error === "no_winget") {
    $("#swBody").innerHTML = `<div class="card">${emptyState("bang", "winget isn't available",
      "Install “App Installer” from the Microsoft Store to enable app updates.")}</div>`;
    return;
  }
  const rows = appUpdates.updates || [];
  const body = rows.length
    ? `<div class="table-wrap"><table>
        <thead><tr><th>Application</th><th>Installed</th><th>Available</th><th>Source</th><th></th></tr></thead>
        <tbody>${rows.map(u => `<tr data-appid="${esc(u.id)}">
          <td class="strong">${esc(u.name)}<div class="muted mono" style="font-size:11px">${esc(u.id)}</div></td>
          <td class="mono">${esc(u.current)}</td>
          <td class="mono" style="color:var(--ok)">${esc(u.available)}</td>
          <td class="muted">${esc(u.source)}</td>
          <td style="width:110px"><button class="btn ghost small" data-update-id="${esc(u.id)}">Update</button></td>
        </tr>`).join("")}</tbody></table></div>`
    : `<div class="card">${emptyState("check", "Everything's up to date", "No app updates available via winget.")}</div>`;
  $("#swBody").innerHTML = `<div class="row" style="margin-bottom:10px">
      ${rows.length ? `<button class="btn primary" id="btnUpdateAll">Update all (${rows.length})</button>` : ""}
      <button class="btn ghost" id="btnAppRescan">Re-check</button>
      <span class="muted" id="appUpdMsg"></span></div>
    ${body}
    <div class="card mt" id="appUpdConsoleCard" style="display:none"><h3>winget output</h3>
      <div class="console" id="appUpdConsole" style="max-height:280px"></div></div>`;
  $("#btnAppRescan") && ($("#btnAppRescan").onclick = scanAppUpdates);
  $("#btnUpdateAll") && ($("#btnUpdateAll").onclick = updateAllApps);
}
async function scanAppUpdates() {
  $("#swBody").innerHTML = `<div class="card"><div class="row"><span class="spin"></span>
    <span class="muted">Asking winget what has updates…</span></div></div>`;
  appUpdates = await api.list_app_updates();
  $("#cntAppUpdates").textContent = appUpdates.ok ? (appUpdates.count || "") : "";
  renderAppUpdates();
}
$("#swBody").addEventListener("click", async e => {
  const one = e.target.closest("[data-update-id]");
  if (!one) return;
  const id = one.dataset.updateId;
  one.disabled = true; one.textContent = "Updating…";
  const r = await api.update_app(id);
  one.textContent = r.ok ? (r.state === "reboot" ? "Reboot" : "Done") : "Failed";
  toast(r.ok ? `${id}: ${r.message}` : `${id}: ${r.message || r.error}`, r.ok ? "good" : "bad", 3500);
});
async function updateAllApps() {
  const r = await api.update_all_apps();
  if (!r.ok) { toast(r.error, "bad"); return; }
  appUpdateJob = r.job;
  $("#appUpdConsoleCard").style.display = "";
  $("#btnUpdateAll") && ($("#btnUpdateAll").disabled = true);
  const con = $("#appUpdConsole");
  con.textContent = "";
  let off = 0, fails = 0;
  const poll = async () => {
    const g = await api.get_update_all_job(appUpdateJob, off);
    if (!g.ok) { if (++fails > 8) return; return void setTimeout(poll, 800); }
    fails = 0;
    if (g.lines && g.lines.length) { off = g.total; con.textContent += g.lines.join("\n") + "\n"; con.scrollTop = con.scrollHeight; }
    if (g.done) { toast("App updates finished", g.state === "reboot" ? "warn" : "good", 3000); scanAppUpdates(); return; }
    setTimeout(poll, 900);
  };
  poll();
}

/* ================= HEALTH page ================= */
const FIX_ACTIONS = {
  av_rt: { label: "Open Windows Security", uri: "ms-settings:windowsdefender" },
  av_sig: { label: "Open Windows Security", uri: "ms-settings:windowsdefender" },
  fw: { label: "Open firewall settings", uri: "ms-settings:windowsdefender" },
  bitlocker: { label: "Open device encryption", uri: "ms-settings:deviceencryption" },
  updates: { label: "Open Windows Update", uri: "ms-settings:windowsupdate" },
  battery: { label: "Open power settings", uri: "ms-settings:powersleep" },
  diskfree: { label: "Analyze disk space", page: "storage" },
};
async function loadHealth(refresh = false) {
  if (refresh) $("#healthChecks").innerHTML = `<div class="card"><div class="skel-block"><div class="skel"></div><div class="skel" style="width:85%"></div></div></div>`;
  const h = await api.get_health(refresh);
  setRing($("#healthRing"), h.score, h.grade);
  setRing($("#dashRing"), h.score, h.grade);
  setAuditVitals(h);
  $("#healthMeta").textContent = `Audited ${h.generated}${h.is_admin ? " · elevated" : " · standard user"}`;

  const iconFor = { good: "check", warn: "bang", bad: "x", unknown: "q" };
  const cats = ["Security", "Maintenance", "Resources"];
  $("#healthChecks").innerHTML = cats.map(cat => {
    const checks = h.checks.filter(c => (c.category || "Security") === cat);
    if (!checks.length) return "";
    return `<div class="card" style="margin-bottom:12px"><h3>${cat}</h3>` + checks.map(c => {
      const fix = c.status !== "good" && c.status !== "unknown" ? FIX_ACTIONS[c.id] : null;
      return `
      <div class="check ${c.status}" title="Weight in overall score: ${c.weight}">
        <div class="icon">${ico(iconFor[c.status], "ic")}</div>
        <div class="body">
          <div class="title">${esc(c.label)} ${c.status !== "good" ? pill(c.status === "bad" ? "bad" : c.status === "warn" ? "warn" : "unknown", { warn: "Warn", bad: "Fail", unknown: "N/A" }[c.status]) : ""}</div>
          <div class="detail">${esc(c.detail)}</div>
          ${fix ? `<div class="fix"><button class="btn small" data-fix="${esc(c.id)}">${esc(fix.label)}${ico("chev", "ic sm")}</button></div>` : ""}
        </div>
      </div>`;
    }).join("") + `</div>`;
  }).join("") + (!h.is_admin ? `<div class="card" style="border-color:rgba(232,179,57,.25)">
      <div class="row">${ico("shield")}
      <div style="flex:1; font-size:12.5px" class="muted">Checks marked N/A need elevation (BitLocker, TPM, Secure Boot, SMART counters). Use <b>Run as admin</b> in the title bar.</div></div></div>` : "");
}
$("#healthChecks").addEventListener("click", e => {
  const b = e.target.closest("[data-fix]");
  if (!b) return;
  const fix = FIX_ACTIONS[b.dataset.fix];
  if (!fix) return;
  if (fix.uri) api.open_settings(fix.uri);
  else if (fix.page) { showPage(fix.page); if (fix.page === "storage") analyzePath("C:\\"); }
});
$("#btnHealthRefresh").onclick = () => loadHealth(true);

/* ================= EVENTS page ================= */
const evHidden = new Set();
let evData = null;
async function loadEvents() {
  $("#evBody").innerHTML = `<tr><td colspan="6"><div class="skel"></div></td></tr>`;
  $("#evSummaryBody").innerHTML = `<div class="card"><div class="skel-block"><div class="skel"></div><div class="skel" style="width:80%"></div></div></div>`;
  evData = await api.get_events(+$("#evDays").value);
  $("#evcCrit").textContent = evData.counts.critical ?? 0;
  $("#evcErr").textContent = evData.counts.error ?? 0;
  $("#evcWarn").textContent = evData.counts.warning ?? 0;
  renderEvents();
  renderEventSummary();
}
function renderEvents() {
  if (!evData) return;
  const note = evData.truncated
    ? `<tr><td colspan="6" class="muted" style="font-size:11.5px">Showing the newest ${evData.events.length} events — the busiest sources may go back further than ${esc(evData.oldest ?? "")}.</td></tr>`
    : "";
  const rows = evData.events.filter(e => !evHidden.has(e.level));
  $("#evBody").innerHTML = note + rows.map(e => `
    <tr><td class="mono" style="white-space:nowrap">${esc(e.time)}</td>
    <td>${pill(e.level === "warning" ? "warn" : "bad", e.level)}</td>
    <td>${esc(e.log)}</td><td class="copy">${esc(e.source)}</td><td class="num mono">${e.id}</td>
    <td class="copy" style="max-width:520px">${esc(e.message)}</td></tr>`).join("")
    || `<tr><td colspan="6">${emptyState("check", "No events in range")}</td></tr>`;
}
function refreshEventsPage() {
  loadEvents();
  if (crashesLoaded) loadCrashes();   // crash data shares the page's Refresh
}
$("#btnEvRefresh").onclick = refreshEventsPage;
$("#evDays").addEventListener("change", loadEvents);
$$("#evFilters button").forEach(b => b.addEventListener("click", () => {
  const lv = b.dataset.lv;
  evHidden.has(lv) ? evHidden.delete(lv) : evHidden.add(lv);
  b.classList.toggle("on", !evHidden.has(lv));
  renderEvents();
}));

/* ---- events: tab switching ---- */
let crashesLoaded = false;
$$("#evTabs .tab").forEach(t => t.addEventListener("click", () => {
  $$("#evTabs .tab").forEach(x => x.classList.toggle("active", x === t));
  const which = t.dataset.ev;
  $("#evTabSummary").style.display = which === "summary" ? "" : "none";
  $("#evTabLog").style.display = which === "log" ? "" : "none";
  $("#evTabCrashes").style.display = which === "crashes" ? "" : "none";
  $("#evTabTimeline").style.display = which === "timeline" ? "" : "none";
  $("#evTabBoot").style.display = which === "boot" ? "" : "none";
  if (which === "crashes" && !crashesLoaded) { crashesLoaded = true; loadCrashes(); }
  if (which === "timeline" && !timelineLoaded) { timelineLoaded = true; loadTimeline(); }
  if (which === "boot" && !bootLoaded) { bootLoaded = true; loadBoot(); }
}));

/* ---- events: boot-time breakdown ---- */
let bootLoaded = false;
async function loadBoot() {
  const r = await api.boot_performance().catch(() => null);
  const el = $("#bootBody");
  if (!r || !r.ok) { el.innerHTML = `<div class="card">${emptyState("bang", "Couldn't read boot performance")}</div>`; return; }
  const fs = r.fast_startup === true ? "on" : r.fast_startup === false ? "off" : "—";
  const head = `<div class="card" style="margin-bottom:12px">
    <div class="speed-row">
      <div class="speed-kpi"><div class="v">${r.uptime_hours != null ? r.uptime_hours : "—"}<small> h</small></div><div class="l">Uptime</div></div>
      <div class="speed-kpi"><div class="v" style="font-size:15px">${esc(r.last_boot || "—")}</div><div class="l">Last boot</div></div>
      <div class="speed-kpi"><div class="v">${fs}</div><div class="l">Fast Startup</div></div>
    </div></div>`;
  if (r.needs_admin) {
    el.innerHTML = head + `<div class="card">${emptyState("shield", "Run as admin for the full boot breakdown")}
      <p class="muted" style="font-size:12px; text-align:center">${esc(r.note || "")}</p></div>`;
    return;
  }
  const last = r.boots && r.boots[0];
  const timing = last ? `<div class="card" style="margin-bottom:12px">
    <h3>Most recent boot</h3>
    <div class="speed-row">
      <div class="speed-kpi"><div class="v">${last.total_s ?? "—"}<small> s</small></div><div class="l">Total to ready</div></div>
      <div class="speed-kpi"><div class="v">${last.to_desktop_s ?? "—"}<small> s</small></div><div class="l">To desktop</div></div>
      <div class="speed-kpi"><div class="v">${last.post_boot_s ?? "—"}<small> s</small></div><div class="l">Settling after</div></div>
    </div>
    ${last.degraded ? `<div class="dom-flag warn" style="margin-top:10px">${ico("bang")}<span>Windows flagged this boot as slower than usual.</span></div>` : ""}
  </div>` : `<div class="card" style="margin-bottom:12px">${emptyState("check", "No boot-timing events recorded yet")}</div>`;
  const deg = (r.degraders && r.degraders.length) ? `<div class="card" style="margin-bottom:12px">
    <h3>What slowed boot down <span class="right muted" style="font-size:11px">named by Windows, worst first</span></h3>
    <div class="table-wrap" style="max-height:300px"><table>
      <thead><tr><th>Type</th><th>Name</th><th class="num">Added</th><th>When</th></tr></thead><tbody>
      ${r.degraders.map(d => `<tr><td>${pill(d.kind === "Driver" || d.kind === "Device" ? "warn" : "info", d.kind)}</td>
        <td class="strong copy">${esc(d.name)}</td><td class="num mono">${d.seconds}s</td>
        <td class="mono muted">${esc(d.time || "—")}</td></tr>`).join("")}
    </tbody></table></div></div>` : "";
  const recent = (r.boots && r.boots.length > 1) ? `<div class="card">
    <h3>Recent boots</h3>
    <div class="table-wrap" style="max-height:240px"><table>
      <thead><tr><th>When</th><th class="num">Total</th><th class="num">To desktop</th><th></th></tr></thead><tbody>
      ${r.boots.map(b => `<tr><td class="mono">${esc(b.time || "—")}</td><td class="num mono">${b.total_s ?? "—"}s</td>
        <td class="num mono">${b.to_desktop_s ?? "—"}s</td><td>${b.degraded ? pill("warn", "slow") : ""}</td></tr>`).join("")}
    </tbody></table></div></div>` : "";
  el.innerHTML = head + timing + deg + recent;
}

/* ---- events: triage knowledge base ----
   Curated explanations for the sources a bench tech meets constantly.
   match(source, id) → true selects the entry. */
const EVENT_KNOWLEDGE = [
  { match: (s, id) => /DistributedCOM/i.test(s) && (id === 10016 || id === 10010),
    title: "Component permission noise",
    advice: "DCOM permission warnings between Windows components. Microsoft ships these misconfigured; they are safe to ignore.", benign: true },
  { match: (s, id) => /Application Hang/i.test(s) || id === 1002 && /Application/i.test(s),
    title: "A program stopped responding",
    advice: "Windows recorded an app hang. If it repeats for the same program, check the Crashes tab and update or reinstall that application.",
    action: { label: "Open Crashes", run: () => { $(`#evTabs [data-ev="crashes"]`).click(); } } },
  { match: s => /Application Error|Windows Error Reporting|\.NET Runtime/i.test(s),
    title: "Application crash",
    advice: "A program crashed. The Crashes tab groups these by application and faulting module.",
    action: { label: "Open Crashes", run: () => { $(`#evTabs [data-ev="crashes"]`).click(); } } },
  { match: s => /Service Control Manager/i.test(s),
    title: "A service failed or crashed",
    advice: "A Windows service terminated or failed to start. Find the service named in the message under Software → Services; if third-party, update or reinstall its application.",
    action: { label: "Open Services", run: () => { showPage("software"); switchSw("services"); } } },
  { match: s => /^disk$|^Ntfs$|volsnap|storahci|stornvme|iaStor/i.test(s),
    title: "Storage subsystem errors",
    advice: "Disk or filesystem errors — the classic early warning of a failing drive or loose cable. Check SMART health under Storage and back up the machine before anything else.",
    action: { label: "Check disks", run: () => showPage("storage") } },
  { match: s => /WHEA-Logger/i.test(s),
    title: "Hardware machine-check",
    advice: "The CPU reported a hardware error (WHEA). Common causes: unstable overclock/XMP, failing RAM, power delivery. Test memory and revert overclocks.", },
  { match: (s, id) => /Kernel-Power/i.test(s) && id === 41,
    title: "Unexpected power loss",
    advice: "The machine lost power or hard-hung without a clean shutdown. If not a forced power-off, suspect PSU, sleep/firmware bugs or overheating.",
    action: { label: "Open Crashes", run: () => { $(`#evTabs [data-ev="crashes"]`).click(); } } },
  { match: s => /BugCheck/i.test(s),
    title: "Blue screen",
    advice: "Windows crashed with a bugcheck. The Crashes tab lists codes and minidumps.",
    action: { label: "Open Crashes", run: () => { $(`#evTabs [data-ev="crashes"]`).click(); } } },
  { match: s => /DNS Client/i.test(s),
    title: "Name resolution problems",
    advice: "DNS lookups are timing out. Often transient; if frequent, test the DNS server under Network and try flushing the resolver cache.",
    action: { label: "Open Network", run: () => showPage("network") } },
  { match: s => /Time-Service/i.test(s),
    title: "Clock synchronisation",
    advice: "Windows had trouble syncing time. Usually self-heals; persistent drift on a domain suggests DC connectivity issues.", benign: true },
  { match: s => /Schannel/i.test(s),
    title: "TLS handshake noise",
    advice: "A TLS connection was rejected or downgraded. Almost always harmless background noise from apps probing protocols.", benign: true },
  { match: s => /WindowsUpdateClient/i.test(s),
    title: "Windows Update failure",
    advice: "An update failed to download or install. Check Software → Pending updates; the Toolbox can reset the update cache.",
    action: { label: "Open Toolbox", run: () => showPage("toolbox") } },
  { match: s => /nvlddmkm|amdkmdag|igfx|Display/i.test(s),
    title: "Graphics driver reset",
    advice: "The GPU driver stopped responding and was recovered (TDR). Update the graphics driver; if it persists under load, check GPU temperatures.", },
  { match: s => /PrintService|Print/i.test(s),
    title: "Printing problems",
    advice: "Print subsystem errors. The Devices page shows queue state and can purge stuck jobs.",
    action: { label: "Open Devices", run: () => showPage("devices") } },
  { match: s => /Kernel-PnP/i.test(s),
    title: "Device configuration",
    advice: "A device failed to start or was misconfigured. Check Devices for anything flagged with an error code.",
    action: { label: "Open Devices", run: () => showPage("devices") } },
];

function renderEventSummary() {
  if (!evData) return;
  const groups = new Map();
  for (const e of evData.events) {
    const key = `${e.source}|${e.id}`;
    let g = groups.get(key);
    if (!g) {
      g = { source: e.source, id: e.id, count: 0, level: e.level,
            sample: e.message, last: e.time };
      groups.set(key, g);
    }
    g.count++;
    if (e.level === "critical" || (e.level === "error" && g.level === "warning")) g.level = e.level;
    if (e.time > g.last) { g.last = e.time; g.sample = e.message; }
  }
  const rows = [...groups.values()].map(g => {
    const kb = EVENT_KNOWLEDGE.find(k => { try { return k.match(g.source || "", g.id); } catch { return false; } });
    return { ...g, kb };
  }).sort((a, b) =>
    (a.kb?.benign === true) - (b.kb?.benign === true) ||
    ({ critical: 0, error: 1, warning: 2 }[a.level] - { critical: 0, error: 1, warning: 2 }[b.level]) ||
    b.count - a.count);

  window._evSummaryActions = rows.map(r => r.kb?.action?.run || null);
  $("#evSummaryBody").innerHTML = rows.length ? `<div class="card">` + rows.map((g, i) => `
    <div class="check ${g.level === "warning" ? "warn" : "bad"}${g.kb?.benign ? " unknown" : ""}">
      <div class="icon">${ico(g.kb?.benign ? "check" : g.level === "warning" ? "bang" : "x")}</div>
      <div class="body">
        <div class="title">${esc(g.kb?.title || g.source)}
          <span class="muted" style="font-weight:400; font-size:11.5px">${esc(g.source)} · ID ${g.id}</span>
          ${pill(g.kb?.benign ? "unknown" : g.level === "warning" ? "warn" : "bad", `×${g.count}`)}
        </div>
        <div class="detail">${esc(g.kb?.advice || "No specific guidance for this source — review the raw log entry below.")}</div>
        <div class="detail muted" style="font-size:11.5px; margin-top:3px">Last ${esc(g.last)} — ${esc((g.sample || "").slice(0, 140))}</div>
        ${g.kb?.action ? `<div class="fix"><button class="btn small" data-evact="${i}">${esc(g.kb.action.label)}${ico("chev", "ic sm")}</button></div>` : ""}
      </div>
    </div>`).join("") + `</div>`
    : `<div class="card">${emptyState("check", "No errors or warnings in this period")}</div>`;
}
$("#evSummaryBody").addEventListener("click", e => {
  const b = e.target.closest("[data-evact]");
  const run = b && window._evSummaryActions[+b.dataset.evact];
  if (run) run();
});
async function loadCrashes() {
  const c = await api.get_crashes();
  const bsod = c.bugchecks.length
    ? `<div class="table-wrap" style="max-height:240px"><table>
        <thead><tr><th>Time</th><th>Stop code</th><th>Name</th><th>Dump</th></tr></thead><tbody>
        ${c.bugchecks.map(b => `<tr><td class="mono">${esc(b.time)}</td>
          <td class="mono copy">${esc(b.hex || b.code)}</td>
          <td class="mono" style="font-size:11px">${esc(b.name || "—")}</td>
          <td class="mono copy">${esc(b.dump)}</td></tr>`).join("")}
        </tbody></table></div>`
    : emptyState("check", "No blue screens in the last 90 days");
  const kpower = (c.kernel_power || []).length
    ? `<div class="table-wrap mt" style="max-height:180px"><table>
        <thead><tr><th>Time</th><th>Stop code</th><th>Name</th></tr></thead><tbody>
        ${c.kernel_power.map(k => `<tr><td class="mono">${esc(k.time)}</td>
          <td class="mono copy">${esc(k.hex)}</td><td class="mono" style="font-size:11px">${esc(k.name || "—")}</td></tr>`).join("")}
        </tbody></table></div>`
    : "";
  const dumps = c.minidumps.length
    ? `<div class="mt">${c.minidumps.map(d => `<div class="an-row">${ico("file", "ic sm")}
        <span class="nm">${esc(d.file)}</span><span class="muted">${esc(d.date)}</span>
        <span class="sz">${fmtBytes(d.size)}</span></div>`).join("")}
      <button class="btn small mt" id="btnOpenDumps">Open minidump folder${ico("open", "ic sm")}</button></div>`
    : "";
  // Parse the dumps for the third-party drivers loaded at crash time — the usual culprits.
  const md = await api.analyze_minidumps().catch(() => null);
  const suspects = (md && md.ok) ? [...new Set(md.dumps.flatMap(d => d.suspect_drivers || []))] : [];
  const mdumpBlock = suspects.length
    ? `<div class="mt"><div class="muted" style="font-size:12px; margin-bottom:4px">Third-party drivers loaded in the crash dumps — the usual BSOD suspects:</div>
        <div style="display:flex; flex-wrap:wrap; gap:4px">${suspects.map(s => pill("warn", esc(s))).join("")}</div></div>`
    : "";
  const apps = c.app_crashes.length
    ? `<div class="table-wrap" style="max-height:320px"><table>
        <thead><tr><th>Application</th><th class="num">Crashes</th><th>Faulting module</th><th>Most recent</th></tr></thead><tbody>
        ${c.app_crashes.map(g => `<tr><td class="strong copy">${esc(g.app)}</td>
          <td class="num" style="color:${g.count >= 10 ? "var(--crit)" : "inherit"}">${g.count}</td>
          <td class="mono copy">${esc(g.module)}</td><td class="mono">${esc(g.last)}</td></tr>`).join("")}
        </tbody></table></div>`
    : emptyState("check", "No application crashes in the last 90 days");
  $("#crashBody").innerHTML = `
    <div class="grid cols-2">
      <div class="card"><h3>Blue screens (90 days) <span class="right">${c.bugchecks.length ? pill("bad", c.bugchecks.length + " bugcheck(s)") : pill("good", "None")}</span></h3>${bsod}${dumps}${mdumpBlock}</div>
      <div class="card"><h3>Unexpected power loss <span class="right">${c.dirty_shutdowns ? pill("warn", c.dirty_shutdowns + " event(s)") : pill("good", "None")}</span></h3>
        <p class="muted" style="font-size:12.5px; line-height:1.5">Kernel-Power 41 events — the machine lost power or hung without a clean shutdown. Frequent occurrences point at PSU, sleep/firmware or forced power-offs.${(c.kernel_power || []).length ? " The events below carried a Stop code — a blue screen, not just a power cut." : ""}</p>${kpower}</div>
    </div>
    <div class="card mt"><h3>Application crashes, grouped (90 days)</h3>${apps}</div>`;
  const openDumps = $("#btnOpenDumps");
  if (openDumps) openDumps.onclick = () => api.open_path(c.dump_dir);
}

/* ================= DEVICES page ================= */
async function loadDevices() {
  api.get_problem_devices().then(d => {
    const list = d.problems.length
      ? d.problems.map(p => `
        <div class="check bad">
          <div class="icon">${ico("bang")}</div>
          <div class="body">
            <div class="title">${esc(p.name)} ${pill("bad", "Code " + p.code)}</div>
            <div class="detail">${esc(p.meaning)} · class ${esc(p.class)}</div>
            <div class="detail mono copy" style="font-size:11px">${esc(p.device_id)}</div>
          </div>
        </div>`).join("")
      : emptyState("check", "Every device reports healthy", `${d.total_devices ?? "?"} devices enumerated`);
    $("#devBody").innerHTML = `<div class="card">
      <h3>Problem devices <span class="right">${d.problems.length ? pill("bad", d.problems.length + " issue(s)") : pill("good", "All clear")}</span></h3>${list}</div>`;
  }).catch(() => { $("#devBody").innerHTML = `<div class="card">${emptyState("bang", "Couldn't load devices")}</div>`; });
  api.printer_doctor().then(p => {
    const spoolerOk = p.spooler === "Running";
    const banner = (p.flags || []).map(f => {
      const i = f.level === "good" ? "check" : f.level === "warn" ? "bang" : "q";
      return `<div class="dom-flag ${esc(f.level)}">${ico(i)}<span>${esc(f.text)}</span></div>`;
    }).join("");
    const printers = p.printers.length ? `<div class="table-wrap" style="max-height:none"><table>
      <thead><tr><th>Printer</th><th>Status</th><th>Address</th><th>Driver</th><th></th></tr></thead><tbody>
      ${p.printers.map((x, i) => `<tr>
        <td class="strong copy">${esc(x.name)}${x.default ? ` <span class="muted" style="font-size:11px">· default</span>` : ""}
          ${x.issues.length ? `<div class="muted" style="font-size:11px">${esc(x.issues.join(" · "))}</div>` : ""}</td>
        <td>${x.offline ? pill("warn", "Offline") : x.reachable === false ? pill("bad", "Unreachable") : x.status === "Idle" ? pill("good", "Idle") : pill("info", esc(x.status))}</td>
        <td class="mono">${esc(x.host || x.port)}</td><td class="muted">${esc(x.driver || "")}</td>
        <td style="white-space:nowrap">${x.offline ? `<button class="btn ghost small" data-prn-online="${esc(x.name)}">Bring online</button>` : ""}
          <button class="btn ghost small" data-prn-test="${esc(x.name)}">Test page</button></td></tr>`).join("")}
      </tbody></table></div>` : emptyState("printer", "No printers installed");
    $("#prnBody").innerHTML = `<div class="card">
      <h3>Printer doctor
        <span class="right row" style="gap:8px">
          ${spoolerOk ? pill("good", "Spooler running") : pill("bad", "Spooler " + esc(p.spooler))}
          <button class="btn small" id="btnPrnRescan">Re-check</button>
          <button class="btn small danger" id="btnPurgeQueue" title="Stop spooler, delete stuck jobs, restart">Purge queue</button>
        </span>
      </h3>${banner}${printers}</div>`;
    $("#btnPrnRescan").onclick = loadDevices;
    $("#btnPurgeQueue").onclick = async () => {
      if (!await confirmModal("Purge print queue?",
          "Stops the spooler, deletes every queued job on all printers, and restarts it.", "Purge",
          "Stops the Spooler service, deletes all files in\nC:\\Windows\\System32\\spool\\PRINTERS, then restarts it.")) return;
      const r = await api.purge_print_queue();
      toast(r.ok ? "Print queue purged" : r.error, r.ok ? "good" : "bad", 5000);
      if (r.ok) loadDevices();
    };
    $("#prnBody").querySelectorAll("[data-prn-online]").forEach(b => b.onclick = async () => {
      const r = await api.printer_clear_offline(b.dataset.prnOnline);
      toast(r.ok ? "Brought the printer back online" : r.error, r.ok ? "good" : "bad", 4000);
      if (r.ok) loadDevices();
    });
    $("#prnBody").querySelectorAll("[data-prn-test]").forEach(b => b.onclick = async () => {
      const r = await api.printer_testpage(b.dataset.prnTest);
      toast(r.ok ? "Test page sent" : r.error, r.ok ? "good" : "bad", 4000);
    });
  }).catch(() => { $("#prnBody").innerHTML = `<div class="card">${emptyState("printer", "Couldn't load printers")}</div>`; });
  api.get_driver_audit().then(d => {
    const flag = x => x.duplicate ? pill("warn", "Duplicate") : x.old ? pill("warn", "Old") : "";
    $("#drvBody").innerHTML = `<div class="card">
      <h3>Third-party drivers (${d.drivers.length})
        <span class="right">${d.dup_count ? pill("warn", `${d.dup_count} duplicate`) : ""}
        ${d.old_count ? pill("warn", `${d.old_count} older than ${d.old_years} yrs`) : ""}
        ${!d.dup_count && !d.old_count ? pill("good", "Tidy") : ""}</span>
      </h3>
      ${d.drivers.length ? `<div class="table-wrap" style="max-height:340px"><table>
        <thead><tr><th>Device</th><th>Provider</th><th>Version</th><th>Date</th><th></th><th>INF</th></tr></thead><tbody>
        ${d.drivers.map(x => `<tr>
          <td class="strong copy">${esc(x.device)}</td><td>${esc(x.provider)}</td>
          <td class="mono copy">${esc(x.version)}</td><td class="mono">${esc(x.date ?? "—")}</td>
          <td>${flag(x)}</td><td class="mono copy" style="font-size:11px">${esc(x.inf)}</td></tr>`).join("")}
        </tbody></table></div>
        <p class="muted" style="font-size:11.5px; margin-top:8px">Duplicates mean a device has more than one
        driver version staged. To remove a stale one: <span class="mono copy">pnputil /delete-driver &lt;inf&gt;</span>
        from an elevated prompt — only after confirming the newer version works.</p>`
      : emptyState("check", "No third-party drivers found")}
    </div>`;
  }).catch(() => { $("#drvBody").innerHTML = `<div class="card">${emptyState("bang", "Couldn't load drivers")}</div>`; });
  api.get_usb_history().then(u => {
    $("#usbBody").innerHTML = `<div class="card">
      <h3>USB device history (${u.count}) <span class="right muted" style="font-size:11px">every USB device ever connected</span></h3>
      ${u.devices.length ? `<div class="table-wrap" style="max-height:300px"><table>
        <thead><tr><th>Device</th><th>Type</th><th>Serial</th></tr></thead><tbody>
        ${u.devices.map(d => `<tr><td class="strong copy">${esc(d.name)}</td><td>${esc(d.kind)}</td>
          <td class="mono copy">${esc(d.serial)}</td></tr>`).join("")}</tbody></table></div>`
      : emptyState("usb", "No USB history found")}</div>`;
  }).catch(() => { $("#usbBody").innerHTML = `<div class="card">${emptyState("usb", "Couldn't load USB history")}</div>`; });
}
$("#btnDevRefresh").onclick = () => loadDevices();

/* ================= TOOLBOX page ================= */
let repairJob = null, repairOffset = 0, repairTimer = null;
async function loadToolbox() {
  const tools = await api.list_repair_tools();
  $("#toolGrid").innerHTML = tools.map(t => `
    <div class="tool-card" data-tool="${t.id}">
      <div class="t-name">${ico("wrench", "ic sm")}${esc(t.label)}</div>
      <div class="t-note">${esc(t.note)}</div>
      <div class="t-note" style="font-size:11px; opacity:0.8; min-height:0; margin-top:-4px">
        <span class="muted" title="${esc(t.where)}">${esc(t.where)}</span>
      </div>
      <button class="btn small" data-run="${t.id}" data-where="${esc(t.where)}">Run</button>
    </div>`).join("");
  refreshBaselineInfo();
  loadTicketSummary();
  loadMemResults();
  loadRestoreCard();
  // Auto-run the cheap, read-only pending-restart check on open — it's fast, needs no
  // elevation, and is high-signal, so the page shows real data instead of a bare button.
  $("#btnRebootCheck")?.click();
}
async function loadRestoreCard() {
  const s = await api.restore_status();
  $("#rpStatus").textContent = s.protection_on === false ? "protection off" : `${s.points.length} point(s)`;
  $("#rpList").innerHTML = s.points.length ? `<div class="table-wrap" style="max-height:170px"><table>
    <thead><tr><th>Created</th><th>Description</th><th>Type</th></tr></thead><tbody>
    ${s.points.slice(0, 12).map(p => `<tr><td class="mono">${esc(p.created || "—")}</td>
      <td class="strong">${esc(p.description)}</td><td class="muted">${esc(p.type)}</td></tr>`).join("")}
    </tbody></table></div>` : `<p class="muted" style="font-size:12px">No restore points yet.</p>`;
}
/* ---- Error-code decoder ---- */
const decodeErrCode = async () => {
  const code = $("#errInput").value.trim();
  if (!code) return;
  $("#errResult").innerHTML = `<div class="muted" style="font-size:12.5px">Decoding…</div>`;
  const r = await api.decode_error(code);
  if (!r.ok) { $("#errResult").innerHTML = `<div class="muted" style="font-size:12.5px">${esc(r.error)}</div>`; return; }
  const interps = r.interpretations.length
    ? r.interpretations.map(i => `<div class="an-row">${ico("q", "ic sm")}
        <span class="nm">${esc(i.source)}</span><span class="muted">${esc(i.text)}</span></div>`).join("")
    : `<div class="muted" style="font-size:12.5px">No description found — it may not be a standard Windows code.</div>`;
  $("#errResult").innerHTML = `
    <div class="row" style="gap:12px; align-items:center; margin-bottom:8px; flex-wrap:wrap">
      <span class="mono strong">${esc(r.hex)}</span>
      <span class="muted">${r.decimal}</span>
      ${pill(r.severity === "Failure" ? "bad" : "good", esc(r.severity))}
      <span class="muted" style="font-size:12px">facility: ${esc(r.facility_name)}</span>
    </div>${interps}`;
};
$("#btnErrDecode").onclick = decodeErrCode;
$("#errInput").addEventListener("keydown", e => { if (e.key === "Enter") decodeErrCode(); });

/* ---- User profile health ---- */
$("#btnProfChk").onclick = async () => {
  $("#profBody").innerHTML = `<div class="muted" style="font-size:12.5px">Scanning profiles…</div>`;
  const r = await api.detect_profiles();
  if (!r || !r.profiles) { $("#profBody").innerHTML = emptyState("bang", "Couldn't read profiles"); return; }
  const rows = r.profiles.map(p => `<tr>
    <td class="strong">${esc(p.account || "—")}</td>
    <td class="mono" style="font-size:11px">${esc(p.path || "")}</td>
    <td>${p.problem ? pill("bad", esc(p.issue || "problem")) : pill("good", "OK")}</td></tr>`).join("");
  $("#profBody").innerHTML = `
    <div style="margin-bottom:8px">${r.problems ? pill("bad", r.problems + " problem profile(s)") : pill("good", "All profiles healthy")}</div>
    <div class="table-wrap" style="max-height:240px"><table>
      <thead><tr><th>Account</th><th>Profile path</th><th>State</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
};

/* ---- What's locking this file? ---- */
$("#btnFindLockers").onclick = async () => {
  const path = $("#lockInput").value.trim();
  if (!path) return;
  $("#lockResult").innerHTML = `<div class="muted" style="font-size:12.5px">Searching for open handles…</div>`;
  const r = await api.find_lockers(path);
  if (!r.ok) { $("#lockResult").innerHTML = `<div class="muted" style="font-size:12.5px">${esc(r.error)}</div>`; return; }
  if (!r.lockers.length) {
    $("#lockResult").innerHTML = emptyState("check", "Nothing is holding that open", "No process has an open handle to it");
    return;
  }
  $("#lockResult").innerHTML = `<div class="table-wrap" style="max-height:240px"><table>
    <thead><tr><th>Process</th><th class="num">PID</th><th>Open handle</th></tr></thead>
    <tbody>${r.lockers.map(l => `<tr><td class="strong">${esc(l.name)}</td>
      <td class="num mono">${l.pid}</td><td class="mono" style="font-size:11px">${esc(l.file)}</td></tr>`).join("")}</tbody></table></div>`;
};

/* ---- File hash ---- */
$("#btnHashPick").onclick = async () => {
  const pick = await api.pick_file();
  if (!pick.ok) return;
  $("#hashName").textContent = "hashing…";
  $("#hashResult").innerHTML = "";
  const r = await api.hash_file(pick.path);
  if (!r.ok) { $("#hashName").textContent = ""; $("#hashResult").innerHTML = `<div class="muted" style="font-size:12.5px">${esc(r.error)}</div>`; return; }
  $("#hashName").textContent = `${r.name} · ${fmtBytes(r.size)}`;
  const row = (label, val) => `<div style="margin:4px 0; display:flex; gap:10px; align-items:baseline">
    <span class="muted" style="width:58px; flex:none">${label}</span>
    <span class="mono copy" style="font-size:11px; word-break:break-all">${esc(val)}</span></div>`;
  $("#hashResult").innerHTML = row("MD5", r.md5) + row("SHA-1", r.sha1) + row("SHA-256", r.sha256);
};

/* ---- Hosts file viewer ---- */
$("#btnHosts").onclick = async () => {
  $("#hostsBody").innerHTML = `<div class="muted" style="font-size:12.5px">Reading…</div>`;
  const r = await api.view_hosts();
  if (!r.ok) { $("#hostsBody").innerHTML = `<div class="muted" style="font-size:12.5px">${esc(r.error)}</div>`; return; }
  const rows = r.entries.length
    ? `<div class="table-wrap" style="max-height:220px"><table>
        <thead><tr><th>IP</th><th>Host</th></tr></thead><tbody>
        ${r.entries.map(e => `<tr><td class="mono">${esc(e.ip)}</td>
          <td class="mono">${esc(e.host)} ${e.flagged ? pill("warn", "non-default") : ""}</td></tr>`).join("")}
        </tbody></table></div>`
    : `<div class="muted" style="font-size:12.5px">${esc(r.summary)}</div>`;
  $("#hostsBody").innerHTML = `<div style="margin-bottom:6px">${r.flagged ? pill("warn", r.flagged + " non-default") : pill("good", "Default")}</div>${rows}`;
};

/* ---- Performance snapshot ("why slow now") ---- */
let lastSnapshot = null;
$("#btnSnapStart").onclick = async () => {
  const btn = $("#btnSnapStart");
  btn.disabled = true;
  $("#btnSnapCopy").style.display = "none";
  $("#snapResult").innerHTML = "";
  $("#snapBar").style.display = "";
  $("#snapBarFill").style.width = "0%";
  const r = await api.start_snapshot(30);
  if (!r.ok) { toast(r.error, "bad"); btn.disabled = false; $("#snapBar").style.display = "none"; return; }
  $("#snapStatus").textContent = `sampling ${r.window}s…`;
  const poll = async () => {
    const g = await api.get_snapshot(r.job);
    if (!g.ok) { btn.disabled = false; return; }
    $("#snapBarFill").style.width = (g.progress || 0) + "%";
    if (!g.done) { setTimeout(poll, 700); return; }
    $("#snapBar").style.display = "none";
    $("#snapStatus").textContent = "";
    btn.disabled = false;
    renderSnapshot(g.result);
  };
  poll();
};
function renderSnapshot(s) {
  if (!s) { $("#snapResult").innerHTML = `<div class="muted">No data.</div>`; return; }
  lastSnapshot = s;
  $("#btnSnapCopy").style.display = "";
  const c = s.counters || {};
  const kpis = `<div class="speed-row">
    <div class="speed-kpi"><div class="v">${s.sys_cpu}<small>%</small></div><div class="l">CPU</div></div>
    <div class="speed-kpi"><div class="v">${s.mem_pct}<small>%</small></div><div class="l">Memory (${s.mem_avail_mb} MB free)</div></div>
    <div class="speed-kpi"><div class="v">${(s.disk_read_mbs + s.disk_write_mbs).toFixed(1)}<small> MB/s</small></div><div class="l">Disk I/O</div></div>
    ${c.disk_queue != null ? `<div class="speed-kpi"><div class="v">${c.disk_queue}</div><div class="l">Disk queue</div></div>` : ""}
  </div>`;
  const tbl = (title, rows, val) => `<div class="dom-sec"><h4>${title}</h4>${
    rows.map(r => `<div class="dr"><span class="dk strong">${esc(r.name)}</span><span class="dv">${val(r)}</span></div>`).join("") || `<div class="muted">—</div>`}</div>`;
  $("#snapResult").innerHTML = kpis + `<div class="dom-grid" style="margin-top:12px">
    ${tbl("Top CPU", s.top_cpu, r => r.cpu + "%")}
    ${tbl("Top memory", s.top_mem, r => r.rss_mb + " MB")}
    ${tbl("Top disk", s.top_disk, r => r.disk_kb + " KB")}</div>`;
}
$("#btnSnapCopy").onclick = () => {
  if (!lastSnapshot) return;
  const s = lastSnapshot;
  const lines = [`Benchly performance snapshot (${s.window}s)`,
    `CPU ${s.sys_cpu}%  |  Memory ${s.mem_pct}% (${s.mem_avail_mb} MB free)  |  Disk ${(s.disk_read_mbs + s.disk_write_mbs).toFixed(1)} MB/s`,
    s.counters && s.counters.disk_queue != null ? `Disk queue ${s.counters.disk_queue}  |  Commit ${s.counters.commit_pct}%` : "",
    "", "Top CPU: " + s.top_cpu.map(r => `${r.name} ${r.cpu}%`).join(", "),
    "Top memory: " + s.top_mem.map(r => `${r.name} ${r.rss_mb}MB`).join(", "),
    "Top disk: " + s.top_disk.map(r => `${r.name} ${r.disk_kb}KB`).join(", ")];
  navigator.clipboard.writeText(lines.filter(Boolean).join("\n")).then(() => toast("Snapshot copied", "good", 1800));
};

/* ---- Power, sleep & wake doctor ---- */
function flagRow(f) {
  const i = f.level === "good" ? "check" : f.level === "warn" ? "bang" : "q";
  return `<div class="dom-flag ${esc(f.level)}">${ico(i)}<span>${esc(f.text)}</span></div>`;
}
$("#btnPowerScan").onclick = async () => {
  $("#powerBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Asking powercfg…</span></div>`;
  const r = await api.power_overview();
  if (!r.ok) { $("#powerBody").innerHTML = `<div class="muted">${esc(r.error || "Failed.")}</div>`; return; }
  const sec = (title, body) => body ? `<div class="dom-sec"><h4>${title}</h4>${body}</div>` : "";
  const blockers = r.requests.admin
    ? (r.requests.blockers.length
        ? r.requests.blockers.map(b => `<div class="dr"><span class="dk">${esc(b.category)}</span><span class="dv">${esc(b.what)}</span></div>`).join("")
        : `<div class="muted" style="font-size:12px">Nothing is keeping the PC awake right now.</div>`)
    : `<div class="muted" style="font-size:12px">Run as admin to see this.</div>`;
  const timers = r.wake_timers.admin
    ? (r.wake_timers.timers.length
        ? r.wake_timers.timers.map(t => `<div class="dr"><span class="dk strong">timer</span><span class="dv">${esc(t.reason || t.owner)}</span></div>`).join("")
        : `<div class="muted" style="font-size:12px">No wake timers are armed.</div>`)
    : `<div class="muted" style="font-size:12px">Run as admin to see this.</div>`;
  const devices = r.wake_devices.length
    ? `<div class="row wrap" style="gap:6px">${r.wake_devices.map(d => `<span class="pill info" title="Can wake the PC">${esc(d)}</span>`).join("")}</div>`
    : `<div class="muted" style="font-size:12px">No devices are armed to wake the PC.</div>`;
  $("#powerBody").innerHTML = `<div class="dom-verdict">${(r.flags || []).map(flagRow).join("")}</div>
    <div class="dom-grid">
      ${sec("Keeping it awake now", blockers)}
      ${sec("Wake timers", timers)}
      ${sec("Devices allowed to wake it", devices)}
      ${sec("Sleep states available", `<div class="muted" style="font-size:12px">${esc(r.sleep_states.join(" · ") || "—")}${r.modern_standby ? " · Modern Standby (S0)" : ""}</div>`)}
      ${r.last_wake ? sec("Last wake", `<div class="muted" style="font-size:12px">${esc(r.last_wake)}</div>`) : ""}
    </div>`;
};

/* ---- Pending restart ---- */
$("#btnRebootCheck").onclick = async () => {
  $("#rebootBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Checking servicing signals…</span></div>`;
  const r = await api.pending_reboot().catch(() => null);
  if (!r || !r.ok) { $("#rebootBody").innerHTML = `<div class="muted">Couldn't read the reboot signals.</div>`; return; }
  const verdict = r.pending
    ? `<div class="dom-flag warn">${ico("bang")}<span>${esc(r.summary)}</span></div>`
    : `<div class="dom-flag good">${ico("check")}<span>${esc(r.summary)}</span></div>`;
  const rows = r.signals.map(s => `<div class="dr">
    <span class="dk">${s.set ? ico("bang", "ic sm") : ico("check", "ic sm")} ${esc(s.label)}</span>
    <span class="dv"><span class="${s.set ? "strong" : "muted"}">${s.set ? "waiting on reboot" : "clear"}</span>
      <div class="muted" style="font-size:11px; line-height:1.45; margin-top:2px">${esc(s.detail)}</div>
      <div class="mono" style="font-size:10.5px; opacity:.6; margin-top:2px">${esc(s.where)}</div></span></div>`).join("");
  const action = r.pending
    ? `<div class="row" style="margin-top:10px"><button class="btn danger small" id="btnRebootNow">Restart now…</button>
        <span class="muted" style="font-size:11.5px">Saves nothing for you — close your work first.</span></div>`
    : "";
  $("#rebootBody").innerHTML = verdict + `<div class="dom-sec" style="margin-top:10px">${rows}</div>` + action;
  const nowBtn = $("#btnRebootNow");
  if (nowBtn) nowBtn.onclick = async () => {
    if (!confirm("Restart this PC now? Make sure your work is saved — this gives a 10-second warning then restarts.")) return;
    nowBtn.disabled = true;
    const x = await api.restart_now();
    toast(x.ok ? "Restarting in 10 seconds…" : (x.error || "Couldn't restart"), x.ok ? "good" : "bad");
  };
};

/* ---- Update doctor (WU history + service health) ---- */
$("#btnWuCheck").onclick = async () => {
  $("#wuBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Reading update history…</span></div>`;
  const [h, health] = await Promise.all([
    api.wu_history(30).catch(() => null),
    api.wu_health().catch(() => null),
  ]);
  if (!h || !h.ok) { $("#wuBody").innerHTML = `<div class="muted">Couldn't read the update history.</div>`; return; }
  const hd = health && health.ok ? health : null;
  const svcConcern = hd && hd.services.some(s => s.concern);
  const healthRow = hd ? `<div class="dom-grid" style="margin-bottom:12px">
    <div class="dom-sec"><h4>Last activity</h4>
      <div class="dr"><span class="dk">Last successful scan</span><span class="dv mono">${esc(hd.last_search || "—")}</span></div>
      <div class="dr"><span class="dk">Last successful install</span><span class="dv mono">${esc(hd.last_install || "—")}</span></div></div>
    <div class="dom-sec"><h4>Update services ${svcConcern ? pill("warn", "check this") : pill("good", "ok")}</h4>
      ${hd.services.map(s => `<div class="dr"><span class="dk">${esc(s.name)}</span>
        <span class="dv ${s.concern ? "strong" : "muted"}">${esc(s.status)} · ${esc(s.start)}</span></div>`).join("")}</div>
  </div>` : "";
  const fails = h.items.filter(i => !i.ok);
  const failNote = h.failures
    ? `<div class="dom-flag warn" style="margin-bottom:10px">${ico("bang")}<span>${h.failures} of the last ${h.total} update attempts didn't succeed. The decoded reason is on each row below.</span></div>`
    : `<div class="dom-flag good" style="margin-bottom:10px">${ico("check")}<span>No failures in the last ${h.total} update attempts.</span></div>`;
  const table = `<div class="table-wrap" style="max-height:340px"><table>
    <thead><tr><th>When</th><th>Result</th><th>Update</th></tr></thead><tbody>
    ${h.items.map(i => `<tr>
      <td class="mono" style="white-space:nowrap">${esc(i.date || "—")}</td>
      <td>${i.ok ? pill("good", "ok") : pill("bad", esc(i.result))}</td>
      <td><div class="strong copy" style="max-width:420px">${esc(i.title)}</div>
        ${!i.ok ? `<div class="muted" style="font-size:11px; margin-top:2px"><span class="mono">${esc(i.hresult || "")}</span> — ${esc(i.meaning || "")}${i.advice ? ` <span style="opacity:.85">${esc(i.advice)}</span>` : ""}</div>` : ""}</td>
    </tr>`).join("")}</tbody></table></div>`;
  $("#wuBody").innerHTML = healthRow + failNote + table;
};

/* ---- Gremlin hunters ---- */
$$("#gremTabs .tab").forEach(t => t.addEventListener("click", () => {
  const which = t.dataset.grem;
  $$("#gremTabs .tab").forEach(x => x.classList.toggle("active", x === t));
  for (const [k, id] of [["disk", "gremDisk"], ["usb", "gremUsb"], ["freeze", "gremFreeze"]])
    $("#" + id).style.display = which === k ? "" : "none";
}));
$("#btnGremDisk").onclick = async () => {
  $("#btnGremDisk").disabled = true;
  $("#gremDiskStatus").innerHTML = `<span class="spin"></span> watching 8s…`;
  const r = await api.disk_cpu_culprit(8);
  $("#btnGremDisk").disabled = false; $("#gremDiskStatus").textContent = "";
  if (!r.ok) { toast(r.error || "failed", "bad"); return; }
  const tbl = (title, rows, fmt) => `<div class="dom-sec"><h4>${title}</h4>${
    rows.length ? rows.map(x => `<div class="dr"><span class="dk strong">${esc(x.name)}${x.why ? `<div class="muted" style="font-size:11px">${esc(x.why)}</div>` : ""}</span><span class="dv">${fmt(x)}</span></div>`).join("") : `<div class="muted" style="font-size:12px">Nothing notable.</div>`}</div>`;
  $("#gremDiskResult").innerHTML = `<div class="muted" style="font-size:12px; margin-bottom:8px">Disk was moving ${(r.disk_read_mbs + r.disk_write_mbs).toFixed(1)} MB/s overall during the sample.</div>
    <div class="dom-grid">${tbl("Top disk users", r.top_disk, x => x.disk_kb_s + " KB/s")}${tbl("Top CPU", r.top_cpu, x => x.cpu + "%")}</div>`;
};
$("#btnGremUsb").onclick = async () => {
  $("#gremUsbResult").innerHTML = `<div class="row"><span class="spin"></span></div>`;
  const r = await api.usb_drop_history(14);
  if (!r.ok) { $("#gremUsbResult").innerHTML = `<div class="muted">${esc(r.error)}</div>`; return; }
  const drops = r.devices.length
    ? `<div class="dom-sec"><h4>Repeatedly reconnecting (last 14 days)</h4>${r.devices.map(d => `<div class="dr"><span class="dk strong">${esc(d.name)}</span><span class="dv">${d.events}× — try turning off USB selective suspend for this device</span></div>`).join("")}</div>`
    : "";
  const probs = r.problem.length
    ? `<div class="dom-sec"><h4>USB devices with a fault</h4>${r.problem.map(d => `<div class="dr"><span class="dk strong">${esc(d.name)}</span><span class="dv">${pill("warn", esc(d.status))}</span></div>`).join("")}</div>`
    : "";
  $("#gremUsbResult").innerHTML = (drops || probs)
    ? `<div class="dom-grid">${drops}${probs}</div>`
    : emptyState("check", "No USB drama", "No devices are repeatedly dropping, and none are faulted.");
};
$("#btnGremFreeze").onclick = async () => {
  $("#gremFreezeResult").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Pulling the logs around now…</span></div>`;
  const r = await api.mark_freeze(120);
  if (!r.ok) { $("#gremFreezeResult").innerHTML = `<div class="muted">${esc(r.error)}</div>`; return; }
  const rows = r.events.length
    ? `<div class="table-wrap" style="max-height:300px"><table><thead><tr><th>Time</th><th>Level</th><th>Source</th><th>ID</th><th>What</th></tr></thead><tbody>
       ${r.events.map(e => `<tr><td class="mono">${esc(e.time)}</td>
         <td>${e.level === "Error" || e.level === "Critical" ? pill("bad", esc(e.level)) : pill("warn", esc(e.level))}</td>
         <td>${esc(e.provider)}</td><td class="mono">${esc(e.id)}</td><td class="muted">${esc(e.msg)}</td></tr>`).join("")}</tbody></table></div>`
    : emptyState("check", "Nothing logged around that moment", `No errors or warnings in the last ${r.window}s.`);
  $("#gremFreezeResult").innerHTML = `<div class="muted" style="font-size:12px; margin-bottom:8px">At the mark: CPU ${r.cpu}% · memory ${r.mem_pct}%. Events in the last ${r.window}s:</div>${rows}`;
};

$("#btnRpCreate").onclick = async () => {
  if (!isAdmin) { toast("Creating a restore point needs elevation — use Run as admin.", "bad", 5000); return; }
  const btn = $("#btnRpCreate"); btn.disabled = true; const old = btn.innerHTML;
  btn.innerHTML = `<span class="spin"></span> Creating…`;
  const r = await api.create_restore_point("Benchly manual checkpoint");
  btn.disabled = false; btn.innerHTML = old;
  toast(r.ok ? "Restore point created" : r.error, r.ok ? "good" : "bad", 5000);
  if (r.ok) loadRestoreCard();
};
$("#btnRpOpen").onclick = () => api.open_restore_ui();
$("#btnBpCheck").onclick = async () => {
  $("#bpBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Auditing backups…</span></div>`;
  const r = await api.get_backup_posture();
  $("#bpOverall").innerHTML = pill(r.overall === "good" ? "good" : r.overall === "warn" ? "warn" : "bad",
    r.overall === "good" ? "Protected" : r.overall === "warn" ? "Gaps" : "At risk");
  $("#bpBody").innerHTML = r.checks.map(c => `<div class="check ${c.status}">
    <div class="icon">${ico(c.status === "good" ? "check" : c.status === "warn" ? "bang" : "x")}</div>
    <div class="body"><div class="title">${esc(c.label)}</div><div class="detail">${esc(c.detail)}</div></div></div>`).join("");
};
$("#toolGrid").addEventListener("click", async e => {
  const b = e.target.closest("[data-run]");
  if (!b) return;
  if (!isAdmin) { toast("Repair tools need elevation — use Run as admin in the title bar.", "bad", 5000); return; }
  const toolId = b.dataset.run;
  const needsConfirm = ["dism_restore", "winsock", "wu_reset"].includes(toolId);
  if (needsConfirm && !await confirmModal("Run this tool?",
      "This makes changes to the system (it can be re-run safely, but a reboot may be needed afterwards).", "Run",
      b.dataset.where)) return;
  const r = await api.start_repair(toolId);
  if (!r.ok) { toast(r.error, "bad", 5000); return; }
  repairJob = r.job; repairOffset = 0;
  $$(".tool-card").forEach(c => c.classList.toggle("running", c.dataset.tool === toolId));
  $$("#toolGrid [data-run]").forEach(x => x.disabled = true);
  $("#repairConsoleCard").style.display = "";
  $("#repairTitle").textContent = r.label;
  const rc = $("#repairConsole");
  rc.textContent = "";
  rc.dataset.committed = "";
  pollRepair();
});
let repairFails = 0;
async function pollRepair() {
  // self-chaining: the next poll is only scheduled after this one resolves,
  // so slow bridge calls can never interleave and double-append lines
  if (!repairJob) return;
  let r;
  try { r = await api.get_repair_job(repairJob, repairOffset); repairFails = 0; }
  catch {
    if (++repairFails > 8) { repairJob = null; $$("#toolGrid [data-run]").forEach(x => x.disabled = false); return; }
    repairTimer = setTimeout(pollRepair, 1500); return;
  }
  if (!r.ok) { repairJob = null; return; }
  const c = $("#repairConsole");
  if (r.lines.length) {
    repairOffset = r.total;
    c.dataset.committed = (c.dataset.committed ? c.dataset.committed + "\n" : "") + r.lines.join("\n");
  }
  // committed lines + the live progress line (e.g. "Verification 42% complete")
  const base = c.dataset.committed || "";
  c.textContent = r.current ? (base ? base + "\n" : "") + r.current : base;
  c.scrollTop = c.scrollHeight;
  if (r.done) {
    repairJob = null;
    $$(".tool-card").forEach(x => x.classList.remove("running"));
    $$("#toolGrid [data-run]").forEach(x => x.disabled = false);
    toast(r.rc === 0 ? "Tool finished successfully" : `Tool finished with exit code ${r.rc}`,
          r.rc === 0 ? "good" : "bad", 5000);
    return;
  }
  repairTimer = setTimeout(pollRepair, 700);
}
$("#btnRepairCancel").onclick = async () => {
  if (!repairJob) return;
  const r = await api.cancel_repair(repairJob);
  toast(r.ok ? "Job cancelled" : r.error, r.ok ? "info" : "bad");
};

/* ---- baseline ---- */
async function refreshBaselineInfo() {
  const info = await api.get_baseline_info();
  $("#blStatus").textContent = info.exists
    ? `saved ${info.time} · ${info.counts.apps} apps · ${info.counts.services} services · score ${info.score}`
    : "no baseline saved yet";
  $("#btnBlCompare").disabled = !info.exists;
}
$("#btnBlSave").onclick = async () => {
  const info = await api.get_baseline_info();
  if (info.exists && !await confirmModal("Overwrite baseline?",
      `A baseline from ${info.time} exists. Replace it with the current state?`, "Overwrite")) return;
  const r = await api.save_baseline();
  toast(r.ok ? "Baseline saved" : r.error, r.ok ? "good" : "bad");
  $("#blResult").innerHTML = "";
  refreshBaselineInfo();
};
$("#btnBlCompare").onclick = async () => {
  $("#blResult").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Comparing…</span></div>`;
  const r = await api.compare_baseline();
  if (!r.ok) { $("#blResult").innerHTML = ""; toast(r.error, "bad"); return; }
  if (r.clean) {
    $("#blResult").innerHTML = emptyState("check", "No drift detected",
      `Nothing changed since the baseline of ${r.baseline_time}.`);
    return;
  }
  const section = (title, diff) => {
    const rows = [
      ...diff.added.map(x => ({ tag: "add", t: "+", name: x.name, val: x.value })),
      ...diff.removed.map(x => ({ tag: "del", t: "−", name: x.name, val: x.value })),
      ...diff.changed.map(x => ({ tag: "chg", t: "~", name: x.name, val: `${x.old} → ${x.new}` })),
    ];
    if (!rows.length) return "";
    return `<div class="diff-section"><h3 style="margin-bottom:6px">${esc(title)} <span class="right muted">${rows.length} change(s)</span></h3>
      ${rows.map(x => `<div class="diff-row"><span class="tag ${x.tag}">${x.t}</span>
        <span class="d-name">${esc(x.name)}</span>
        <span class="d-val" style="flex:1" title="${esc(x.val)}">${esc(x.val)}</span></div>`).join("")}</div>`;
  };
  const score = r.score.old !== r.score.new
    ? `<div class="diff-section"><h3 style="margin-bottom:6px">Health score</h3>
       <div class="diff-row"><span class="tag chg">~</span><span class="d-name">${r.score.old} → ${r.score.new}</span></div></div>` : "";
  const build = r.os_build.old !== r.os_build.new
    ? `<div class="diff-section"><h3 style="margin-bottom:6px">OS build</h3>
       <div class="diff-row"><span class="tag chg">~</span><span class="d-name">${esc(r.os_build.old)} → ${esc(r.os_build.new)}</span></div></div>` : "";
  const settings = (r.settings && r.settings.length)
    ? `<div class="diff-section"><h3 style="margin-bottom:6px">Windows settings <span class="right muted">${r.settings.length} change(s)</span></h3>
       ${r.settings.map((s, i) => `<div class="diff-row"><span class="tag chg">~</span>
         <span class="d-name">${esc(s.label)}</span>
         <span class="d-val" style="flex:1">${esc(s.old)} → <b>${esc(s.new)}</b></span>
         ${s.revertable ? `<button class="btn ghost small" data-revert="${i}">Put back</button>` : ""}</div>`).join("")}</div>` : "";
  $("#blResult").innerHTML = `<p class="muted" style="font-size:12px; margin-bottom:10px">
    Baseline ${esc(r.baseline_time)} → now ${esc(r.now_time)}</p>` + settings + score + build +
    section("Applications", r.apps) + section("Services", r.services) + section("Startup entries", r.startup);
  $("#blResult").querySelectorAll("[data-revert]").forEach(b => b.onclick = async () => {
    const s = r.settings[+b.dataset.revert];
    const res = await api.revert_setting(s.key, s.old_raw);
    if (!res.ok) { toast(res.error, "bad", 4000); return; }
    toast(`Put “${s.label}” back to ${s.old}`, "good", 2500);
    if (res.restart === "explorer") toast("Restart Explorer (in Cleanup → Tweaks) to see it fully.", "info", 4000);
    b.closest(".diff-row").style.opacity = "0.5"; b.disabled = true;
  });
};

/* ================= SECURITY page ================= */
async function loadSecurity(refresh = false) {
  api.get_setting("vt_api_key").then(k => { if (k) $("#vtKey").value = k; });
  const [h, inv] = await Promise.all([api.get_health(refresh), api.get_inventory()]);

  const products = h.av_products || [];
  $("#secAv").innerHTML = `<h3>Antivirus products</h3>` + (products.length ? products.map(p => `
    <div class="check ${p.enabled ? "good" : "unknown"}">
      <div class="icon">${ico(p.enabled ? "check" : "q")}</div>
      <div class="body">
        <div class="title">${esc(p.name)}
          ${p.enabled ? pill("good", "Active") : pill("unknown", "Inactive")}
          ${p.outdated ? pill("warn", "Definitions stale") : ""}
        </div>
        <div class="detail">${p.enabled ? "Real-time protection on" : "Registered but not the active scanner"}${p.timestamp ? ` · last reported ${esc(p.timestamp)}` : ""}</div>
      </div>
    </div>`).join("") : emptyState("q", "No products registered with Security Center"));

  const fw = (h.firewall_profiles || []).map(f =>
    `<dt>${esc(f.name)} firewall</dt><dd>${f.enabled ? "Enabled" : `<span style="color:var(--crit)">Disabled</span>`}</dd>`).join("");
  const bl = (h.bitlocker_volumes || []).map(v =>
    `<dt>BitLocker ${esc(v.mount)}</dt><dd>${esc(v.protection)} (${esc(String(v.status ?? ""))})</dd>`).join("")
    || `<dt>BitLocker</dt><dd class="muted">${h.is_admin ? "No volumes reported" : "Needs elevation"}</dd>`;
  const checkById = id => h.checks.find(c => c.id === id);
  const fmtCheck = id => {
    const c = checkById(id);
    return c ? `${c.status === "good" ? "" : c.status === "unknown" ? "Unknown — " : "⚠ "}${esc(c.detail)}` : "—";
  };
  $("#secDefenses").innerHTML = `<h3>Defenses</h3><dl class="kv">
    ${fw}${bl}
    <dt>UAC</dt><dd>${fmtCheck("uac")}</dd>
    <dt>Secure Boot</dt><dd>${inv.secure_boot === true ? "Enabled" : inv.secure_boot === false ? `<span style="color:var(--warn)">Disabled</span>` : "Unknown (needs admin)"}</dd>
    <dt>TPM</dt><dd>${inv.tpm ? (inv.tpm.enabled ? "Enabled" : "Present, disabled") : "Unknown (needs admin)"}</dd>
  </dl>`;
}
$("#btnSecRefresh").onclick = () => loadSecurity(true);

$("#btnVtSaveKey").onclick = async () => {
  const r = await api.set_setting("vt_api_key", $("#vtKey").value.trim());
  toast(r.ok ? "API key saved" : r.error, r.ok ? "good" : "bad");
};
$("#btnVtBrowse").onclick = async () => {
  const f = await api.pick_file();
  if (!f.ok) { if (f.error !== "cancelled") toast(f.error, "bad"); return; }
  $("#vtResult").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Hashing ${esc(f.path)}…</span></div>`;
  const h = await api.vt_hash_file(f.path);
  if (!h.ok) { $("#vtResult").innerHTML = ""; toast(h.error, "bad"); return; }
  $("#vtHash").value = h.sha256;
  vtCheck(`${h.name} (${fmtBytes(h.size)})`);
};
$("#btnVtCheck").onclick = () => vtCheck();
$("#vtHash").addEventListener("keydown", e => { if (e.key === "Enter") vtCheck(); });

async function vtCheck(fileLabel = null) {
  const hash = $("#vtHash").value.trim();
  if (!hash) { toast("Choose a file or paste a hash first.", "bad"); return; }
  $("#vtResult").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Asking VirusTotal…</span></div>`;
  const r = await api.vt_check_hash(hash);
  if (!r.ok) {
    $("#vtResult").innerHTML = r.error === "no_key"
      ? emptyState("q", "No API key saved", "Paste your free VirusTotal API key above and save it first.")
      : emptyState("bang", "Lookup failed", r.error);
    return;
  }
  if (!r.found) {
    $("#vtResult").innerHTML = emptyState("q", "Unknown to VirusTotal",
      "No engine has analysed this hash. That is common for fresh or private files — it is not a verdict either way.");
    return;
  }
  const bad = r.malicious + r.suspicious;
  const verdictColor = r.malicious > 3 ? "var(--crit)" : bad > 0 ? "var(--warn)" : "var(--ok)";
  const verdictText = r.malicious > 3 ? "Malicious" : bad > 0 ? "Suspicious" : "Clean";
  $("#vtResult").innerHTML = `
    <div class="speed-row" style="align-items:center">
      <div class="speed-kpi"><div class="v" style="color:${verdictColor}">${bad}<small> / ${r.total}</small></div>
        <div class="l">Engines flagging</div></div>
      <div>
        <div style="font-weight:600; color:${verdictColor}">${verdictText}</div>
        <div class="muted" style="font-size:12px">${esc(fileLabel || r.names[0] || r.hash.slice(0, 16) + "…")}${r.type ? " · " + esc(r.type) : ""}</div>
      </div>
      <div class="spacer" style="flex:1"></div>
      <button class="btn" id="btnVtOpen">Full report on VirusTotal${ico("open", "ic sm")}</button>
    </div>
    ${r.flagged.length ? `<div class="table-wrap mt" style="max-height:200px"><table>
      <thead><tr><th>Engine</th><th>Verdict</th><th>Detection name</th></tr></thead><tbody>
      ${r.flagged.map(f => `<tr><td class="strong">${esc(f.engine)}</td>
        <td>${pill(f.verdict === "malicious" ? "bad" : "warn", f.verdict)}</td>
        <td class="mono copy">${esc(f.label || "—")}</td></tr>`).join("")}</tbody></table></div>` : ""}`;
  $("#btnVtOpen").onclick = () => api.open_in_browser(r.link);
}

/* ================= LAN toolkit ================= */
$$("#lanTabs .tab").forEach(t => t.addEventListener("click", () => {
  $$("#lanTabs .tab").forEach(x => x.classList.toggle("active", x === t));
  for (const [key, id] of [["scan", "lanTabScan"], ["wol", "lanTabWol"], ["dhcp", "lanTabDhcp"]])
    $("#" + id).style.display = t.dataset.lan === key ? "" : "none";
  if (t.dataset.lan === "wol") renderWol();
}));

/* ---- subnet scan ---- */
let scanRunning = false;
async function initSubnetChips() {
  const subs = await api.list_subnets();
  $("#scanSubnets").innerHTML = subs.map(s =>
    `<button class="btn small" data-net="${esc(s.network)}" title="${esc(s.adapter)} — ~${s.hosts} hosts${s.capped ? " (capped to /24)" : ""}">${esc(s.network)}</button>`).join("");
  if (subs[0]) $("#scanNetwork").value = subs[0].network;
}
$("#scanSubnets").addEventListener("click", e => {
  const b = e.target.closest("[data-net]");
  if (b) $("#scanNetwork").value = b.dataset.net;
});
$("#btnScanStart").onclick = async () => {
  if (scanRunning) return;
  const network = $("#scanNetwork").value.trim();
  const r = await api.start_subnet_scan(network);
  if (!r.ok) { toast(r.error, "bad"); return; }
  scanRunning = true;
  $("#btnScanStart").disabled = true;
  $("#scanBar").style.display = "";
  $("#scanResult").innerHTML = "";
  let scanFails = 0;
  const poll = async () => {
    let j;
    try { j = await api.get_scan_job(r.job); scanFails = 0; }
    catch { if (++scanFails > 8) { scanRunning = false; $("#btnScanStart").disabled = false; return; } setTimeout(poll, 1500); return; }
    if (!j.ok) { scanRunning = false; $("#btnScanStart").disabled = false; return; }
    $("#scanBarFill").style.width = `${j.done_count / j.total * 100}%`;
    $("#scanStatus").textContent = j.done
      ? `${j.found.length} device(s) on ${esc(network)}`
      : `probing ${j.done_count}/${j.total}…`;
    if (!j.done) { setTimeout(poll, 800); return; }
    scanRunning = false;
    $("#btnScanStart").disabled = false;
    $("#scanBar").style.display = "none";
    $("#scanResult").innerHTML = j.found.length ? `<div class="table-wrap" style="max-height:340px"><table>
      <thead><tr><th>IP</th><th>Hostname</th><th>MAC</th><th>Vendor</th><th></th></tr></thead><tbody>
      ${j.found.map(h => `<tr>
        <td class="mono copy">${esc(h.ip)}</td>
        <td class="strong copy">${esc(h.name || "—")}${h.self ? ` <span class="muted" style="font-size:11px">· this machine</span>` : ""}</td>
        <td class="mono copy">${esc(h.mac || "—")}</td>
        <td>${esc(h.vendor || "—")}</td>
        <td style="width:120px">${h.self ? "" : `<button class="btn ghost small row-action" data-profile="${esc(h.ip)}">Profile</button>${h.mac ? `<button class="btn ghost small row-action" data-wake="${esc(h.mac)}" title="Send magic packet">Wake</button>` : ""}`}</td>
      </tr>`).join("")}</tbody></table></div>`
      : emptyState("inbox", "No devices responded", "Hosts with firewalled ICMP won't appear in a ping sweep.");
  };
  poll();
};
$("#scanResult").addEventListener("click", async e => {
  const prof = e.target.closest("[data-profile]");
  if (prof) {
    showToolConsole("port");
    $("#netHost").value = prof.dataset.profile;
    runPortProfile();
    return;
  }
  const wake = e.target.closest("[data-wake]");
  if (wake) {
    const r = await api.wol_send(wake.dataset.wake);
    toast(r.ok ? `Magic packet sent to ${wake.dataset.wake}` : r.error, r.ok ? "good" : "bad");
  }
});
function showToolConsole(tool) {
  const tab = $(`#netTabs [data-tool="${tool}"]`);
  if (tab) tab.click();
  $("#netConsole").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ---- port profile ---- */
async function runPortProfile() {
  const host = $("#netHost").value.trim();
  if (!host) { toast("Enter a host first.", "bad"); return; }
  const btn = $("#btnPortProfile");
  btn.disabled = true;
  consoleLog(`<span class="ok">[${new Date().toLocaleTimeString()}] port profile ${esc(host)} (25 common ports)</span>`);
  try {
    const r = await api.port_profile(host);
    if (!r.ok) { consoleLog(`<span class="err">${esc(r.error)}</span>`); return; }
    consoleLog(r.open.length
      ? r.open.map(p => `${padCol(p.port, 6)} <span class="ok">open</span>  ${padCol(p.service, 16)} ${esc(p.banner)}`).join("\n")
        + `\n(${r.open.length} open of ${r.scanned} scanned on ${esc(r.ip)})`
      : `No common ports open on ${esc(r.ip)} (${r.scanned} scanned).`);
  } finally { btn.disabled = false; }
}
$("#btnPortProfile").onclick = runPortProfile;

/* ---- Wake-on-LAN ---- */
async function renderWol() {
  const machines = await api.wol_machines();
  $("#wolList").innerHTML = machines.length ? `<div class="table-wrap" style="max-height:260px"><table>
    <thead><tr><th>Machine</th><th>MAC</th><th></th></tr></thead><tbody>
    ${machines.map((m, i) => `<tr>
      <td class="strong">${esc(m.name)}</td><td class="mono copy">${esc(m.mac)}</td>
      <td style="width:120px"><button class="btn small" data-wolsend="${i}">Wake</button>
      <button class="btn ghost small row-action" data-woldel="${i}" title="Remove">${ico("x", "ic sm")}</button></td>
    </tr>`).join("")}</tbody></table></div>`
    : emptyState("inbox", "No saved machines", "Save a name and MAC above — or use Wake straight from a subnet scan.");
}
$("#btnWolAdd").onclick = async () => {
  const name = $("#wolName").value.trim() || "Unnamed";
  const mac = $("#wolMac").value.trim().toUpperCase();
  if (!/^([0-9A-F]{2}[:-]){5}[0-9A-F]{2}$/.test(mac)) { toast("MAC must look like AA:BB:CC:DD:EE:FF", "bad"); return; }
  const machines = await api.wol_machines();
  machines.push({ name, mac });
  await api.wol_save(machines);
  $("#wolName").value = ""; $("#wolMac").value = "";
  toast(`Saved ${name}`, "good");
  renderWol();
};
$("#wolList").addEventListener("click", async e => {
  const send = e.target.closest("[data-wolsend]");
  if (send) {
    const machines = await api.wol_machines();
    const m = machines[+send.dataset.wolsend];
    const r = await api.wol_send(m.mac);
    toast(r.ok ? `Magic packet sent to ${m.name}` : r.error, r.ok ? "good" : "bad");
    return;
  }
  const del = e.target.closest("[data-woldel]");
  if (del) {
    const machines = await api.wol_machines();
    machines.splice(+del.dataset.woldel, 1);
    await api.wol_save(machines);
    renderWol();
  }
});

/* ---- DHCP & DNS ---- */
$("#btnDhcpCheck").onclick = async () => {
  $("#dhcpStatus").innerHTML = `<span class="spin"></span>`;
  $("#btnDhcpCheck").disabled = true;
  try {
    const d = await api.dhcp_dns_health();
    $("#dhcpStatus").textContent = "";
    const leaseRows = d.leases.map(l => `
      <tr><td class="strong">${esc(l.adapter)}</td>
      <td class="mono copy">${esc(l.ip)}</td>
      <td>${l.dhcp ? pill("info", "DHCP") : pill("unknown", "Static")}</td>
      <td class="mono copy">${esc(l.server || "—")}</td>
      <td class="mono">${esc(l.obtained || "—")} → ${esc(l.expires || "—")}</td></tr>`).join("");
    const dnsRows = d.dns_tests.map(t => `
      <tr><td class="mono copy">${esc(t.server)}</td>
      <td>${t.ok ? pill("good", "Responding") : pill("bad", "Failed")}</td>
      <td class="num">${t.ms !== null && t.ms !== undefined ? t.ms + " ms" : "—"}</td></tr>`).join("");
    $("#dhcpResult").innerHTML = `
      ${d.multiple_dhcp ? `<div class="check warn" style="border:none; padding-bottom:12px">
        <div class="icon">${ico("bang")}</div><div class="body">
        <div class="title">Multiple DHCP servers seen ${pill("warn", "Check")}</div>
        <div class="detail">${esc(d.dhcp_servers.join(", "))} — more than one DHCP server on a flat network usually means a rogue device or a misconfigured router.</div></div></div>` : ""}
      <div class="table-wrap" style="max-height:200px"><table>
        <thead><tr><th>Adapter</th><th>IP</th><th>Mode</th><th>DHCP server</th><th>Lease</th></tr></thead>
        <tbody>${leaseRows}</tbody></table></div>
      <div class="table-wrap mt" style="max-height:160px"><table>
        <thead><tr><th>DNS server</th><th>Status</th><th class="num">Lookup time</th></tr></thead>
        <tbody>${dnsRows || `<tr><td colspan="3" class="muted">No DNS servers configured</td></tr>`}</tbody></table></div>
      <p class="muted" style="font-size:11.5px; margin-top:8px">True rogue-DHCP detection needs a dedicated
      DHCPDISCOVER probe listening on port 68 — this view reports what each adapter actually leased.</p>`;
  } finally { $("#btnDhcpCheck").disabled = false; }
};

/* ================= SENSORS (System page) ================= */
let sensorsStarted = false;
function startSensorsLoop() {
  if (sensorsStarted) return;
  sensorsStarted = true;
  pollLoop(4000, async () => {
    if (currentPage !== "system") return;
    let s;
    try { s = await api.get_sensors(); } catch { return; }
    const rows = [];
    for (const g of s.gpus) {
      rows.push(["GPU — " + g.name,
        `${g.temp_c ?? "—"} °C · ${g.util_pct ?? 0}% load · ${fmtBytes((g.vram_used_mb ?? 0) * 1048576)} / ${fmtBytes((g.vram_total_mb ?? 0) * 1048576)} VRAM${g.power_w ? ` · ${g.power_w.toFixed(0)} W` : ""}`]);
    }
    if (s.cpu_lhm !== null && s.cpu_lhm !== undefined) rows.push(["CPU package (LibreHardwareMonitor)", `${s.cpu_lhm} °C`]);
    for (const d of s.disks) rows.push(["Disk — " + d.name, `${d.temp_c} °C`]);
    for (const z of s.acpi) rows.push(["ACPI — " + z.name, `${z.temp_c} °C`]);
    setHTML($("#sensorsBody"), rows.length
      ? `<dl class="kv">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`
      : emptyState("q", "No sensors readable",
          "CPU core temps need a kernel driver on Windows — run LibreHardwareMonitor's web server and Benchly will pick it up. Disk temps appear when elevated."));
    $("#sensorsNote").textContent = s.cpu_lhm === null && !s.gpus.length ? "best effort — see note" : "live · 4 s";
  });
}

/* ---- battery trend ---- */
async function loadBatteryTrend() {
  const b = await api.get_battery_history();
  if (!b.present) return;
  $("#batteryCard").style.display = "";
  const h = b.history;
  if (!h.length) {
    $("#batteryBody").innerHTML = `<p class="muted" style="font-size:12px">First reading will be recorded automatically — the trend builds one point per day the app runs.</p>`;
    return;
  }
  const w = 600, ht = 80, min = Math.min(...h.map(x => x.health_pct), 60);
  const pts = h.map((x, i) => {
    const px = h.length === 1 ? w : i / (h.length - 1) * w;
    const py = ht - ((x.health_pct - min) / (100 - min)) * (ht - 8) - 4;
    return `${px.toFixed(1)},${py.toFixed(1)}`;
  }).join(" ");
  const latest = h[h.length - 1];
  $("#batteryNote").textContent = `${latest.health_pct}% of design capacity · ${h.length} reading(s)`;
  $("#batteryBody").innerHTML = `
    <svg viewBox="0 0 ${w} ${ht}" style="width:100%; height:${ht}px" preserveAspectRatio="none">
      <polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linejoin="round"/>
    </svg>
    <div class="row muted" style="justify-content:space-between; font-size:11px">
      <span>${esc(h[0].date)}</span>
      <span>${(latest.full_mwh / 1000).toFixed(1)} Wh of ${(latest.design_mwh / 1000).toFixed(1)} Wh design</span>
      <span>${esc(latest.date)}</span>
    </div>`;
}

/* ================= ticket summary + memory diag (Toolbox) ================= */
async function loadTicketSummary() {
  try {
    const t = await api.get_ticket_summary();
    $("#ticketText").textContent = t.text;
  } catch {
    $("#ticketText").innerHTML = `<span class="console-empty">Could not build the summary.</span>`;
  }
}
$("#btnTicketCopy").onclick = () => {
  navigator.clipboard.writeText($("#ticketText").textContent)
    .then(() => toast("Ticket summary copied", "good", 2000));
};
$("#btnMemDiag").onclick = async () => {
  if (!await confirmModal("Schedule memory test?",
      "Windows will offer to restart now or test on the next boot. The test takes ~10 minutes and the machine is unusable during it.", "Open scheduler",
      "Launches the built-in mdsched.exe. The verdict is written to the System event log (MemoryDiagnostics-Results) after the reboot.")) return;
  const r = await api.launch_memory_test();
  toast(r.ok ? "Memory Diagnostic scheduler opened" : r.error, r.ok ? "good" : "bad");
};
async function loadMemResults() {
  const results = await api.get_memory_results();
  $("#memResults").innerHTML = results.length
    ? results.map(r => `<div class="check ${r.passed ? "good" : r.passed === false ? "bad" : "unknown"}" style="padding:8px 0">
        <div class="icon">${ico(r.passed ? "check" : r.passed === false ? "x" : "q")}</div>
        <div class="body"><div class="title">${esc(r.time)} ${r.passed ? pill("good", "No errors") : r.passed === false ? pill("bad", "Errors") : ""}</div>
        <div class="detail">${esc(r.message.slice(0, 160))}</div></div></div>`).join("")
    : `<p class="muted" style="font-size:12px">No past results — the verdict is logged after the machine reboots from a test.</p>`;
}

/* ================= FLEET page ================= */
async function loadFleet() { /* static page — handlers below */ }

$("#btnRemote").onclick = async () => {
  const host = $("#rmHost").value.trim();
  if (!host) { toast("Enter a computer name or IP.", "bad"); return; }
  const btn = $("#btnRemote");
  btn.disabled = true;
  $("#rmStatus").innerHTML = `<span class="spin"></span> contacting ${esc(host)}…`;
  try {
    const r = await api.remote_snapshot(host, $("#rmUser").value.trim(), $("#rmPass").value);
    $("#rmStatus").textContent = "";
    if (!r.ok) { $("#rmResult").innerHTML = emptyState("bang", "Snapshot failed", r.error); return; }
    const s = r.snapshot;
    const freePct = s.c_total_gb ? Math.round(s.c_free_gb / s.c_total_gb * 100) : null;
    $("#rmResult").innerHTML = `
      <div class="row" style="gap:8px; margin-bottom:10px">
        <span style="font-family:var(--font-display); font-size:16px; font-weight:600">${esc(s.host)}</span>
        ${s.reboot_pending ? pill("warn", "Reboot pending") : pill("good", "No reboot pending")}
        ${s.av ? pill("good", esc(s.av)) : pill("warn", "No active AV")}
        ${s.stopped_count ? pill("warn", `${s.stopped_count} auto service(s) stopped`) : pill("good", "Services healthy")}
      </div>
      <dl class="kv">
        <dt>OS</dt><dd class="copy">${esc(s.os)} (build ${esc(s.build)})</dd>
        <dt>Model</dt><dd class="copy">${esc(s.model)}</dd>
        <dt>CPU</dt><dd class="copy">${esc(s.cpu)}</dd>
        <dt>RAM</dt><dd>${s.ram_gb} GB</dd>
        <dt>C: free</dt><dd>${s.c_free_gb ?? "—"} GB of ${s.c_total_gb ?? "—"} GB${freePct !== null ? ` (${freePct}%)` : ""}</dd>
        <dt>Last boot</dt><dd>${esc(s.boot)}</dd>
        <dt>Logged on</dt><dd class="copy">${esc(s.logged_on || "—")}</dd>
        <dt>Last hotfix</dt><dd>${esc(s.last_kb || "—")}</dd>
        ${s.stopped_services.length ? `<dt>Stopped (auto)</dt><dd>${esc(s.stopped_services.join(", "))}${s.stopped_count > s.stopped_services.length ? ` +${s.stopped_count - s.stopped_services.length} more` : ""}</dd>` : ""}
      </dl>`;
  } finally { btn.disabled = false; $("#rmPass").value = ""; }
};
$("#rmHost").addEventListener("keydown", e => { if (e.key === "Enter") $("#btnRemote").click(); });

/* ---- report compare ---- */
const cmpPaths = { a: null, b: null };
async function pickReport(which) {
  const f = await api.pick_file();
  if (!f.ok) return;
  if (!f.path.toLowerCase().endsWith(".json")) { toast("Pick the .json saved next to an exported report.", "bad"); return; }
  cmpPaths[which] = f.path;
  $(which === "a" ? "#cmpAName" : "#cmpBName").textContent = f.path.split("\\").pop();
  $("#btnCmpRun").disabled = !(cmpPaths.a && cmpPaths.b);
}
$("#btnCmpA").onclick = () => pickReport("a");
$("#btnCmpB").onclick = () => pickReport("b");
$("#btnCmpRun").onclick = async () => {
  $("#cmpResult").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Comparing…</span></div>`;
  const r = await api.compare_reports(cmpPaths.a, cmpPaths.b);
  if (!r.ok) { $("#cmpResult").innerHTML = emptyState("bang", "Comparison failed", r.error); return; }
  const metaRow = (label, ka, kb) => `<tr><th class="strong">${esc(label)}</th>
    <td${String(ka) !== String(kb) ? ` style="color:var(--warn)"` : ""}>${esc(ka ?? "—")}</td>
    <td${String(ka) !== String(kb) ? ` style="color:var(--warn)"` : ""}>${esc(kb ?? "—")}</td></tr>`;
  const statusPill = st => st === null ? `<span class="muted">—</span>`
    : pill(st === "good" ? "good" : st === "warn" ? "warn" : st === "bad" ? "bad" : "unknown", st);
  const diffSection = (title, diff) => {
    const rows = [
      ...diff.added.map(x => ({ tag: "add", t: "+", name: x.name, val: x.value })),
      ...diff.removed.map(x => ({ tag: "del", t: "−", name: x.name, val: x.value })),
      ...diff.changed.map(x => ({ tag: "chg", t: "~", name: x.name, val: `${x.old} → ${x.new}` })),
    ];
    if (!rows.length) return "";
    return `<div class="diff-section mt"><h3 style="margin-bottom:6px">${esc(title)} <span class="right muted">${rows.length} difference(s) — relative to A</span></h3>
      ${rows.slice(0, 80).map(x => `<div class="diff-row"><span class="tag ${x.tag}">${x.t}</span>
        <span class="d-name">${esc(x.name)}</span>
        <span class="d-val" style="flex:1" title="${esc(x.val)}">${esc(x.val)}</span></div>`).join("")}
      ${rows.length > 80 ? `<div class="muted" style="font-size:11.5px; padding:4px 0">…and ${rows.length - 80} more</div>` : ""}</div>`;
  };
  $("#cmpResult").innerHTML = `
    <div class="table-wrap" style="max-height:none"><table>
      <thead><tr><th></th><th>A — ${esc(r.a.host)} (${esc(r.a.generated)})</th><th>B — ${esc(r.b.host)} (${esc(r.b.generated)})</th></tr></thead>
      <tbody>
        ${metaRow("OS", `${r.a.os} (${r.a.build})`, `${r.b.os} (${r.b.build})`)}
        ${metaRow("Model", r.a.model, r.b.model)}
        ${metaRow("CPU", r.a.cpu, r.b.cpu)}
        ${metaRow("RAM", fmtBytes(r.a.ram_total), fmtBytes(r.b.ram_total))}
        ${metaRow("Health score", `${r.a.score} (${r.a.grade})`, `${r.b.score} (${r.b.grade})`)}
      </tbody></table></div>
    <div class="table-wrap mt" style="max-height:260px"><table>
      <thead><tr><th>Check</th><th>A</th><th>B</th></tr></thead>
      <tbody>${r.checks.map(c => `<tr${c.a !== c.b ? ` style="background:rgba(232,179,57,0.04)"` : ""}>
        <td class="strong">${esc(c.label)}</td><td>${statusPill(c.a)}</td><td>${statusPill(c.b)}</td></tr>`).join("")}</tbody></table></div>
    ${diffSection("Applications", r.apps)}
    ${diffSection("Services (start type)", r.services)}
    ${diffSection("Startup entries", r.startup)}`;
};

/* ================= Security tabs (autoruns / hijack / remote) ================= */
const secLoaded = {};
$$("#secTabs .tab").forEach(t => t.addEventListener("click", () => {
  const which = t.dataset.sec;
  $$("#secTabs .tab").forEach(x => x.classList.toggle("active", x === t));
  for (const [k, id] of [["overview", "secTabOverview"], ["autoruns", "secTabAutoruns"],
                         ["hijack", "secTabHijack"], ["remote", "secTabRemote"], ["vt", "secTabVt"],
                         ["certs", "secTabCerts"], ["listeners", "secTabListeners"], ["email", "secTabEmail"],
                         ["persist", "secTabPersist"], ["harden", "secTabHarden"]])
    $("#" + id).style.display = which === k ? "" : "none";
  if (which === "autoruns" && !secLoaded.autoruns) { secLoaded.autoruns = true; loadAutoruns(); }
  if (which === "hijack" && !secLoaded.hijack) { secLoaded.hijack = true; loadHijack(); }
  if (which === "remote" && !secLoaded.remote) { secLoaded.remote = true; loadRemote(); }
  if (which === "certs" && !secLoaded.certs) { secLoaded.certs = true; loadCerts(); }
  if (which === "listeners" && !secLoaded.listeners) { secLoaded.listeners = true; loadListeners(); }
  if (which === "harden" && !secLoaded.harden) { secLoaded.harden = true; loadHardening(); }
}));

/* ---- Persistence & exclusions ---- */
function flagRowSec(f) {
  const i = f.level === "good" ? "check" : f.level === "warn" ? "bang" : "q";
  return `<div class="dom-flag ${esc(f.level)}">${ico(i)}<span>${esc(f.text)}</span></div>`;
}
$("#btnPersistScan").onclick = loadPersistence;
async function loadPersistence() {
  $("#persistBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Mapping persistence, exclusions and recent execution…</span></div>`;
  const [p, d, e] = await Promise.all([api.map_persistence(), api.audit_defender(), api.recent_execution(14)]);
  const total = (p.total || 0) + (d.flagged || 0) + (e.lolbin_count || 0);
  $("#cntPersist").textContent = total ? `${total}⚠` : "";
  const sec = (title, body, count) => `<div class="dom-sec"><h4>${esc(title)}${count != null ? ` <span class="right muted">${count}</span>` : ""}</h4>${body}</div>`;
  const reasonList = arr => arr && arr.length ? `<div class="muted" style="font-size:11px">${esc(arr.join(" · "))}</div>` : "";

  const wmi = p.wmi.length
    ? p.wmi.map(w => `<div class="dr"><span class="dk strong">${esc(w.name)}<div class="muted" style="font-size:11px">${esc(w.type)}</div></span>
        <span class="dv mono" style="font-size:11px; word-break:break-all">${esc(w.payload)}${reasonList(w.reasons)}</span></div>`).join("")
    : `<div class="muted" style="font-size:12px">None — good.</div>`;
  const svc = p.services.length
    ? p.services.map(s => `<div class="dr"><span class="dk strong">${esc(s.display || s.name)}</span><span class="dv mono" style="font-size:11px; word-break:break-all">${esc(s.path)}${reasonList(s.reasons)}</span></div>`).join("")
    : `<div class="muted" style="font-size:12px">Nothing odd.</div>`;
  const tasks = p.tasks.length
    ? p.tasks.map(t => `<div class="dr"><span class="dk strong">${esc(t.name)}<div class="muted" style="font-size:11px">${esc(t.author)}</div></span><span class="dv mono" style="font-size:11px; word-break:break-all">${esc(t.exec)}${reasonList(t.reasons)}</span></div>`).join("")
    : `<div class="muted" style="font-size:12px">Nothing odd.</div>`;

  let defenderHtml;
  if (!d.defender) defenderHtml = `<div class="muted" style="font-size:12px">${esc(d.message)}</div>`;
  else if (d.needs_admin) defenderHtml = `<div class="muted" style="font-size:12px">Run as admin to read the exclusion list.</div>`;
  else if (!d.exclusions.length) defenderHtml = `<div class="muted" style="font-size:12px">No exclusions set.</div>`;
  else defenderHtml = d.exclusions.map((x, i) => `<div class="dr"><span class="dk">${esc(x.kind)}</span>
      <span class="dv mono" style="font-size:11px; word-break:break-all">${esc(x.value)}${x.risk ? `<div class="bad-reason" style="font-size:11px; color:var(--warn)">${esc(x.risk)}</div>` : ""}</span>
      ${x.risk ? `<button class="btn ghost small" data-excl="${i}">Remove</button>` : ""}</div>`).join("");

  let execHtml;
  if (!e.ok && e.error === "no_admin") execHtml = `<div class="muted" style="font-size:12px">Run as admin to read what's executed recently (Prefetch).</div>`;
  else if (!e.ok) execHtml = `<div class="muted" style="font-size:12px">${esc(e.message || e.error)}</div>`;
  else execHtml = `<div class="table-wrap" style="max-height:260px"><table><thead><tr><th>Last run</th><th>Program</th></tr></thead><tbody>
      ${e.entries.filter(x => x.recent).slice(0, 60).map(x => `<tr><td class="mono">${esc(x.last_run)}</td><td class="strong">${esc(x.exe)}${x.lolbin ? ` ${pill("warn", "LOLBin")}` : ""}</td></tr>`).join("")}</tbody></table></div>`;

  const allFlags = [...(p.flags || []), ...(d.flags || []), ...(e.flags || [])];
  $("#persistBody").innerHTML = `<div class="dom-verdict">${allFlags.map(flagRowSec).join("")}</div>
    <div class="dom-grid">
      ${sec("WMI event subscriptions", wmi, p.wmi.length)}
      ${sec("Suspicious services", svc, p.services.length)}
      ${sec("Suspicious scheduled tasks", tasks, p.tasks.length)}
      ${sec("Defender exclusions", defenderHtml, d.defender && !d.needs_admin ? d.exclusions.length : null)}
      ${sec("Recently executed (last 14 days)", execHtml, e.ok ? e.recent_count : null)}
    </div>`;
  if (d.exclusions) $("#persistBody").querySelectorAll("[data-excl]").forEach(b => b.onclick = async () => {
    const x = d.exclusions[+b.dataset.excl];
    if (!await confirmModal("Remove Defender exclusion?", `Defender will stop ignoring:\n${x.value}`, "Remove")) return;
    const r = await api.remove_exclusion(x.kind, x.value);
    toast(r.ok ? "Exclusion removed" : r.error, r.ok ? "good" : "bad", 4000);
    if (r.ok) loadPersistence();
  });
}

/* ---- Hardening scorecard + ASR ---- */
async function loadHardening() {
  $("#hardenBody").innerHTML = `<div class="row"><span class="spin"></span></div>`;
  const h = await api.hardening_scorecard();
  $("#cntHarden").textContent = (h.total - h.passed) ? `${h.total - h.passed}` : "";
  const grade = h.score >= 80 ? "good" : h.score >= 50 ? "warn" : "bad";
  $("#hardenScore").innerHTML = pill(grade, `${h.score}/100 · ${h.passed} of ${h.total}`);
  $("#hardenBody").innerHTML = h.controls.map((c, i) => `
    <div class="toggle-row">
      <div class="t-info">
        <div class="t-name">${c.ok ? pill("good", "OK") : pill("warn", "Review")} ${esc(c.label)}
          <span class="muted" style="font-size:11px"> · ${esc(c.cat)}${c.admin ? " · admin" : ""}</span></div>
        <div class="t-help">${esc(c.help)}</div>
        <div class="t-help mono copy" style="font-size:10.5px; margin-top:2px; opacity:0.8">${esc(c.where)} · now: ${esc(c.current)}</div>
      </div>
      ${c.ok ? "" : `<button class="btn small" data-harden="${esc(c.key)}" ${c.admin && !h.is_admin ? "disabled title='needs admin'" : ""}>Apply fix</button>`}
    </div>`).join("");
  $("#hardenBody").querySelectorAll("[data-harden]").forEach(b => b.onclick = async () => {
    b.disabled = true; b.textContent = "Applying…";
    const r = await api.apply_control(b.dataset.harden);
    if (!r.ok) { b.disabled = false; b.textContent = "Apply fix"; toast(r.error, "bad", 4000); return; }
    toast("Applied" + (r.reboot ? " — takes effect after a reboot" : ""), "good", 3000);
    loadHardening();
  });
  loadAsr();
}
async function loadAsr() {
  const a = await api.asr_rules();
  const modePill = m => m === "block" ? pill("good", "Block") : m === "audit" ? pill("info", "Audit") : m === "warn" ? pill("warn", "Warn") : `<span class="muted" style="font-size:11px">Off</span>`;
  $("#asrBody").innerHTML = `<div class="table-wrap"><table><thead><tr><th>Rule</th><th>State</th><th></th></tr></thead><tbody>
    ${a.rules.map(r => `<tr><td class="strong">${esc(r.label)}</td><td>${modePill(r.state)}</td>
      <td style="white-space:nowrap">
        <button class="btn ghost small" data-asr="${esc(r.id)}" data-mode="audit" ${!a.is_admin ? "disabled" : ""}>Audit</button>
        <button class="btn ghost small" data-asr="${esc(r.id)}" data-mode="block" ${!a.is_admin ? "disabled" : ""}>Block</button>
        ${r.state !== "off" ? `<button class="btn ghost small" data-asr="${esc(r.id)}" data-mode="off" ${!a.is_admin ? "disabled" : ""}>Off</button>` : ""}
      </td></tr>`).join("")}</tbody></table></div>`;
  $("#asrBody").querySelectorAll("[data-asr]").forEach(b => b.onclick = async () => {
    const r = await api.set_asr(b.dataset.asr, b.dataset.mode);
    toast(r.ok ? `ASR rule set to ${b.dataset.mode}` : r.error, r.ok ? "good" : "bad", 3000);
    if (r.ok) loadAsr();
  });
}
$("#btnHardenRescan") && ($("#btnHardenRescan").onclick = () => { secLoaded.harden = true; loadHardening(); });

/* ---- Root certificate audit ---- */
async function loadCerts() {
  $("#certBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Reading the trusted root stores…</span></div>`;
  const r = await api.audit_certs();
  if (!r.ok) { $("#certBody").innerHTML = `<div class="muted">${esc(r.error || "Scan failed.")}</div>`; return; }
  $("#cntCerts").textContent = (r.alert + r.review) ? `${r.alert + r.review}⚠` : r.total;
  const lvl = { alert: pill("bad", "Interception"), review: pill("warn", "Review"), ok: pill("good", "OK") };
  const banner = (r.alert || r.review)
    ? `<div class="dom-flag warn" style="margin-bottom:12px">${ico("bang")}<span>${r.alert} interception and ${r.review} unrecognised root(s) found — review the highlighted entries.</span></div>`
    : `<div class="dom-flag good" style="margin-bottom:12px">${ico("check")}<span>No unexpected root certificates — ${r.total} trusted roots, all from recognised CAs.</span></div>`;
  $("#certBody").innerHTML = banner + `<div class="table-wrap" style="max-height:calc(100vh - 380px)"><table>
    <thead><tr><th></th><th>Subject</th><th>Store</th><th>Expires</th><th>Key</th></tr></thead><tbody>
    ${r.certs.map(c => `<tr>
      <td>${lvl[c.level]}</td>
      <td class="strong copy" style="max-width:420px">${esc(c.subject)}${c.reasons.length ? `<div class="muted" style="font-size:11px">${esc(c.reasons.join(" · "))}</div>` : ""}</td>
      <td class="muted" style="font-size:11px">${esc(c.store)}</td>
      <td class="mono" style="font-size:11px">${esc(c.not_after || "—")}</td>
      <td class="muted" style="font-size:11px">${esc((c.sig || "") + (c.key_size ? " · " + c.key_size + "-bit" : ""))}</td>
    </tr>`).join("")}</tbody></table></div>`;
}
$("#btnCertScan").onclick = () => { secLoaded.certs = true; loadCerts(); };

/* ---- Listening ports ---- */
async function loadListeners() {
  $("#listenBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Mapping listening ports to processes…</span></div>`;
  const r = await api.get_listeners();
  if (!r.ok) { $("#listenBody").innerHTML = `<div class="muted">${esc(r.error)}</div>`; return; }
  $("#cntListeners").textContent = r.flagged ? `${r.flagged}⚠` : r.total;
  const sigBadge = x => x.signed === true ? pill("good", "Signed") : x.signed === false ? pill("warn", "Unsigned") : `<span class="muted" style="font-size:11px">—</span>`;
  $("#listenBody").innerHTML = `<div class="table-wrap" style="max-height:calc(100vh - 360px)"><table>
    <thead><tr><th></th><th>Address</th><th>Proto</th><th>Service</th><th>Process</th><th>Signature</th></tr></thead><tbody>
    ${r.listeners.map(x => `<tr>
      <td>${x.suspect ? pill("warn", "Check") : x.public ? pill("info", "Public") : `<span class="muted" style="font-size:11px">local</span>`}</td>
      <td class="mono copy">${esc(x.addr)}${x.reasons && x.reasons.length ? `<div class="muted" style="font-size:11px">${esc(x.reasons.join(" · "))}</div>` : ""}</td>
      <td>${esc(x.proto)}</td>
      <td class="muted">${esc(x.service || "")}</td>
      <td class="strong">${esc(x.process || "?")}${x.signer ? `<div class="muted" style="font-size:11px">${esc(x.signer)}</div>` : ""}</td>
      <td>${sigBadge(x)}</td>
    </tr>`).join("")}</tbody></table></div>`;
}
$("#btnListenScan").onclick = () => { secLoaded.listeners = true; loadListeners(); };

/* ---- Email header analyzer ---- */
function renderEmail(r) {
  const flags = (r.flags || []).map(f => {
    const i = f.level === "good" ? "check" : f.level === "warn" ? "bang" : "q";
    return `<div class="dom-flag ${esc(f.level)}">${ico(i)}<span>${esc(f.text)}</span></div>`;
  }).join("");
  const a = r.auth || {};
  const authPill = (lbl, v) => {
    const cls = v === "pass" ? "good" : (v === "fail" || v === "softfail") ? "bad" : "unk";
    return pill(cls, `${lbl} ${v || "—"}`);
  };
  const rows = [
    domRow("From", `${esc(r.from_name || "")} <span class="mono">${esc(r.from_addr || "")}</span>`),
    domRow("Return-Path", r.return_path ? `<span class="mono">${esc(r.return_path)}</span>` : ""),
    domRow("Reply-To", r.reply_to ? `<span class="mono">${esc(r.reply_to)}</span>` : ""),
    domRow("Subject", esc(r.subject || "")),
    domRow("Auth", `${authPill("SPF", a.spf)} ${authPill("DKIM", a.dkim)} ${authPill("DMARC", a.dmarc)}`),
    domRow("Origin IP", r.origin_ip ? `<span class="mono copy">${esc(r.origin_ip)}</span>` : `<span class="muted">unknown</span>`),
    domRow("Mailer", r.x_mailer ? esc(r.x_mailer) : ""),
  ].filter(Boolean).join("");
  const hops = (r.hops || []).length
    ? `<div class="dom-sec" style="margin-top:12px"><h4>Delivery path (origin first)</h4>${
        [...r.hops].reverse().map((h, i) => `<div class="dr"><span class="dk">${i + 1}</span>
          <span class="dv mono" style="font-size:11px">${esc((h.ip || "—"))}${h.helo ? " · " + esc(h.helo) : ""}${h.time ? " · " + esc(h.time) : ""}</span></div>`).join("")}</div>`
    : "";
  return `<div class="dom-verdict">${flags}</div><div class="dom-grid"><div class="dom-sec"><h4>Message</h4>${rows}</div>${hops}</div>`;
}
$("#btnEmailCheck").onclick = async () => {
  const raw = $("#emailHeaders").value.trim();
  if (!raw) return;
  $("#emailResult").innerHTML = `<div class="row"><span class="spin"></span></div>`;
  const r = await api.analyze_headers(raw);
  if (!r.ok) { $("#emailResult").innerHTML = pill("bad", r.error); return; }
  $("#emailResult").innerHTML = renderEmail(r);
};
$("#btnEmailClear").onclick = () => { $("#emailHeaders").value = ""; $("#emailResult").innerHTML = ""; };

let autorunsData = [];
async function loadAutoruns() {
  const r = await api.get_autoruns();
  autorunsData = r.entries;
  $("#cntAutoruns").textContent = r.flagged ? `${r.flagged}⚠` : r.entries.length;
  $("#autorunsBody").innerHTML = `<div class="table-wrap" style="max-height:calc(100vh - 320px)"><table>
    <thead><tr><th></th><th>Name</th><th>Category</th><th>Signer</th><th>Path</th><th></th></tr></thead><tbody>
    ${r.entries.map(e => `<tr data-ar="${e.id}">
      <td>${e.suspicion >= 2 ? pill("bad", "Check") : e.suspicion === 1 ? pill("warn", "?") : e.signed ? pill("good", "OK") : pill("unknown", "—")}</td>
      <td class="strong copy">${esc(e.name)}${e.reasons.length ? `<div class="muted" style="font-size:11px">${esc(e.reasons.join(" · "))}</div>` : ""}</td>
      <td>${esc(e.category)}</td>
      <td class="muted">${esc(e.signer || (e.signed ? "signed" : "unsigned"))}</td>
      <td class="mono copy" style="max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap" title="${esc(e.path)}">${esc(e.path || "—")}</td>
      <td style="width:90px">${e.exists ? `<button class="btn ghost small row-action" data-vtcheck="${e.id}">VirusTotal</button>` : ""}</td>
    </tr>`).join("")}</tbody></table></div>`;
}
$("#autorunsBody").addEventListener("click", async e => {
  const b = e.target.closest("[data-vtcheck]");
  if (!b) return;
  const entry = autorunsData.find(x => x.id === +b.dataset.vtcheck);
  if (!entry || !entry.path) return;
  $("#secTabs [data-sec='vt']").click();
  $("#vtResult").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Hashing ${esc(entry.name)}…</span></div>`;
  const h = await api.vt_hash_file(entry.path);
  if (!h.ok) { $("#vtResult").innerHTML = ""; toast(h.error, "bad"); return; }
  $("#vtHash").value = h.sha256;
  vtCheck(`${entry.name} (${fmtBytes(h.size)})`);
});

async function loadHijack() {
  $("#hijackBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Scanning…</span></div>`;
  const r = await api.hijack_scan();
  $("#hijackBody").innerHTML = r.clean
    ? emptyState("check", "No hijack indicators found", "Hosts file, proxy, homepages and search engines all look normal.")
    : r.findings.map(f => `<div class="check ${f.severity === "bad" ? "bad" : "warn"}">
        <div class="icon">${ico(f.severity === "bad" ? "x" : "bang")}</div>
        <div class="body"><div class="title">${esc(f.kind)} ${pill(f.severity === "bad" ? "bad" : "warn", f.severity === "bad" ? "Hijack" : "Check")}</div>
        <div class="detail">${esc(f.detail)}</div>
        ${f.items.length ? `<div class="detail mono copy" style="font-size:11px; margin-top:3px">${f.items.map(esc).join("<br>")}</div>` : ""}</div></div>`).join("");
}
$("#btnHijackScan").onclick = loadHijack;

async function loadRemote() {
  $("#remoteBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Scanning…</span></div>`;
  const r = await api.remote_access_audit();
  const tools = r.tools.length
    ? r.tools.map(t => `<div class="check ${t.running ? "bad" : "warn"}">
        <div class="icon">${ico(t.running ? "bang" : "q")}</div>
        <div class="body"><div class="title">${esc(t.name)} ${t.running ? pill("bad", "Running now") : pill("warn", "Installed")}</div>
        <div class="detail">Remote-access tool${t.running ? " — currently active. If you didn't start a support session, end it and investigate." : " is installed. Confirm you authorised it."}</div></div></div>`).join("")
    : `<div class="check good"><div class="icon">${ico("check")}</div><div class="body"><div class="title">No remote-access tools detected ${pill("good", "Clear")}</div><div class="detail">None of the common scam/remote tools are installed or running.</div></div></div>`;
  $("#remoteBody").innerHTML = tools + `
    <div class="drawer-sec">Local administrators (${r.admins.length})</div>
    <div class="mono-list">${r.admins.map(a => esc(a.name + "  (" + a.class + ")")).join("<br>") || "—"}</div>
    <div class="drawer-sec">Enabled local accounts</div>
    <div class="mono-list">${r.accounts.map(a => esc(a.name + (a.desc ? "  — " + a.desc : ""))).join("<br>") || "—"}</div>`;
}
$("#btnRemoteScan").onclick = loadRemote;

/* ================= process detail drawer ================= */
$("#procDrawerClose").onclick = () => { $("#drawer-veil").hidden = true; };
$("#drawer-veil").addEventListener("click", e => { if (e.target.id === "drawer-veil") $("#drawer-veil").hidden = true; });
async function openProcDrawer(pid) {
  $("#drawer-veil").hidden = false;
  $("#procDrawerTitle").textContent = `PID ${pid}`;
  $("#procDrawerBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Inspecting…</span></div>`;
  const d = await api.process_detail(pid);
  if (!d.ok) { $("#procDrawerBody").innerHTML = emptyState("q", d.error || "Gone"); return; }
  $("#procDrawerTitle").textContent = `${d.name} · ${d.pid}`;
  const kv = rows => `<dl class="kv tight">${rows.filter(r => r[1]).map(([k, v]) =>
    `<dt>${k}</dt><dd class="copy">${esc(v)}</dd>`).join("")}</dl>`;
  $("#procDrawerBody").innerHTML = kv([
    ["User", d.user], ["Status", d.status], ["Started", d.started], ["Parent", d.parent],
    ["Threads", d.threads], ["Memory", `${fmtBytes(d.rss)} (private ${fmtBytes(d.vms)})`],
    ["Path", d.exe], ["Command", d.cmdline], ["Working dir", d.cwd],
  ]) + `<div class="row mt"><button class="btn small" id="drawerOpenLoc">Open file location</button>
        <button class="btn small danger" id="drawerKill">End task</button></div>`
    + (d.connections.length ? `<div class="drawer-sec">Connections (${d.connections.length})</div>
       <div class="mono-list">${d.connections.map(c => esc(`${c.proto}  ${c.laddr} → ${c.raddr || "*"}  ${c.status}`)).join("<br>")}</div>` : "")
    + (d.open_files.length ? `<div class="drawer-sec">Open files (${d.open_files.length})</div>
       <div class="mono-list">${d.open_files.map(f => `<div title="${esc(f)}">${esc(f)}</div>`).join("")}</div>` : "")
    + (d.modules.length ? `<div class="drawer-sec">Loaded modules (${d.modules.length})</div>
       <div class="mono-list">${d.modules.map(m => `<div title="${esc(m)}">${esc(m)}</div>`).join("")}</div>` : "");
  const loc = $("#drawerOpenLoc");
  if (d.exe) loc.onclick = () => api.open_path(d.exe); else loc.disabled = true;
  $("#drawerKill").onclick = async () => {
    if (!await confirmModal("End task?", `Terminate ${d.name} (PID ${d.pid})?`, "End process")) return;
    const r = await api.kill_process(d.pid);
    toast(r.ok ? `Ended ${d.name}` : r.error, r.ok ? "good" : "bad");
    if (r.ok) { $("#drawer-veil").hidden = true; refreshProcs(); }
  };
}

/* ================= reliability timeline (Events) ================= */
let timelineLoaded = false;
async function loadTimeline() {
  const r = await api.get_reliability();
  const sparkW = 600, sparkH = 50;
  const m = r.metrics;
  let spark = "";
  if (m.length > 1) {
    const pts = m.map((x, i) => `${(i / (m.length - 1) * sparkW).toFixed(0)},${(sparkH - x.index / 10 * (sparkH - 4) - 2).toFixed(1)}`).join(" ");
    spark = `<svg viewBox="0 0 ${sparkW} ${sparkH}" style="width:100%; height:${sparkH}px" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="1.5"/></svg>`;
  }
  const dotLabel = { crash: "Crash", hardware: "Hardware", update: "Update", install: "Install", info: "Info" };
  $("#timelineBody").innerHTML = `
    <div class="card" style="margin-bottom:12px">
      <h3>Stability index <span class="right">${r.current_index !== null ? pill(r.current_index >= 8 ? "good" : r.current_index >= 5 ? "warn" : "bad", r.current_index + " / 10") : ""}
        ${r.whea_count ? pill("warn", r.whea_count + " hardware error(s)") : ""}</span></h3>
      ${spark || `<div class="muted" style="font-size:12px">Not enough reliability history yet.</div>`}
      <div class="muted" style="font-size:11px; margin-top:4px">Windows' own 1–10 reliability score over recent days. Dips line up with the events below.</div>
    </div>
    <div class="card"><h3>Timeline (90 days)</h3>
      ${r.timeline.length ? r.timeline.map(t => `<div class="tl-row">
        <div class="tl-marker"><span class="tl-dot ${t.type}"></span></div>
        <div class="tl-body"><div class="tl-time">${esc(t.time)} · ${dotLabel[t.type] || t.type} · ${esc(t.source)}</div>
        <div class="tl-msg">${esc(t.message)}</div></div></div>`).join("") : emptyState("check", "No reliability events recorded")}
    </div>`;
}

/* ================= FIX-IT page ================= */
let runbooks = [];
async function loadFixit() {
  runbooks = await api.list_runbooks();
  $("#runbookDetail").style.display = "none";
  $("#btnFixitBack").style.display = "none";
  $("#runbookList").style.display = "";
  $("#postScamCard").style.display = "";
  $("#runbookList").innerHTML = runbooks.map(rb => `
    <div class="card lift" data-runbook="${rb.id}" style="cursor:pointer">
      <h3 style="color:var(--text-1); text-transform:none; letter-spacing:0; font-size:14px; font-weight:600">${esc(rb.title)}</h3>
      <p class="muted" style="font-size:12.5px; line-height:1.5">${esc(rb.symptom)}</p>
      <div class="muted" style="font-size:11.5px; margin-top:8px">${rb.steps.length} steps →</div>
    </div>`).join("");
}
$("#runbookList").addEventListener("click", e => {
  const c = e.target.closest("[data-runbook]");
  if (c) openRunbook(c.dataset.runbook);
});
$("#btnPostScam").onclick = async () => {
  const btn = $("#btnPostScam"); btn.disabled = true;
  $("#postScamResult").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Checking remote tools, persistence, exclusions and accounts…</span></div>`;
  const r = await api.post_scam_check();
  btn.disabled = false;
  if (!r.ok) { $("#postScamResult").innerHTML = pill("bad", r.error || "failed"); return; }
  const findings = r.findings.length
    ? r.findings.map(f => `<div class="dom-flag ${f.level === "warn" ? "warn" : "info"}">${ico(f.level === "warn" ? "bang" : "q")}
        <span><b>${esc(f.title)}:</b> ${esc(f.detail)}</span></div>`).join("")
    : `<div class="dom-flag good">${ico("check")}<span>Nothing obviously wrong turned up. Still follow the steps below to be safe.</span></div>`;
  const steps = `<div class="dom-sec" style="margin-top:12px"><h4>What to do now — in this order</h4>
    <ol style="margin:0 0 0 18px; padding:0; font-size:12.5px; line-height:1.8">${r.checklist.map(s => `<li>${esc(s)}</li>`).join("")}</ol></div>`;
  $("#postScamResult").innerHTML = `<div class="dom-verdict">${findings}</div>${steps}
    <p class="muted" style="font-size:11.5px; margin-top:10px">This is triage, not a clean bill of health — for anything serious, a fresh Windows install is the only certainty.</p>`;
};
$("#btnFixitBack").onclick = loadFixit;
function openRunbook(id) {
  const rb = runbooks.find(r => r.id === id);
  if (!rb) return;
  $("#runbookList").style.display = "none";
  $("#postScamCard").style.display = "none";
  $("#btnFixitBack").style.display = "";
  $("#runbookDetail").style.display = "";
  $("#runbookDetail").innerHTML = `<div class="card">
    <h3 style="text-transform:none; letter-spacing:0; font-size:15px; color:var(--text-1)">${esc(rb.title)}</h3>
    <p class="muted" style="font-size:12.5px; margin-bottom:8px">${esc(rb.symptom)}</p>
    <div id="stepList">${rb.steps.map((s, i) => `
      <div class="step-row" data-step="${s.id}" id="step-${s.id}">
        <div class="step-num">${i + 1}</div>
        <div class="step-body">
          <div class="row" style="justify-content:space-between">
            <div><span style="font-weight:500; color:var(--text-1)">${esc(s.label)}</span>
              ${s.kind === "fix" ? pill("info", "fix") : `<span class="muted" style="font-size:11px">check</span>`}
              ${s.admin ? `<span class="muted" style="font-size:11px"> · needs admin</span>` : ""}</div>
            <button class="btn small ${s.kind === "fix" ? "danger" : ""}" data-runstep="${s.id}">${s.kind === "fix" ? "Run fix" : "Check"}</button>
          </div>
          ${s.note ? `<div class="muted" style="font-size:11.5px; margin-top:3px">${esc(s.note)}</div>` : ""}
          <div class="step-out" style="display:none"></div>
        </div>
      </div>`).join("")}</div>
  </div>`;
  $("#stepList").querySelectorAll("[data-runstep]").forEach(btn => btn.onclick = async () => {
    const stepId = btn.dataset.runstep;
    const step = rb.steps.find(s => s.id === stepId);
    if (step.kind === "fix" && !await confirmModal("Run this fix?",
        `"${step.label}". ${step.note || "This changes the system."}`, "Run fix")) return;
    btn.disabled = true; btn.innerHTML = `<span class="spin"></span>`;
    const r = await api.run_runbook_step(rb.id, stepId);
    btn.disabled = false; btn.textContent = step.kind === "fix" ? "Run fix" : "Check";
    const row = $(`#step-${stepId}`), out = row.querySelector(".step-out");
    out.style.display = "";
    if (!r.ok) { out.textContent = "⚠ " + (r.error || "failed"); return; }
    row.classList.add("done");
    out.textContent = r.output || "Done.";
    if (r.status === "bad") out.style.color = "var(--crit)";
    else if (r.status === "warn") out.style.color = "var(--warn)";
    else out.style.color = "";
  });
}

/* ================= HELPER page ================= */
function helperFlag(f) {
  const i = f.level === "good" ? "check" : f.level === "warn" ? "bang" : "q";
  return `<div class="dom-flag ${esc(f.level)}">${ico(i)}<span>${esc(f.text)}</span></div>`;
}
$("#btnHelperCard").onclick = async () => {
  $("#helperCardResult").innerHTML = `<div class="row"><span class="spin"></span></div>`;
  const h = await api.helper_card();
  if (!h.ok) { $("#helperCardResult").innerHTML = pill("bad", "Couldn't build the summary."); return; }
  const issues = h.issues.length
    ? h.issues.map(i => `<div class="dom-flag ${i.level === "bad" ? "warn" : "info"}">${ico(i.level === "bad" ? "bang" : "q")}<span>${esc(i.text)}</span></div>`).join("")
    : `<div class="dom-flag good">${ico("check")}<span>Nothing obvious looks wrong.</span></div>`;
  $("#helperCardResult").innerHTML = `<div style="font-weight:600; margin-bottom:6px">${esc(h.headline)} <span class="muted" style="font-weight:400">Score ${h.score}/100</span></div>
    <div class="dom-verdict">${issues}</div>
    ${h.facts.map(f => `<div class="muted" style="font-size:12px">${esc(f)}</div>`).join("")}
    <div class="row mt"><button class="btn small" id="btnHelperCopy"><svg class="ic sm"><use href="#i-copy"/></svg>Copy to send</button></div>`;
  $("#btnHelperCopy").onclick = () => navigator.clipboard.writeText(h.share_text).then(() => toast("Summary copied — paste it into a message", "good", 2500));
};
$("#btnQuietMode").onclick = async () => {
  if (!await confirmModal("Calm this computer down?",
    "Turns off taskbar widgets, tips, lock-screen ads, Start suggestions, web search in Start, the advertising ID and tailored experiences. All reversible in Cleanup → Tweaks.", "Quiet mode")) return;
  const r = await api.apply_quiet_mode();
  $("#quietResult").innerHTML = `<span style="color:var(--ok)">Silenced ${r.applied.length} source(s) of noise.</span>${r.skipped.length ? ` <span class="muted">(${r.skipped.length} need admin)</span>` : ""}`;
  toast("Quiet mode applied — sign out or restart Explorer to see the taskbar change", "good", 4000);
};
$("#btnDisplayCheck").onclick = async () => {
  const d = await api.detect_display();
  $("#displayResult").innerHTML = (d.flags || []).map(f => esc(f.text)).join(" · ")
    + (d.monitors.length ? `<div style="margin-top:4px">${d.monitors.map(m => `${esc(m.name)}: ${m.width}×${m.height}${m.refresh ? " @ " + m.refresh + "Hz" : ""}`).join(" · ")}</div>` : "");
};
$$("#page-helper [data-textscale]").forEach(b => b.onclick = async () => {
  const r = await api.set_text_scale(+b.dataset.textscale);
  toast(r.ok ? `Text size set to ${b.dataset.textscale}% — ${r.note}` : r.error, r.ok ? "good" : "bad", 4000);
});
$("#btnOpenDisplay").onclick = () => api.open_settings("ms-settings:display");
$("#btnAvCheck").onclick = async () => {
  $("#avResult").innerHTML = `<div class="row"><span class="spin"></span></div>`;
  const a = await api.av_check();
  const dev = (label, cap, data) => {
    const apps = data.apps.slice(0, 8).map(x => `<div class="dr"><span class="dk">${esc(x.name)}${x.in_use ? ` ${pill("info", "in use")}` : ""}</span>
      <span class="dv">${x.allowed ? pill("good", "Allowed") : pill("warn", "Blocked")}
      ${!x.allowed ? `<button class="btn ghost small" data-allow="${cap}|${esc(x.raw)}|${x.nonpackaged ? 1 : 0}">Allow</button>` : ""}</span></div>`).join("");
    return `<div class="dom-sec"><h4>${label} ${data.global === "Deny" ? pill("warn", "off for all apps") : pill("good", "on")}</h4>${apps || `<div class="muted" style="font-size:12px">No apps listed.</div>`}</div>`;
  };
  $("#avResult").innerHTML = `<div class="dom-verdict">${(a.flags || []).map(helperFlag).join("")}</div>
    <div class="dom-grid">${dev("Camera", "webcam", a.camera)}${dev("Microphone", "microphone", a.microphone)}</div>`;
  $("#avResult").querySelectorAll("[data-allow]").forEach(b => b.onclick = async () => {
    const [cap, raw, np] = b.dataset.allow.split("|");
    const r = await api.set_av_permission(cap, raw, np === "1", true);
    toast(r.ok ? "Allowed" : r.error, r.ok ? "good" : "bad", 3000);
    if (r.ok) $("#btnAvCheck").click();
  });
};
$("#btnBitlocker").onclick = async () => {
  $("#bitlockerResult").innerHTML = `<div class="row"><span class="spin"></span></div>`;
  const b = await api.bitlocker_status();
  const vols = b.volumes.map(v => `<div class="dr"><span class="dk strong">${esc(v.mount)}</span>
    <span class="dv">${v.on ? pill("good", "Encrypted") : `<span class="muted">Off</span>`}
    ${v.on ? (v.has_recovery ? `<button class="btn ghost small" data-bkey="${esc(v.mount)}">Show key</button>` : pill("warn", "no recovery key")) : ""}</span></div>`).join("");
  $("#bitlockerResult").innerHTML = `<div class="dom-verdict">${(b.flags || []).map(helperFlag).join("")}</div>${vols}`;
  $("#bitlockerResult").querySelectorAll("[data-bkey]").forEach(btn => btn.onclick = async () => {
    const r = await api.get_recovery_key(btn.dataset.bkey);
    if (!r.ok) { toast(r.error, "bad", 4000); return; }
    btn.outerHTML = `<span class="mono copy" style="font-size:12px; user-select:all">${esc(r.key)}</span>`;
    toast("Write this down and keep it somewhere safe — NOT only on this PC.", "info", 6000);
  });
};
$("#btnRescueScan").onclick = async () => {
  $("#rescueResult").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Measuring your folders…</span></div>`;
  const r = await api.rescue_scan();
  const rows = r.folders.map(f => `<div class="dr"><span class="dk strong">${esc(f.name)}</span><span class="dv">${fmtBytes(f.bytes)} · ${f.files} files</span></div>`).join("");
  $("#rescueResult").innerHTML = `<div class="dom-sec"><h4>What we'd copy <span class="right muted">${fmtBytes(r.total_bytes)} total</span></h4>${rows || `<div class="muted" style="font-size:12px">Nothing found in the usual folders.</div>`}</div>
    <div class="row wrap mt"><input class="input" id="rescueDest" placeholder="Destination drive, e.g. E:\\" style="width:240px" spellcheck="false">
      <button class="btn primary" id="btnRescueStart">Copy to that drive</button></div>
    <div class="console mt" id="rescueConsole" style="max-height:220px; display:none"></div>`;
  $("#btnRescueStart").onclick = async () => {
    const dest = $("#rescueDest").value.trim();
    const start = await api.rescue_start(dest);
    if (!start.ok) { toast(start.error, "bad", 5000); return; }
    const con = $("#rescueConsole"); con.style.display = ""; con.textContent = "";
    let off = 0, fails = 0;
    const poll = async () => {
      const s = await api.rescue_status(start.job, off);
      if (!s.ok) { if (++fails > 8) return; return void setTimeout(poll, 800); }
      fails = 0;
      if (s.lines.length) { off = s.total; con.textContent += s.lines.join("\n") + "\n"; con.scrollTop = con.scrollHeight; }
      if (s.done) { toast("Rescue copy finished", "good", 3000); return; }
      setTimeout(poll, 700);
    };
    poll();
  };
};
$("#btnScamClear").onclick = () => { $("#scamInput").value = ""; $("#scamResult").innerHTML = ""; };
$("#btnScamCheck").onclick = async () => {
  const text = $("#scamInput").value.trim();
  if (!text) return;
  $("#scamResult").innerHTML = `<div class="row"><span class="spin"></span></div>`;
  const looksUrl = /^https?:\/\/|^www\.|^[\w-]+\.[a-z]{2,}(\/|$)/i.test(text) && !/\s/.test(text);
  if (looksUrl) {
    const r = await api.unmask_url(text);
    if (!r.ok) { $("#scamResult").innerHTML = pill("bad", r.error); return; }
    const bad = (r.flags || []).some(f => f.level === "warn");
    $("#scamResult").innerHTML = `${scamLight(bad ? "amber" : "green")}
      <div style="margin-top:6px">${(r.flags || []).map(f => `<div class="muted" style="font-size:12px">• ${esc(f.text)}</div>`).join("")}</div>
      <div class="muted" style="font-size:12px; margin-top:4px">Goes to: <span class="mono">${esc(r.final_host || "?")}</span></div>
      <p class="muted" style="font-size:11.5px; margin-top:6px">Don't click the link unless you're sure. Type the company's address yourself instead.</p>`;
  } else {
    const r = await api.analyze_headers(text);
    if (!r.ok) { $("#scamResult").innerHTML = pill("bad", r.error + " (paste the email's text or headers)"); return; }
    const warns = (r.flags || []).filter(f => f.level === "warn");
    $("#scamResult").innerHTML = `${scamLight(warns.length >= 2 ? "red" : warns.length ? "amber" : "green")}
      <div style="margin-top:6px">${(r.flags || []).map(f => `<div class="muted" style="font-size:12px">• ${esc(f.text)}</div>`).join("")}</div>
      <p class="muted" style="font-size:11.5px; margin-top:6px">If anything's red, don't reply, click links or call numbers in it. Contact the company through a number you already trust.</p>`;
  }
};
function scamLight(c) {
  const map = { green: ["good", "Looks OK — but still be careful"], amber: ["warn", "Be careful — some warning signs"], red: ["bad", "Looks like a scam — do not trust it"] };
  const [cls, label] = map[c] || map.amber;
  return `<div class="dom-flag ${cls}" style="font-size:13px; font-weight:600">${ico(c === "green" ? "check" : "bang")}<span>${label}</span></div>`;
}

/* ================= HOME-LAB (Bundle D) ================= */
function dFlags(arr) { return (arr || []).map(f => { const i = f.level === "good" ? "check" : f.level === "warn" ? "bang" : "q"; return `<div class="dom-flag ${esc(f.level)}">${ico(i)}<span>${esc(f.text)}</span></div>`; }).join(""); }
$("#btnGpuForensics").onclick = async () => {
  $("#gpuForensicsBody").innerHTML = `<div class="row"><span class="spin"></span></div>`;
  const g = await api.gpu_forensics();
  const gpus = g.gpus.map(x => `<div class="dr"><span class="dk strong">${esc(x.name)}</span><span class="dv">${x.temp_c ?? "?"}°C · ${Math.round(x.clock_mhz || 0)}/${Math.round(x.max_clock_mhz || 0)} MHz · ${Math.round(x.power_w || 0)}/${Math.round(x.power_limit_w || 0)} W${x.throttle.length ? ` · ${pill("warn", "throttling: " + x.throttle.join(", "))}` : ""}</span></div>`).join("");
  const tdr = g.tdr_count ? `<div class="dom-sec" style="margin-top:8px"><h4>Driver resets (TDR) — last 30 days <span class="right">${g.tdr_count}</span></h4>${g.tdr_times.map(t => `<div class="muted mono" style="font-size:11px">${esc(t)}</div>`).join("")}</div>` : "";
  $("#gpuForensicsBody").innerHTML = `<div class="dom-verdict">${dFlags(g.flags)}</div>${gpus}${tdr}`;
};
$("#btnDisplayLinks").onclick = async () => {
  $("#displayLinksBody").innerHTML = `<div class="row"><span class="spin"></span></div>`;
  const l = await api.display_links();
  const rows = l.monitors.map(m => `<div class="dr"><span class="dk strong">${esc(m.name)}</span><span class="dv">${m.width}×${m.height} @ ${m.refresh}Hz${m.underclocked ? ` ${pill("warn", "max " + m.max_refresh + "Hz")}` : ` ${pill("good", "best")}`}</span></div>`).join("");
  $("#displayLinksBody").innerHTML = `<div class="dom-verdict">${dFlags(l.flags)}</div>${rows}`;
};
$("#btnVirt").onclick = async () => {
  $("#virtBody").innerHTML = `<div class="row"><span class="spin"></span></div>`;
  const v = await api.virt_health();
  let wsl = "";
  if (v.wsl.installed) {
    const distros = v.wsl.distros.map(d => `${esc(d.name)} (v${d.version}, ${esc(d.state)})`).join(", ") || "none";
    const vhdx = v.wsl.vhdx.map((x, i) => `<div class="dr"><span class="dk mono" style="font-size:11px; word-break:break-all">${esc(x.path)}</span><span class="dv">${fmtBytes(x.bytes)} ${x.bytes > 21474836480 ? `<button class="btn ghost small" data-vhdx="${esc(x.path)}">Compact</button>` : ""}</span></div>`).join("");
    wsl = `<div class="dom-sec"><h4>WSL</h4><div class="muted" style="font-size:12px">Distros: ${distros}${v.wsl.mem_cap ? ` · memory cap ${esc(v.wsl.mem_cap)}` : " · no memory cap set"}</div>${vhdx}</div>`;
  } else wsl = `<div class="dom-sec"><h4>WSL</h4><div class="muted" style="font-size:12px">Not installed.</div></div>`;
  const sw = v.switches.length ? `<div class="dom-sec"><h4>Hyper-V switches</h4>${v.switches.map(s => `<div class="dr"><span class="dk">${esc(s.name)}</span><span class="dv muted">${esc(s.type)}${s.adapter ? " · " + esc(s.adapter) : ""}</span></div>`).join("")}</div>` : "";
  $("#virtBody").innerHTML = `<div class="dom-verdict">${dFlags(v.flags)}</div>
    <div class="muted" style="font-size:12px; margin-bottom:6px">VT-x: ${v.vt_enabled ? "on" : "off"} · Hyper-V: ${v.hyperv ? "present" : "no"}</div>
    <div class="dom-grid">${wsl}${sw}</div>`;
  $("#virtBody").querySelectorAll("[data-vhdx]").forEach(b => b.onclick = async () => {
    if (!await confirmModal("Compact this virtual disk?", "Shrinks the file to reclaim space (non-destructive). Shut down WSL first (wsl --shutdown) for it to free much.", "Compact")) return;
    b.disabled = true; b.textContent = "Working…";
    const r = await api.compact_vhdx(b.dataset.vhdx);
    toast(r.ok ? r.detail : r.error, r.ok ? "good" : "bad", 5000); b.disabled = false; b.textContent = "Compact";
  });
};
$("#btnSmartPredict").onclick = async () => {
  $("#smartPredictBody").innerHTML = `<div class="row"><span class="spin"></span></div>`;
  const s = await api.smart_predict();
  const lvl = { alert: pill("bad", "Replace soon"), watch: pill("warn", "Watch"), ok: pill("good", "OK") };
  const rows = s.disks.map(d => `<div class="dr"><span class="dk">${lvl[d.level]} <span class="strong">${esc(d.name)}</span>
    ${d.reasons.length ? `<div class="muted" style="font-size:11px">${esc(d.reasons.join(" · "))}</div>` : ""}</span>
    <span class="dv muted" style="font-size:11.5px">${d.wear_pct != null ? `wear ${d.wear_pct}% · ` : ""}${d.power_on_hours != null ? `${d.power_on_hours}h · ` : ""}${d.temp_c ? d.temp_c + "°C · " : ""}${d.samples} sample(s)</span></div>`).join("");
  $("#smartPredictBody").innerHTML = `<div class="dom-verdict">${dFlags(s.flags)}</div>${rows}`;
};
$("#btnBufferbloat").onclick = async () => {
  $("#btnBufferbloat").disabled = true;
  $("#bufferbloatBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Measuring idle, then saturating the link…</span></div>`;
  const b = await api.bufferbloat_test();
  $("#btnBufferbloat").disabled = false;
  if (!b.ok) { $("#bufferbloatBody").innerHTML = pill("bad", b.error); return; }
  const grade = b.grade === "A" || b.grade === "B" ? "good" : b.grade === "C" ? "warn" : "bad";
  $("#bufferbloatBody").innerHTML = `<div class="speed-row">
      <div class="speed-kpi"><div class="v">${b.grade}</div><div class="l">Bufferbloat grade</div></div>
      <div class="speed-kpi"><div class="v">${b.idle_ms}<small> ms</small></div><div class="l">Idle latency</div></div>
      <div class="speed-kpi"><div class="v">${b.loaded_ms}<small> ms</small></div><div class="l">Under load</div></div>
      <div class="speed-kpi"><div class="v">+${b.added_ms}<small> ms</small></div><div class="l">Added by load</div></div>
    </div><div class="dom-verdict mt">${dFlags(b.flags)}</div>`;
};

/* ================= CLEANUP page ================= */
$$("#cleanTabs .tab").forEach(t => t.addEventListener("click", () => {
  const which = t.dataset.clean;
  $$("#cleanTabs .tab").forEach(x => x.classList.toggle("active", x === t));
  for (const [k, id] of [["junk", "cleanTabJunk"], ["large", "cleanTabLarge"],
                         ["debloat", "cleanTabDebloat"], ["tweaks", "cleanTabTweaks"], ["repair", "cleanTabRepair"]])
    $("#" + id).style.display = which === k ? "" : "none";
  if (which === "debloat" && !cleanLoaded.debloat) { cleanLoaded.debloat = true; loadDebloat(); }
  if (which === "tweaks" && !cleanLoaded.tweaks) { cleanLoaded.tweaks = true; loadTweaks(); }
  if (which === "repair" && !cleanLoaded.repair) { cleanLoaded.repair = true; loadShellRepairs(); }
}));
const cleanLoaded = {};
async function loadShellRepairs() {
  const items = await api.list_shell_repairs();
  $("#repairBody").innerHTML = items.map(r => `
    <div class="toggle-row">
      <div class="t-info">
        <div class="t-name">${esc(r.label)}${r.admin ? `<span class="muted" style="font-size:11px"> · admin</span>` : ""}</div>
        <div class="t-help">${esc(r.fixes)}</div>
        <div class="t-help mono copy" style="font-size:10.5px; margin-top:2px; opacity:0.8">${esc(r.where)}</div>
      </div>
      <button class="btn small" data-repair="${r.key}">Repair</button>
    </div>`).join("");
  $("#repairBody").querySelectorAll("[data-repair]").forEach(b => b.onclick = async () => {
    b.disabled = true; b.textContent = "Working…";
    const r = await api.run_shell_repair(b.dataset.repair);
    b.disabled = false; b.textContent = r.ok ? "Done" : "Repair";
    toast(r.ok ? r.message : r.error, r.ok ? "good" : "bad", 4000);
    if (r.ok && r.restart) $("#repairExplorerRow").style.display = "";
  });
}
$("#btnRepairRestartExplorer").onclick = async () => {
  const r = await api.restart_explorer();
  toast(r.ok ? "Explorer restarted" : r.error, r.ok ? "good" : "bad");
  if (r.ok) $("#repairExplorerRow").style.display = "none";
};
function loadCleanup() { /* junk tab is on-demand via button */ }

/* ================= WORKPLACE page (identity, licensing, policy, baseline) ================= */
let wpBaselineLoaded = false;
function loadWorkplace() {
  loadWpPosture();
}
$("#btnWpRefresh").onclick = () => { loadWpPosture(); if (wpBaselineLoaded) loadWpBaseline(); };
$$("#wpTabs .tab").forEach(t => t.addEventListener("click", () => {
  $$("#wpTabs .tab").forEach(x => x.classList.toggle("active", x === t));
  const which = t.dataset.wp;
  $("#wpTabPosture").style.display = which === "posture" ? "" : "none";
  $("#wpTabBaseline").style.display = which === "baseline" ? "" : "none";
  if (which === "baseline" && !wpBaselineLoaded) { wpBaselineLoaded = true; loadWpBaseline(); }
}));

const wpLevelPill = (lvl, txt) => pill(lvl === "good" ? "good" : lvl === "bad" ? "bad" : lvl === "warn" ? "warn" : "info", txt);
const wpRow = (k, v) => `<div class="dr"><span class="dk">${esc(k)}</span><span class="dv">${v}</span></div>`;

async function loadWpPosture() {
  const el = $("#wpPosture");
  el.innerHTML = `<div class="card"><div class="row"><span class="spin"></span><span class="muted">Reading machine posture…</span></div></div>`;
  const [lic, idn, gpo, time] = await Promise.all([
    api.licensing_status().catch(() => null),
    api.identity_status().catch(() => null),
    api.gpo_results().catch(() => null),
    api.time_status().catch(() => null),
  ]);

  // Activation & licensing
  let licCard = `<div class="card"><h3>Activation &amp; licensing</h3>`;
  if (lic && lic.ok) {
    licCard += `<div class="dom-flag ${lic.level}">${ico(lic.level === "good" ? "check" : "bang")}<span>${esc(lic.status)} — ${esc(lic.detail)}</span></div>
      <div class="dom-sec" style="margin-top:8px">
      ${wpRow("Edition", esc(lic.edition || "—"))}
      ${wpRow("Channel", esc(lic.channel || "—"))}
      ${lic.partial_key ? wpRow("Active key (last 5)", `<span class="mono copy">${esc(lic.partial_key)}</span>`) : ""}
      ${lic.oem_key ? wpRow("Firmware (OEM) key", `<span class="mono copy" title="The product key embedded in this PC's firmware — its own key">${esc(lic.oem_key)}</span>`) : ""}
      ${lic.kms_host ? wpRow("KMS host", esc(lic.kms_host)) : ""}
      ${lic.grace_days != null ? wpRow("Grace remaining", lic.grace_days + " days") : ""}
      </div>`;
  } else { licCard += emptyState("bang", "Couldn't read licensing"); }
  licCard += `</div>`;

  // Identity & domain
  let idCard = `<div class="card"><h3>Identity &amp; domain</h3>`;
  if (idn && idn.ok) {
    idCard += `<div class="row" style="margin-bottom:8px">${wpLevelPill(idn.level, idn.verdict)}${idn.managed ? pill("warn", "centrally managed") : ""}</div>
      <div class="dom-sec">
      ${wpRow("Signed-in user", esc(idn.user || "—"))}
      ${idn.upn ? wpRow("UPN", esc(idn.upn)) : ""}
      ${idn.domain ? wpRow("Domain", esc(idn.domain)) : wpRow("Workgroup", esc(idn.workgroup || "—"))}
      ${idn.role ? wpRow("Role", esc(idn.role)) : ""}
      ${idn.rows.map(r => wpRow(r.label, esc(r.value))).join("")}
      </div>`;
  } else { idCard += emptyState("bang", "Couldn't read identity"); }
  idCard += `</div>`;

  // Group policy
  let gpoCard = `<div class="card"><h3>Group Policy</h3>`;
  if (gpo && gpo.ok) {
    const gpoList = (s) => s.applied.length
      ? s.applied.map(g => `<div class="dr"><span class="dk strong">${esc(g)}</span><span class="dv good">applied</span></div>`).join("")
      : `<div class="muted" style="font-size:12px">None applied.</div>`;
    gpoCard += `<p class="muted" style="font-size:12.5px; margin-bottom:8px">${esc(gpo.summary)}</p>
      <div class="dom-sec"><h4>Computer scope${gpo.computer_needs_admin ? ` ${pill("info", "needs admin")}` : ""}</h4>
        ${gpo.computer.last_applied ? `<div class="muted" style="font-size:11px; margin-bottom:4px">Last applied ${esc(gpo.computer.last_applied)}</div>` : ""}
        ${gpoList(gpo.computer)}</div>
      <div class="dom-sec"><h4>User scope</h4>
        ${gpo.user.last_applied ? `<div class="muted" style="font-size:11px; margin-bottom:4px">Last applied ${esc(gpo.user.last_applied)}</div>` : ""}
        ${gpoList(gpo.user)}</div>`;
  } else { gpoCard += emptyState("bang", "Couldn't read Group Policy"); }
  gpoCard += `</div>`;

  // Time sync
  let timeCard = `<div class="card"><h3>Clock &amp; time sync <span class="right"><button class="btn small" id="btnTimeResync">Resync now</button></span></h3>`;
  if (time && time.ok) {
    timeCard += `<div class="dom-flag ${time.level}">${ico(time.level === "good" ? "check" : "bang")}<span>${esc(time.verdict)}</span></div>
      <div class="dom-sec" style="margin-top:8px">
      ${time.offset_s != null ? wpRow("Current offset", `<span class="mono">${time.offset_s > 0 ? "+" : ""}${time.offset_s}s</span>`) : ""}
      ${wpRow("Source", esc(time.source || "—"))}
      ${wpRow("Sync type", esc(time.sync_type || "—"))}
      ${time.last_sync ? wpRow("Last sync", esc(time.last_sync)) : ""}
      ${wpRow("Time service", `<span class="${time.service_concern ? "strong" : "muted"}">${esc(time.service)}</span>`)}
      </div>`;
  } else { timeCard += emptyState("bang", "Couldn't read time sync"); }
  timeCard += `</div>`;

  el.innerHTML = licCard + idCard + gpoCard + timeCard;
  const rsBtn = $("#btnTimeResync");
  if (rsBtn) rsBtn.onclick = async () => {
    rsBtn.disabled = true; rsBtn.textContent = "Syncing…";
    const r = await api.time_resync();
    toast(r.ok ? (r.message || "Time resynced") : (r.error || "Resync failed"), r.ok ? "good" : "bad");
    rsBtn.disabled = false; rsBtn.textContent = "Resync now";
    if (r.ok) loadWpPosture();
  };
}

/* ---- Managed baseline (F5 configurator) ---- */
function wpBaselineWidget(c) {
  const cur = c.current;
  if (c.gated) return `<span class="muted" style="font-size:11.5px">${esc(c.gated)}</span>`;
  if (c.type === "toggle") {
    const on = cur === 1;
    return `<select class="input small" id="bw_${c.key}" style="width:90px">
      <option value="1"${on ? " selected" : ""}>On</option>
      <option value="0"${cur === 0 ? " selected" : ""}>Off</option></select>`;
  }
  if (c.type === "number") {
    const v = cur != null ? cur : c.recommended;
    return `<input class="input small" type="number" id="bw_${c.key}" min="${c.min}" max="${c.max}" value="${v}" style="width:90px"> <span class="muted" style="font-size:11px">${esc(c.unit || "")}</span>`;
  }
  if (c.type === "choice") {
    return `<select class="input small" id="bw_${c.key}" style="width:auto">${c.options.map(o => `<option value="${o[0]}"${cur === o[0] ? " selected" : ""}>${esc(o[1])}</option>`).join("")}</select>`;
  }
  // string
  return `<input class="input small" type="text" id="bw_${c.key}" value="${esc(cur != null ? cur : "")}" placeholder="${esc(c.placeholder || "")}" style="width:120px">`;
}
function wpCurrentText(c) {
  if (c.current == null) return `<span class="muted">not set — Windows default</span>`;
  if (c.type === "toggle") return `<span class="strong">${c.current === 1 ? "On" : "Off"}</span>`;
  if (c.type === "choice") { const o = c.options.find(o => o[0] === c.current); return `<span class="strong">${esc(o ? o[1] : String(c.current))}</span>`; }
  return `<span class="strong">${esc(String(c.current))}${c.unit ? " " + esc(c.unit) : ""}</span>`;
}
async function loadWpBaseline() {
  const el = $("#wpBaseline");
  el.innerHTML = `<div class="card"><div class="row"><span class="spin"></span><span class="muted">Reading policy state…</span></div></div>`;
  const r = await api.baseline_read().catch(() => null);
  if (!r || !r.ok) { el.innerHTML = `<div class="card">${emptyState("bang", "Couldn't read the policy baseline")}</div>`; return; }
  const ctx = r.context || {};
  const banners = [];
  if (!r.is_admin) banners.push(`<div class="dom-flag warn">${ico("bang")}<span>Run as admin to change any of these — they're machine-wide policies. You can read the current state without it.</span></div>`);
  if (ctx.managed) banners.push(`<div class="dom-flag bad">${ico("bang")}<span>This machine is centrally managed (${esc(ctx.managed_verdict || "GPO/Intune")}). Setting policy here may be overwritten on the next policy refresh — this screen is meant for unmanaged PCs.</span></div>`);

  // group controls by category
  const cats = {};
  r.controls.forEach(c => { (cats[c.cat] = cats[c.cat] || []).push(c); });
  const catHtml = Object.entries(cats).map(([cat, items]) => `
    <div class="card" style="margin-bottom:12px"><h3>${esc(cat)}</h3>
    ${items.map(c => `<div class="b-ctrl" style="padding:10px 0; border-top:1px solid var(--line)">
      <div class="row" style="justify-content:space-between; align-items:flex-start; gap:12px">
        <div style="flex:1; min-width:0">
          <div class="strong">${esc(c.label)}</div>
          <div class="muted" style="font-size:11.5px; line-height:1.5; margin:2px 0">${esc(c.help)}</div>
          <div style="font-size:11px">Current: ${wpCurrentText(c)} · <span class="mono" style="opacity:.6">${esc(c.where)}</span></div>
        </div>
        <div class="row" style="gap:6px; align-items:center; flex-shrink:0">
          ${wpBaselineWidget(c)}
          ${!c.gated ? `<button class="btn small primary b-apply" data-bkey="${c.key}" ${r.is_admin ? "" : "disabled"}>Apply</button>` : ""}
          ${!c.gated && c.set ? `<button class="btn small ghost b-clear" data-bkey="${c.key}" ${r.is_admin ? "" : "disabled"} title="Delete the policy — back to Windows default">Clear</button>` : ""}
        </div>
      </div></div>`).join("")}
    </div>`).join("");

  const pw = (r.password_policy && r.password_policy.length) ? `<div class="card" style="margin-bottom:12px">
    <h3>Password &amp; lockout policy <span class="right muted" style="font-size:11px">read-only</span></h3>
    <div class="dom-sec">${r.password_policy.map(p => wpRow(p.label, `<span class="strong">${esc(p.value)}</span>`)).join("")}</div></div>` : "";

  const head = `<div class="card" style="margin-bottom:12px">
    <p class="muted" style="font-size:12.5px; line-height:1.55; margin-bottom:10px">
      The policies an admin usually pushes via GPO or Intune — set them here on a standalone PC. Every change shows the
      exact registry key, and <span class="strong">Clear</span> deletes the policy to return to the Windows default.
      <span class="muted">Edition: ${esc(ctx.edition || "—")}${ctx.has_tpm ? " · TPM present" : " · no TPM detected"}</span>
    </p>
    ${banners.join("")}
    <div class="row"><button class="btn ghost small" id="btnBaselineExport"><svg class="ic sm"><use href="#i-copy"/></svg>Export current state (JSON)</button></div>
  </div>`;

  el.innerHTML = head + catHtml + pw;

  $$("#wpBaseline .b-apply").forEach(b => b.onclick = async () => {
    const key = b.dataset.bkey;
    const w = $("#bw_" + key);
    const val = w ? w.value : "";
    b.disabled = true;
    const res = await api.baseline_apply(key, val);
    toast(res.ok ? `Applied — ${res.where}` : (res.error || "Couldn't apply"), res.ok ? "good" : "bad", 3500);
    b.disabled = false;
    if (res.ok) loadWpBaseline();
  });
  $$("#wpBaseline .b-clear").forEach(b => b.onclick = async () => {
    const key = b.dataset.bkey;
    if (!confirm("Delete this policy and return the setting to its Windows default?")) return;
    b.disabled = true;
    const res = await api.baseline_clear(key);
    toast(res.ok ? "Cleared — back to Windows default" : (res.error || "Couldn't clear"), res.ok ? "good" : "bad");
    b.disabled = false;
    if (res.ok) loadWpBaseline();
  });
  const exp = $("#btnBaselineExport");
  if (exp) exp.onclick = async () => {
    const e = await api.baseline_export();
    if (e && e.ok) navigator.clipboard.writeText(JSON.stringify(e, null, 2)).then(() => toast("Baseline JSON copied", "good", 2000));
  };
}

$("#btnJunkScan").onclick = async () => {
  $("#junkBody").innerHTML = `<div class="row"><span class="spin"></span><span class="muted">Measuring caches…</span></div>`;
  const r = await api.scan_junk();
  $("#junkTotal").textContent = r.total ? pill("info", fmtBytes(r.total) + " reclaimable") : "";
  if (!r.categories.length) { $("#junkBody").innerHTML = emptyState("check", "Nothing to clean"); return; }
  $("#junkBody").innerHTML = r.categories.map(c => `
    <label class="pick-row"><input type="checkbox" checked data-junk="${c.id}" data-path="${esc(c.path)}">
      <span class="p-name">${esc(c.label)}${c.path ? `<div class="mono" style="font-size:10.5px; color:var(--text-3); opacity:0.8">${esc(c.path)}</div>` : ""}</span>
      <span class="muted">${fmtBytes(c.size)}</span></label>`).join("")
    + `<div class="row mt"><button class="btn primary" id="btnJunkClean">Clean selected</button>
       <span class="muted" id="junkCleanStatus"></span></div>`;
  $("#btnJunkClean").onclick = async () => {
    const boxes = [...$("#junkBody").querySelectorAll("[data-junk]:checked")];
    const ids = boxes.map(c => c.dataset.junk);
    if (!ids.length) return;
    const paths = boxes.map(c => c.dataset.path || "Recycle Bin").filter(Boolean).join("\n");
    if (!await confirmModal("Clean junk?", "Deletes the selected temp files and caches. Your documents are never touched.", "Clean",
        "Deletes the contents of:\n" + paths)) return;
    $("#junkCleanStatus").innerHTML = `<span class="spin"></span>`;
    const res = await api.clean_junk(ids);
    toast(`Freed ${fmtBytes(res.freed)}`, "good");
    $("#btnJunkScan").click();
  };
};

$("#btnBigScan").onclick = async () => {
  const path = $("#bigPath").value.trim();
  if (!path) { toast("Enter a folder.", "bad"); return; }
  $("#bigStatus").innerHTML = `<span class="spin"></span>`;
  const r = await api.find_large_files(path, 100);
  $("#bigStatus").textContent = r.ok ? `${r.count} file(s) over 100 MB` : "";
  if (!r.ok) { toast(r.error, "bad"); return; }
  renderFileList(r.files, "Large files");
};
let dupRunning = false;
$("#btnDupScan").onclick = async () => {
  if (dupRunning) return;
  const path = $("#bigPath").value.trim();
  if (!path) { toast("Enter a folder.", "bad"); return; }
  const r = await api.start_duplicate_scan(path);
  if (!r.ok) { toast(r.error, "bad"); return; }
  dupRunning = true;
  $("#btnDupScan").disabled = true;
  $("#bigStatus").innerHTML = `<span class="spin"></span> scanning…`;
  let fails = 0;
  const stop = () => { dupRunning = false; $("#btnDupScan").disabled = false; };
  const poll = async () => {
    let j;
    try { j = await api.get_duplicate_job(r.job); }
    catch { if (++fails > 8) { stop(); $("#bigStatus").textContent = ""; return; } setTimeout(poll, 1500); return; }
    if (!j.ok) { stop(); $("#bigStatus").textContent = ""; toast("Duplicate scan failed", "bad"); return; }
    $("#bigStatus").textContent = j.done ? `${j.groups.length} duplicate set(s) · ${fmtBytes(j.wasted)} wasted` : `${j.phase}… ${j.scanned} hashed`;
    if (!j.done) { setTimeout(poll, 700); return; }
    stop();
    $("#bigResult").innerHTML = j.groups.length ? j.groups.map(g => `
      <div class="card" style="margin-bottom:8px; padding:12px">
        <div class="row" style="justify-content:space-between; margin-bottom:6px">
          <span class="strong">${g.count} copies · ${fmtBytes(g.size)} each · ${fmtBytes(g.wasted)} wasted</span></div>
        ${g.files.map((f, i) => `<div class="an-row"><span class="nm copy" title="${esc(f)}">${esc(f)}</span>
          ${i === 0 ? `<span class="muted" style="font-size:11px">keep</span>` : `<button class="btn ghost small" data-recycle="${esc(f)}">Recycle</button>`}</div>`).join("")}
      </div>`).join("") : emptyState("check", "No duplicates found");
  };
  poll();
};
$("#bigResult").addEventListener("click", async e => {
  const b = e.target.closest("[data-recycle]");
  if (!b) return;
  if (!await confirmModal("Recycle file?", "Send this file to the Recycle Bin? It stays recoverable until the bin is emptied.", "Recycle", b.dataset.recycle)) return;
  const r = await api.recycle_files([b.dataset.recycle]);
  toast(r.ok ? "Sent to Recycle Bin" : r.error, r.ok ? "good" : "bad");
  if (r.ok) b.closest(".an-row").remove();
});
function renderFileList(files, title) {
  $("#bigResult").innerHTML = `<div class="card"><h3>${title}</h3>${files.length ? files.map(f => `
    <div class="an-row"><span class="nm copy" title="${esc(f.path)}">${esc(f.path)}</span>
      <span class="sz">${fmtBytes(f.size)}</span>
      <button class="btn ghost small row-action" data-recycle="${esc(f.path)}">Recycle</button>
      <button class="btn ghost small row-action" data-reveal="${esc(f.path)}">${ico("open", "ic sm")}</button></div>`).join("")
    : emptyState("check", "No files over the threshold")}</div>`;
}
$("#bigResult").addEventListener("click", e => {
  const r = e.target.closest("[data-reveal]");
  if (r) api.open_path(r.dataset.reveal);
});

async function loadDebloat() {
  const apps = await api.list_appx();
  const groups = { bloat: "Recommended to remove", optional: "Optional", other: "Other apps" };
  $("#debloatBody").innerHTML = Object.keys(groups).map(g => {
    const list = apps.filter(a => a.category === g);
    if (!list.length) return "";
    return `<div class="drawer-sec">${groups[g]}</div>` + list.map(a => `
      <label class="pick-row"><input type="checkbox" ${g === "bloat" ? "checked" : ""} data-appx="${esc(a.full_name)}">
        <span class="p-name">${esc(a.friendly)} ${g === "bloat" ? `<span class="tag-bloat">bloat</span>` : ""}
          <span class="muted" style="font-size:11px"> · ${esc(a.publisher)}</span></span></label>`).join("");
  }).join("") + `<div class="row mt"><button class="btn danger" id="btnDebloat">Remove selected</button>
    <span class="muted" id="debloatStatus"></span></div>`;
  $("#btnDebloat").onclick = async () => {
    const names = [...$("#debloatBody").querySelectorAll("[data-appx]:checked")].map(c => c.dataset.appx);
    if (!names.length) return;
    if (!await confirmModal("Remove apps?", `Uninstall ${names.length} app(s) for the current user? They can be reinstalled from the Store.`, "Remove",
        "Runs Remove-AppxPackage for the current user only. System packages are never touched; nothing is deleted for other users.")) return;
    $("#debloatStatus").innerHTML = `<span class="spin"></span>`;
    const r = await api.remove_appx(names);
    toast(`Removed ${r.removed}${r.errors.length ? `, ${r.errors.length} failed` : ""}`, r.errors.length ? "warn" : "good");
    cleanLoaded.debloat = false; loadDebloat();
  };
}

async function loadTweaks() {
  const r = await api.get_tweaks();
  const cats = ["Performance", "Gaming", "Network & power", "Privacy", "Interface", "Ads & noise"];
  $("#tweaksBody").innerHTML = cats.map(cat => {
    const items = r.items.filter(i => i.cat === cat);
    if (!items.length) return "";
    return `<div class="card" style="margin-bottom:12px"><h3>${cat}</h3>` + items.map(i => `
      <div class="toggle-row">
        <div class="t-info">
          <div class="t-name">${esc(i.label)}${i.admin ? `<span class="muted" style="font-size:11px"> · admin</span>` : ""}${i.restart === "reboot" ? `<span class="muted" style="font-size:11px"> · needs reboot</span>` : ""}</div>
          <div class="t-help">${esc(i.help)}</div>
          <div class="t-help mono copy" style="font-size:10.5px; margin-top:2px; opacity:0.8">${esc(i.where)}</div>
        </div>
        <button class="switch ${i.enabled ? "on" : ""}" role="switch" aria-checked="${i.enabled}" aria-label="${esc(i.label)}" data-tweak="${i.key}" data-restart="${i.restart || ""}" ${i.admin && !r.is_admin ? "disabled" : ""}></button>
      </div>`).join("") + `</div>`;
  }).join("");
  $("#tweaksBody").querySelectorAll("[data-tweak]").forEach(sw => sw.onclick = async () => {
    const enable = !sw.classList.contains("on");
    const res = await api.set_tweak(sw.dataset.tweak, enable);
    if (!res.ok) { toast(res.error, "bad"); return; }
    sw.classList.toggle("on", enable);
    sw.setAttribute("aria-checked", String(enable));
    toast(enable ? "Applied" : "Restored Windows default", "good", 1500);
    if (sw.dataset.restart === "explorer") $("#explorerRow").style.display = "";
    if (sw.dataset.restart === "reboot") toast("Takes effect after a reboot.", "info", 3000);
  });
}
$("#cleanTabTweaks").addEventListener("click", async e => {
  const plan = e.target.closest("[data-plan]");
  if (plan) {
    const r = await api.set_power_plan(plan.dataset.plan);
    $("#planStatus").textContent = r.ok ? `Active: ${r.label}` : "";
    toast(r.ok ? `Power plan: ${r.label}` : r.error, r.ok ? "good" : "bad");
  }
});
$("#btnRestartExplorer").onclick = async () => {
  const r = await api.restart_explorer();
  toast(r.ok ? "Explorer restarted" : r.error, r.ok ? "good" : "bad");
  if (r.ok) $("#explorerRow").style.display = "none";
};

/* ================= in-app changelog ================= */
const CHANGELOG = [
  { v: "2.9.0", name: "One-stop tools, deeper diagnostics & UI polish", items: [
    "File hash (Toolbox) — MD5 / SHA-1 / SHA-256 of any file, computed locally; pairs with the VirusTotal check.",
    "Hosts file viewer (Toolbox) — shows active host overrides and flags non-default entries (a redirect/hijack check).",
    "SMART attributes (Storage) — the raw drive self-monitoring counters, with reallocated/pending/uncorrectable sectors flagged.",
    "Crash-dump suspects (Event Log → Crashes) — the third-party drivers loaded in your minidumps, the usual BSOD culprits.",
    "Five more tweaks (53 total): a new Network & power group (disable IPv6, show Hibernate), plus 'Take ownership' right-click, This PC on the desktop, and drive letters before names.",
    "UI fixes from a full design + accessibility sweep: the sidebar number shortcuts now read in a clean 1–0 sequence, and tweak toggles and inputs are properly labelled for screen readers.",
  ] },
  { v: "2.8.1", name: "23 more tweaks", items: [
    "Cleanup → Tweaks grew from 25 to 48 reversible toggles, including a new Gaming group.",
    "Gaming: disable mouse acceleration, Game DVR background recording, and network throttling.",
    "Performance: disable transparency effects, window animations, and Fast Startup (the true-full-shutdown fix).",
    "Privacy: disable Activity History, Cortana, inking/typing personalization, most-used-app tracking, and language-list sharing.",
    "Interface: hide Task View, compact Explorer, disable Aero Shake, snappier menus, full path in title bar, and 'End task' on the taskbar right-click.",
    "Ads & noise: hide File Explorer promos, 'Finish setting up' nags, the post-update welcome page, suggested actions, and Start menu recommendations — the new ones also fold into the one-click 'calm this PC down'.",
  ] },
  { v: "2.8.0", name: "The repair bench — fixes, decoding & accessibility", items: [
    "Error-code decoder (Toolbox / Ctrl+K) — paste any 0x8007…, NTSTATUS, Stop code or decimal and get plain English: the meaning, the HRESULT severity/facility breakdown, and Windows-Update-specific advice.",
    "What's locking this file? (Toolbox) — enter a path and see which processes hold it open: the 'can't delete, it's in use' answer.",
    "Full network reset (Toolbox) — Winsock + TCP/IP stack reset, flush DNS and release/renew in one guided run, plus a standalone TCP/IP stack reset.",
    "User profile health (Toolbox) — read-only detection of corrupted (.bak) and temporary user profiles.",
    "Re-register Store & built-in apps (Toolbox) — the standard fix for a broken Start menu or Store; per-user and reversible.",
    "Blue screens now name the Stop code (Event Log → Crashes) — e.g. 0x000000D1 DRIVER_IRQL_NOT_LESS_OR_EQUAL — and Kernel-Power 41 events that carried a bugcheck are shown as the crashes they were.",
    "Wider autostart/persistence coverage (Security → Autoruns) — RunServices, policy Run keys, RunOnceEx, LSA providers and print monitors.",
    "Accessibility: dim text lifted to meet WCAG AA contrast, the OS 'reduce motion' setting is honoured, and icon-only buttons got accessible labels.",
  ] },
  { v: "2.7.1", name: "Security & maintenance", items: [
    "Security hardening from a full code scan: the domain TLS inspector now requires TLS 1.2 or better explicitly, and page navigation can only ever dispatch to a known page loader.",
    "Under the hood — pinned build dependencies and a documented dependency/CVE audit, so the toolchain stays clean release to release. No feature changes.",
  ] },
  { v: "2.7.0", name: "Power, storage & runtime forensics", items: [
    "Battery & power efficiency (System) — battery wear and cycle count, plus a short powercfg trace that names what's hurting power efficiency (selective-suspend off, devices blocking sleep, thirsty drivers).",
    "Environment & PATH audit (System) — checks every Machine and User PATH entry for missing folders, duplicates and quoting issues — the baffling “command not found / wrong version runs” fixer. One-click clean of broken & duplicate entries, with the prior value backed up.",
    "Installed runtimes (System) — the .NET Framework, .NET (Core/5+), Visual C++ redistributables and DirectX a program quietly needs. The “app won't start, missing runtime” diagnosis in one place.",
    "Advanced storage health (Storage) — beyond SMART: is TRIM running on the SSDs, Storage Spaces pool health, the drives' reliability counters, shadow-copy (System Restore) space, and the filesystem dirty bit.",
    "Audio device doctor (Devices) — the “no sound / wrong output / can't pick a device” triage: playback and recording endpoints with their state, the audio services, and a one-click restart.",
  ] },
  { v: "2.6.0", name: "Network & sharing deep", items: [
    "New Sharing & firewall section on the Network page, for the silent “can't see the printer / keeps asking me to sign in” problems.",
    "Network profile — spots a connection left on Public (which blocks file/printer sharing and discovery) and flips it to Private in one click.",
    "Firewall audit — the per-profile state plus the inbound allow rules that are actually enabled, with anything running from a user-writable folder flagged.",
    "Drives & credentials — mapped network drives and their status (stale ones flagged), and the Credential Manager entries (names and types only — passwords are never read).",
    "DNS & Winsock — the live DNS resolver cache (an unexpected address for a known site is a hijack hint) and the Winsock/LSP catalog, flagging any third-party layered providers.",
  ] },
  { v: "2.5.0", name: "Workplace — identity, licensing & a managed baseline", items: [
    "New Workplace page, built for the corporate and small-business machines an IT pro actually looks after.",
    "Activation & licensing — is Windows activated, on what channel (OEM / Retail / Volume), and the product key embedded in this PC's firmware (handy before a reinstall).",
    "Identity & domain — Entra (Azure AD) joined, hybrid, AD domain or just a workgroup, plus SSO and tenant detail. The fast “why won't Teams/Outlook sign in” answer.",
    "Group Policy results — which GPOs are actually applied (computer and user scope), when policy last refreshed, and what got filtered out.",
    "Time sync health — where the clock gets its time, how far off it currently is, and a one-click resync. Clock drift quietly breaks HTTPS, Kerberos and sign-in.",
    "Managed baseline — set the policies an admin usually pushes via GPO/Intune (Windows Update deferrals, BitLocker startup-PIN policy, telemetry level, auto-lock, UAC) on a standalone PC. Every change shows the exact registry key and is reversible — Clear returns it to the Windows default. Warns if the machine is already centrally managed.",
  ] },
  { v: "2.4.0", name: "Won't update, won't boot, disk's full", items: [
    "Pending restart check (Toolbox) — reads every signal Windows leaves when it's waiting on a reboot (component servicing, Windows Update, files queued to move, a queued rename) and explains in plain English why updates and installers might be silently failing. One-click restart when you're ready.",
    "Update doctor (Toolbox) — the recent Windows Update history with the cryptic 0x800f… / 0x80070… error codes translated into plain English and what to do, plus the last successful scan/install and the health of the services updates depend on.",
    "Component store cleanup (Toolbox → repair tools) — analyzes the WinSxS folder, tells you how much is reclaimable, and cleans it up (with an optional deeper Reset Base). The honest answer to “where did the space on C: go?”",
    "Boot-time breakdown (Event Log → Boot time) — how long the last boots actually took (to desktop and to settled), the specific apps, drivers and services Windows blamed for slowing it down, and a trend over time.",
  ] },
  { v: "2.3.1", name: "Reliable self-update", items: [
    "Fixed the updater getting stuck on “closing application” for installed copies. Updates now swap the program file in place — the same proven method the portable build already used — and relaunch cleanly.",
    "Heads-up: this fix takes effect from the next update onward, so install v2.3.1 by hand once. After that, updates apply themselves.",
  ] },
  { v: "2.3.0", name: "Home lab & power user", items: [
    "GPU stability & throttle forensics (System) — live clocks, throttle reasons, and a 30-day history of GPU driver resets (TDRs): “is my overclock stable?”",
    "Display refresh check (System) — catches a monitor left below its best refresh rate (the classic “144 Hz panel stuck at 60”).",
    "Virtualization health (System) — WSL distros and memory cap, ballooning WSL/Docker virtual disks (with optional compact), Hyper-V switches, and whether VT-x is on.",
    "Drive health forecast (Storage) — trends the scary SMART numbers (wear, growing read/write errors) over time and scores each drive's risk, so you can replace a dying disk before it dies.",
    "Bufferbloat test (Network) — measures latency while idle and under load and grades it, so you know why calls stutter when someone's downloading.",
  ] },
  { v: "2.2.0", name: "Helper — for fixing the family PC", items: [
    "New Helper page — friendly, big-button tools for fixing a relative's computer and handing it off.",
    "Text my tech person — a plain-English health summary you can copy into a message.",
    "Calm this computer down — silences pop-ups, widgets, tips, lock-screen ads and Start web-search in one click (all reversible).",
    "Make it normal again — instant, reversible text-size presets for “everything's huge/tiny”.",
    "Camera & microphone doctor — checks the Windows privacy permission and which app is using the device; allow a blocked app in one click.",
    "BitLocker recovery key — see which drives are encrypted and reveal the recovery key so you can save it before a repair ever asks.",
    "Rescue my photos & documents — copy Desktop/Documents/Pictures onto a drive you plug in (copies only, never moves).",
    "Is this a scam? — paste an email or a link and get a simple red/amber/green read.",
  ] },
  { v: "2.1.0", name: "Security & incident response", items: [
    "Persistence & exclusions (Security) — maps the hiding spots autoruns misses: WMI event subscriptions (fileless persistence), services and tasks with suspicious paths, Microsoft Defender exclusions, and what's run recently (from Prefetch).",
    "Hardening scorecard (Security) — high-value Windows hardening checks scored out of 100, each with a reversible one-click fix that documents exactly what it changes.",
    "Attack Surface Reduction rules — set the key anti-ransomware rules to Audit first, then Block, right from the app.",
    "Recover from a scam (Fix-It) — one guided pass after a remote-access incident: remote tools, persistence, exclusions and admin accounts, then a clear ordered checklist of what to do next.",
    "Defender exclusion removal, plus all findings framed as ranked context — legit software trips some heuristics, so nothing is auto-removed.",
  ] },
  { v: "2.0.1", name: "Nicer update progress", items: [
    "The self-updater now shows a proper progress bar — download stage, percentage, and megabytes, in the Benchly look (and a moving bar if the server doesn't report the size).",
  ] },
  { v: "2.0.0", name: "Everyday fixes & gremlin hunting", items: [
    "Power, sleep & wake doctor (Toolbox) — why won't it sleep, what woke it at 3 AM, and what's armed to wake it, in plain English.",
    "Gremlin hunters (Toolbox) — find what's hammering the disk when “nothing” is, spot USB devices that keep dropping, and a “mark the freeze” button that pulls every log around the moment it hiccupped.",
    "Cache & shell repair (Cleanup → Repair) — one-click fixes for blank icons, broken thumbnails, garbled fonts and a dead Start search.",
    "Printer doctor (Devices) — catches “offline” printers, a printer that got a new IP from DHCP, and duplicate drivers; bring it back online or print a test page.",
    "“What changed?” (Toolbox → baseline) — now spots everyday Windows settings that changed (display language, default browser, taskbar, dark mode, mouse, text size) with one-click “put it back”.",
  ] },
  { v: "1.9.0", name: "One-click updates", items: [
    "Benchly can now update itself. When a new version is out, “Check for updates” offers Download & install — it fetches the new build, verifies it, and restarts into the new version.",
    "Works for both flavours: an installed copy updates in place via the installer, and a portable exe swaps itself out and relaunches.",
    "Downloads are checked against the release's published SHA-256 sums before anything runs.",
  ] },
  { v: "1.8.1", name: "Frosted Glass & friendlier docs", items: [
    "The glass theme is now called Frosted Glass — same look, clearer name. Switch it from the Appearance menu in the title bar.",
    "Rewrote the documentation in a friendlier, more conversational style, with a gallery of screenshots.",
  ] },
  { v: "1.8.0", name: "Triage toolkit & app updates", items: [
    "App updates — find and install updates for your installed apps via winget, individually or all at once (Software → App updates).",
    "Trusted root certificate audit — flags interception/adware roots and unrecognised self-signed CAs (Security → Root certificates).",
    "Listening ports — every port the PC accepts connections on, the owning process, and whether it's signed (Security → Listening ports).",
    "Email header analyzer — paste raw headers to trace the path, originating IP and SPF/DKIM/DMARC, and catch spoofing (Security → Email headers).",
    "URL / redirect unmasker — expand short links and reveal the real destination, every hop (Network).",
    "Wi-Fi analyzer — nearby networks, signal, band and 2.4 GHz channel congestion (Network).",
    "Performance snapshot — a 30-second “why is it slow right now?” capture of the top CPU/memory/disk offenders (Toolbox).",
    "More tweaks — Windows 11 classic right-click menu, faster shutdown, hibernation, kill lock-screen/Settings ads, verbose sign-in.",
    "Check for updates — Benchly can now check for a newer release (set your release source in What's new).",
  ] },
  { v: "1.7.0", name: "Domain & website lookup", items: [
    "New Domain & website lookup in the Network page — check any domain or URL before you trust it.",
    "WHOIS / RDAP registration: registrar, registration & expiry dates, domain age, status flags, and abuse contact.",
    "DNS records (A / AAAA / NS / MX) plus SPF and DMARC email-spoofing checks.",
    "Hosting intelligence: the resolved IP, reverse DNS, and the owning network / organisation and country.",
    "Live TLS certificate inspection — issuer, validity window, expiry countdown and the names it covers.",
    "Optional VirusTotal domain reputation when an API key is configured.",
    "A plain-English trust verdict that flags young domains, invalid certificates and bad reputation.",
  ] },
  { v: "1.6.0", name: "Tweaks & transparency", items: [
    "New Tweaks tab in Cleanup — performance (Game Mode, GPU scheduling, power plans), privacy (Copilot, Recall, web search, location) and Windows interface toggles (taskbar, file extensions, dark mode).",
    "Every action that changes Windows now shows exactly what it does and where it writes.",
    "This in-app changelog.",
    "Security & stability hardening after a full code and security review — content-security-policy, encrypted API-key storage, and safer file cleanup.",
  ] },
  { v: "1.5.0", name: "Safety, cleanup & malware triage", items: [
    "Security hub: autostart persistence map with VirusTotal checks, browser-hijack scan, and a remote-access / scam check.",
    "New Cleanup page: junk files, large & duplicate finder, app debloat.",
    "New Fix-It page with guided runbooks for common problems.",
    "Restore-point safety net and a backup-posture audit in the Toolbox.",
    "Per-process deep inspect, a reliability timeline, USB device history, and startup-impact ratings.",
    "Frosted Glass appearance with a customizable glass background.",
  ] },
  { v: "1.4.0", name: "Field kit & stability", items: [
    "LAN toolkit: subnet scanner, Wake-on-LAN, DHCP/DNS health, and a port profiler.",
    "Fleet: remote machine snapshots over WinRM and cross-machine report comparison.",
    "Live sensors, third-party driver audit, memory diagnostic, battery health trend, and a paste-ready ticket summary.",
    "Resolved a rare unresponsiveness when left idle for long periods; added background crash logging.",
  ] },
  { v: "1.3.0", name: "Security & reporting", items: [
    "Correct third-party antivirus detection; HTML + PDF report export.",
    "Event-log triage with plain-English explanations and one-click fixes, plus a crashes / BSOD view.",
    "A faster, lighter dashboard.",
  ] },
  { v: "1.2.0", name: "Repair power tools", items: [
    "Repair toolbox: SFC, DISM, chkdsk, Winsock reset and Windows Update cache reset.",
    "Problem-device audit, printer triage, scheduled tasks, browser extensions and pending updates.",
    "Configuration baseline snapshot & diff, and a Ctrl+K command palette.",
  ] },
  { v: "1.1.0", name: "Refined experience", items: [
    "Polished interface and faster deep pages, click-to-copy values, and remediation links throughout.",
  ] },
  { v: "1.0.0", name: "First release", items: [
    "Live dashboard, full hardware inventory, SMART storage, network tools, process manager, software audit, health score and event log — with a standalone report.",
  ] },
];
function renderChangelog() {
  const updatePanel = `<div class="cl-update" id="clUpdate">
    <div class="row" style="align-items:center">
      <button class="btn small primary" id="btnCheckUpdate">Check for updates</button>
      <span class="muted" id="updateMsg" style="font-size:12px">Current version ${esc(CHANGELOG[0].v)}</span>
    </div>
    <div id="updateResult" style="margin-top:8px"></div>
  </div>`;
  $("#clBody").innerHTML = updatePanel + CHANGELOG.map((r, i) => `<div class="cl-ver">
    <div class="v"><b>${esc(r.v)}</b><span class="name">${esc(r.name)}</span>${i === 0 ? `<span class="latest">Latest</span>` : ""}</div>
    <ul>${r.items.map(it => `<li>${esc(it)}</li>`).join("")}</ul></div>`).join("");
  $("#btnCheckUpdate").onclick = runUpdateCheck;
}
async function runUpdateCheck() {
  $("#updateMsg").innerHTML = `<span class="spin"></span> checking…`;
  $("#updateResult").innerHTML = "";
  const r = await api.check_update();
  if (!r.ok) { $("#updateMsg").innerHTML = pill("bad", r.error); return; }
  if (!r.configured) {
    $("#updateMsg").textContent = "";
    $("#updateResult").innerHTML = `<div class="muted" style="font-size:12px">${esc(r.message)}</div>
      <div class="row" style="margin-top:6px">
        <input class="input" id="updateRepo" placeholder="owner/repo (e.g. yourname/benchly)" style="flex:1; min-width:200px" spellcheck="false">
        <button class="btn small" id="btnSaveRepo">Save</button></div>`;
    $("#btnSaveRepo").onclick = async () => {
      const v = $("#updateRepo").value.trim();
      if (!v) return;
      await api.set_setting("update_repo", v);
      toast("Update source saved", "good", 1500);
      runUpdateCheck();
    };
    return;
  }
  if (!r.reachable) { $("#updateMsg").innerHTML = pill("warn", r.message); return; }
  if (r.newer) {
    $("#updateMsg").innerHTML = pill("good", `Update available: ${r.latest}`);
    const canAuto = r.can_apply;
    $("#updateResult").innerHTML = `<div class="dom-flag good" style="margin-top:4px">${ico("download")}
      <span>Benchly ${esc(r.latest)} is available (you have ${esc(r.current)}).</span></div>
      <div class="row" style="margin-top:8px; align-items:center">
        ${canAuto ? `<button class="btn small primary" id="btnDoUpdate">Download &amp; install</button>` : ""}
        <a href="${esc(r.url)}" class="lnk" data-ext="1" style="font-size:12px">View release page</a>
      </div>
      <div class="upd-progress" id="updProgress" style="display:none">
        <div class="upd-stage"><span id="updStage">Starting…</span><span id="updPct" class="muted"></span></div>
        <div class="upd-track"><div class="upd-fill" id="updFill" style="width:0%"></div></div>
        <div class="upd-meta muted" id="updMeta"></div>
      </div>`;
    $("#updateResult").querySelector('a[data-ext="1"]').onclick = e => { e.preventDefault(); api.open_in_browser(r.url); };
    if (canAuto) $("#btnDoUpdate").onclick = () => startSelfUpdate(r.latest);
  } else {
    $("#updateMsg").innerHTML = pill("good", `Up to date (${r.current})`);
  }
}
async function startSelfUpdate(latest) {
  const go = await confirmModal("Update Benchly?",
    `Benchly ${latest} will download and install, then restart. Any unsaved work in the app will be lost.`,
    "Download & install");
  if (!go) return;
  const fill = $("#updFill"), stage = $("#updStage"), pct = $("#updPct"), meta = $("#updMeta");
  const STAGE = { starting: "Starting…", downloading: "Downloading update", verifying: "Verifying download" };
  const fail = (msg) => {
    stage.textContent = "Update failed"; pct.textContent = "";
    meta.innerHTML = pill("bad", msg); fill.classList.remove("indet");
    fill.classList.add("done"); fill.style.background = "var(--crit)";
    $("#btnDoUpdate").disabled = false;
  };
  $("#btnDoUpdate").disabled = true;
  $("#updProgress").style.display = "";
  fill.classList.remove("done"); fill.style.background = "";
  fill.classList.add("indet"); stage.textContent = "Starting…"; pct.textContent = ""; meta.textContent = "";
  const r = await api.download_update();
  if (!r.ok) { fail(r.error); return; }
  let fails = 0;
  const poll = async () => {
    const s = await api.update_status(r.job);
    if (!s.ok) { if (++fails > 8) { fail("lost track of the download"); return; } return void setTimeout(poll, 800); }
    fails = 0;
    if (s.error) { fail(s.error); return; }
    if (s.done && s.ready) {
      fill.classList.remove("indet"); fill.classList.add("done"); fill.style.width = "100%";
      stage.textContent = "Installing — Benchly will restart…"; pct.textContent = "";
      meta.textContent = "The window will close and reopen on the new version.";
      const a = await api.apply_update();
      if (!a.ok) { fail(a.error); return; }
      return;  // portable: window closes itself · installed: Inno closes us
    }
    if (s.stage === "downloading") {
      const known = s.total_mb > 0;
      fill.classList.toggle("indet", !known);
      if (known) { fill.style.width = (s.progress || 0) + "%"; pct.textContent = (s.progress || 0) + "%"; }
      else { pct.textContent = ""; }
      stage.textContent = STAGE.downloading;
      meta.textContent = known ? `${s.got_mb} of ${s.total_mb} MB` : `${s.got_mb} MB downloaded`;
    } else if (s.stage === "verifying" || s.stage === "ready") {
      fill.classList.remove("indet"); fill.classList.add("done"); fill.style.width = "100%";
      stage.textContent = STAGE.verifying; pct.textContent = ""; meta.textContent = "Checking the download is intact…";
    } else {
      stage.textContent = STAGE[s.stage] || "Working…";
    }
    setTimeout(poll, 400);
  };
  poll();
}
function openChangelog() {
  renderChangelog();
  $("#changelog-veil").hidden = false;
  $("#verDot")?.remove();
  api.set_setting("last_seen_version", CHANGELOG[0].v);
}
$("#clClose").onclick = () => { $("#changelog-veil").hidden = true; };
$("#changelog-veil").addEventListener("click", e => { if (e.target.id === "changelog-veil") $("#changelog-veil").hidden = true; });

/* ================= command palette ================= */
const PAGE_LABELS = { dashboard: "Dashboard", system: "System", storage: "Storage",
  network: "Network", processes: "Processes", software: "Software", devices: "Devices",
  health: "Health audit", events: "Event log", toolbox: "Toolbox", security: "Security",
  fleet: "Fleet", fixit: "Fix-It", helper: "Helper", cleanup: "Cleanup", workplace: "Workplace" };
const PALETTE_ITEMS = [
  ...PAGES.map((p, i) => ({
    cat: "Pages", icon: "chev", label: PAGE_LABELS[p] || p,
    hint: i === 9 ? "0" : i < 9 ? String(i + 1) : "", run: () => showPage(p),
  })),
  { cat: "Actions", icon: "shield", label: "Check a file on VirusTotal", run: () => { showPage("security"); $("#btnVtBrowse").click(); } },
  { cat: "Actions", icon: "wrench", label: "Scan the local subnet", run: () => { showPage("network"); $(`#lanTabs [data-lan="scan"]`).click(); $("#btnScanStart").click(); } },
  { cat: "Actions", icon: "shield", label: "Look up a domain / website", run: () => { showPage("network"); $("#domHost").focus(); } },
  { cat: "Actions", icon: "shield", label: "Unmask a URL / short link", run: () => { showPage("network"); $("#urlInput").focus(); } },
  { cat: "Actions", icon: "wrench", label: "Scan Wi-Fi networks", run: () => { showPage("network"); $("#btnWifiScan").click(); } },
  { cat: "Actions", icon: "shield", label: "Firewall rules audit", run: () => { showPage("network"); $("#btnSharing")?.click(); $(`#shTabs [data-sh="firewall"]`)?.click(); } },
  { cat: "Actions", icon: "wrench", label: "Network profile (Public/Private)", run: () => { showPage("network"); $("#btnSharing")?.click(); } },
  { cat: "Actions", icon: "shield", label: "Mapped drives & saved credentials", run: () => { showPage("network"); $("#btnSharing")?.click(); $(`#shTabs [data-sh="creds"]`)?.click(); } },
  { cat: "Actions", icon: "wrench", label: "DNS cache & Winsock catalog", run: () => { showPage("network"); $("#btnSharing")?.click(); $(`#shTabs [data-sh="dns"]`)?.click(); } },
  { cat: "Actions", icon: "q", label: "Decode an error code", run: () => { showPage("toolbox"); setTimeout(() => $("#errInput")?.focus(), 60); } },
  { cat: "Actions", icon: "wrench", label: "Find what's locking a file", run: () => { showPage("toolbox"); setTimeout(() => $("#lockInput")?.focus(), 60); } },
  { cat: "Actions", icon: "aid", label: "Check user profile health", run: () => { showPage("toolbox"); $("#btnProfChk")?.click(); } },
  { cat: "Actions", icon: "wrench", label: "Full network reset (Winsock + TCP/IP)", run: () => { showPage("toolbox"); setTimeout(() => $(`[data-run="net_full"]`)?.scrollIntoView({ block: "center" }), 60); } },
  { cat: "Actions", icon: "cpu2", label: "Battery wear & power efficiency", run: () => { showPage("system"); $("#btnBatteryReport")?.click(); } },
  { cat: "Actions", icon: "wrench", label: "Environment & PATH audit", run: () => { showPage("system"); $("#btnEnvAudit")?.click(); } },
  { cat: "Actions", icon: "cpu2", label: "Installed runtimes (.NET / VC++ / DirectX)", run: () => { showPage("system"); $("#btnRuntimes")?.click(); } },
  { cat: "Actions", icon: "drive", label: "Advanced storage health (TRIM / VSS)", run: () => { showPage("storage"); $("#btnStorageDeep")?.click(); } },
  { cat: "Actions", icon: "q", label: "Audio device doctor", run: () => { showPage("devices"); $("#btnAudioCheck")?.click(); } },
  { cat: "Actions", icon: "download", label: "Check for app updates (winget)", run: () => { showPage("software"); $(`#swTabs [data-sw="appupdates"]`).click(); } },
  { cat: "Actions", icon: "shield", label: "Audit trusted root certificates", run: () => { showPage("security"); $(`#secTabs [data-sec="certs"]`).click(); } },
  { cat: "Actions", icon: "shield", label: "Listening ports", run: () => { showPage("security"); $(`#secTabs [data-sec="listeners"]`).click(); } },
  { cat: "Actions", icon: "bug", label: "Persistence & Defender exclusions", run: () => { showPage("security"); $(`#secTabs [data-sec="persist"]`).click(); $("#btnPersistScan")?.click(); } },
  { cat: "Actions", icon: "shield", label: "Hardening scorecard & ASR rules", run: () => { showPage("security"); $(`#secTabs [data-sec="harden"]`).click(); } },
  { cat: "Actions", icon: "shield", label: "Recover from a scam (post-incident check)", run: () => { showPage("fixit"); $("#btnPostScam")?.click(); } },
  { cat: "Actions", icon: "wrench", label: "Text my tech person (health summary)", run: () => { showPage("helper"); $("#btnHelperCard")?.click(); } },
  { cat: "Actions", icon: "cpu2", label: "Calm this computer down (quiet mode)", run: () => { showPage("helper"); $("#btnQuietMode")?.scrollIntoView({ block: "center" }); } },
  { cat: "Actions", icon: "q", label: "Camera & microphone doctor", run: () => { showPage("helper"); $("#btnAvCheck")?.click(); } },
  { cat: "Actions", icon: "shield", label: "BitLocker recovery key", run: () => { showPage("helper"); $("#btnBitlocker")?.click(); } },
  { cat: "Actions", icon: "download", label: "Rescue my photos & documents", run: () => { showPage("helper"); $("#btnRescueScan")?.click(); } },
  { cat: "Actions", icon: "shield", label: "Is this a scam? (check email or link)", run: () => { showPage("helper"); $("#scamInput")?.focus(); } },
  { cat: "Actions", icon: "cpu2", label: "GPU stability & throttle forensics", run: () => { showPage("system"); $("#btnGpuForensics")?.click(); } },
  { cat: "Actions", icon: "cpu2", label: "Display refresh-rate check", run: () => { showPage("system"); $("#btnDisplayLinks")?.click(); } },
  { cat: "Actions", icon: "cpu2", label: "Virtualization health (WSL / Docker)", run: () => { showPage("system"); $("#btnVirt")?.click(); } },
  { cat: "Actions", icon: "wrench", label: "Drive health forecast (SMART trend)", run: () => { showPage("storage"); $("#btnSmartPredict")?.click(); } },
  { cat: "Actions", icon: "wrench", label: "Bufferbloat test", run: () => { showPage("network"); $("#btnBufferbloat")?.click(); } },
  { cat: "Actions", icon: "shield", label: "Analyze email headers (phishing)", run: () => { showPage("security"); $(`#secTabs [data-sec="email"]`).click(); } },
  { cat: "Actions", icon: "zap", label: "Performance snapshot — why is it slow?", run: () => { showPage("toolbox"); $("#btnSnapStart").click(); } },
  { cat: "Actions", icon: "zap", label: "Power, sleep & wake doctor", run: () => { showPage("toolbox"); $("#btnPowerScan").click(); } },
  { cat: "Actions", icon: "refresh", label: "Check for a pending restart", run: () => { showPage("toolbox"); $("#btnRebootCheck")?.click(); } },
  { cat: "Actions", icon: "download", label: "Update doctor (why is Windows Update stuck?)", run: () => { showPage("toolbox"); $("#btnWuCheck")?.click(); } },
  { cat: "Actions", icon: "history", label: "Boot-time breakdown", run: () => { showPage("events"); $(`#evTabs [data-ev="boot"]`)?.click(); } },
  { cat: "Actions", icon: "drive", label: "Clean up the component store (WinSxS)", run: () => { showPage("toolbox"); $(`[data-run="dism_analyze"]`)?.scrollIntoView({ block: "center" }); } },
  { cat: "Actions", icon: "bug", label: "Gremlin hunters (disk / USB / freeze)", run: () => { showPage("toolbox"); $("#btnGremDisk")?.scrollIntoView({ block: "center" }); } },
  { cat: "Actions", icon: "wrench", label: "Cache & shell repair (blank icons, fonts…)", run: () => { showPage("cleanup"); $(`#cleanTabs [data-clean="repair"]`).click(); } },
  { cat: "Actions", icon: "printer", label: "Printer doctor", run: () => { showPage("devices"); $("#prnBody")?.scrollIntoView({ block: "center" }); } },
  { cat: "Actions", icon: "shield", label: "Activation & licensing status", run: () => { showPage("workplace"); $(`#wpTabs [data-wp="posture"]`)?.click(); } },
  { cat: "Actions", icon: "shield", label: "Identity & domain join (Entra / AD)", run: () => { showPage("workplace"); $(`#wpTabs [data-wp="posture"]`)?.click(); } },
  { cat: "Actions", icon: "shield", label: "Group Policy results", run: () => { showPage("workplace"); $(`#wpTabs [data-wp="posture"]`)?.click(); } },
  { cat: "Actions", icon: "history", label: "Time sync health (clock drift)", run: () => { showPage("workplace"); $(`#wpTabs [data-wp="posture"]`)?.click(); } },
  { cat: "Actions", icon: "wrench", label: "Managed baseline (enterprise policy)", run: () => { showPage("workplace"); $(`#wpTabs [data-wp="baseline"]`)?.click(); } },
  { cat: "Actions", icon: "download", label: "Check for Benchly updates", run: () => openChangelog() },
  { cat: "Actions", icon: "copy", label: "Copy ticket summary", run: async () => { const t = await api.get_ticket_summary(); navigator.clipboard.writeText(t.text).then(() => toast("Ticket summary copied", "good", 2000)); } },
  { cat: "Actions", icon: "chev", label: "Remote snapshot…", run: () => { showPage("fleet"); $("#rmHost").focus(); } },
  { cat: "Actions", icon: "bug", label: "Autostart persistence map", run: () => { showPage("security"); $(`#secTabs [data-sec="autoruns"]`).click(); } },
  { cat: "Actions", icon: "shield", label: "Browser hijack scan", run: () => { showPage("security"); $(`#secTabs [data-sec="hijack"]`).click(); } },
  { cat: "Actions", icon: "shield", label: "Remote-access / scam check", run: () => { showPage("security"); $(`#secTabs [data-sec="remote"]`).click(); } },
  { cat: "Actions", icon: "broom", label: "Scan for junk files", run: () => { showPage("cleanup"); $("#btnJunkScan").click(); } },
  { cat: "Actions", icon: "shield", label: "Create a restore point", run: () => { showPage("toolbox"); $("#btnRpCreate").click(); } },
  { cat: "Actions", icon: "aid", label: "Guided Fix-It runbooks", run: () => showPage("fixit") },
  { cat: "Actions", icon: "history", label: "What's new (changelog)", run: openChangelog },
  { cat: "Actions", icon: "cpu2", label: "Windows tweaks", run: () => { showPage("cleanup"); $(`#cleanTabs [data-clean="tweaks"]`).click(); } },
  { cat: "Actions", icon: "download", label: "Export health report", run: () => $("#btnReport").click() },
  { cat: "Actions", icon: "layers", label: "Save configuration baseline", run: () => { showPage("toolbox"); $("#btnBlSave").click(); } },
  { cat: "Actions", icon: "layers", label: "Compare with baseline", run: () => { showPage("toolbox"); $("#btnBlCompare").click(); } },
  { cat: "Actions", icon: "zap", label: "Run speed test", run: () => { showPage("network"); $(`#netTabs [data-tool="speed"]`).click(); $("#btnNetRun").click(); } },
  { cat: "Actions", icon: "refresh", label: "Flush DNS cache", run: flushDns },
  { cat: "Actions", icon: "wrench", label: "Run System File Checker", run: () => { showPage("toolbox"); $(`[data-run="sfc"]`)?.click(); } },
  { cat: "Actions", icon: "folder", label: "Analyze C: drive space", run: () => { showPage("storage"); analyzePath("C:\\"); } },
  { cat: "Actions", icon: "shield", label: "Re-run health audit", run: () => { showPage("health"); loadHealth(true); } },
];
let palSel = 0, palMatches = [];
function openPalette() {
  $("#palette-veil").classList.add("open");
  const input = $("#paletteInput");
  input.value = ""; palSel = 0;
  renderPalette();
  input.focus();
}
function closePalette() { $("#palette-veil").classList.remove("open"); }
function renderPalette() {
  const q = $("#paletteInput").value.trim().toLowerCase();
  palMatches = PALETTE_ITEMS.filter(x => !q || x.label.toLowerCase().includes(q));
  palSel = Math.min(palSel, Math.max(0, palMatches.length - 1));
  let lastCat = "";
  $("#paletteList").innerHTML = palMatches.map((x, i) => {
    const cat = x.cat !== lastCat ? `<div class="pal-cat">${x.cat}</div>` : "";
    lastCat = x.cat;
    return cat + `<div class="pal-item ${i === palSel ? "sel-item" : ""}" data-i="${i}">
      ${ico(x.icon, "ic")}<span>${esc(x.label)}</span>${x.hint ? `<span class="hint">${x.hint}</span>` : ""}</div>`;
  }).join("") || `<div class="empty" style="padding:20px">No matches</div>`;
}
$("#paletteInput").addEventListener("input", () => { palSel = 0; renderPalette(); });
$("#paletteInput").addEventListener("keydown", e => {
  if (e.key === "Escape") { closePalette(); return; }
  if (e.key === "ArrowDown") { e.preventDefault(); palSel = Math.min(palSel + 1, palMatches.length - 1); renderPalette(); }
  if (e.key === "ArrowUp") { e.preventDefault(); palSel = Math.max(palSel - 1, 0); renderPalette(); }
  if (e.key === "Enter" && palMatches[palSel]) { closePalette(); palMatches[palSel].run(); }
});
$("#paletteList").addEventListener("click", e => {
  const item = e.target.closest(".pal-item");
  if (item) { closePalette(); palMatches[+item.dataset.i].run(); }
});
$("#palette-veil").addEventListener("click", e => { if (e.target.id === "palette-veil") closePalette(); });

/* ================= report ================= */
$("#btnReport").onclick = async () => {
  const btn = $("#btnReport");
  if (btn.disabled) return;
  btn.disabled = true;
  const old = btn.innerHTML;
  const restore = () => { btn.disabled = false; btn.innerHTML = old; };
  try {
    const start = await api.start_report();
    if (!start.ok) { restore(); toast(start.error, "bad"); return; }
    let reportFails = 0;
    const poll = async () => {            // self-chaining — no overlapping ticks
      let j;
      try { j = await api.get_report_job(start.job); reportFails = 0; }
      catch { if (++reportFails > 8) { restore(); return; } setTimeout(poll, 1500); return; }
      if (!j.ok) { restore(); toast(j.error, "bad"); return; }
      if (!j.done) {
        btn.innerHTML = `<span class="spin"></span> ${esc(j.stages[j.stage] ?? "Working")}…`;
        setTimeout(poll, 600);
        return;
      }
      restore();
      if (j.result_ok) {
        toast(`Report saved${j.pdf ? " (HTML + PDF)" : ""}: ${j.html}`, "good", 7000);
        api.open_in_browser(j.pdf || j.html);
      } else {
        toast("Report failed: " + (j.error || "unknown error"), "bad", 7000);
      }
    };
    poll();
  } catch (e) {
    restore();
    toast("Report failed to start: " + e, "bad");
  }
};

/* ================= go ================= */
boot();
initDriveChips();
const startPage = location.hash.slice(1).split(",")[0];
if (startPage && PAGES.includes(startPage)) showPage(startPage);
