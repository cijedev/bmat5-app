# BMAT5

Next-generation BMAT application.

## Published from cije.live archive

This repository was published from a cleaned project archive. Secrets, runtime databases, uploads, and dependency folders were removed. Configure via environment variables (see `.env.example` if present, or the docs below).

**Do not commit** `.env`, password files, private keys, or live databases.


# Better Mental Wellness (BMW) — Flask app

## Features
- Optional **AI Wellness** (OpenAI) when `OPENAI_API_KEY` is set — supportive reflection, not medical advice (`/ai-wellness`; legacy `/wellness-assistant` still works)
- Email/password accounts (Flask-Login, werkzeug hashing)
- Daily check-ins (mood, stress, sleep, notes)
- PHQ-9 + GAD-7 screenings (scoring + severity)
- Safety messaging when PHQ-9 item #9 > 0
- Care plan suggestions based on latest signals
- History dashboards
- **Admin (Ethical Mode)**:
  - Aggregated metrics overview (default)
  - User list with emails masked by default
  - Risk flags panel (awareness, not surveillance)
  - CSV export gated by acknowledgement; masks PII unless `?pii=1` (datasets: users, assessments, check-ins, audit_log, action_completions, visit_session, visit_event, trusted_contact, check_in_on_me_request, clinical_review)
  - Audit log of key admin actions

## Quick start (Windows)
1) Double-click **`run_dev.bat`** (uses the venv Python only; no PowerShell script policy needed), **or** double-click **`run_dev.cmd`** if you prefer the PowerShell script with a one-process `ExecutionPolicy Bypass`.
2) Open the URL printed in the terminal (usually http://127.0.0.1:5000)

If `.\run_dev.ps1` fails with “not digitally signed,” use `run_dev.bat` or `run_dev.cmd` instead of changing system-wide policy.

## Create an admin account (recommended)
Set env vars before first run (PowerShell example):

```powershell
$env:ADMIN_EMAIL="admin@yourdomain.com"
$env:ADMIN_PASSWORD="ChangeThisPassword123!"
$env:ADMIN_NAME="Admin"
.\run_dev.ps1
```

Admin is created once and stored in the SQLite DB.

## Render ad HTML to video (optional)
Install Playwright and Chromium, then from the repo root:

```powershell
pip install playwright
playwright install chromium
python scripts/render_ad_videos.py
```

Outputs `bmat/static/videos/bmat_ad_reel.webm` and `bmat_commercial_20s.webm` (1920×1080). If `ffmpeg` is on your PATH, matching `.mp4` files are written too. See also `scripts/render_demo_video.py` for the product demo page.

## Home page hero video
Place **`bmat/static/videos/bmat_ad_flask.mp4`** for the pre-login background. Resolution order: **`bmat_ad_flask_h264.mp4`** (if you transcode), then **`bmat_ad_flask.mp4`**, then `landing-hero.mp4` / `landing-hero.webm`. If the MP4 won’t play in Chrome (often HEVC), install ffmpeg and run:

```powershell
python scripts/transcode_bmat_ad_flask.py
```

That writes **`bmat_ad_flask_h264.mp4`**, which the home page will use first.

## Release zip & server setup (Windows / Linux)

Build a deployable archive (no `venv`, no `.env`, no local DB):

```powershell
python scripts/package_release.py
```

Creates `dist/bmat-flask-release-<timestamp>.zip` with a top-level **`bmat-flask/`** folder. Optional: add `--with-videos` to pack `bmat/static/videos` media.

**Windows:** unzip → `.\setup.ps1` (or `py scripts\setup_bmat.py`).  
**Linux/macOS:** unzip → `chmod +x setup.sh` → `./setup.sh` (or `python3 scripts/setup_bmat.py`).

Unattended Linux:

```bash
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="CHANGE_ME"
./setup.sh --non-interactive
```

Then activate `venv` and run `python bmat_serve.py`. Full notes: **`DEPLOY.md`**.

## Interactive menu (Windows)

From the project root, **`bmat_menu.py`** opens a text menu: backup → `scripts/backup_app.py`, setup → `scripts/setup_bmat.py`, run dev → `run_dev.ps1`, open **https://cije.live/bmw/**, compress → `scripts/compress_slideshow_office.py` (smaller `.pptx` / `.ppsx` under `bmat/media/slideshows`). Double-click **`bmat_menu.bat`** if you prefer Explorer.

## Full backup (snapshot with database)

```powershell
python scripts/backup_app.py
```

Creates **`distros/bmat-app-backup-<timestamp>.zip`** (app code, `instance/bmat.db`, media, scripts; excludes `venv` and `distros/`). Options: `--with-videos`, `--include-env` (includes secrets). See **`DEPLOY.md`**.

## Data storage
SQLite file is created at: `instance/bmat.db`

## Analytics retention cleanup
Prune old first-party tracking data:

```powershell
python scripts/cleanup_analytics.py --dry-run
python scripts/cleanup_analytics.py
```

Defaults: events older than 90 days, sessions older than 180 days (sessions are only removed when they have no events).


## Added in v1.4
- Phase 1: action completion tracking, daily completion counts, streaks, wellness score
- Phase 2: adaptive care plans, recommended-for-you suggestions, featured resource, pattern insights
- Phase 5 (baseline): Connections (`/connections`) + Personalization — together under **Personal profile** hub (`/personal-profile`)
- Phase 6 (baseline): Admin **Clinical** dashboard, longitudinal charts, PDF progress report (`reportlab`), internal review notes (`ClinicalReview`) + CSV export `clinical_review`

- Added Chart.js charts on the Trends & History page for assessments, check-ins, and action completions.

**Roadmap:** Phases **1–7** baseline are shipped; **Phase 8** includes optional **AI Wellness** (`/ai-wellness`) when `OPENAI_API_KEY` is set — see **[`features.md`](features.md)**. Never commit API keys; use `.env` (see `.env.example`).
