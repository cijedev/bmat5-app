# Better Mental Wellness (BMW)

## About

Better Mental Wellness (BMW) is a web app for all people seeking mental wellness: check-ins, evidence-informed screenings, and supportive care planning. The in-app **About BMW** page (`/about`) mirrors this section for end users.

### Documentation map

| Doc | Role |
|-----|------|
| **`features.md` (this file)** | Full product picture: user-facing summary, shipped phases 1–8 baseline, roadmap (Phase 8 follow-ups + 9), recommended build order. |
| **`README.md`** | Quick start, scripts, deploy zip/backup, analytics cleanup; **roadmap** defers here for phase detail. |
| **`DEPLOY.md`** | Production deployment (Waitress, reverse proxy, HTTPS notes). |

### The Warren Model

BMW draws on the **Warren Model**, developed by **Dr. Rosalyn Warren Avant**, a professional with more than 20 years of experience. Originally researched with a midlife wellness focus, the Warren Model’s principles of steady, culturally humble support are offered here for **everyone**.

### What users can do with BMW

- **Account & privacy** — Secure sign-in, session handling, and optional cookie preferences.
- **Screenings** — Hub at **`/screenings`** to choose **PHQ-9** (depression) or **GAD-7** (anxiety); scores, severity labels, and history; safety messaging when indicated.
- **Daily check-in** — Track mood, stress, sleep, and notes over time.
- **Care plan** — Adaptive suggestions, tiny actions you can mark done, curated resources and embedded video.
- **Personal profile** (`/personal-profile`) — Hub to open **Connections** (trusted contacts, private “check-in on me” log at `/connections`) or **Personalization** (care-plan topic tuning at `/personalization`).
- **Cultural fit** (`/culture`) — Daily affirmations, language tone presets, optional “Representation & voices” video strip on the care plan; stored in `UserPreference` with Phase 4 prefs.
- **AI Wellness** (`/ai-wellness`) — Optional OpenAI-powered supportive reflection (server must set `OPENAI_API_KEY`); not medical advice. Legacy URL: `/wellness-assistant`.
- **Trends & history** — Charts and tables for assessments, check-ins, and action completions.
- **Wellness snapshot** — A wellness score and pattern insights drawn from your latest signals.
- **Private session** — Optional browser-based stream so others can join with a room code (you choose what to share).
- **Warren Model slides** — Weekly slide decks from `bmat/media/slideshows` (About BMW → Warren Model section).
- **Admin (when enabled)** — Ethical, aggregated oversight; optional clinical tools for authorized staff.

### Development

The main developers for this app are **Jeremy Carpenter** and **Ciara Smith** of **CIJE dev**, a private software development company that started in **2019**.

### Designers & collaborators

Further credits for designers and other contributors will be added here (and on the `/about` page when updated).

### In-app About page (`/about`)

Kept in sync with **What users can do** above, including **Personal profile** (hub → Connections + Personalization), **Cultural fit** (affirmations + tone; care-plan integration), **AI Wellness** (optional OpenAI when the server is configured), **Warren Model slides** (weekly decks from `bmat/media/slideshows` in the Warren spotlight), and **Admin** copy that mentions optional **clinical** tools for authorized staff.

---

## Current state (through Phase 8 baseline)

Phases **1–4**, **5** (connections), **6** (clinical), **7** (cultural intelligence), and **8** (optional OpenAI **AI Wellness**) are implemented in code. Phase 8 follow-ups (**per-user rate limits** + **optional journaling with consent**) are shipped. Optional RAG / mood-aware suggestions remain later. Details below.

### Core Functionality (Complete)
- User authentication (`login`, `signup`, `logout`)
- Role-based access (`User` / `Therapist` / `Admin`)
- Secure password handling
- Session management

### Assessments (Complete)
- **Screening hub** (`/screenings`): two tiles to open **PHQ-9** or **GAD-7** (sidebar: **Screenings**)
- PHQ-9 (depression screening)
- GAD-7 (anxiety screening)
- Score calculation with severity labels
- Historical storage

### Daily Check-In (Complete)
- Mood tracking (1-10)
- Stress tracking (1-10)
- Sleep tracking (hours)
- Notes field
- Historical logging

### Care Plan Engine (v2, Adaptive, Complete)
- Dynamic focus detection:
  - High stress
  - Low sleep
  - Low mood
  - High PHQ/GAD signals
