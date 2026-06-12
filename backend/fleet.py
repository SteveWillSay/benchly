"""Cross-machine report comparison — diff two Benchly report JSON exports."""

import json


def _load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "schema" not in data or "apps" not in data:
        raise ValueError("not a Benchly report JSON")
    return data


def _dict_diff(old, new, limit=400):
    added = sorted((k for k in new if k not in old), key=str.lower)
    removed = sorted((k for k in old if k not in new), key=str.lower)
    changed = sorted((k for k in new if k in old and old[k] != new[k]), key=str.lower)
    return {
        "added": [{"name": k, "value": str(new[k])[:120]} for k in added[:limit]],
        "removed": [{"name": k, "value": str(old[k])[:120]} for k in removed[:limit]],
        "changed": [{"name": k, "old": str(old[k])[:80], "new": str(new[k])[:80]}
                    for k in changed[:limit]],
    }


def compare_reports(path_a: str, path_b: str):
    try:
        a, b = _load(path_a), _load(path_b)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        return {"ok": False, "error": f"Could not read report JSON: {e}"}

    def meta(d):
        return {
            "host": d.get("host"),
            "generated": d.get("generated"),
            "os": (d.get("os") or {}).get("name"),
            "build": (d.get("os") or {}).get("build"),
            "model": f"{(d.get('system') or {}).get('manufacturer') or ''} "
                     f"{(d.get('system') or {}).get('model') or ''}".strip(),
            "cpu": (d.get("cpu") or {}).get("name"),
            "ram_total": d.get("ram_total"),
            "score": d.get("score"),
            "grade": d.get("grade"),
        }

    # health checks side by side, differences first
    checks = []
    all_ids = {**(a.get("checks") or {}), **(b.get("checks") or {})}
    for cid, any_check in all_ids.items():
        ca = (a.get("checks") or {}).get(cid)
        cb = (b.get("checks") or {}).get(cid)
        checks.append({
            "id": cid,
            "label": (ca or cb or any_check).get("label", cid),
            "a": ca["status"] if ca else None,
            "b": cb["status"] if cb else None,
        })
    checks.sort(key=lambda c: (c["a"] == c["b"], c["label"].lower()))

    return {
        "ok": True,
        "a": meta(a),
        "b": meta(b),
        "checks": checks,
        "apps": _dict_diff(a.get("apps") or {}, b.get("apps") or {}),
        "services": _dict_diff(a.get("services") or {}, b.get("services") or {}),
        "startup": _dict_diff(a.get("startup") or {}, b.get("startup") or {}),
    }
