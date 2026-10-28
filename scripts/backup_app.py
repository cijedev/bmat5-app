#!/usr/bin/env python3
"""
Full backup of the BMW Flask app: application code, instance data (SQLite DB),
static assets, scripts, and docs. Output is a timestamped zip under distros/.

Unlike package_release.py, this includes instance/*.db and is meant for
disaster recovery / migrating a live deployment — not for clean public release.

Run from repo root:

  python scripts/backup_app.py
  python scripts/backup_app.py --with-videos
  python scripts/backup_app.py -o distros/my-backup.zip
  python scripts/backup_app.py --include-env   # adds .env (secrets) — use with care

Excludes: venv, .git, Python caches, dist/, distros/ (avoid nesting zips), node_modules,
and by default large video files and .env (unless --include-env).
"""
from __future__ import annotations

import argparse
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_TOP = "bmat-app-backup"

# Do not traverse these directory names anywhere in the path.
EXCLUDE_DIR_NAMES = frozenset(
    {
        "venv",
        ".git",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".cursor",
        ".vv-context",
        "node_modules",
        "dist",
        "distros",
        "_playwright_record",
        "_playwright_ads",
    }
)

SKIP_SUFFIXES = frozenset({".pyc", ".pyo"})

ALLOW_DOTFILES = frozenset({".env.example", ".gitignore", ".gitkeep", ".cursorrules"})


def path_has_excluded_dir(rel: Path) -> bool:
    return bool(set(rel.parts) & EXCLUDE_DIR_NAMES)


def should_skip(
    rel: Path,
    *,
    with_videos: bool,
    include_env: bool,
) -> bool:
    if path_has_excluded_dir(rel):
        return True
    if rel.suffix.lower() in SKIP_SUFFIXES:
        return True
    name = rel.name
    if name.startswith(".") and name not in ALLOW_DOTFILES:
        if name == ".env":
            return not include_env
        return True
    if not with_videos:
        try:
            vi = rel.parts.index("videos")
        except ValueError:
            pass
        else:
            if len(rel.parts) > vi and rel.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}:
                return True
    return False


def iter_backup_files(with_videos: bool, include_env: bool) -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if path.is_dir():
            continue
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            continue
        if should_skip(rel, with_videos=with_videos, include_env=include_env):
            continue
        out.append(rel)
    out.sort(key=lambda p: str(p).lower())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Zip BMW app + instance DB into distros/")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output zip path (default: distros/bmat-app-backup-<UTC>.zip)",
    )
    ap.add_argument(
        "--with-videos",
        action="store_true",
        help="Include large files under bmat/static/videos (default: skip)",
    )
    ap.add_argument(
        "--include-env",
        action="store_true",
        help="Include .env if present (contains secrets — protect the zip)",
    )
    args = ap.parse_args()

    distros = ROOT / "distros"
    distros.mkdir(parents=True, exist_ok=True)

    if args.output:
        out_path = args.output
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
        out_path = distros / f"bmat-app-backup-{stamp}.zip"

    if args.include_env:
        print("WARNING: --include-env will embed .env secrets in the zip. Store it safely.", flush=True)

    files = iter_backup_files(args.with_videos, args.include_env)
    if not files:
        print("No files to pack.", flush=True)
        return 1

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            src = ROOT / rel
            arc = f"{ARCHIVE_TOP}/{rel.as_posix()}"
            zf.write(src, arcname=arc)

    size_kb = out_path.stat().st_size // 1024
    print(f"Wrote {out_path} ({size_kb} KB, {len(files)} files)")
    print(f"  Restore: unzip, recreate venv (pip install -r requirements.txt), place .env if omitted, run app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
