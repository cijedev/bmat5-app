# Better Mental Wellness (BMW) rebrand

**Date:** 2026-09-20 (PT)  
**From:** BMAT / Black Mental Wellness (Black-women-focused framing)  
**To:** Better Mental Wellness (BMW) — general audience  
**Public URL:** `https://cije.live/bmw/` (port **5669** unchanged)

## Product naming

| Role | Value |
|------|--------|
| Full name | Better Mental Wellness |
| Short name | BMW |
| Template globals | `APP_NAME`, `APP_SHORT` in `bmat/routes.py` `inject_globals()` |

## What changed (user-facing)

- Nav, titles, About, culture/care-plan copy, crisis disclaimer, clinical PDF labels, AI system prompt, ad/demo HTML, README / features / DEPLOY docs.
- Audience framing: **all people** seeking mental wellness; Warren Model kept as research foundation, not exclusivity.
- Cultural “representation” strip reframed as optional **diverse voices & wellness media** for anyone.
- URL prefix: `/bmat5` → `/bmw` (`APPLICATION_ROOT`, ScriptNameMiddleware default, session cookie path, Apache proxy + redirects).
- PHQ-9 / GAD-7 scoring unchanged; **988** / **911** crisis resources retained.

## Leftover internal `bmat` paths (intentional)

Kept for import/deploy stability. **Not** shown as product marketing:

| Item | Notes |
|------|--------|
| Python package `bmat/` | Imports: `from bmat import create_app`, etc. |
| Entry scripts | `bmat.py`, `bmat_run.py`, `bmat_serve.py`, `bmat_serve_bmat5.py`, `bmat_menu.py` |
| Env var names | `BMAT_HOST`, `BMAT_PORT`, `BMAT_WAITRESS_THREADS`, `BMAT_ENV`, `BMAT_CORS_ORIGINS`, `BMAT_SCREENSHARE_ENABLED` |
| Config keys | `BMAT_SCREENSHARE_ENABLED`, `BMAT_IS_DEVELOPMENT`, `BMAT_CORS_ORIGINS` |
| SQLite default | `instance/bmat.db` |
| CSS / DOM | Classes/ids like `bmat-card`, `bmat-nav`, `bmatLandingHero` |
| Media filenames | e.g. `bmat_ad_flask.mp4`, ad HTML under `bmat/static/ad/` |
| Cookie | `bmat_vid` analytics visitor cookie |
| OS / systemd | User `bmat5`, unit `bmat5-app.service`, path `/home/bmat5/app` |

## Deploy notes

- Never overwrite live `.env` or `instance/*.db` with the overlay.
- Merge only: `APPLICATION_ROOT=/bmw` into existing `.env` (keep `SECRET_KEY`, OpenAI/Groq settings).
- Apache: proxy `/bmw/` → `http://127.0.0.1:5669/`; redirect `/bmat5` and `/bmat5/` → `/bmw/`.

## Verify

```bash
curl -sI https://cije.live/bmw/ | head -5
curl -sI https://cije.live/bmat5 | head -10
curl -sL https://cije.live/bmw/ | grep -oE 'Better Mental Wellness|BMW|BMAT|Black women' | sort | uniq -c
```

## Deploy verification (2026-09-20 PT)

| Check | Result |
|-------|--------|
| `https://cije.live/bmw/` | HTTP 200 |
| `https://cije.live/bmat5` | 301 → `/bmw/` |
| `https://cije.live/bmat5/` | 301 → `/bmw/` |
| Homepage brand | Better Mental Wellness / BMW present; no BMAT / Black-women-only marketing |
| About page | Same |
| `APPLICATION_ROOT` | `/bmw` |
| Session cookie Path | `/bmw` |
| Port / service | 5669 / `bmat5-app.service` (internal unit name unchanged) |
| Server backup | `/home/bmat5/backups/bmw-rebrand-pre-20260920-160919` |

### Files changed (primary)

- `bmat/routes.py` — `APP_NAME` / `APP_SHORT`
- `bmat/ai_service.py` — general-audience system prompt
- `bmat/templates/about.html`, `base.html`, `culture.html`, `careplan.html`, `index.html`, `phq9_crisis.html`, `ai_wellness.html`, `personal_profile.html`, `bmat_demo.html`
- `bmat/forms.py`, `bmat/clinical_pdf.py`, `bmat/resources.py`, `bmat/cultural.py`, `bmat/middleware.py`, `bmat/sockets.py`
- `bmat/static/ad/*.html`
- `bmat_serve_bmat5.py` — default ScriptName `/bmw`
- `.env.example`, `README.md`, `features.md`, `DEPLOY.md`, `P0_CHANGES.md`, menus/scripts copy
- Apache: `bmw-proxy.conf` (old `bmat5-proxy.conf` disabled)
