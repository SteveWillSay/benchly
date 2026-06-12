"""Client-ready standalone HTML (and PDF) report — the technician's leave-behind document.

Generation runs as a polled background job so the UI can show stage-by-stage
progress and a hung collector can never freeze the window.
"""

import datetime
import html
import json
import os
import socket
import subprocess
import time

import psutil

from .jobs import JobStore
from .ps import CREATE_NO_WINDOW, fmt_gb as _gb
from . import sysinfo, storage, network, security, software, events as events_mod


def _esc(value):
    return html.escape(str(value)) if value not in (None, "") else "—"


def _row(label, value):
    return f"<tr><th>{html.escape(label)}</th><td>{_esc(value)}</td></tr>"


_STATUS_BADGE = {
    "good": '<span class="badge good">PASS</span>',
    "warn": '<span class="badge warn">WARN</span>',
    "bad": '<span class="badge bad">FAIL</span>',
    "unknown": '<span class="badge unk">N/A</span>',
}

_CSS = """
:root { --ink:#1a2330; --mut:#5d6b7e; --line:#dde4ec; --accent:#0b6bcb; }
* { box-sizing:border-box; }
body { font-family:'Segoe UI',system-ui,sans-serif; color:var(--ink); margin:0;
       background:#f3f5f8; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
.page { max-width:960px; margin:0 auto; padding:48px 40px; background:#fff; min-height:100vh; }
header { display:flex; justify-content:space-between; align-items:flex-end;
         border-bottom:3px solid var(--accent); padding-bottom:18px; margin-bottom:8px; }
h1 { font-size:26px; margin:0; letter-spacing:-.5px; }
h1 small { display:block; font-size:13px; font-weight:400; color:var(--mut); margin-top:4px; }
.scorebox { text-align:right; }
.score { font-size:42px; font-weight:700; line-height:1; }
.score.gA{color:#1a9e55}.score.gB{color:#5aa83a}.score.gC{color:#d99114}.score.gD{color:#e05d2a}.score.gF{color:#cc2f3e}
.scorebox small { color:var(--mut); }
h2 { font-size:16px; text-transform:uppercase; letter-spacing:1.5px; color:var(--accent);
     border-bottom:1px solid var(--line); padding-bottom:6px; margin:36px 0 14px; }
table { width:100%; border-collapse:collapse; font-size:13.5px; }
th,td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
table.kv th { width:230px; color:var(--mut); font-weight:600; }
thead th { background:#f0f4f9; color:var(--ink); font-weight:600; }
.badge { display:inline-block; padding:2px 9px; border-radius:20px; font-size:11px; font-weight:700; }
.badge.good{background:#dcf3e5;color:#157347}.badge.warn{background:#fdf0d3;color:#9a6700}
.badge.bad{background:#fbdde0;color:#b02a37}.badge.unk{background:#e9edf2;color:#5d6b7e}
.muted{color:var(--mut)} .num{text-align:right; font-variant-numeric:tabular-nums;}
footer { margin-top:48px; padding-top:14px; border-top:1px solid var(--line);
         font-size:12px; color:var(--mut); display:flex; justify-content:space-between; }
@media print { body{background:#fff} .page{padding:24px 8px} }
"""


# ---- background job machinery -------------------------------------------------

_store = JobStore()

_STAGES = ["Hardware inventory", "Storage", "Network", "Health audit",
           "Installed software", "Event log", "Writing HTML + JSON", "Rendering PDF"]

REPORT_SCHEMA = 1


def start_report():
    job_id = _store.start(_run_job, stage=0, stages=_STAGES,
                          ok=None, error=None, html=None, pdf=None, json=None)
    if job_id is None:
        return {"ok": False, "error": "A report is already being generated."}
    return {"ok": True, "job": job_id, "stages": _STAGES}


def get_report_job(job_id: str):
    job = _store.get(job_id)
    if not job:
        return {"ok": False, "error": "No such job."}
    return {"ok": True, "stage": job["stage"], "stages": job["stages"], "done": job["done"],
            "result_ok": job["ok"], "error": job["error"], "html": job["html"],
            "pdf": job["pdf"], "json": job["json"]}