- Adaptive prioritization:
  - Actions
  - Resources
- Personalized UX:
  - "Recommended for you" section
  - Featured resource
  - Tag-based resource filtering

### Content System (Complete)
- YouTube integration (resources + actions)
- Embedded videos
- Thumbnail fallback
- Multi-column premium UI layout
- **Warren Model weekly slide decks** on **`/about`**: files under `bmat/media/slideshows/` (e.g. `.pdf`, `.html`, `.pptx`, `.ppsx`); Office formats use Microsoft’s online viewer when the site is served over **HTTPS** (local `http://` may need PDF export for testing)

### Tiny Actions System (Phase 1 Complete)
- Dynamically generated action list
- Mark action as done
- Undo completion
- Stored in database

### Engagement Metrics (Phase 1 Complete)
- Daily completion count
- Action streak tracking
- Last 7-day activity tracking

### Wellness Intelligence (Phase 1-2 Complete)
- Wellness score (0-100)
- Score labels:
  - Strong
  - Steady
  - Needs support
  - High support
- Inputs used:
  - Check-in data
  - PHQ-9
  - GAD-7

### Trends and Visualization (Phase 2 Complete)
- Chart.js integration
- Assessment trends (PHQ/GAD)
- Check-in trends (mood/stress/sleep)
- Action completion trends
- Tabular history views

### Pattern Insights (Phase 2 Complete)
- Sleep to mood correlation
- Stress pattern detection
- Weekly trend observations
- Early behavioral insights

### Smart Dashboard (Phase 3, Complete)
- KPI row: wellness score, streak, completed today, latest mood
- Mini charts on home (last 7 check-ins + recent assessments) with empty-state hints when there is no data yet
- Auto-generated **Today's focus** from the care plan engine
- **Recommended for you** preview on home (links through to full care plan)
- **Quick action:** mark top suggested tiny action done from home + optional **Play guided step** (YouTube) for that action
- **Continue where you left off** (check-in / screenings / care plan based on freshness)
- **Streak motivation:** milestone goal (3→7→14→30 days), progress bar, short message
- **Pattern insights** block when the engine has themes to show
- **Next best steps:** top three care-plan actions on the home page

### Personalization (Phase 4, Complete)
- **Personal profile hub** (`/personal-profile`): sidebar entry to **Connections** or **Personalization** (two tiles)
- Multi-factor care plan scoring (flags + check-in trends + PHQ/GAD change vs last)
- Action rotation: 7d / 14d / 28d completion windows + stable weekly tie-break for variety
- Resource + action tuning: learned tag affinity from “mark done”
- Explicit **Personalization** page: “show more” / “show less” by topic (rest, sleep, support, boundaries), merged with safety guards so critical signals still surface help
- Per-user `UserPreference` JSON in the database

### First-party analytics (Complete)
- Anonymous visit sessions + events (`VisitSession`, `VisitEvent`); admin KPIs on **Analytics** (`/admin/analytics`)
- CSV exports for sessions/events (masked by default; `?pii=1` when authorized)
- Optional retention job: `scripts/cleanup_analytics.py`

### Admin dashboard (ethical mode, Complete)
- Aggregated metrics: users, assessments, check-ins, risk awareness, session/analytics KPIs
- Masked PII by default; **Reveal** on user list when need-based
- **Add user** and **Make admin** / **Remove admin** (cannot remove sole administrator)
- Audit logging; ethical acknowledgment gate before admin tools
- **CSV export** (acknowledgement): users, assessments, check-ins, audit_log, action_completions, visit_session, visit_event, trusted_contact, check_in_on_me_request, clinical_review (use `?pii=1` only when appropriate)

### Clinical and professional tools — Phase 6 (Complete — therapist role, PDF branding, escalation)
- **Clinical** (`/admin/clinical`): roster snapshot; per-user longitudinal view + PDF report; internal **ClinicalReview** notes (CSV export)
- **Therapist role** (`user` | `admin` | `therapist`): therapists access clinical tools after ethical ack; cannot manage admins, promote to admin, or use broad admin destructive / PII-reveal tools
- **PDF branding**: header “Better Mental Wellness (BMW)”, brand accent, footer “Not a diagnosis · For care coordination only”, generated timestamp, masked email
- **Automated escalation**: on PHQ-9 / GAD-7 save — item 9 > 0, PHQ-9 ≥ 15, or GAD-7 ≥ 15 creates open system `ClinicalReview` (type `escalation`) with 7-day dedupe; roster **Needs attention** badge/count
- Clinical access: admin **or** therapist + acknowledgment

