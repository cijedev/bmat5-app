"""
Record HTML ads under bmat/static/ad/ to WebM (and MP4 if ffmpeg is available).

Uses Playwright Chromium, same pattern as render_demo_video.py.

Prerequisites:
  pip install playwright
  playwright install chromium

Optional (for .mp4):
  ffmpeg on PATH

Run from repo root:
  python scripts/render_ad_videos.py
  python scripts/render_ad_videos.py --only bmat_ad_reel
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
PORT = 5801
# Extra tail so the last frame / CSS loop isn't cut off
PAD_MS = 400

# slug -> relative URL path (Flask /static/...), record duration in ms
ADS: list[dict[str, str | int]] = [
    {
        "slug": "bmat_ad_reel",
        "url_path": "/static/ad/bmat_ad_reel.html",
        "record_ms": 12_000 + PAD_MS,  # --ad-sec: 12 in the HTML
    },
    {
        "slug": "bmat_commercial_20s",
        "url_path": "/static/ad/bmat_commercial_20s.html",
        "record_ms": 20_000 + PAD_MS,  # JS loop totals 20s
    },
]


def _run_flask() -> None:
    os.chdir(ROOT)
    from bmat import create_app

    app = create_app()
    app.run(host="127.0.0.1", port=PORT, use_reloader=False, debug=False, threaded=True)


def _ffmpeg_webm_to_mp4(webm: Path, mp4: Path) -> bool:
    exe = shutil.which("ffmpeg")
    if not exe:
        return False
    cmd = [
        exe,
        "-y",
        "-i",
        str(webm),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(mp4),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _record_one(
    slug: str,
    url_path: str,
    record_ms: int,
    out_dir: Path,
    tmp_dir: Path,
) -> Path | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Missing playwright. Run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return None

    ad_tmp = tmp_dir / slug
    if ad_tmp.exists():
        shutil.rmtree(ad_tmp)
    ad_tmp.mkdir(parents=True)

    url = f"http://127.0.0.1:{PORT}{url_path}"
    webm_path = out_dir / f"{slug}.webm"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(ad_tmp),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="load", timeout=120_000)
        except Exception as exc:
            print(f"[{slug}] Failed to load {url}: {exc}", file=sys.stderr)
            context.close()
            browser.close()
            shutil.rmtree(ad_tmp, ignore_errors=True)
            return None
        page.wait_for_timeout(record_ms)
        context.close()
        browser.close()

    vids = sorted(glob.glob(str(ad_tmp / "*.webm")))
    if not vids:
        print(f"[{slug}] No video file from Playwright.", file=sys.stderr)
        shutil.rmtree(ad_tmp, ignore_errors=True)
        return None

    shutil.move(vids[0], webm_path)
    shutil.rmtree(ad_tmp, ignore_errors=True)
    return webm_path


def main() -> int:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)

    parser = argparse.ArgumentParser(description="Render BMW static/ad HTML to video.")
    parser.add_argument(
        "--only",
        metavar="SLUG",
        help="Single ad slug, e.g. bmat_ad_reel or bmat_commercial_20s",
    )
    args = parser.parse_args()

    ads = ADS
    if args.only:
        ads = [a for a in ADS if a["slug"] == args.only]
        if not ads:
            print(f"Unknown slug {args.only!r}. Known: {[a['slug'] for a in ADS]}", file=sys.stderr)
            return 1

    out_dir = ROOT / "bmat" / "static" / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_root = out_dir / "_playwright_ads"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True)

    server = Thread(target=_run_flask, daemon=True)
    server.start()
    time.sleep(2.5)

    code = 0
    for ad in ads:
        slug = str(ad["slug"])
        path = _record_one(
            slug,
            str(ad["url_path"]),
            int(ad["record_ms"]),
            out_dir,
            tmp_root,
        )
        if path is None:
            code = 2
            continue
        kb = path.stat().st_size // 1024
        print(f"Wrote {path} ({kb} KB)")
        mp4 = path.with_suffix(".mp4")
        wrote_mp4 = _ffmpeg_webm_to_mp4(path, mp4)
        if wrote_mp4:
            print(f"Wrote {mp4} ({mp4.stat().st_size // 1024} KB)")
        else:
            print(f"(Skip MP4: ffmpeg not found or failed; WebM is at {path.name})")

        if slug == "bmat_commercial_20s":
            landing_webm = out_dir / "landing-hero.webm"
            shutil.copy2(path, landing_webm)
            print(f"Copied to {landing_webm.name} (home page hero — Chrome/Firefox/Edge)")
            if wrote_mp4:
                landing_mp4 = out_dir / "landing-hero.mp4"
                shutil.copy2(mp4, landing_mp4)
                print(f"Copied to {landing_mp4.name} (home page hero — Safari / broadest support)")

    shutil.rmtree(tmp_root, ignore_errors=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
