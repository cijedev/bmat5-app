"""
Transcode bmat/static/videos/bmat_ad_flask.mp4 → bmat_ad_flask_h264.mp4 (H.264 + yuv420p).

Use when the source is HEVC or otherwise won’t play in Chrome/Edge <video>.

Requires ffmpeg on PATH. Run from repo root:

  python scripts/transcode_bmat_ad_flask.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "bmat" / "static" / "videos" / "bmat_ad_flask.mp4"
DST = ROOT / "bmat" / "static" / "videos" / "bmat_ad_flask_h264.mp4"


def main() -> int:
    if not SRC.is_file():
        print(f"Missing source: {SRC}", file=sys.stderr)
        print("Place your file at bmat/static/videos/bmat_ad_flask.mp4", file=sys.stderr)
        return 1
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not on PATH. Install ffmpeg, then re-run.", file=sys.stderr)
        return 2
    DST.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(SRC),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(DST),
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("ffmpeg failed.", file=sys.stderr)
        return e.returncode or 3
    kb = DST.stat().st_size // 1024
    print(f"Wrote {DST} ({kb} KB) — home page uses this before bmat_ad_flask.mp4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
