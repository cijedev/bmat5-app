#!/usr/bin/env python3
"""
Cross-platform first-time setup: virtualenv, pip install, .env

  Windows (after unzip):  py scripts\setup_bmat.py
  Linux/macOS:            python3 scripts/setup_bmat.py

Non-interactive (CI / cloud-init), set env vars then:

  python3 scripts/setup_bmat.py --non-interactive

Required for --non-interactive: ADMIN_EMAIL, ADMIN_PASSWORD
Optional: SECRET_KEY, ADMIN_NAME, BMAT_HOST, BMAT_PORT, BMAT_WAITRESS_THREADS
"""
from __future__ import annotations

import argparse
import getpass
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / "venv"


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def quote_env(s: str) -> str:
    if any(c in s for c in " \n\r\t#") or '"' in s or "'" in s or s.startswith("#"):
        t = s.replace("\\", "\\\\").replace('"', '\\"')
        return '"' + t + '"'
    return s


def write_env(d: dict[str, str]) -> None:
    keys = [
        "SECRET_KEY",
        "ADMIN_EMAIL",
        "ADMIN_PASSWORD",
        "ADMIN_NAME",
        "BMAT_HOST",
        "BMAT_PORT",
        "BMAT_WAITRESS_THREADS",
    ]
    lines = [f"{k}={quote_env(str(d[k]))}" for k in keys]
    (ROOT / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(".env written at", ROOT / ".env")


def run(cmd: list[str], **kw) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True, **kw)


def ensure_venv(create: bool) -> Path:
    py = venv_python()
    if py.is_file():
        return py
    if not create:
        print("venv not found. Run with default venv creation or create venv manually.", file=sys.stderr)
        sys.exit(1)
    print("Creating virtual environment in", VENV_DIR)
    run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if not py.is_file():
        print("venv python missing after create:", py, file=sys.stderr)
        sys.exit(1)
    return py


def pip_install(vp: Path) -> None:
    run([str(vp), "-m", "pip", "install", "--upgrade", "pip"])
    req = ROOT / "requirements.txt"
    if not req.is_file():
        print("Missing requirements.txt", file=sys.stderr)
        sys.exit(1)
    run([str(vp), "-m", "pip", "install", "-r", str(req)])


def interactive_env() -> dict[str, str]:
    print("\nAdmin account (applied when the database is first created).")
    email = input("Admin email: ").strip().lower()
    if not email:
        print("Admin email is required.", file=sys.stderr)
        sys.exit(1)
    pw = getpass.getpass("Admin password (min 10 chars): ")
    if len(pw) < 10:
        print("Password must be at least 10 characters.", file=sys.stderr)
        sys.exit(1)
    name = input("Admin display name [Admin]: ").strip() or "Admin"

    print("\nServer bind (Waitress production entrypoint: bmat_serve.py)")
    print("  Use 0.0.0.0 for all interfaces, 127.0.0.1 for local only.")
    host = input("BMAT_HOST [0.0.0.0]: ").strip() or "0.0.0.0"
    port = input("BMAT_PORT [5000]: ").strip() or "5000"
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        print("Invalid port.", file=sys.stderr)
        sys.exit(1)
    threads = input("BMAT_WAITRESS_THREADS [16]: ").strip() or "16"
    if not threads.isdigit() or int(threads) < 1:
        print("Invalid thread count.", file=sys.stderr)
        sys.exit(1)

    existing = ""
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("SECRET_KEY="):
                existing = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

    secret = existing or secrets.token_hex(32)
    return {
        "SECRET_KEY": secret,
        "ADMIN_EMAIL": email,
        "ADMIN_PASSWORD": pw,
        "ADMIN_NAME": name,
        "BMAT_HOST": host,
        "BMAT_PORT": port,
        "BMAT_WAITRESS_THREADS": threads,
    }


def noninteractive_env() -> dict[str, str]:
    email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    pw = os.environ.get("ADMIN_PASSWORD") or ""
    if not email or not pw:
        print("Non-interactive mode requires ADMIN_EMAIL and ADMIN_PASSWORD in the environment.", file=sys.stderr)
        sys.exit(1)
    if len(pw) < 10:
        print("ADMIN_PASSWORD must be at least 10 characters.", file=sys.stderr)
        sys.exit(1)
    port = (os.environ.get("BMAT_PORT") or "5000").strip()
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        print("BMAT_PORT must be an integer 1–65535.", file=sys.stderr)
        sys.exit(1)
    threads = (os.environ.get("BMAT_WAITRESS_THREADS") or "16").strip()
    if not threads.isdigit() or int(threads) < 1:
        print("BMAT_WAITRESS_THREADS must be a positive integer.", file=sys.stderr)
        sys.exit(1)
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        "ADMIN_EMAIL": email,
        "ADMIN_PASSWORD": pw,
        "ADMIN_NAME": (os.environ.get("ADMIN_NAME") or "Admin").strip() or "Admin",
        "BMAT_HOST": (os.environ.get("BMAT_HOST") or "0.0.0.0").strip(),
        "BMAT_PORT": port,
        "BMAT_WAITRESS_THREADS": threads,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="BMW venv + pip + .env setup")
    ap.add_argument("--non-interactive", action="store_true", help="Read config from environment variables")
    ap.add_argument("--no-venv", action="store_true", help="Do not create venv; use current Python for pip (advanced)")
    args = ap.parse_args()

    os.chdir(ROOT)

    if args.no_venv:
        vp = Path(sys.executable)
        pip_install(vp)
    else:
        vp = ensure_venv(create=not args.no_venv)
        pip_install(vp)

    if args.non_interactive:
        data = noninteractive_env()
    else:
        data = interactive_env()

    write_env(data)

    print("\nDone.")
    if sys.platform == "win32":
        print("  Activate:  .\\venv\\Scripts\\Activate.ps1")
        print("  Production:  python bmat_serve.py")
        print("  Dev (SocketIO):  python bmat_run.py")
    else:
        print("  Activate:  source venv/bin/activate")
        print("  Production:  python bmat_serve.py")
        print("  Dev (SocketIO):  python bmat_run.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