### Human connection — Phase 5 (Complete — email + consent)
- **Connections** (`/connections`): trusted contacts; master + per-contact email consent; “Record check-in request” can email eligible contacts (no SMS); reachable from **`/personal-profile`**

### Cultural intelligence — Phase 7 baseline (Complete)
- **`/culture` (Cultural fit):** language tone presets (warm default, community-centered, faith-friendly inclusive, direct & grounded); daily rotating affirmations; optional **Representation & voices** strip on the care plan (`resources.py` entries tagged `representation`)
- **`bmat/cultural.py`:** tone maps for Today’s focus, recommended lines, streak microcopy; optional hints on tiny actions
- Stored in **`UserPreference.data_json`** (`tone_preset`, `highlight_representation`) alongside Phase 4 topic prefs

### AI layer — Phase 8 baseline (optional, Complete when configured)
- **`/ai-wellness`** (and legacy **`/wellness-assistant`**): OpenAI-compatible chat via **`bmat/ai_service.py`**; requires **`OPENAI_API_KEY`**, optional **`OPENAI_BASE_URL`** (e.g. Groq `https://api.groq.com/openai/v1`), and **`OPENAI_MODEL`** / **`GROQ_MODEL`** — see **`.env.example`** and **`DEPLOY.md`**
- Uses **Cultural fit** tone as a soft prompt hint; crisis language handled in system instructions (988)
- **Home AI prompt** (dashboard): inline card after **New check-in**, before **Today's affirmation**; dismissible via `localStorage` (`bmat_ai_dashboard_prompt_v1`); posts to `/ai-wellness`
- **Phase 8 follow-ups (shipped):** per-user rate limits (`AI_DAILY_LIMIT`, default 20/UTC day); optional journaling history with explicit consent (default off)

### UI/UX (Advanced)
- Full background image + layered lighting / vignette overlays
- Frosted glass cards
- Premium video UI
- Responsive layout (collapsible top nav on small screens)
- **Mobile sidebar compact toggle:** icon-only / collapsed menu on small screens (`body.bmat-sidebar-icon-only`); toggle updates aria-label / title
- Inter font loaded from Google Fonts + system-ui fallbacks; improved contrast and muted text tuning
- Keyboard: visible focus rings; skip link to main content
- `prefers-reduced-motion`: disables hover lift on premium cards
- Cookie consent banner (Accept / Decline optional), choice stored in browser `localStorage`
- **Home AI Wellness card** on dashboard (in-flow, not fixed overlay) — see Phase 8


### Color schemes
- Switchable themes via CSS custom properties (`bmat/static/css/themes/default.css`, `beach.css`) + `app.css` vars.
- Schemes: **`default`** (original neon glass) and **`beach`** (charcoal-blue / verdigris / tuscan-sun / sandy-brown / burnt-peach).
- Active scheme: env/config **`COLOR_SCHEME`** (default `beach`) → `<html data-theme="...">` and meta `theme-color`.
- Preview: append `?theme=default` or `?theme=beach` (stored in `bmat_color_scheme` cookie for 30 days). Clear cookie or set `?theme=` to the configured scheme to reset preview.
- PWA `manifest.webmanifest` theme/background colors are set for the **beach** scheme statically; change them if you switch the live default back to `default`.

### Deployment and maintainer tooling (Complete)
- **Release zip:** `scripts/package_release.py` → `dist/` (clean deploy; no DB)
- **Full backup:** `scripts/backup_app.py` → `distros/` (includes `instance/bmat.db`, media)
- **Launcher menu:** `bmat_menu.py` / `bmat_menu.bat` (backup, setup, dev server, open site, compress slides)
- **OOXML slideshow recompress:** `scripts/compress_slideshow_office.py` (`.pptx` / `.ppsx` under `bmat/media/slideshows`)
- Flask + Waitress; WebSocket-capable; reverse proxy–friendly (`DEPLOY.md`)

## Gap vs original vision

- **Vision:** A therapist-grade, culturally relevant, intelligent wellness platform.
- **Estimate:** Roughly **~85–92%** of the *technical* roadmap through Phase 7 baseline; next differentiation tranches are **Phase 8+** (AI, deeper cultural content, mobile).

