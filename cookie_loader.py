import json
import os
import sqlite3
import shutil
import base64
import tempfile
import ctypes
import threading
from pathlib import Path

from Cryptodome.Cipher import AES

COOKIES_FILE = Path(__file__).parent / "hh_cookies.json"
BROWSERS = [
    (Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data", "Chrome"),
    (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data", "Edge"),
]


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _unprotect_data(encrypted: bytes) -> bytes:
    blob_in = DATA_BLOB(
        len(encrypted),
        ctypes.cast(ctypes.create_string_buffer(encrypted), ctypes.POINTER(ctypes.c_char)),
    )
    blob_out = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32

    result = {}

    def worker():
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, ctypes.byref(blob_out)
        )
        if ok:
            result["data"] = ctypes.string_at(blob_out.pbData, blob_out.cbData)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=5)
    if "data" in result:
        return result["data"]
    raise RuntimeError("CryptUnprotectData timed out or failed")


def _get_encryption_key(local_state_path: str) -> bytes:
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    encrypted_key = encrypted_key[5:]
    return _unprotect_data(encrypted_key)


def _decrypt_value(value: bytes, key: bytes) -> str:
    if not value:
        return ""
    try:
        if value[:3] in (b"v10", b"v11"):
            nonce, ciphertext, tag = value[3:15], value[15:-16], value[-16:]
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
        return _unprotect_data(value).decode("utf-8")
    except Exception:
        return ""


def _load_cookies_from_db(db_path: str, key: bytes, host_filter: str = "hh.ru") -> dict:
    tmp = Path(tempfile.gettempdir()) / "hh_read_cookies.db"
    shutil.copy2(db_path, tmp)
    conn = sqlite3.connect(str(tmp))
    cookies: dict[str, str] = {}
    try:
        rows = conn.execute(
            "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE ?",
            (f"%{host_filter}%",),
        ).fetchall()
        for name, enc_value in rows:
            val = _decrypt_value(enc_value, key)
            if val:
                cookies[name] = val
    finally:
        conn.close()
        tmp.unlink(missing_ok=True)
    return cookies


def _scan_browser_cookies() -> tuple[dict, str]:
    """Scan Chrome/Edge for hh.ru cookies. Runs DPAPI in a subprocess to avoid hangs."""
    import subprocess, sys

    code = r'''
import sys, json
sys.path.insert(0, %r)
sys.path.insert(0, %r)
import cookie_loader as cl
for base, browser_name in cl.BROWSERS:
    local_state = base / "Local State"
    cookies_db = base / "Default" / "Network" / "Cookies"
    if not local_state.exists() or not cookies_db.exists():
        continue
    alt = base / "Profile 1" / "Network" / "Cookies"
    dbs = [cookies_db]
    if alt.exists():
        dbs.append(alt)
    try:
        key = cl._get_encryption_key(str(local_state))
        for db in dbs:
            cookies = cl._load_cookies_from_db(str(db), key)
            if cookies.get("hhtoken") or cookies.get("jwt_token"):
                print(json.dumps({"cookies": cookies, "source": f"browser ({browser_name}, {db.parent.parent.name})"}, ensure_ascii=False))
                sys.exit(0)
    except Exception:
        continue
print(json.dumps({"cookies": {}, "source": "none"}))
sys.exit(0)
''' % (str(Path(__file__).parent), r"D:\libs")

    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", code],
            capture_output=True, text=True, timeout=10,
        )
        out = result.stdout.strip().splitlines()
        if out:
            data = json.loads(out[-1])
            return data["cookies"], data["source"]
    except Exception:
        pass
    return {}, "none"


def load_hh_cookies() -> tuple[dict, str]:
    """Load hh.ru cookies. Prefers saved file, falls back to browser decryption."""
    if COOKIES_FILE.exists():
        try:
            rows = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
            cookies = {r["name"]: r["value"] for r in rows if r.get("name") and r.get("value")}
            if cookies:
                return cookies, "saved file"
        except Exception:
            pass

    return _scan_browser_cookies()


def save_hh_cookies(cookies: dict, source: str = "browser"):
    """Save a copy of cookies to hh_cookies.json for later sessions."""
    rows = [{"name": k, "value": v, "domain": ".hh.ru", "path": "/", "secure": False}
            for k, v in cookies.items()]
    COOKIES_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return source