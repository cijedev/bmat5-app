# BMW P0 security / production fixes (historical)

Tree: `/workspace/bmw-p0-build` (copy of `bmat5-latest/bmat-app-backup`).
Deploy artifact: `/workspace/bmw-p0-deploy.tgz`.

## P0 requirements covered

1. **SECRET_KEY** — Outside `BMAT_ENV=development` / `FLASK_ENV=development`, refuse weak/missing keys (`changeme`, `dev-change-me`, empty, &lt;16 chars, etc.). No auto-generate in production.
2. **CSRFProtect** — Global Flask-WTF CSRFProtect; tokens on state-changing POSTs; `bmatFetch()` sends `X-CSRFToken`.
3. **Open redirect** — `safe_redirect_target()`; used on action complete/uncomplete `next` redirects.
4. **Admin risk emails** — Masked by default; full emails only with `reveal=1&confirm=1`.
5. **PHQ-9 item 9** — If item 9 &gt; 0 after submit, render `phq9_crisis.html` (988/911) before history.
6. **Screenshare / Socket.IO** — Auth on connect; CORS from env (no `*` in prod); non-guessable room codes (no default BMAT123); Waitress gate disables `/screenshare` with clear page; `bmat_run.py` keeps hardened Socket.IO path.
7. **/bmw prefix** — `ScriptNameMiddleware` (`X-Script-Name` / `X-Forwarded-Prefix` / `APPLICATION_ROOT`); session cookie path `/bmw` when root set; relative CSS asset path; Socket.IO client `path: scriptRoot + '/socket.io'`.

## Files changed

| Path | Summary |
|------|---------|
| `bmat/__init__.py` | Secret gate, CSRF init, CORS, APPLICATION_ROOT cookie path, screenshare flag |
| `bmat/extensions.py` | `csrf = CSRFProtect()` |
| `bmat/middleware.py` | **New** `ScriptNameMiddleware` + `application_root_from_env()` |
| `bmat/utils.py` | `safe_redirect_target()` |
| `bmat/sockets.py` | Auth on connect; room-code hardening |
| `bmat/routes.py` | Safe redirects; PHQ-9 crisis; admin risk mask/reveal; screenshare gate; CSRF bind on analyze-scores |
| `bmat/templates/base.html` | CSRF meta + `bmatFetch()` |
| `bmat/templates/admin_ack.html` | CSRF token |
| `bmat/templates/careplan.html` | CSRF on complete/uncomplete |
| `bmat/templates/dashboard.html` | CSRF on quick complete |
| `bmat/templates/admin_users.html` | CSRF on role POSTs |
| `bmat/templates/connections.html` | CSRF on contact delete |
| `bmat/templates/admin_clinical_user.html` | CSRF on review add/resolve |
| `bmat/templates/phq9_crisis.html` | **New** crisis interstitial |
| `bmat/templates/screenshare_disabled.html` | **New** Waitress disabled message |
| `bmat/templates/screenshare.html` | Random `suggested_room`; Socket.IO script-root path |
| `bmat/templates/admin_risk.html` | Masked emails + reveal confirm UX |
| `bmat/static/css/app.css` | Relative `../imgs/...` instead of `/static/...` |
| `bmat_serve.py` | Waitress + optional middleware; screenshare default off |
| `bmat_serve_bmat5.py` | **New** Waitress + `/bmw` ScriptNameMiddleware |
| `bmat_run.py` | Screenshare default on for Socket.IO entry |
| `.env.example` | SECRET_KEY, BMAT_ENV, APPLICATION_ROOT=/bmw, BMAT_CORS_ORIGINS |
| `P0_CHANGES.md` | This document |

## Naming mismatches vs other trees / live helpers

| Topic | This tree | Notes |
|-------|-----------|-------|
| App factory | `create_app()` in `bmat/__init__.py` | Import: `from bmat import create_app` |
| Waitress entry | `bmat_serve.py`, `bmat_serve_bmat5.py` | Live workspace samples may say `create_app` — use this package’s `create_app` |
| Prefix | `/bmw` | Matches P0 brief (`APPLICATION_ROOT=/bmw`) |
| Email helper | `mask_email()` | Used by admin users/risk |
| Redirect helper | `safe_redirect_target()` | Open-redirect guard |

## Live `.env` (cije.live)

```env
SECRET_KEY=<long-random-value>
BMAT_ENV=production
APPLICATION_ROOT=/bmw
BMAT_CORS_ORIGINS=https://cije.live
BMAT_HOST=127.0.0.1
BMAT_PORT=5000
BMAT_WAITRESS_THREADS=16
BMAT_SCREENSHARE_ENABLED=0
```

Apache should pass `X-Script-Name: /bmw` and/or `X-Forwarded-Prefix: /bmw`. Middleware also applies `APPLICATION_ROOT` when headers are absent.

## Smoke checklist

1. `BMAT_ENV=development SECRET_KEY=dev-test python -c 'from bmat import create_app; create_app()'` → OK
2. `BMAT_ENV=production SECRET_KEY=changeme python -c 'from bmat import create_app; create_app()'` → exit 2 + FATAL
3. CSRF: POSTs without token fail; with `csrf_token` / `X-CSRFToken` succeed
4. Open redirect: `next=https://evil.example` on action complete → safe fallback
5. `/admin/risk` masked; `/admin/risk?reveal=1&confirm=1` reveals + audit
6. PHQ-9 item9 &gt; 0 → crisis page before history
7. Waitress (`bmat_serve_bmat5.py`) → `/screenshare` disabled page
8. `bmat_run.py` → screenshare enabled, random room, Socket.IO under script root
9. With `APPLICATION_ROOT=/bmw`: cookie path `/bmw`; static + socket.io honor prefix

## Tarball

`/workspace/bmw-p0-deploy.tgz` — excludes `.venv`, `__pycache__`, `.env`, `*.db`.
