#!/usr/bin/env python3
"""
Interactive launcher for BMW: backup, setup, dev server, open site, compress slideshow OOXML.

Run from the project root:

  python bmat_menu.py

Windows users can double-click bmat_menu.bat instead.
"""
from __future__ import annotations

import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKUP_SCRIPT = ROOT / "scripts" / "backup_app.py"
COMPRESS_SCRIPT = ROOT / "scripts" / "compress_slideshow_office.py"
SETUP_SCRIPT = ROOT / "scripts" / "setup_bmat.py"
RUN_DEV_PS1 = ROOT / "run_dev.ps1"
BMAT_RUN = ROOT / "bmat_run.py"
BMAT_URL = "https://bmat6.cije.live"


def _venv_python() -> Path | None:
    if sys.platform == "win32":
        p = ROOT / "venv" / "Scripts" / "python.exe"
    else:
        p = ROOT / "venv" / "bin" / "python"
    return p if p.is_file() else None


def run_compress_slideshows() -> None:
    if not COMPRESS_SCRIPT.is_file():
        print(f"Missing {COMPRESS_SCRIPT}", flush=True)
        return
    print("Compressing OOXML slideshows (.pptx / .ppsx)…", flush=True)
    r = subprocess.run([sys.executable, str(COMPRESS_SCRIPT)], cwd=ROOT)
    print(f"Compress finished (exit code {r.returncode}).", flush=True)


def run_backup() -> None:
    if not BACKUP_SCRIPT.is_file():
        print(f"Missing {BACKUP_SCRIPT}", flush=True)
        return
    print("Running backup…", flush=True)
    r = subprocess.run([sys.executable, str(BACKUP_SCRIPT)], cwd=ROOT)
    print(f"Backup finished (exit code {r.returncode}).", flush=True)


def run_setup() -> None:
    if not SETUP_SCRIPT.is_file():
        print(f"Missing {SETUP_SCRIPT}", flush=True)
        return
    print("Running setup (virtualenv, pip, .env)…", flush=True)
    r = subprocess.run([sys.executable, str(SETUP_SCRIPT)], cwd=ROOT)
    print(f"Setup finished (exit code {r.returncode}).", flush=True)


def run_bmat_dev() -> None:
    if sys.platform == "win32":
        if not RUN_DEV_PS1.is_file():
            print(f"Missing {RUN_DEV_PS1}", flush=True)
            return
        print("Starting dev server (run_dev.ps1)…", flush=True)
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(RUN_DEV_PS1),
            ],
            cwd=ROOT,
        )
        print(f"Dev server process ended (exit code {r.returncode}).", flush=True)
        return

    py = _venv_python()
    exe = str(py) if py else sys.executable
    if not BMAT_RUN.is_file():
        print(f"Missing {BMAT_RUN}", flush=True)
        return
    print("Starting dev server (bmat_run.py)…", flush=True)
    r = subprocess.run([exe, str(BMAT_RUN)], cwd=ROOT)
    print(f"Dev server process ended (exit code {r.returncode}).", flush=True)


def open_bmat_site() -> None:
    print(f"Opening {BMAT_URL} …", flush=True)
    webbrowser.open(BMAT_URL, new=1)


def print_menu() -> None:
    print()
    print("  ========== BMW menu ==========")
    print("  1  Backup BMW      (zip to distros/)")
    print("  2  Setup BMW       (venv, pip, .env)")
    print("  3  Run BMW (dev)   (run_dev.ps1 on Windows)")
    print(f"  4  Open BMAT site   ({BMAT_URL})")
    print("  5  Compress slides  (.pptx / .ppsx in media/slideshows)")
    print("  0  Exit")
    print("  ================================")


def main() -> int:
    if Path.cwd().resolve() != ROOT:
        print("Tip: run this script from the BMW project root for correct paths.", flush=True)

    while True:
        print_menu()
        try:
            choice = input("Enter choice [0-5]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.", flush=True)
            return 0

        if choice == "0":
            print("Bye.", flush=True)
            return 0
        if choice == "1":
            run_backup()
        elif choice == "2":
            run_setup()
        elif choice == "3":
            run_bmat_dev()
        elif choice == "4":
            open_bmat_site()
        elif choice == "5":
            run_compress_slideshows()
        else:
            print("Invalid choice — enter 0, 1, 2, 3, 4, or 5.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
