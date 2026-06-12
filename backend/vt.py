"""VirusTotal hash lookups (API v3).

Privacy by design: only the SHA-256 hash ever leaves the machine — files are
hashed locally and never uploaded.
"""

import hashlib
import json
import os
import re
import urllib.error
import urllib.request

from . import settings

_HASH_RE = re.compile(r"^[A-Fa-f0-9]{32}$|^[A-Fa-f0-9]{40}$|^[A-Fa-f0-9]{64}$")


def hash_file(path: str):
    try:
        if not os.path.isfile(path):
            return {"ok": False, "error": "File not found."}
        h = hashlib.sha256()
        size = 0
        with open(path, "rb") as f:
            while chunk := f.read(1 << 20):
                h.update(chunk)
                size += len(chunk)
        return {"ok": True, "sha256": h.hexdigest(), "size": size,
                "name": os.path.basename(path)}
    except OSError as e:
        return {"ok": False, "error": str(e)}


def check_hash(file_hash: str):
    api_key = (settings.get("vt_api_key") or "").strip()
    if not api_key:
        return {"ok": False, "error": "no_key"}
    file_hash = (file_hash or "").strip().lower()
    if not _HASH_RE.match(file_hash):
        return {"ok": False, "error": "Enter a valid MD5, SHA-1 or SHA-256 hash."}

    req = urllib.request.Request(
        f"https://www.virustotal.com/api/v3/files/{file_hash}",
        headers={"x-apikey": api_key, "User-Agent": "Benchly"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": True, "found": False, "hash": file_hash}
        if e.code == 401:
            return {"ok": False, "error": "VirusTotal rejected the API key (401)."}
        if e.code == 429:
            return {"ok": False, "error": "VirusTotal rate limit reached (free tier: 4 lookups/min)."}
        return {"ok": False, "error": f"VirusTotal error HTTP {e.code}."}
    except Exception as e:
        return {"ok": False, "error": f"Lookup failed: {e}"}

    attr = (data.get("data") or {}).get("attributes") or {}
    stats = attr.get("last_analysis_stats") or {}
    results = attr.get("last_analysis_results") or {}
    flagged = [{"engine": k, "verdict": v.get("category"), "label": v.get("result")}
               for k, v in results.items()
               if v.get("category") in ("malicious", "suspicious")]
    flagged.sort(key=lambda x: (x["verdict"] != "malicious", x["engine"].lower()))

    return {
        "ok": True,
        "found": True,
        "hash": file_hash,
        "malicious": stats.get("malicious", 0),
        "suspicious": stats.get("suspicious", 0),
        "total": sum(stats.get(k, 0) for k in ("malicious", "suspicious", "undetected", "harmless")),
        "names": (attr.get("names") or [])[:4],
        "type": attr.get("type_description"),
        "flagged": flagged[:12],
        "link": f"https://www.virustotal.com/gui/file/{file_hash}",
    }
