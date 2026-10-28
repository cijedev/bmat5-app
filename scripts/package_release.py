#!/usr/bin/env python3
"""
Build a clean release zip for deploying BMW (no venv, no secrets, no local DB).

Run from repo root:

  python scripts/package_release.py
  python scripts/package_release.py --with-videos
  python scripts/package_release.py -o dist/my-bmat.zip

Archive layout: bmat-flask/<files> so unzip creates a single folder.
"""
from __future__ import annotations

import argparse
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_TOP = "bmat-flask"

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
        "_playwright_record",
        "_playwright_ads",
    }
)

SKIP_SUFFIXES = frozenset({".pyc", ".pyo"})

ALLOW_TREE_TOP = frozenset({"bmat", "scripts", "instance"})
ALLOW_ROOT_FILES = frozenset(
    {
        "requirements.txt",
        "requirements-dev.txt",
        "bmat_serve.py",
        "bmat_run.py",
        "setup_write_env.py",
        "setup.ps1",
        "setup.sh",
        "run_dev.bat",
        "run_dev.cmd",
        "run_dev.ps1",
        "bmat_menu.py",
        "bmat_menu.bat",
        "README.md",
        "features.md",
        "DEPLOY.md",
        ".env.example",
        ".gitignore",
    }
)


def is_release_path(rel: Path) -> bool:
    top = rel.parts[0]
    if top in ALLOW_TREE_TOP:
        return True
    if len(rel.parts) == 1 and top in ALLOW_ROOT_FILES:
        return True
    return False


def should_skip(rel: Path, with_videos: bool) -> bool:
    if not is_release_path(rel):
        return True
    parts = set(rel.parts)
    if parts & EXCLUDE_DIR_NAMES:
        return True
    for p in rel.parts:
        if p in EXCLUDE_DIR_NAMES:
            return True
    if rel.suffix.lower() in SKIP_SUFFIXES:
        return True
    name = rel.name
    if name == ".env":
        return True
    if name.endswith(".db") and "instance" in rel.parts:
        return True
    if not with_videos:
        try:
            vi = rel.parts.index("videos")
        except ValueError:
            pass
        else:
            if len(rel.parts) > vi and rel.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}:
                return True
    if name.startswith(".") and name not in {".env.example", ".gitignore", ".gitkeep"}:
        return True
    return False


def iter_files(with_videos: bool) -> list[Path]:
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if path.is_dir():
            continue
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            continue
        if should_skip(rel, with_videos):
            continue
        out.append(rel)
    out.sort(key=lambda p: str(p).lower())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Zip BMW sources for release")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output zip path (default: dist/bmat-flask-release-UTCSTAMP.zip)",
    )
    ap.add_argument(
        "--with-videos",
        action="store_true",
        help="Include large video files under bmat/static/videos (default: skip)",
    )
    args = ap.parse_args()

    dist_dir = ROOT / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    if args.output:
        out_path = args.output
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        out_path = dist_dir / f"bmat-flask-release-{stamp}.zip"

    files = iter_files(args.with_videos)
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
    print(f"  Unzip, then run setup.ps1 (Windows) or ./setup.sh (Linux/macOS), then python bmat_serve.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