def _run_job(job):
    try:
        result = generate(progress=lambda i: job.update(stage=i))
        job["ok"] = result["ok"]
        job["error"] = result.get("error")
        job["html"] = result.get("path")
        job["pdf"] = result.get("pdf")
        job["json"] = result.get("json")
    except Exception as e:
        job["ok"] = False
        job["error"] = str(e)


def _find_edge():
    for base in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
        candidate = os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")
        if base and os.path.exists(candidate):
            return candidate
    return None


def _render_pdf(html_path: str):
    """Best-effort PDF via Edge headless. Returns the pdf path or None."""
    edge = _find_edge()
    if not edge:
        return None
    pdf_path = os.path.splitext(html_path)[0] + ".pdf"
    try:
        url = "file:///" + html_path.replace("\\", "/")
        subprocess.run(
            [edge, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={pdf_path}", url],
            capture_output=True, timeout=90, creationflags=CREATE_NO_WINDOW)
        return pdf_path if os.path.exists(pdf_path) else None
    except Exception:
        return None


def _out_dir():
    for candidate in (os.path.join(os.path.expanduser("~"), "Desktop"),
                      os.path.join(os.path.expanduser("~"), "Documents")):
        if os.path.isdir(candidate):
            return candidate
    return os.path.expanduser("~")


def generate(out_path: str | None = None, progress=lambda i: None) -> dict:
    try:
        host = socket.gethostname()
        now = datetime.datetime.now()
        progress(0)
        inv = sysinfo.get_inventory()
        progress(1)
        stor = storage.get_storage()
        progress(2)
        net = network.get_network_info()
        progress(3)
        health = security.get_health()
        progress(4)
        apps = software.get_installed()
        progress(5)
        evt = events_mod.get_events(days=7, max_events=60)
        progress(6)

        if not out_path:
            out_path = os.path.join(
                _out_dir(), f"Benchly_Report_{host}_{now.strftime('%Y%m%d_%H%M%S')}.html")

        parts = [f"""<!doctype html><html><head><meta charset="utf-8">
<title>Benchly Report — {html.escape(host)}</title><style>{_CSS}</style></head>
<body><div class="page">
<header>
  <h1>Workstation Health Report<small>{html.escape(host)} &middot; generated by Benchly &middot; {now.strftime('%d %B %Y, %H:%M')}</small></h1>
  <div class="scorebox"><div class="score g{health['grade']}">{health['score']}<span style="font-size:18px">/100</span></div>
  <small>Health grade {health['grade']}</small></div>
</header>"""]

        # Health checklist
        parts.append("<h2>Health &amp; Security Audit</h2><table><thead><tr><th>Check</th><th>Result</th><th>Detail</th></tr></thead><tbody>")
        for c in health["checks"]:
            parts.append(f"<tr><td>{_esc(c['label'])}</td><td>{_STATUS_BADGE[c['status']]}</td>"
                         f"<td class='muted'>{_esc(c['detail'])}</td></tr>")
        parts.append("</tbody></table>")
        if not health["is_admin"]:
            parts.append("<p class='muted' style='font-size:12px'>Some checks were skipped because "
                         "Benchly was not running as Administrator.</p>")

        # System
        os_info, sysd, bios, board = inv["os"], inv["system"], inv["bios"], inv["board"]
        parts.append("<h2>System</h2><table class='kv'>")
        parts.append(_row("Machine", f"{sysd.get('manufacturer') or ''} {sysd.get('model') or ''}".strip() or None))
        parts.append(_row("Type", sysd.get("type")))
        parts.append(_row("Operating system", f"{os_info.get('name')} (build {os_info.get('build')}, {os_info.get('arch')})"))
        parts.append(_row("OS installed", os_info.get("installed")))
        parts.append(_row("Domain / Workgroup", sysd.get("domain")))
        parts.append(_row("Motherboard", f"{board.get('manufacturer') or ''} {board.get('product') or ''}".strip() or None))
        parts.append(_row("BIOS / UEFI", f"{bios.get('vendor') or ''} {bios.get('version') or ''} ({bios.get('date') or '?'})"))
        for c in inv["cpus"]:
            parts.append(_row("Processor", f"{c['name']} — {c['cores']}C/{c['threads']}T"))
        parts.append(_row("Memory", _gb(inv.get("ram_total")) + f" in {len(inv['ram_modules'])} module(s)"))
        for m in inv["ram_modules"]:
            detail = f"{_gb(m['capacity'])} {m.get('type') or ''} @ {m.get('speed') or '?'} MT/s — {m.get('manufacturer') or ''} {m.get('part') or ''}"
            parts.append(_row(f"&nbsp;&nbsp;{m['slot']}", detail))
        for g in inv["gpus"]:
            parts.append(_row("Graphics", f"{g['name']} (driver {g.get('driver') or '?'})"))
        parts.append("</table>")

        # Storage
        parts.append("<h2>Storage</h2>")
        if stor["disks"]:
            parts.append("<table><thead><tr><th>Disk</th><th>Type</th><th class='num'>Size</th>"
                         "<th>Health</th><th class='num'>Temp</th><th class='num'>Power-on</th></tr></thead><tbody>")
            for d in stor["disks"]:
                temp = f"{d['temp_c']} °C" if d.get("temp_c") else "—"
                poh = f"{d['power_on_hours']:,} h" if d.get("power_on_hours") else "—"
                parts.append(f"<tr><td>{_esc(d['name'])}</td><td>{_esc(d.get('media'))} / {_esc(d.get('bus'))}</td>"
                             f"<td class='num'>{_gb(d.get('size'))}</td><td>{_esc(d.get('health'))}</td>"
                             f"<td class='num'>{temp}</td><td class='num'>{poh}</td></tr>")
            parts.append("</tbody></table><br>")
        parts.append("<table><thead><tr><th>Volume</th><th>Label</th><th>FS</th>"
                     "<th class='num'>Size</th><th class='num'>Free</th><th class='num'>Used</th></tr></thead><tbody>")
        for v in stor["volumes"]:
            parts.append(f"<tr><td>{_esc(v['letter'])}:</td><td>{_esc(v['label'])}</td><td>{_esc(v['fs'])}</td>"
                         f"<td class='num'>{_gb(v['size'])}</td><td class='num'>{_gb(v['free'])}</td>"
                         f"<td class='num'>{v['percent']}%</td></tr>")
        parts.append("</tbody></table>")

        # Network
        parts.append("<h2>Network</h2><table><thead><tr><th>Adapter</th><th>IPv4</th><th>Gateway</th>"
                     "<th>DNS</th><th>MAC</th><th>Link</th></tr></thead><tbody>")
        for a in net["adapters"]:
            if a.get("status") != "Up":
                continue
            parts.append(f"<tr><td>{_esc(a['alias'])}<br><span class='muted'>{_esc(a.get('desc'))}</span></td>"
                         f"<td>{_esc(a['ipv4'])}</td><td>{_esc(a['gateway'])}</td><td>{_esc(a['dns'])}</td>"
                         f"<td>{_esc(a['mac'])}</td><td>{_esc(a['speed'])}</td></tr>")
        parts.append("</tbody></table>")
        if net.get("wifi"):
            w = net["wifi"]
            parts.append(f"<p class='muted'>Wi-Fi: {_esc(w.get('ssid'))} — signal {_esc(w.get('signal'))}, "
                         f"{_esc(w.get('radio'))}, channel {_esc(w.get('channel'))}</p>")

        # Events summary
        c = evt["counts"]
        parts.append(f"<h2>Event Log (last {evt['days']} days)</h2>"
                     f"<p>{c.get('critical', 0)} critical &middot; {c.get('error', 0)} errors &middot; "
                     f"{c.get('warning', 0)} warnings. Most recent below.</p>")
        parts.append("<table><thead><tr><th>Time</th><th>Level</th><th>Source</th><th>Message</th></tr></thead><tbody>")
        for e in evt["events"][:15]:
            badge = {"critical": "bad", "error": "bad", "warning": "warn"}.get(e["level"], "unk")
            parts.append(f"<tr><td style='white-space:nowrap'>{_esc(e['time'])}</td>"
                         f"<td><span class='badge {badge}'>{e['level'].upper()}</span></td>"
                         f"<td>{_esc(e['source'])}</td><td class='muted'>{_esc(e['message'][:160])}</td></tr>")
        parts.append("</tbody></table>")

        # Software summary
        parts.append(f"<h2>Installed Software ({len(apps)})</h2>"
                     "<table><thead><tr><th>Application</th><th>Version</th><th>Publisher</th><th>Installed</th></tr></thead><tbody>")
        for a in apps:
            parts.append(f"<tr><td>{_esc(a['name'])}</td><td>{_esc(a['version'])}</td>"
                         f"<td class='muted'>{_esc(a['publisher'])}</td><td>{_esc(a['installed'])}</td></tr>")
        parts.append("</tbody></table>")

        parts.append(f"""<footer><span>Benchly — workstation triage &amp; diagnostics</span>
<span>{html.escape(host)} &middot; {now.strftime('%Y-%m-%d %H:%M')}</span></footer>
</div></body></html>""")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("".join(parts))

        # machine-readable twin — feeds the Fleet page's cross-machine compare
        json_path = os.path.splitext(out_path)[0] + ".json"
        snapshot = {
            "schema": REPORT_SCHEMA,
            "generated": now.strftime("%Y-%m-%d %H:%M"),
            "host": host,
            "os": inv["os"], "system": inv["system"],
            "cpu": inv["cpus"][0] if inv["cpus"] else {},
            "ram_total": inv.get("ram_total"),
            "score": health["score"], "grade": health["grade"],
            "checks": {c["id"]: {"status": c["status"], "label": c["label"]}
                       for c in health["checks"]},
            "disks": [{"name": d["name"], "health": d["health"], "size": d["size"]}
                      for d in stor["disks"]],
            "volumes": [{"letter": v["letter"], "size": v["size"], "free": v["free"]}
                        for v in stor["volumes"]],
            "apps": {a["name"]: a["version"] for a in apps},
            "services": {s["name"]: s["start"] for s in software.get_services()},
            "startup": {s["name"]: s["command"] for s in software.get_startup()},
            "event_counts": evt["counts"],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f)

        progress(7)
        pdf = _render_pdf(out_path)
        return {"ok": True, "path": out_path, "pdf": pdf, "json": json_path}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---- ticket summary -------------------------------------------------------------

def build_ticket_summary():
    """Plain-text triage block ready to paste into a PSA/RMM ticket."""
    inv = sysinfo.get_inventory()
    health = security.get_health()
    stor = storage.get_storage()
    now = datetime.datetime.now()
    uptime_days = (time.time() - psutil.boot_time()) / 86400

    lines = [
        f"=== {inv['hostname']} — Benchly triage {now.strftime('%Y-%m-%d %H:%M')} ===",
        f"Machine : {(inv['system'].get('manufacturer') or '?')} {(inv['system'].get('model') or '')}".rstrip(),
        f"OS      : {inv['os'].get('name')} (build {inv['os'].get('build')})",
        f"CPU     : {(inv['cpus'][0]['name'] if inv['cpus'] else '?')}",
        f"RAM     : {_gb(inv.get('ram_total'))}",
        f"Uptime  : {uptime_days:.1f} days",
    ]
    try:
        du = psutil.disk_usage("C:\\")
        lines.append(f"C: free : {_gb(du.free)} of {_gb(du.total)} ({100 - du.percent:.0f}%)")
    except Exception:
        pass
    av = next((p["name"] for p in health.get("av_products", []) if p["enabled"]), None)
    if av:
        lines.append(f"AV      : {av}")
    bad_disks = [d for d in stor["disks"] if d.get("health") and d["health"] != "Healthy"]
    if bad_disks:
        lines.append("DISKS   : " + ", ".join(f"{d['name']} ({d['health']})" for d in bad_disks))
    lines.append(f"Health  : {health['score']}/100 (grade {health['grade']})")
    flagged = [c for c in health["checks"] if c["status"] in ("bad", "warn")]
    if flagged:
        lines.append("Findings:")
        for c in flagged:
            lines.append(f"  [{'FAIL' if c['status'] == 'bad' else 'WARN'}] {c['label']} — {c['detail']}")
    else:
        lines.append("Findings: none — all checks pass")
    return {"ok": True, "text": "\n".join(lines)}
