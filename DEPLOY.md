# Deploying Better Mental Wellness / BMW (Flask)

## 1. Build a release zip (maintainers)

From a clone of the repo, with Python 3 available:

```bash
python scripts/package_release.py
```

Optional: include large files under `bmat/static/videos`:

```bash
python scripts/package_release.py --with-videos
```

The zip is written to `dist/bmat-flask-release-<UTC-time>.zip`. Unpacking creates a **`bmat-flask/`** folder.

### Full backup (code + SQLite + media)

For a **recoverable snapshot** of a live tree (includes `instance/bmat.db`, slideshows under `bmat/media/`, etc.), use the separate backup script — **not** the release packager above:

```bash
python scripts/backup_app.py
```

Output: `distros/bmat-app-backup-<UTC>Z.zip` with top-level folder **`bmat-app-backup/`**.

- **`--with-videos`**: include large files under `bmat/static/videos`.
- **`--include-env`**: include `.env` if present (**secrets** — store the zip accordingly).
- Excludes: `venv`, `.git`, caches, `dist/`, `distros/` (so old backups are not nested into new ones).

Restore: unzip, recreate `venv` (`pip install -r requirements.txt`), copy or recreate `.env` if it was omitted, run `python bmat_serve.py` (or your process manager).

### Optional: OpenAI (AI Wellness)

**AI Wellness** (`/ai-wellness`; older path `/wellness-assistant` still works) calls OpenAI when configured. On the server, set in `.env` (do not commit):

- `OPENAI_API_KEY` — required for AI responses
- `OPENAI_MODEL` — optional, default `gpt-4o-mini`

Restart the app after changing these variables.

### Interactive menu (Windows dev machine)

From the repo root:

```text
python bmat_menu.py
```

Or double-click `bmat_menu.bat`. Options: (1) run `backup_app.py`, (2) run `setup_bmat.py`, (3) run `run_dev.ps1`, (4) open https://bmat6.cije.live in the default browser, (5) run `compress_slideshow_office.py` to recompress `.pptx` / `.ppsx` in `bmat/media/slideshows`.

### Compress slideshow files (OOXML)

`.pptx` and `.ppsx` are ZIP archives; re-packing with maximum DEFLATE often shrinks them without changing slides:

```bash
python scripts/compress_slideshow_office.py
python scripts/compress_slideshow_office.py --dry-run
```

Legacy binary `.ppt` / `.pps` (non-ZIP) are skipped. Re-save those in PowerPoint as `.pptx` / `.ppsx` if you need compression.

## 2. First-time setup on the server

### Windows Server / Windows 10+

1. Unzip so you have a folder containing `setup.ps1`, `bmat/`, `requirements.txt`, etc.
2. Open **PowerShell** in that folder (Run as Administrator only if your policy requires it).
3. If execution policy blocks scripts: use `run_dev.bat` for dev, or run:
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   ```
4. Run:
   ```powershell
   .\setup.ps1
   ```
   Answer prompts for admin user, password, bind address, port, and Waitress thread count.

Alternatively, cross-platform Python setup (no PowerShell prompts for pip/venv):

```powershell
py scripts\setup_bmat.py
```

### Linux / macOS

1. Unzip and `cd` into the release folder.
2. Make the shell helper executable once:
   ```bash
   chmod +x setup.sh
   ```
3. Run:
   ```bash
   ./setup.sh
   ```

Non-interactive example (cloud-init, CI):

```bash
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="CHANGE_ME"
export BMAT_HOST="0.0.0.0"
export BMAT_PORT="5000"
./setup.sh --non-interactive
```

## 3. Run in production (Waitress)

Activate the virtual environment, then:

```bash
# Linux/macOS
source venv/bin/activate
python bmat_serve.py

# Windows PowerShell
.\venv\Scripts\Activate.ps1
python bmat_serve.py
```

Environment variables (from `.env` or the shell):

| Variable | Purpose |
|----------|---------|
| `BMAT_HOST` | Bind address (e.g. `0.0.0.0`) |
| `BMAT_PORT` | Port (e.g. `5000`) |
| `BMAT_WAITRESS_THREADS` | Worker threads (default `16`) |
| `SECRET_KEY` | Flask session secret |
| `ADMIN_*` | Bootstrap admin on **first** DB creation only |

SQLite is created at `instance/bmat.db` unless `DATABASE_URL` is set.

## 4. Development (SocketIO debug server)

```bash
source venv/bin/activate   # or Windows Activate.ps1
python bmat_run.py
```

Listens on `0.0.0.0:5030` with `debug=True` — **not** for production.

## 5. Reverse proxy

Put **nginx**, **Caddy**, or **IIS** (ARR) in front of Waitress for HTTPS and static caching. Forward HTTP to `127.0.0.1:<BMAT_PORT>`. WebSocket paths used by Flask-SocketIO must be proxied if you rely on sockets in production.

## 6. Analytics retention (recommended cron/scheduled task)

Dry run:

```bash
python scripts/cleanup_analytics.py --dry-run
```

Apply cleanup:

```bash
python scripts/cleanup_analytics.py
```

Defaults: delete `VisitEvent` rows older than 90 days; delete `VisitSession` rows older than 180 days only when no events are attached.

## Phase 5 email check-in (consent)

Env (merged into live `.env`, do not wipe secrets):

- `MAIL_ENABLED=1`
- `MAIL_FROM=noreply@cije.live` (domain `cije.live`; aliases `noreply@` / `bmw@` → local `cije` mailbox)
- `MAIL_SMTP_HOST=127.0.0.1`
- `MAIL_SMTP_PORT=25`

### How to test

1. **Dry-run body/subject (no SMTP):**
   ```bash
   cd /home/bmat5/app
   sudo -u bmat5 env MAIL_ENABLED=0 ./venv/bin/python scripts/test_mailer_dryrun.py
   ```
2. **Live SMTP send to a real inbox:**
   ```bash
   sudo -u bmat5 env MAIL_ENABLED=1 MAIL_TO=you@example.com \
     ./venv/bin/python scripts/test_mailer_dryrun.py --send
   ```
3. **In app:** log in → Connections → enable master consent → add/mark a contact with email + “email on check-in” → Record check-in request → confirm flash + recent log “email: sent”.
4. **Rate limit:** four requests the same UTC day with consent should flash rate-limited on the 4th batch.
5. **Logged-out:** `GET /bmw/connections` → 302 to `/bmw/login`.

SMS/Twilio is intentionally not implemented.
