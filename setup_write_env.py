"""Writes .env from JSON; used by setup.ps1 (path to temp JSON as argv[1])."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def quote_env(s: str) -> str:
    if any(c in s for c in " \n\r\t#") or '"' in s or "'" in s or s.startswith("#"):
        t = s.replace("\\", "\\\\").replace('"', '\\"')
        return '"' + t + '"'
    return s


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: setup_write_env.py <path-to-json>")
    payload = Path(sys.argv[1]).read_text(encoding="utf-8-sig")
    d = json.loads(payload)
    keys = [
        "SECRET_KEY",
        "ADMIN_EMAIL",
        "ADMIN_PASSWORD",
        "ADMIN_NAME",
        "BMAT_HOST",
        "BMAT_PORT",
        "BMAT_WAITRESS_THREADS",
    ]
    defaults = {"BMAT_WAITRESS_THREADS": "16"}
    lines = [f"{k}={quote_env(str(d.get(k, defaults.get(k, ''))))}" for k in keys]
    Path(".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(".env written.")


if __name__ == "__main__":
    main()
