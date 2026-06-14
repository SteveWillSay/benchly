"""\"Text my tech person\" — a plain-English health card and handoff.

Turns Benchly's diagnostics into something a non-technical person can read and a
helper can act on. Produces a friendly summary (the few things that look wrong, in
human words) plus a copy-ready text block to send to whoever fixes their computer.
Nothing is sent anywhere — the user copies/saves it themselves.
"""

import datetime

from . import security, storage


def _plain(check):
    """A failing health check, said the way you'd say it to a relative."""
    cid = check.get("id", "")
    label = check.get("label", "")
    detail = check.get("detail", "")
    friendly = {
        "av_rt": "Your antivirus protection looks turned off.",
        "av_sig": "Your antivirus is out of date.",
        "fw": "The Windows Firewall looks turned off.",
        "updates": "Windows updates need attention.",
        "diskfree": "Your main drive is nearly full.",
        "reboot": "The computer needs restarting to finish some updates.",
        "battery": "The battery health is low.",
        "bitlocker": "Drive encryption isn't set up.",
    }
    return friendly.get(cid) or (label + (": " + detail if detail else ""))


def helper_card():
    h = security.get_health()
    issues = []
    for c in h.get("checks", []):
        if c.get("status") in ("bad", "warn"):
            issues.append({"level": c["status"], "text": _plain(c)})

    # disk space, in friendly terms
    facts = []
    try:
        for v in (storage.get_storage().get("volumes") or []):
            if str(v.get("letter") or "").upper().startswith("C"):
                free_gb = round((v.get("free") or 0) / (1024 ** 3))
                total_gb = round((v.get("size") or 0) / (1024 ** 3))
                if total_gb:
                    facts.append(f"Main drive: {free_gb} GB free of {total_gb} GB")
                break
    except Exception:
        pass

    score = h.get("score")
    grade = h.get("grade")
    headline = ("This computer looks healthy." if not any(i["level"] == "bad" for i in issues) and len(issues) <= 1
                else "A few things on this computer could use a look.")

    # build the share text
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"Benchly health summary — {now}", headline, f"Overall score: {score}/100 (grade {grade})", ""]
    if issues:
        lines.append("Things to look at:")
        lines += [f"  - {i['text']}" for i in issues]
        lines.append("")
    if facts:
        lines += facts + [""]
    lines.append("(Sent from Benchly — the technician can open the full report for details.)")
    share_text = "\n".join(lines)

    return {
        "ok": True,
        "headline": headline,
        "score": score,
        "grade": grade,
        "issues": issues,
        "facts": facts,
        "share_text": share_text,
        "clean": not issues,
    }
