"""Tiny persisted settings store — %APPDATA%\\Benchly\\settings.json.

Secret values (API keys) are encrypted at rest with Windows DPAPI so they are
bound to the user profile and never sit on disk in cleartext.
"""

import base64
import ctypes
import json
import os
from ctypes import wintypes

# Shared per-user data dir (settings, baseline snapshot)
APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Benchly")
_PATH = os.path.join(APP_DIR, "settings.json")

# Keys whose values are DPAPI-encrypted on disk
_SECRET_KEYS = {"vt_api_key"}


class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi_encrypt(text: str) -> str:
    data = text.encode("utf-8")
    blob_in = _BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)),
                                           ctypes.POINTER(ctypes.c_char)))
    blob_out = _BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("CryptProtectData failed")
    try:
        return base64.b64encode(ctypes.string_at(blob_out.pbData, blob_out.cbData)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _dpapi_decrypt(b64: str) -> str:
    enc = base64.b64decode(b64)
    buf = ctypes.create_string_buffer(enc, len(enc))
    blob_in = _BLOB(len(enc), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def load() -> dict:
    """Raw on-disk data (secret values stay in their encrypted form)."""
    try:
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def get(key: str, default=None):
    v = load().get(key, default)
    if key in _SECRET_KEYS and isinstance(v, dict) and "_enc" in v:
        try:
            return _dpapi_decrypt(v["_enc"])
        except Exception:
            return default
    return v


def set_value(key: str, value):
    data = load()
    if key in _SECRET_KEYS and value:
        try:
            data[key] = {"_enc": _dpapi_encrypt(str(value))}
        except Exception:
            # Never silently downgrade a secret to cleartext — refuse and surface it.
            return {"ok": False,
                    "error": "Couldn't encrypt this value with Windows DPAPI, so it was not saved "
                             "(refusing to store a secret in cleartext)."}
    else:
        data[key] = value
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return {"ok": True}
    except OSError as e:
        return {"ok": False, "error": str(e)}
