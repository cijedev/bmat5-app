"""Discover weekly slide decks under bmat/media/slideshows/."""
from __future__ import annotations

import os
import re
from pathlib import Path

ALLOWED_EXT = frozenset({".pptx", ".ppsx", ".ppt", ".pps", ".pdf", ".html", ".htm"})

WEEK_PATTERNS = (
    re.compile(r"(?i)week[\s._-]*(\d+)"),
    re.compile(r"(?i)wk[\s._-]*(\d+)"),
    re.compile(r"(?i)^\s*(\d+)\s*[-–_]"),
)


def parse_week_from_filename(name: str) -> int | None:
    stem = Path(name).stem
    for pat in WEEK_PATTERNS:
        m = pat.search(stem)
        if m:
            return int(m.group(1))
    return None


def embed_kind_for_ext(ext: str) -> str:
    e = ext.lower()
    if e in {".pdf"}:
        return "pdf"
    if e in {".html", ".htm"}:
        return "html"
    if e in {".pptx", ".ppsx", ".ppt", ".pps"}:
        return "office"
    return "unknown"


def safe_slideshow_path(root: str, filename: str) -> str | None:
    """Return absolute file path if it exists under root, else None."""
    root = os.path.realpath(root)
    if not os.path.isdir(root):
        return None
    # normalize: reject absolute paths and traversal
    name = filename.replace("\\", "/").strip("/")
    if not name or ".." in name.split("/"):
        return None
    full = os.path.realpath(os.path.join(root, *name.split("/")))
    if not full.startswith(root + os.sep) and full != root:
        return None
    if not os.path.isfile(full):
        return None
    if Path(full).suffix.lower() not in ALLOWED_EXT:
        return None
    return full


def list_warren_slideshows(root: str) -> list[dict]:
    """
    Return sorted list of dicts: week (int|None), filename (relative posix), label, ext, embed_kind.
    """
    if not os.path.isdir(root):
        return []

    out: list[dict] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            ext = Path(fn).suffix.lower()
            if ext not in ALLOWED_EXT:
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            rel_posix = rel.replace("\\", "/")
            week = parse_week_from_filename(fn)
            wk = week if week is not None else parse_week_from_filename(rel_posix)
            label = f"Week {wk}" if wk is not None else Path(fn).stem.replace("_", " ")
            out.append(
                {
                    "week": wk,
                    "filename": rel_posix,
                    "label": label,
                    "ext": ext,
                    "embed_kind": embed_kind_for_ext(ext),
                }
            )

    def sort_key(d: dict) -> tuple:
        w = d["week"]
        if w is None:
            return (10_000, d["filename"])
        return (w, d["filename"])

    out.sort(key=sort_key)
    return out
