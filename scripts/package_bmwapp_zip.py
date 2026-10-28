#!/usr/bin/env python3
"""Build bmat/static/bmwapp.zip — public source snapshot without secrets or PHI."""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bmat" / "static" / "bmwapp.zip"

INCLUDE_TOP = {
    "bmat",
    "scripts",
    "requirements.txt",
    "requirements-dev.txt",
    ".env.example",
    "README.md",
    "DEPLOY.md",
    "features.md",
    "REBRAND.md",
    "P0_CHANGES.md",
    "bmat.py",
    "bmat_run.py",
    "bmat_serve.py",
    "bmat_serve_bmat5.py",
    "bmat_menu.py",
    "bmat_menu.bat",
    "setup.sh",
    "setup.ps1",
    "setup.cmd",
    "setup_write_env.py",
    "run_dev.bat",
    "run_dev.cmd",
    "run_dev.ps1",
}

SKIP_DIR_NAMES = {
    "venv",
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "instance",
    "dist",
    "distros",
    "node_modules",
}

SKIP_FILE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".zip",
    ".zip.tmp",
    ".bak",
    ".bak-groq",
)


def should_skip(path: Path, rel: Path) -> bool:
    if any(part in SKIP_DIR_NAMES for part in rel.parts):
        return True
    name = path.name
    if name == ".env" or name.startswith(".env.") and name != ".env.example":
        return True
    if name == "bmwapp.zip" or name.startswith("bmwapp.zip"):
        return True
    lower = name.lower()
    if lower.endswith(SKIP_FILE_SUFFIXES):
        return True
    # avoid nesting any zip artifacts under static/
    if "static" in rel.parts and lower.endswith((".zip", ".tmp")):
        return True
    try:
        if path.resolve() == OUT.resolve():
            return True
    except OSError:
        pass
    return False


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".zip.building")
    if tmp.exists():
        tmp.unlink()

    count = 0
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("instance/.gitkeep", "")
        count += 1

        for name in sorted(INCLUDE_TOP):
            src = ROOT / name
            if not src.exists():
                continue
            if src.is_file():
                rel = Path(name)
                if should_skip(src, rel):
                    continue
                zf.write(src, arcname=rel.as_posix())
                count += 1
                continue
            for dirpath, dirnames, filenames in os.walk(src):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
                for fn in filenames:
                    fp = Path(dirpath) / fn
                    rel = fp.relative_to(ROOT)
                    if should_skip(fp, rel):
                        continue
                    zf.write(fp, arcname=rel.as_posix())
                    count += 1

    os.replace(tmp, OUT)
    size = OUT.stat().st_size
    print(f"Wrote {OUT} ({size} bytes, {count} entries)")


if __name__ == "__main__":
    main()
