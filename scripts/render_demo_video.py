"""
Record bmat_demo.html to static/videos/bmat_demo.webm (Playwright + Chromium).

Prerequisites:
  pip install playwright
  playwright install chromium

Run from repo root:
  python scripts/render_demo_video.py
"""
from __future__ import annotations

import glob
import os
import shutil
import sys
import time
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
PORT = 5799
# Demo loop is 15s; pad for last frame + autostart delay
RECORD_MS = 17_000


def _run_flask() -> None:
    os.chdir(ROOT)
    from bmat import create_app

    app = create_app()
    app.run(host="127.0.0.1", port=PORT, use_reloader=False, debug=False, threaded=True)


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Missing playwright. Run: pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)

    out_dir = ROOT / "bmat" / "static" / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / "bmat_demo.webm"
    tmp_dir = out_dir / "_playwright_record"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)

    server = Thread(target=_run_flask, daemon=True)
    server.start()
    time.sleep(2.5)

    url = f"http://127.0.0.1:{PORT}/demo?autostart=1"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(tmp_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="load", timeout=120_000)
        except Exception as exc:
            print(f"Failed to load demo: {exc}", file=sys.stderr)
            context.close()
            browser.close()
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return 3
        page.wait_for_timeout(RECORD_MS)
        context.close()
        browser.close()

    vids = sorted(glob.glob(str(tmp_dir / "*.webm")))
    if not vids:
        print("No video file was written by Playwright.", file=sys.stderr)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return 2

    shutil.move(vids[0], final_path)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"Wrote {final_path} ({final_path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
