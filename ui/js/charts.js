/* Benchly — lightweight canvas sparkline charts (no dependencies). */
"use strict";

class Sparkline {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {object} opts {color, max (100 | null = sticky session max), samples}
   */
  constructor(canvas, opts = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.color = opts.color || "#56a8ff";
    this.fixedMax = opts.max !== undefined ? opts.max : 100;
    this.sessionMax = 1; // for rate charts: never shrinks, so magnitude stays honest
    this.samples = opts.samples || 90;
    this.data = new Array(this.samples).fill(null);
    this._resize();
    new ResizeObserver(() => { this._resize(); this.draw(); }).observe(canvas);
  }

  _resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    if (rect.width === 0) return;
    this.canvas.width = Math.round(rect.width * dpr);
    this.canvas.height = Math.round(rect.height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.w = rect.width;
    this.h = rect.height;
  }

  push(value) {
    this.data.push(value);
    if (this.data.length > this.samples) this.data.shift();
    if (value > this.sessionMax) this.sessionMax = value;
    this.draw();
  }

  draw() {
    const { ctx, w, h } = this;
    if (!w || !h) return;
    ctx.clearRect(0, 0, w, h);

    const vals = this.data.filter(v => v !== null);
    if (vals.length < 2) return;

    const max = this.fixedMax !== null ? this.fixedMax : this.sessionMax * 1.1;

    const step = w / (this.samples - 1);
    const pts = [];
    for (let i = 0; i < this.data.length; i++) {
      const v = this.data[i];
      if (v === null) continue;
      const x = i * step;
      const y = h - Math.min(v / max, 1) * (h - 2) - 1;
      pts.push([x, y]);
    }

    // area fill — the one sanctioned gradient: color 12% -> 0
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, this.color + "1f");
    grad.addColorStop(1, this.color + "00");
    ctx.beginPath();
    ctx.moveTo(pts[0][0], h);
    for (const [x, y] of pts) ctx.lineTo(x, y);
    ctx.lineTo(pts[pts.length - 1][0], h);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // line
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.strokeStyle = this.color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.stroke();
  }
}

/** Animated SVG score ring — three status stops only. */
function setRing(rootEl, score, grade) {
  const arc = rootEl.querySelector(".arc");
  const num = rootEl.querySelector(".num");
  const cap = rootEl.querySelector(".cap");
  const r = 56;
  const circ = 2 * Math.PI * r;
  // aligned with the backend grade bands: A/B (≥75) green, C (≥60) amber, D/F red
  const color = score >= 75 ? "var(--ok)" : score >= 60 ? "var(--warn)" : "var(--crit)";
  arc.style.strokeDasharray = `${circ}`;
  arc.style.strokeDashoffset = `${circ * (1 - score / 100)}`;
  arc.style.stroke = color;
  num.textContent = score;
  num.style.color = color;
  if (cap && grade) cap.textContent = `Grade ${grade}`;
}