## Roadmap — remaining phases

### Phase 5: Human Connection Layer
**Goal:** Reduce isolation (critical for target audience).

**Shipped:**
- **Connections** (`/connections`): trusted contact list; master toggle `notify_contacts_email` + per-contact `email_on_check_in`; check-in request log with optional plain-text email via local Postfix (`bmat/mailer.py`); rate limit 3 batches/UTC day; no clinical scores in email; **still no SMS**.

**Still to build:**
- SMS / Twilio (out of scope for this pass)
- Later: anonymous community feed

### Phase 6: Clinical and Professional Tools
**Goal:** Make BMW usable in real care environments.

**Shipped:**
- **Clinical dashboard** (`/admin/clinical`): per-user wellness index, latest PHQ-9 / GAD-7, Item 9 flag, last check-in, open internal review count; **Needs attention** for open escalations (admins and therapists, after acknowledgment).
- **Therapist role:** `User.role` includes `therapist`; clinical routes use `require_clinical` (admin OR therapist); admin UI can promote/demote therapist; nav Clinical link for therapists; broad admin tools remain admin-only.
- **Longitudinal view** (`/admin/clinical/user/<id>`): charts + tables + automated pattern notes; confirmation step before PII-heavy view; logged.
- **PDF progress report** (`/admin/clinical/user/<id>/report.pdf`): branded “Better Mental Wellness (BMW)” header, care-coordination footer, generated timestamp; masked email on PDF.
- **Risk / follow-up notes** (`ClinicalReview`): internal notes with resolve workflow; CSV export `clinical_review` (redact notes unless `?pii=1`); `review_type` / `reason_code` for escalations.
- **Automated escalation:** on assessment submit — PHQ item 9 > 0, PHQ-9 ≥ 15, or GAD-7 ≥ 15 → open system escalation (dedupe identical open reason within 7 days).

**Still to build:**
- SMS / Twilio for clinical alerts remains out of scope (Phase 5 SMS still pending)

---

### Phase 7: Cultural Intelligence
**Goal:** Make BMW truly differentiated.

**Shipped (baseline):**
- **Cultural fit** (`/culture`): tone presets, daily affirmations (deterministic per user/day), care-plan integration
- **Representation & voices:** optional curated video strip on care plan; resource entries tagged `representation` in `resources.py`
- **Context-aware copy:** tone-mapped focus labels, “Recommended for you,” Today’s focus subtitle, optional action hints

**Still to build:**
- Richer affirmation library, community-sourced lines (with moderation), locale/dialect, A/B or clinician-reviewed copy

### Phase 8: AI layer
**Goal:** Make the app feel like a supportive assistant.

