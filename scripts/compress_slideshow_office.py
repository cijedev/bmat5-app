#!/usr/bin/env python3
"""
Re-pack Office Open XML slideshows/presentations with maximum DEFLATE compression.

.ppsx and .pptx files are ZIP archives; recompressing often reduces size with no
loss of content. Legacy binary .pps / .ppt (OLE) are not ZIP-based — those are
skipped unless the file is actually OOXML (wrong extension).

Usage (from repo root):

  python scripts/compress_slideshow_office.py
  python scripts/compress_slideshow_office.py --dry-run
  python scripts/compress_slideshow_office.py --path bmat/media/slideshows
"""
from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OOXML_EXT = frozenset({".pptx", ".ppsx"})
LEGACY_EXT = frozenset({".ppt", ".pps"})
ZIP_MAGIC = b"PK\x03\x04"


def is_zip_ooxml(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == ZIP_MAGIC
    except OSError:
        return False


def recompress_ooxml_zip(path: Path, *, dry_run: bool) -> tuple[int, int, bool]:
    """
    Returns (old_bytes, new_bytes, changed).
    If dry_run, changed is False and new_bytes is projected size from memory.
    """
    old = path.stat().st_size
    buf = io.BytesIO()
    with zipfile.ZipFile(path, "r") as zin:
        with zipfile.ZipFile(
            buf,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as zout:
            for info in zin.infolist():
                if info.is_dir():
                    continue
                data = zin.read(info.filename)
                zout.writestr(
                    info,
                    data,
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
    data = buf.getvalue()
    new_len = len(data)
    if dry_run:
        return old, new_len, new_len < old

    if new_len >= old:
        return old, new_len, False

    tmp = path.with_name(path.name + ".compress.tmp")
    try:
        tmp.write_bytes(data)
        with zipfile.ZipFile(tmp, "r") as zcheck:
            bad = zcheck.testzip()
            if bad is not None:
                raise zipfile.BadZipFile(f"Corrupt after recompress: {bad}")
        tmp.replace(path)
        return old, new_len, True
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Recompress OOXML slideshows under bmat/media/slideshows")
    ap.add_argument(
        "--path",
        type=Path,
        default=ROOT / "bmat" / "media" / "slideshows",
        help="Folder to scan (default: bmat/media/slideshows)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Show projected sizes only; do not write files")
    args = ap.parse_args()

    base = args.path
    if not base.is_absolute():
        base = ROOT / base
    if not base.is_dir():
        print(f"Not a directory: {base}", flush=True)
        return 1

    total_old = 0
    total_new = 0
    n_done = 0
    n_skip = 0

    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in OOXML_EXT | LEGACY_EXT:
            continue
        if ext in LEGACY_EXT and not is_zip_ooxml(path):
            print(f"Skip (legacy OLE .ppt/.pps, not OOXML): {path.relative_to(base)}", flush=True)
            n_skip += 1
            continue
        if ext in LEGACY_EXT and is_zip_ooxml(path):
            print(f"OOXML with legacy extension: {path.relative_to(base)}", flush=True)
        if not is_zip_ooxml(path):
            print(f"Skip (not a ZIP): {path.relative_to(base)}", flush=True)
            n_skip += 1
            continue

        try:
            old, new, changed = recompress_ooxml_zip(path, dry_run=args.dry_run)
        except (zipfile.BadZipFile, OSError) as e:
            print(f"Error {path.relative_to(base)}: {e}", flush=True)
            return 1

        total_old += old
        if args.dry_run or changed:
            total_new += new
        else:
            total_new += old
        n_done += 1
        rel = path.relative_to(base)
        if args.dry_run:
            pct = 100.0 * (1 - new / old) if old else 0
            print(f"  {rel}: {old} -> {new} bytes (~{pct:.1f}% smaller)", flush=True)
        elif changed:
            pct = 100.0 * (1 - new / old) if old else 0
            print(f"  {rel}: {old} -> {new} bytes (~{pct:.1f}% smaller)", flush=True)
        else:
            print(f"  {rel}: already compact ({old} bytes), left unchanged", flush=True)

    if n_done == 0:
        print("No .pptx/.ppsx (or OOXML-as-.ppt/.pps) files found.", flush=True)
        return 0

    if args.dry_run:
        pct = 100.0 * (1 - total_new / total_old) if total_old else 0
        print(
            f"Dry-run total: {total_old} -> {total_new} bytes (~{pct:.1f}% smaller). "
            "Run without --dry-run to write.",
            flush=True,
        )
    else:
        saved = total_old - total_new
        print(
            f"Done: {n_done} file(s), {n_skip} skipped. "
            f"Total before: {total_old} B, after: {total_new} B (saved {saved} B).",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
