"""Quick file hash — MD5 / SHA-1 / SHA-256 of any file, computed locally.

Pairs with the VirusTotal check (which only ever sends the SHA-256): this gives all
three digests at once for matching against an advisory, verifying a download, or
spotting two identically-named files that differ. Read-only — nothing leaves the machine.
"""

import hashlib
import os

_MAX_BYTES = 4 * 1024 ** 3   # 4 GB guard — don't chew on a disk image by accident


def hash_file(path):
    try:
        full = os.path.abspath(str(path))
        if not os.path.isfile(full):
            return {"ok": False, "error": "That path isn't a file."}
        size = os.path.getsize(full)
        if size > _MAX_BYTES:
            return {"ok": False, "error": f"File is larger than 4 GB ({size // 1024**3} GB) — skipped."}
        md5, sha1, sha256 = hashlib.md5(), hashlib.sha1(), hashlib.sha256()
        with open(full, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)
        return {
            "ok": True, "path": full, "name": os.path.basename(full), "size": size,
            "md5": md5.hexdigest(), "sha1": sha1.hexdigest(), "sha256": sha256.hexdigest(),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