**Shipped (baseline):**
- **AI Wellness** (`/ai-wellness`, legacy `/wellness-assistant`): optional OpenAI-compatible reflection (`bmat/ai_service.py`); **`OPENAI_API_KEY`** + optional **`OPENAI_BASE_URL`** (Groq-compatible) / **`OPENAI_MODEL`**; respects **Cultural fit** tone; safety-oriented system prompt (988)
- **Home AI prompt** on dashboard (after New check-in, before Today's affirmation); dismissible; no fixed overlay
- Production deploy path: **`https://cije.live/bmw`** (legacy `/bmat5` redirects)

**Follow-ups (shipped):**
- Per-user **rate limits** on successful AI generations (`AiUsageDaily`; env `AI_DAILY_LIMIT` default **20**/UTC day); friendly flash when exceeded; remaining quota shown on `/ai-wellness`
- Optional **journaling history** with explicit consent (`ai_journal_consent` default off; `AiJournalEntry` user+assistant rows); clear-history control; consent-aware privacy alert; journal kept user-private (not in admin CSV / clinical PDF)

**Still later:**
- Mood-aware suggestions, admin policy toggles, optional RAG on Warren content

### Phase 9: Mobile and notifications
**Goal:** Improve daily engagement.

**Shipped (baseline):**
- **Install to Home Screen (PWA)**: manifest (`/bmw/static/manifest.webmanifest`), 192/512 and maskable icons, minimal service worker at `/bmw/sw.js` (installability only — network pass-through, no offline cache of auth/API/Socket.IO), Home “Install to Home Screen” control (Chrome `beforeinstallprompt`; iOS Safari Share → Add to Home Screen guide). Not push notifications.

Still to build:
- Push notifications
- SMS/email reminders
- Fuller offline / mobile app version

## Recommended build order (after Phase 7 baseline)

1. **Phase 5 follow-ups** — SMS with consent (email shipped; SMS still pending Twilio); community feed (later).
2. **Phase 6 follow-ups** — Therapist role, PDF branding, and automated escalation **shipped**; further clinical polish as needed.
3. **Deeper insights** — Richer correlations / longitudinal UX for end users (complements existing history).
4. **Phase 7 follow-ups** — Expand affirmations, representation catalog, moderated community lines.
5. **Phase 8 follow-ups** — rate limits + journaling with consent (**shipped**); then mood-aware suggestions / optional RAG.
6. **Phase 9 — PWA install baseline shipped**; push notifications and SMS still open.

---

## Recent deploy notes (cije.live /bmw)

- Live app: **`https://cije.live/bmw`** (Apache reverse proxy → Waitress on port **5669**); `/bmat5` → `/bmw`
- PWA install baseline: manifest, icons, `/bmw/sw.js`, Home install control (no push).
- AI backend: Groq OpenAI-compatible API via `OPENAI_BASE_URL` (model set in `.env`)
- UX: mobile sidebar collapse; Home AI card in-flow (not fixed bottom banner)
- Public source zip (no secrets): **`https://cije.live/bmw/bmwapp.zip`**
- Webmail redirect: `/webmail` → `/roundcube`

---

## Release notes alignment (v1.4 baseline)

High-level shipped items also summarized in **`README.md`** (“Added in v1.4”). This list adds **Phases 3–4** and cross-doc context so nothing is missing:

- **Phase 1:** Action completion tracking, daily completion counts, streaks, wellness score
- **Phase 2:** Adaptive care plans, recommended-for-you, featured resource, pattern insights
- **Phase 3:** Smart dashboard — KPI row, home mini charts, Today’s focus, quick action + guided step, continue where you left off, streak motivation, pattern insights block, next best steps
- **Phase 4:** Personalization page + per-user `UserPreference` (topic tuning with safety guards)
- **Phase 7 (baseline):** **Cultural fit** (`/culture`) — tone presets, daily affirmations, optional representation strip on care plan (`bmat/cultural.py`)
- **Phase 8 (baseline):** **AI Wellness** (`/ai-wellness`) — OpenAI reflection when `OPENAI_API_KEY` is set (`bmat/ai_service.py`)
- **Phase 5:** **Connections** (`/connections`) — trusted contacts, email consent, check-in email notify (no SMS)
- **Phase 6:** Admin/therapist **Clinical** — roster + Needs attention, longitudinal view, branded PDF (`reportlab`), **ClinicalReview** notes/escalations + CSV export `clinical_review`; therapist role
- **Also shipped:** First-party analytics (`/admin/analytics`, CSV, `cleanup_analytics.py`); Warren slides on **`/about`**; maintainer scripts (`package_release`, `backup_app`, `bmat_menu`, `compress_slideshow_office`); see **Current state** sections above
- **Trends & history:** Chart.js charts for assessments, check-ins, and action completions

**Next:** Deeper insights / Phase 7 content expansion; Phase 8 mood-aware suggestions / optional RAG; Phase 9 push notifications (PWA install baseline shipped); SMS still pending Twilio.

## Private Session (screen share) enabled in production (2026-10-18)
- BMW now runs under **Gunicorn** (gthread worker, `-w 1 --threads 100`) instead of Waitress, so Flask-SocketIO (async_mode=threading + simple-websocket) works, including WebSocket upgrade.
- systemd: `bmat5-app.service` ExecStart -> `venv/bin/gunicorn -w 1 --threads 100 --timeout 120 -b 127.0.0.1:5669 bmat_serve_bmat5:app` (ScriptNameMiddleware /bmw prefix unchanged).
- `.env`: `BMAT_SCREENSHARE_ENABLED=1`. Socket.IO CORS still restricted to https://cije.live; socket connect requires a logged-in session.
- Apache: existing bmw-proxy.conf already proxies /bmw/socket.io (WebSocket rewrite to ws://127.0.0.1:5669); no change needed.
- **Keep one worker** (in-memory rooms). WebRTC across strict NATs needs a TURN server (STUN only today).
- Rollback: /home/bmat5/backups/screenshare_20261018_004250/ (restore .env + bmat5-app.service, daemon-reload, restart).
