from __future__ import annotations

import csv
import mimetypes
import os
import io
import json
import hashlib
import secrets
from urllib.parse import urlparse
from datetime import date, datetime, timedelta

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    Response,
    send_file,
    session,
    url_for,
)
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func
from wtforms import RadioField
from flask_wtf import FlaskForm

from .extensions import db
from .models import (
    User,
    CheckIn,
    Assessment,
    AuditLog,
    ActionCompletion,
    UserPreference,
    VisitSession,
    VisitEvent,
    TrustedContact,
    CheckInOnMeRequest,
    ClinicalReview,
    AiUsageDaily,
    AiJournalEntry,
    DeletionRequest,
    AIContentReport,
)
from .clinical_pdf import build_clinical_progress_pdf_bytes
from .clinical_escalation import maybe_create_escalations
from .slideshows import list_warren_slideshows, safe_slideshow_path
from .forms import (
    LoginForm,
    SignupForm,
    CheckInForm,
    PersonalizationForm,
    CulturalPrefsForm,
    AiWellnessForm,
    AiJournalConsentForm,
    AiJournalClearForm,
    TrustedContactForm,
    CheckInOnMeForm,
    NotifyContactsEmailForm,
    AdminCreateUserForm,
    DeletionRequestForm,
    DeleteAccountNowForm,
    AiContentReportForm,
)
from .mailer import mail_enabled, send_check_in_notifications, send_plain_email
from .surveys import PHQ9_ITEMS, GAD7_ITEMS, CHOICES, severity_phq9, severity_gad7
from .cultural import tone_streak_message
from .utils import (
    apply_completion_learning,
    build_care_plan,
    calculate_wellness_score,
    get_action_stats,
    get_recent_insights,
    mask_email,
    normalize_prefs_dict,
    safe_redirect_target,
)

bp = Blueprint("main", __name__)


@bp.get("/sw.js")
def service_worker():
    """Serve the installability service worker at app root so its scope is /bmw/."""
    path = os.path.join(current_app.static_folder or "", "sw.js")
    resp = send_file(
        path,
        mimetype="application/javascript",
        conditional=False,
        etag=False,
        max_age=0,
    )
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Service-Worker-Allowed"] = "/bmw/"
    return resp



# Top-bar logo, self-hosted (previously hot-linked from a Bing image URL).
LOGO_STATIC_PATH = "imgs/bmw-logo.png"
LOGO_VERSION = "1"
# Absolute URL for contexts without a request (emails, PDFs, external links).
LOGO_ABSOLUTE_URL = "https://cije.live/bmw/static/" + LOGO_STATIC_PATH + "?v=" + LOGO_VERSION


COLOR_SCHEMES = frozenset({"default", "beach"})
THEME_COLORS = {
    "default": "#1a1423",
    "beach": "#264653",
}
BMAT_THEME_COOKIE = "bmat_color_scheme"


def _normalize_scheme(value: str | None) -> str | None:
    if not value:
        return None
    key = value.strip().lower()
    return key if key in COLOR_SCHEMES else None


def _resolve_color_scheme() -> str:
    """Active scheme: ?theme= preview cookie override, else COLOR_SCHEME config."""
    preview = _normalize_scheme(request.args.get("theme"))
    if preview:
        return preview
    cookie = _normalize_scheme(request.cookies.get(BMAT_THEME_COOKIE))
    if cookie:
        return cookie
    cfg = _normalize_scheme(str(current_app.config.get("COLOR_SCHEME") or ""))
    return cfg or "beach"


# Landing hero: first match wins. bmat_ad_flask_h264.mp4 = H.264 transcode (scripts/transcode_bmat_ad_flask.py). Internal filenames kept.
LANDING_HERO_CANDIDATES = [
    "videos/bmat_ad_flask_h264.mp4",
    "videos/bmat_ad_flask.mp4",
    "videos/landing-hero.mp4",
    "videos/landing-hero.webm",
]
TRACK_COOKIE_NAME = "bmat_vid"


def _landing_hero_resolve() -> tuple[str, str] | tuple[None, None]:
    """Return (absolute_path, mimetype) or (None, None)."""
    root = current_app.static_folder
    if not root:
        return None, None
    root_real = os.path.realpath(root)
    for rel in LANDING_HERO_CANDIDATES:
        rel = rel.replace("\\", "/")
        full = os.path.realpath(os.path.join(root, *rel.split("/")))
        if not full.startswith(root_real + os.sep) and full != root_real:
            continue
        if os.path.isfile(full):
            if rel.endswith(".webm"):
                return full, "video/webm"
            return full, "video/mp4"
    return None, None


def _anon_hash(value: str) -> str:
    if not value:
        return ""
    secret = current_app.config.get("SECRET_KEY", "bmat-dev-secret")
    payload = f"{secret}|analytics|{value}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_visit_session() -> str | None:
    if request.endpoint == "static":
        return None
    if request.path.startswith("/static/"):
        return None
    session_id = (request.cookies.get(TRACK_COOKIE_NAME) or "").strip()
    if len(session_id) < 16 or len(session_id) > 64:
        session_id = secrets.token_urlsafe(24)
        g.analytics_set_cookie = session_id

    now = datetime.utcnow()
    row = VisitSession.query.filter_by(session_id=session_id).first()
    ip = ((request.headers.get("X-Forwarded-For") or "").split(",")[0].strip() or request.remote_addr or "")
    ua = request.headers.get("User-Agent") or ""
    ref = urlparse(request.referrer).hostname if request.referrer else None
    if row is None:
        row = VisitSession(
            session_id=session_id,
            user_id=(current_user.id if current_user.is_authenticated else None),
            is_authenticated=bool(current_user.is_authenticated),
            ip_hash=_anon_hash(ip),
            user_agent_hash=_anon_hash(ua),
            referrer_host=(ref or None),
            utm_source=(request.args.get("utm_source") or None),
            utm_medium=(request.args.get("utm_medium") or None),
            utm_campaign=(request.args.get("utm_campaign") or None),
            first_seen_at=now,
            last_seen_at=now,
        )
        db.session.add(row)
    else:
        row.last_seen_at = now
        row.is_authenticated = bool(current_user.is_authenticated)
        if current_user.is_authenticated and not row.user_id:
            row.user_id = current_user.id
        if not row.referrer_host and ref:
            row.referrer_host = ref
        if not row.utm_source and request.args.get("utm_source"):
            row.utm_source = request.args.get("utm_source")
        if not row.utm_medium and request.args.get("utm_medium"):
            row.utm_medium = request.args.get("utm_medium")
        if not row.utm_campaign and request.args.get("utm_campaign"):
            row.utm_campaign = request.args.get("utm_campaign")
    g.analytics_session_id = session_id
    return session_id


def log_visit_event(event_name: str, meta: dict | None = None, status_code: int | None = None) -> None:
    sid = getattr(g, "analytics_session_id", None)
    if not sid:
        sid = _ensure_visit_session()
    if not sid:
        return
    payload = meta if meta is None else json.dumps(meta)
    db.session.add(
        VisitEvent(
            session_id=sid,
            user_id=(current_user.id if current_user.is_authenticated else None),
            event_name=event_name,
            path=request.path,
            method=request.method,
            status_code=status_code,
            meta_json=payload,
        )
    )


@bp.before_app_request
def analytics_before_request():
    # Keep the service worker response free of session cookies.
    if request.path == "/sw.js":
        return
    try:
        _ensure_visit_session()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Analytics before-request failed.")


@bp.after_app_request
def analytics_after_request(response):
    if request.path == "/sw.js":
        return response
    if getattr(g, "skip_analytics", False):
        # Set after an account deletion so no new analytics rows point at the purged visit session.
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return response
    try:
        if request.endpoint != "static" and not request.path.startswith("/static/"):
            log_visit_event("page_view", status_code=response.status_code)
        if getattr(g, "analytics_set_cookie", None):
            response.set_cookie(
                TRACK_COOKIE_NAME,
                g.analytics_set_cookie,
                max_age=60 * 60 * 24 * 365,
                samesite="Lax",
                secure=request.is_secure,
                httponly=True,
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
    return response


def log_admin(action: str, target_user_id=None):
    if not current_user.is_authenticated:
        return
    if not (getattr(current_user, "is_admin", False) or getattr(current_user, "is_therapist", False)):
        return
    db.session.add(AuditLog(admin_user_id=current_user.id, action=action, target_user_id=target_user_id))
    db.session.commit()


@bp.context_processor
def inject_globals():
    scheme = getattr(g, "color_scheme", None) or _resolve_color_scheme()
    return {
        "APP_NAME": "Better Mental Wellness",
        "APP_SHORT": "BMW",
        "LOGO_URL": url_for("static", filename=LOGO_STATIC_PATH) + "?v=" + LOGO_VERSION,
        "SCRIPT_ROOT": (request.script_root or "").rstrip("/"),
        "BMAT_SCREENSHARE_ENABLED": bool(current_app.config.get("BMAT_SCREENSHARE_ENABLED")),
        "COLOR_SCHEME": scheme,
        "THEME_COLOR": THEME_COLORS.get(scheme, THEME_COLORS["beach"]),
    }


@bp.before_app_request
def _apply_theme_preview():
    """Allow ?theme=default|beach to preview; persist in a short-lived cookie."""
    preview = _normalize_scheme(request.args.get("theme"))
    scheme = _resolve_color_scheme()
    g.color_scheme = scheme
    if preview:
        # Stash so after_request can set the cookie on the real response
        g._bmat_theme_cookie = preview


@bp.after_app_request
def _set_theme_preview_cookie(response):
    preview = getattr(g, "_bmat_theme_cookie", None)
    if preview:
        response.set_cookie(
            BMAT_THEME_COOKIE,
            preview,
            max_age=60 * 60 * 24 * 30,
            samesite="Lax",
            path=current_app.config.get("SESSION_COOKIE_PATH") or "/",
        )
    return response


def _load_user_prefs(user_id: int) -> dict:
    row = UserPreference.query.get(user_id)
    if not row or not row.data_json:
        return {}
    try:
        return normalize_prefs_dict(json.loads(row.data_json))
    except json.JSONDecodeError:
        return {}


def _save_user_prefs(user_id: int, data: dict) -> None:
    row = UserPreference.query.get(user_id)
    if not row:
        row = UserPreference(user_id=user_id, data_json="{}")
        db.session.add(row)
    row.data_json = json.dumps(data)
    row.updated_at = datetime.utcnow()


def get_user_state():
    latest_phq = Assessment.query.filter_by(user_id=current_user.id, kind="PHQ9").order_by(Assessment.created_at.desc()).first()
    latest_gad = Assessment.query.filter_by(user_id=current_user.id, kind="GAD7").order_by(Assessment.created_at.desc()).first()
    latest_checkin = CheckIn.query.filter_by(user_id=current_user.id).order_by(CheckIn.created_at.desc()).first()
    assessments = Assessment.query.filter_by(user_id=current_user.id).order_by(Assessment.created_at.desc()).all()
    checkins = CheckIn.query.filter_by(user_id=current_user.id).order_by(CheckIn.created_at.desc()).all()
    completions = ActionCompletion.query.filter_by(user_id=current_user.id).order_by(ActionCompletion.completed_date.desc(), ActionCompletion.created_at.desc()).all()

    score, score_label = calculate_wellness_score(latest_phq, latest_gad, latest_checkin)
    insights = get_recent_insights(checkins, assessments)
    completed_today, streak_days, total_completed, last7_count = get_action_stats(completions)

    return {
        "latest_phq": latest_phq,
        "latest_gad": latest_gad,
        "latest_checkin": latest_checkin,
        "assessments": assessments,
        "checkins": checkins,
        "completions": completions,
        "wellness_score": score,
        "wellness_label": score_label,
        "insights": insights,
        "completed_today": completed_today,
        "streak_days": streak_days,
        "total_completed": total_completed,
        "last7_count": last7_count,
        "prefs": _load_user_prefs(current_user.id),
    }


def _admin_user_state(user_id: int):
    """Same signals as get_user_state for an arbitrary user (admin clinical tools)."""
    latest_phq = Assessment.query.filter_by(user_id=user_id, kind="PHQ9").order_by(Assessment.created_at.desc()).first()
    latest_gad = Assessment.query.filter_by(user_id=user_id, kind="GAD7").order_by(Assessment.created_at.desc()).first()
    latest_checkin = CheckIn.query.filter_by(user_id=user_id).order_by(CheckIn.created_at.desc()).first()
    assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).all()
    checkins = CheckIn.query.filter_by(user_id=user_id).order_by(CheckIn.created_at.desc()).all()
    completions = ActionCompletion.query.filter_by(user_id=user_id).order_by(
        ActionCompletion.completed_date.desc(), ActionCompletion.created_at.desc()
    ).all()
    score, score_label = calculate_wellness_score(latest_phq, latest_gad, latest_checkin)
    insights = get_recent_insights(checkins, assessments)
    completed_today, streak_days, total_completed, last7_count = get_action_stats(completions)
    return {
        "latest_phq": latest_phq,
        "latest_gad": latest_gad,
        "latest_checkin": latest_checkin,
        "assessments": assessments,
        "checkins": checkins,
        "completions": completions,
        "wellness_score": score,
        "wellness_label": score_label,
        "insights": insights,
        "completed_today": completed_today,
        "streak_days": streak_days,
        "total_completed": total_completed,
        "last7_count": last7_count,
        "prefs": _load_user_prefs(user_id),
    }


@bp.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    hero_path, _ = _landing_hero_resolve()
    return render_template("index.html", landing_hero_video=hero_path is not None)


@bp.get("/media/landing-hero")
def landing_hero_media():
    """Serve first available hero clip (MP4 or WebM). ETag disabled to avoid range/cache issues with <video>."""
    full, mime = _landing_hero_resolve()
    if not full:
        abort(404)
    resp = send_file(
        full,
        mimetype=mime,
        conditional=True,
        etag=False,
        max_age=86_400,
    )
    resp.headers["Accept-Ranges"] = "bytes"
    return resp


@bp.get("/media/landing-hero.mp4")
def landing_hero_media_legacy():
    """Old URL; hero may be WebM — redirect to canonical media route."""
    return redirect(url_for("main.landing_hero_media"), code=302)


@bp.get("/demo")
def bmat_demo():
    """Public calm product demo page (for screen capture / render_demo_video.py)."""
    return render_template("bmat_demo.html")


@bp.get("/bmwapp.zip")
def download_bmwapp_zip():
    """Public downloadable source zip (no secrets / no live DB). URL: /bmw/bmwapp.zip behind proxy."""
    candidates = [
        os.path.join(current_app.root_path, "static", "bmwapp.zip"),
        os.path.join(current_app.root_path, "static", "downloads", "bmwapp.zip"),
    ]
    for full in candidates:
        if os.path.isfile(full):
            return send_file(
                full,
                mimetype="application/zip",
                as_attachment=True,
                download_name="bmwapp.zip",
                max_age=3600,
            )
    abort(404)


def _slideshows_root() -> str:
    return os.path.join(current_app.root_path, "media", "slideshows")


@bp.get("/about")
def about():
    """Public about page: features, model attribution, designers (placeholder)."""
    root = _slideshows_root()
    slides = list_warren_slideshows(root)
    for s in slides:
        s["url"] = url_for("main.serve_slideshow", filename=s["filename"], _external=True)
    return render_template("about.html", warren_slideshows=slides)


@bp.get("/privacy")
def privacy():
    """Public privacy policy (no login). Used as the Google Play privacy policy URL: /bmw/privacy."""
    return render_template("privacy.html")


# ------------------ Account deletion (Google Play requirement) ------------------
DELETION_CONTACT_EMAIL = "admin@cije.live"
DELETION_MAX_REQUESTS_PER_IP_PER_DAY = 5
STAFF_ROLES = ("admin", "therapist")


def _client_ip() -> str:
    return (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip() or request.remote_addr or ""


def _self_delete_blocked_reason(user) -> str | None:
    """Return why this user may not delete themselves instantly (None = allowed)."""
    if user.role in STAFF_ROLES:
        return "staff"
    # Former staff with audit-log history: keep the audit trail intact; handle via request.
    if AuditLog.query.filter_by(admin_user_id=user.id).first() is not None:
        return "audit_history"
    if ClinicalReview.query.filter_by(admin_user_id=user.id).first() is not None:
        return "audit_history"
    return None


def purge_user_account(user_id: int) -> dict:
    """Delete a user and every row tied to them. Caller commits.

    Uses bulk deletes so ORM backrefs never try to NULL out NOT NULL foreign keys.
    """
    db.session.flush()
    user = db.session.get(User, user_id)
    if user is None:
        return {}
    email = (user.email or "").strip().lower()
    counts: dict[str, int] = {}

    def _del(name, q):
        counts[name] = q.delete(synchronize_session=False)

    _del("assessments", Assessment.query.filter(Assessment.user_id == user_id))
    _del("checkins", CheckIn.query.filter(CheckIn.user_id == user_id))
    _del("action_completions", ActionCompletion.query.filter(ActionCompletion.user_id == user_id))
    _del("preferences", UserPreference.query.filter(UserPreference.user_id == user_id))
    _del("trusted_contacts", TrustedContact.query.filter(TrustedContact.user_id == user_id))
    _del("check_in_on_me_requests", CheckInOnMeRequest.query.filter(CheckInOnMeRequest.user_id == user_id))
    _del("clinical_reviews", ClinicalReview.query.filter(ClinicalReview.user_id == user_id))
    _del("ai_usage_daily", AiUsageDaily.query.filter(AiUsageDaily.user_id == user_id))
    _del("ai_journal_entries", AiJournalEntry.query.filter(AiJournalEntry.user_id == user_id))
    _del("ai_content_reports", AIContentReport.query.filter(AIContentReport.user_id == user_id))

    # Analytics: every visit session linked to the account (and all events in them),
    # any other events carrying the user id, and failed log-ins that recorded this email.
    session_ids = [
        sid for (sid,) in db.session.query(VisitSession.session_id).filter(VisitSession.user_id == user_id).all()
    ]
    ev = 0
    if session_ids:
        ev += VisitEvent.query.filter(VisitEvent.session_id.in_(session_ids)).delete(synchronize_session=False)
    ev += VisitEvent.query.filter(VisitEvent.user_id == user_id).delete(synchronize_session=False)
    if email:
        ev += VisitEvent.query.filter(
            VisitEvent.event_name == "login_failed",
            VisitEvent.meta_json.contains(json.dumps({"email": email})),
        ).delete(synchronize_session=False)
    counts["visit_events"] = ev
    _del("visit_sessions", VisitSession.query.filter(VisitSession.user_id == user_id))

    # Staff audit entries about this user stay (security record) but lose the link to the account.
    counts["audit_unlinked"] = AuditLog.query.filter(AuditLog.target_user_id == user_id).update(
        {AuditLog.target_user_id: None}, synchronize_session=False
    )
    _del("user", User.query.filter(User.id == user_id))
    db.session.expire_all()
    return counts


def _notify_admin_of_deletion_request(req: DeletionRequest) -> str:
    """Email the admin inbox about a new request. Never raises; returns a status string."""
    if not mail_enabled():
        return "disabled"
    body = "\n".join(
        [
            "A Better Mental Wellness account deletion request was submitted.",
            "",
            f"Request #{req.id}",
            f"Email entered: {req.email}",
            f"Submitted (UTC): {req.created_at:%Y-%m-%d %H:%M}",
            f"Reason: {(req.reason or '').strip() or '(none given)'}",
            "",
            "Verify the requester controls this address, then process it within 30 days:",
            "https://cije.live/bmw/admin/overview",
        ]
    )
    try:
        send_plain_email(
            to_addr=DELETION_CONTACT_EMAIL,
            subject=f"BMW account deletion request #{req.id}",
            body=body,
        )
        return "sent"
    except Exception:  # noqa: BLE001 — never fail the request because of mail
        current_app.logger.exception("deletion request email failed (request %s)", req.id)
        return "failed"


@bp.route("/delete-account", methods=["GET", "POST"])
def delete_account():
    """Public account-deletion page + request form (Play URL: /bmw/delete-account).

    Signed-in regular users also get an instant in-app deletion option.
    """
    req_form = DeletionRequestForm(prefix="req")
    now_form = DeleteAccountNowForm(prefix="now")
    authed = current_user.is_authenticated
    if authed and request.method == "GET":
        req_form.email.data = current_user.email
    block_reason = _self_delete_blocked_reason(current_user) if authed else None

    if request.method == "POST" and "req-submit" in request.form:
        if authed:
            req_form.email.data = current_user.email  # locked to the account email
        if req_form.validate_on_submit():
            email = (req_form.email.data or "").strip().lower()
            honeypot = (req_form.website.data or "").strip()
            ip_hash = _anon_hash(_client_ip())
            since = datetime.utcnow() - timedelta(hours=24)
            store = not honeypot
            if store and ip_hash:
                recent_ip = DeletionRequest.query.filter(
                    DeletionRequest.ip_hash == ip_hash,
                    DeletionRequest.source == "web_form",
                    DeletionRequest.created_at >= since,
                ).count()
                if recent_ip >= DELETION_MAX_REQUESTS_PER_IP_PER_DAY:
                    store = False
            if store:
                dup = DeletionRequest.query.filter(
                    DeletionRequest.email == email,
                    DeletionRequest.status == "pending",
                    DeletionRequest.created_at >= since,
                ).first()
                if dup is not None:
                    store = False
            if store:
                req = DeletionRequest(
                    email=email,
                    reason=(req_form.reason.data or "").strip() or None,
                    source="web_form",
                    status="pending",
                    ip_hash=ip_hash or None,
                )
                db.session.add(req)
                db.session.commit()
                req.notify_email_status = _notify_admin_of_deletion_request(req)
                db.session.commit()
            log_visit_event("deletion_request_submitted")
            # Same response whether or not the email has an account (or was throttled).
            flash(
                "Thanks — we received your request. If that email matches a BMW account, we will delete it "
                f"and its data within 30 days. We may email you from {DELETION_CONTACT_EMAIL} to confirm it is you.",
                "success",
            )
            return redirect(url_for("main.delete_account", submitted=1))

    elif request.method == "POST" and "now-submit" in request.form:
        if not authed:
            flash("Please log in to delete your account from the app, or use the request form below.", "warning")
            return redirect(url_for("main.delete_account"))
        if block_reason:
            flash(
                "Staff accounts can't be deleted instantly. Use the request form and we'll handle it.",
                "warning",
            )
            return redirect(url_for("main.delete_account"))
        if now_form.validate_on_submit():
            if not current_user.check_password(now_form.password.data or ""):
                flash("That password isn't right. Your account was not deleted.", "danger")
            else:
                uid = current_user.id
                masked = mask_email(current_user.email or "")
                try:
                    logout_user()
                    session.pop("admin_ack", None)
                    purge_user_account(uid)
                    db.session.add(
                        DeletionRequest(
                            email=masked,
                            source="in_app",
                            status="completed",
                            processed_at=datetime.utcnow(),
                            admin_note="Deleted by the user in the app",
                        )
                    )
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    current_app.logger.exception("in-app account deletion failed for user %s", uid)
                    flash(
                        f"Something went wrong and your account was not deleted. Please try again or email {DELETION_CONTACT_EMAIL}.",
                        "danger",
                    )
                    return redirect(url_for("main.delete_account"))
                g.skip_analytics = True
                flash(
                    "Your BMW account and all of its data have been permanently deleted. Take care of yourself.",
                    "success",
                )
                resp = redirect(url_for("main.delete_account", deleted=1))
                resp.delete_cookie(TRACK_COOKIE_NAME)
                return resp

    return render_template(
        "delete_account.html",
        req_form=req_form,
        now_form=now_form,
        block_reason=block_reason,
        contact_email=DELETION_CONTACT_EMAIL,
        just_submitted=request.args.get("submitted") == "1",
        just_deleted=request.args.get("deleted") == "1",
    )


@bp.post("/admin/deletion-requests/<int:req_id>/process")
@login_required
def admin_deletion_request_process(req_id: int):
    """Admin: delete the matching account for a request, or close it without deleting."""
    if not require_admin():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return redirect(url_for("main.admin"))
    if not FlaskForm().validate_on_submit():
        flash("Security check failed. Please reload and try again.", "danger")
        return redirect(url_for("main.admin_overview"))
    req = db.session.get(DeletionRequest, req_id)
    if req is None or req.status != "pending":
        flash("That request was already handled.", "info")
        return redirect(url_for("main.admin_overview"))
    action = (request.form.get("action") or "").strip()
    email = (req.email or "").strip().lower()
    if action == "delete":
        user = User.query.filter_by(email=email).first() if email else None
        if user is None:
            req.admin_note = "No account with this email; nothing to delete"
        elif user.id == current_user.id or _self_delete_blocked_reason(user):
            flash(
                "That account is (or was) a staff account with audit history, so it can't be auto-deleted here. "
                "Handle it manually so the audit trail stays intact.",
                "warning",
            )
            return redirect(url_for("main.admin_overview"))
        else:
            uid = user.id
            purge_user_account(uid)
            req = db.session.get(DeletionRequest, req_id)
            req.admin_note = "Account and data deleted"
            db.session.add(AuditLog(admin_user_id=current_user.id, action="account_deleted_on_request", target_user_id=None))
    elif action == "close":
        req.admin_note = "Closed without deleting"
    else:
        flash("Unknown action.", "warning")
        return redirect(url_for("main.admin_overview"))
    req.status = "completed" if action == "delete" else "closed"
    req.processed_at = datetime.utcnow()
    req.email = mask_email(email) if email else req.email
    db.session.commit()
    flash(f"Deletion request #{req_id}: {req.admin_note}.", "success")
    return redirect(url_for("main.admin_overview"))


@bp.get("/manifest.webmanifest")
def web_manifest_alias():
    """Alias for the static PWA manifest at the app root (/bmw/manifest.webmanifest)."""
    path = os.path.join(current_app.static_folder or "", "manifest.webmanifest")
    resp = send_file(path, mimetype="application/manifest+json", max_age=3600)
    return resp


@bp.get("/media/slideshows/<path:filename>")
def serve_slideshow(filename: str):
    """Serve weekly slide files from bmat/media/slideshows/ (PDF, HTML, PPT/PPTX/PPS/PPSX)."""
    root = _slideshows_root()
    full = safe_slideshow_path(root, filename)
    if not full:
        abort(404)
    mt, _enc = mimetypes.guess_type(full)
    if not mt:
        ext = os.path.splitext(full)[1].lower()
        if ext == ".pptx":
            mt = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif ext == ".ppsx":
            mt = "application/vnd.openxmlformats-officedocument.presentationml.slideshow"
        elif ext == ".ppt":
            mt = "application/vnd.ms-powerpoint"
        elif ext == ".pps":
            mt = "application/vnd.ms-powerpoint"
        elif ext == ".pdf":
            mt = "application/pdf"
        elif ext in {".html", ".htm"}:
            mt = "text/html"
        else:
            mt = "application/octet-stream"
    return send_file(full, mimetype=mt, conditional=True, max_age=3600)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if not user or not user.check_password(form.password.data):
            log_visit_event("login_failed", {"email": form.email.data.strip().lower()})
            flash("Invalid email or password.", "danger")
        else:
            login_user(user)
            log_visit_event("login_success")
            flash(f"Welcome back, {user.display_name}!", "success")
            return redirect(url_for("main.dashboard"))
    elif request.method == "GET":
        log_visit_event("login_view")
    return render_template("auth_login.html", form=form)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = SignupForm()
    if form.validate_on_submit():
        log_visit_event("signup_started")
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash("That email is already registered.", "warning")
        else:
            user = User(
                email=email,
                display_name=form.display_name.data.strip(),
                role="user",
                age_confirmed_at=datetime.utcnow(),
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            log_visit_event("signup_completed", {"user_id": user.id})
            flash("Account created — you’re in.", "success")
            return redirect(url_for("main.dashboard"))
    elif request.method == "GET":
        log_visit_event("signup_view")
    return render_template("auth_signup.html", form=form)


@bp.get("/logout")
@login_required
def logout():
    log_visit_event("logout")
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("main.index"))


@bp.get("/dashboard")
@login_required
def dashboard():
    state = get_user_state()
    plan = build_care_plan(
        state["latest_phq"],
        state["latest_gad"],
        state["latest_checkin"],
        checkins=state["checkins"],
        assessments=state["assessments"],
        completions=state["completions"],
        prefs=state["prefs"],
        user_id=current_user.id,
    )
    recent_checkins = list(reversed(state["checkins"][:7]))
    checkin_chart = {
        "labels": [c.created_at.strftime("%m/%d") for c in recent_checkins],
        "mood": [c.mood for c in recent_checkins],
        "stress": [c.stress for c in recent_checkins],
        "sleep": [round(c.sleep_hours, 1) for c in recent_checkins],
    }
    recent_assessments = list(reversed(state["assessments"][:8]))
    assessment_chart = {
        "labels": [a.created_at.strftime("%m/%d") for a in recent_assessments],
        "phq": [a.total_score if a.kind == "PHQ9" else None for a in recent_assessments],
        "gad": [a.total_score if a.kind == "GAD7" else None for a in recent_assessments],
    }

    focus_points = plan.get("focus") or []
    today_focus_title = focus_points[0] if focus_points else "Maintain your momentum"
    today_focus_subtitle = (plan.get("cultural") or {}).get("today_focus_subtitle") or (
        "Start with one small action below and re-check tonight."
        if focus_points
        else "Protect your baseline with one low-effort reset."
    )

    completed_today = state["completed_today"]
    quick_action = next((a for a in plan.get("actions", []) if a.get("key") not in completed_today), None)

    latest_checkin = state["latest_checkin"]
    latest_phq = state["latest_phq"]
    latest_gad = state["latest_gad"]
    if not latest_checkin or latest_checkin.created_at.date() < date.today():
        continue_path = url_for("main.checkin")
        continue_label = "Complete today's check-in"
    elif not latest_phq or latest_phq.created_at.date() < (date.today() - timedelta(days=14)):
        continue_path = url_for("main.screenings")
        continue_label = "Update PHQ-9 screening"
    elif not latest_gad or latest_gad.created_at.date() < (date.today() - timedelta(days=14)):
        continue_path = url_for("main.screenings")
        continue_label = "Update GAD-7 screening"
    else:
        continue_path = url_for("main.careplan")
        continue_label = "Review your care plan"

    streak_days = state["streak_days"]
    if streak_days < 3:
        streak_goal = 3
    elif streak_days < 7:
        streak_goal = 7
    elif streak_days < 14:
        streak_goal = 14
    elif streak_days < 30:
        streak_goal = 30
    else:
        streak_goal = streak_days
    streak_progress_pct = 100 if streak_goal == 0 else min(100, int((streak_days / streak_goal) * 100))
    streak_remaining = max(0, streak_goal - streak_days)
    if streak_remaining > 0:
        streak_message = f"{streak_remaining} day{'s' if streak_remaining != 1 else ''} to your next streak milestone."
    else:
        streak_message = "You're at a milestone - keep the momentum going."
    streak_message = tone_streak_message(streak_message, (plan.get("cultural") or {}).get("tone", "warm_standard"))

    return render_template(
        "dashboard.html",
        latest_phq=state["latest_phq"],
        latest_gad=state["latest_gad"],
        latest_checkin=state["latest_checkin"],
        wellness_score=state["wellness_score"],
        wellness_label=state["wellness_label"],
        streak_days=state["streak_days"],
        completed_today_count=len(state["completed_today"]),
        total_completed=state["total_completed"],
        insights=state["insights"],
        plan=plan,
        checkin_chart=checkin_chart,
        assessment_chart=assessment_chart,
        today_focus_title=today_focus_title,
        today_focus_subtitle=today_focus_subtitle,
        quick_action=quick_action,
        continue_path=continue_path,
        continue_label=continue_label,
        streak_goal=streak_goal,
        streak_progress_pct=streak_progress_pct,
        streak_message=streak_message,
        cultural_affirmation=(plan.get("cultural") or {}).get("affirmation"),
        cultural_tone_label=(plan.get("cultural") or {}).get("tone_label"),
        ai_prompt_form=AiWellnessForm(),
    )


@bp.route("/checkin", methods=["GET", "POST"])
@login_required
def checkin():
    form = CheckInForm(mood=6, stress=5, sleep_hours=7.0)
    if form.validate_on_submit():
        c = CheckIn(
            user_id=current_user.id,
            mood=form.mood.data,
            stress=form.stress.data,
            sleep_hours=form.sleep_hours.data,
            note=form.note.data.strip() if form.note.data else None,
        )
        db.session.add(c)
        log_visit_event("checkin_submitted")
        db.session.commit()
        flash("Saved. Proud of you for checking in with yourself.", "success")
        return redirect(url_for("main.history"))
    return render_template("checkin.html", form=form)


def build_survey_form(items):
    fields = {}
    for idx, question in enumerate(items, start=1):
        fields[f"q{idx}"] = RadioField(question, choices=CHOICES, default="0")
    class_dict = {k: v for k, v in fields.items() if k.startswith("q")}
    from wtforms import SubmitField
    class_dict["submit"] = SubmitField("Save results")
    DynamicForm = type("DynamicSurveyForm", (FlaskForm,), class_dict)
    return DynamicForm()


@bp.get("/screenings")
@login_required
def screenings():
    log_visit_event("screenings_hub_view")
    state = get_user_state()
    return render_template(
        "screenings.html",
        latest_phq=state["latest_phq"],
        latest_gad=state["latest_gad"],
    )


@bp.route("/phq9", methods=["GET", "POST"])
@login_required
def phq9():
    form = build_survey_form(PHQ9_ITEMS)
    if form.validate_on_submit():
        responses = [int(getattr(form, f"q{i}").data) for i in range(1, len(PHQ9_ITEMS) + 1)]
        total = sum(responses)
        sev = severity_phq9(total)
        item9 = responses[8]
        a = Assessment(
            user_id=current_user.id,
            kind="PHQ9",
            total_score=total,
            severity=sev,
            item9_score=item9,
            responses_json=json.dumps(responses),
        )
        db.session.add(a)
        maybe_create_escalations(
            user_id=current_user.id,
            kind="PHQ9",
            total_score=total,
            item9_score=item9,
        )
        log_visit_event("phq9_submitted", {"score": total, "severity": sev, "item9": item9})
        db.session.commit()
        flash("PHQ-9 saved to your history.", "success")
        if item9 > 0:
            return render_template(
                "phq9_crisis.html",
                total=total,
                severity=sev,
                item9_score=item9,
            )
        return redirect(url_for("main.history"))
    preview_total = sum(int(getattr(form, f"q{i}").data or 0) for i in range(1, len(PHQ9_ITEMS) + 1))
    preview_sev = severity_phq9(preview_total)
    item9 = int(getattr(form, "q9").data or 0)
    return render_template("survey.html", title="PHQ-9", form=form, total=preview_total, severity=preview_sev, show_safety=(item9 > 0))


@bp.route("/gad7", methods=["GET", "POST"])
@login_required
def gad7():
    form = build_survey_form(GAD7_ITEMS)
    if form.validate_on_submit():
        responses = [int(getattr(form, f"q{i}").data) for i in range(1, len(GAD7_ITEMS) + 1)]
        total = sum(responses)
        sev = severity_gad7(total)
        a = Assessment(
            user_id=current_user.id,
            kind="GAD7",
            total_score=total,
            severity=sev,
            item9_score=None,
            responses_json=json.dumps(responses),
        )
        db.session.add(a)
        maybe_create_escalations(
            user_id=current_user.id,
            kind="GAD7",
            total_score=total,
            item9_score=None,
        )
        log_visit_event("gad7_submitted", {"score": total, "severity": sev})
        db.session.commit()
        flash("GAD-7 saved to your history.", "success")
        return redirect(url_for("main.history"))
    preview_total = sum(int(getattr(form, f"q{i}").data or 0) for i in range(1, len(GAD7_ITEMS) + 1))
    preview_sev = severity_gad7(preview_total)
    return render_template("survey.html", title="GAD-7", form=form, total=preview_total, severity=preview_sev, show_safety=False)


@bp.route("/actions/complete", methods=["POST"])
@login_required
def complete_action():
    action_key = (request.form.get("action_key") or "").strip()
    action_title = (request.form.get("action_title") or "").strip()
    next_url = safe_redirect_target(request.form.get("next"), url_for("main.careplan"))

    if not action_key or not action_title:
        flash("Could not complete that action.", "warning")
        return redirect(next_url)

    existing = ActionCompletion.query.filter_by(
        user_id=current_user.id,
        action_key=action_key,
        completed_date=date.today(),
    ).first()

    if not existing:
        db.session.add(ActionCompletion(
            user_id=current_user.id,
            action_key=action_key,
            action_title=action_title,
            completed_date=date.today(),
        ))
        pdata = dict(_load_user_prefs(current_user.id))
        apply_completion_learning(pdata, action_key)
        _save_user_prefs(current_user.id, pdata)
        log_visit_event("careplan_action_completed", {"action_key": action_key})
        db.session.commit()
        flash(f"Marked complete: {action_title}", "success")
    else:
        flash(f"Already completed today: {action_title}", "info")

    return redirect(next_url)


@bp.route("/actions/uncomplete", methods=["POST"])
@login_required
def uncomplete_action():
    action_key = (request.form.get("action_key") or "").strip()
    next_url = safe_redirect_target(request.form.get("next"), url_for("main.careplan"))

    completion = ActionCompletion.query.filter_by(
        user_id=current_user.id,
        action_key=action_key,
        completed_date=date.today(),
    ).first()

    if completion:
        db.session.delete(completion)
        db.session.commit()
        flash("Action completion removed for today.", "info")

    return redirect(next_url)


@bp.get("/careplan")
@login_required
def careplan():
    state = get_user_state()
    plan = build_care_plan(
        state["latest_phq"],
        state["latest_gad"],
        state["latest_checkin"],
        checkins=state["checkins"],
        assessments=state["assessments"],
        completions=state["completions"],
        prefs=state["prefs"],
        user_id=current_user.id,
    )
    show_safety = bool(state["latest_phq"] and state["latest_phq"].item9_score and state["latest_phq"].item9_score > 0)
    return render_template(
        "careplan.html",
        plan=plan,
        show_safety=show_safety,
        completed_today=state["completed_today"],
        streak_days=state["streak_days"],
        wellness_score=state["wellness_score"],
        wellness_label=state["wellness_label"],
        insights=state["insights"],
    )


@bp.get("/personal-profile")
@login_required
def personal_profile():
    log_visit_event("personal_profile_hub_view")
    n_contacts = TrustedContact.query.filter_by(user_id=current_user.id).count()
    return render_template("personal_profile.html", n_contacts=n_contacts)


@bp.route("/personalization", methods=["GET", "POST"])
@login_required
def personalization():
    form = PersonalizationForm()
    pdata = dict(_load_user_prefs(current_user.id))
    if request.method == "GET":
        form.emphasize_tags.data = pdata.get("emphasize_tags", [])
        form.steer_clear_tags.data = pdata.get("steer_clear_tags", [])
    if form.validate_on_submit():
        em = list(form.emphasize_tags.data or [])
        st = [t for t in (form.steer_clear_tags.data or []) if t not in em]
        pdata["emphasize_tags"] = em
        pdata["steer_clear_tags"] = st
        _save_user_prefs(current_user.id, pdata)
        flash("Personalization saved. Your care plan will weight topics from here.", "success")
        return redirect(url_for("main.personalization"))
    return render_template("personalization.html", form=form)


@bp.route("/culture", methods=["GET", "POST"])
@login_required
def culture():
    form = CulturalPrefsForm()
    pdata = dict(_load_user_prefs(current_user.id))
    if request.method == "GET":
        form.tone_preset.data = pdata.get("tone_preset", "warm_standard")
        form.highlight_representation.data = pdata.get("highlight_representation", True)
    if form.validate_on_submit():
        pdata["tone_preset"] = form.tone_preset.data
        pdata["highlight_representation"] = bool(form.highlight_representation.data)
        _save_user_prefs(current_user.id, pdata)
        log_visit_event("culture_prefs_saved", {"tone": pdata["tone_preset"]})
        flash("Cultural preferences saved. Home and your care plan will use this tone.", "success")
        return redirect(url_for("main.culture"))
    if request.method == "GET":
        log_visit_event("culture_view")
    state = get_user_state()
    plan = build_care_plan(
        state["latest_phq"],
        state["latest_gad"],
        state["latest_checkin"],
        checkins=state["checkins"],
        assessments=state["assessments"],
        completions=state["completions"],
        prefs=state["prefs"],
        user_id=current_user.id,
    )
    return render_template(
        "culture.html",
        form=form,
        plan=plan,
        affirmation=plan.get("cultural", {}).get("affirmation", ""),
        representation=plan.get("representation_spotlight") or [],
    )


@bp.get("/wellness-assistant")
@login_required
def wellness_assistant_redirect():
    """Legacy path — canonical URL is /ai-wellness."""
    return redirect(url_for("main.ai_wellness"), code=301)


@bp.route("/ai-wellness", methods=["GET", "POST"])
@login_required
def ai_wellness():
    from .ai_service import ai_enabled, generate_score_insight, generate_wellness_reflection

    form = AiWellnessForm()
    consent_form = AiJournalConsentForm()
    clear_form = AiJournalClearForm()
    consent_form.ai_journal_consent.data = bool(
        getattr(current_user, "ai_journal_consent", False)
    )
    reply = None
    score_reply = None
    analysis_requested = False
    state = get_user_state()
    latest_checkin = state["latest_checkin"]
    latest_phq = state["latest_phq"]
    latest_gad = state["latest_gad"]
    if request.method == "GET":
        log_visit_event("ai_wellness_view")

    action = (request.form.get("action") or "").strip()
    if request.method == "POST" and action == "analyze_scores":
        # Global CSRFProtect already validates; bind posted token into the form too.
        form.process(formdata=request.form)
        if form.csrf_token.errors:
            flash("Security check failed. Please reload and try again.", "danger")
            return redirect(url_for("main.ai_wellness"))
        analysis_requested = True
        if not ai_enabled():
            flash(
                "AI Wellness is not configured. Add OPENAI_API_KEY to the server environment (.env) and restart.",
                "warning",
            )
        elif not _ai_quota_ok(current_user.id):
            used, limit, _rem = _ai_usage_counts(current_user.id)
            flash(
                f"You've used your {limit} AI reflections for today (UTC). "
                "Come back tomorrow — your check-ins and screenings are still here anytime.",
                "info",
            )
        else:
            prefs = _load_user_prefs(current_user.id)
            tone = prefs.get("tone_preset", "warm_standard")
            if not (latest_checkin or latest_phq or latest_gad):
                flash("Complete a check-in or PHQ-9/GAD-7 first so AI Wellness has data to analyze.", "info")
            else:
                score_reply, err = generate_score_insight(
                    display_name=current_user.display_name,
                    tone_preset=tone,
                    mood=(latest_checkin.mood if latest_checkin else None),
                    stress=(latest_checkin.stress if latest_checkin else None),
                    sleep_hours=(latest_checkin.sleep_hours if latest_checkin else None),
                    phq_score=(latest_phq.total_score if latest_phq else None),
                    phq_severity=(latest_phq.severity if latest_phq else None),
                    phq_item9=(latest_phq.item9_score if latest_phq else None),
                    gad_score=(latest_gad.total_score if latest_gad else None),
                    gad_severity=(latest_gad.severity if latest_gad else None),
                )
                if err:
                    flash(err, "danger")
                    score_reply = None
                else:
                    _increment_ai_usage(current_user.id)
                    user_prompt = (
                        "Please explain my latest check-in, PHQ-9, and GAD-7 scores "
                        "and suggest gentle next steps."
                    )
                    _maybe_store_ai_journal(
                        user_prompt=user_prompt,
                        assistant_reply=score_reply or "",
                        kind="score_insight",
                    )
                    db.session.commit()
                    log_visit_event("ai_wellness_scores_reply", {})
    elif form.validate_on_submit():
        if not ai_enabled():
            flash(
                "AI Wellness is not configured. Add OPENAI_API_KEY to the server environment (.env) and restart.",
                "warning",
            )
        elif not _ai_quota_ok(current_user.id):
            _used, limit, _rem = _ai_usage_counts(current_user.id)
            flash(
                f"You've used your {limit} AI reflections for today (UTC). "
                "Come back tomorrow — your check-ins and screenings are still here anytime.",
                "info",
            )
        else:
            prefs = _load_user_prefs(current_user.id)
            tone = prefs.get("tone_preset", "warm_standard")
            user_text = form.message.data.strip()
            reply, err = generate_wellness_reflection(
                user_text,
                tone_preset=tone,
                display_name=current_user.display_name,
            )
            if err:
                flash(err, "danger")
                reply = None
            else:
                _increment_ai_usage(current_user.id)
                _maybe_store_ai_journal(
                    user_prompt=user_text,
                    assistant_reply=reply or "",
                    kind="free_text",
                )
                db.session.commit()
                log_visit_event("ai_wellness_reply", {"chars": len(user_text)})

    used, limit, remaining = _ai_usage_counts(current_user.id)
    journal_consent = bool(getattr(current_user, "ai_journal_consent", False))
    journal_entries = []
    journal_entry_count = (
        AiJournalEntry.query.filter_by(user_id=current_user.id).count()
    )
    if journal_consent:
        journal_entries = (
            AiJournalEntry.query.filter_by(user_id=current_user.id)
            .order_by(AiJournalEntry.created_at.desc(), AiJournalEntry.id.desc())
            .limit(20)
            .all()
        )

    return render_template(
        "ai_wellness.html",
        form=form,
        consent_form=consent_form,
        clear_form=clear_form,
        reply=reply,
        score_reply=score_reply,
        analysis_requested=analysis_requested,
        latest_checkin=latest_checkin,
        latest_phq=latest_phq,
        latest_gad=latest_gad,
        ai_enabled=ai_enabled(),
        ai_used=used,
        ai_daily_limit=limit,
        ai_remaining=remaining,
        ai_journal_consent=journal_consent,
        journal_entries=journal_entries,
        journal_entry_count=journal_entry_count,
        report_form=AiContentReportForm(formdata=None),
        report_reasons=AI_REPORT_REASON_LABELS,
        reply_prompt=(form.message.data or "").strip() if reply else "",
    )


# ------------------ AI content reports (Google Play AI-generated content policy) ------------------
AI_REPORT_REASON_LABELS = {
    "offensive": "Offensive or hateful",
    "harmful": "Harmful or unsafe advice",
    "inaccurate": "Inaccurate or misleading",
    "other": "Something else",
}
AI_REPORT_SOURCES = ("free_text", "score_insight", "journal")
AI_REPORT_MAX_PER_HOUR = 10
AI_REPORT_MAX_PER_DAY = 30
AI_REPORT_TEXT_MAX = 4000
AI_REPORT_PROMPT_MAX = 2000


def _ai_report_response(ok: bool, message: str, status: int = 200):
    """JSON for the in-page (fetch) submit; flash + redirect for the no-JS fallback."""
    wants_json = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
    if wants_json:
        return {"ok": ok, "message": message}, status
    flash(message, "success" if ok else "warning")
    return redirect(url_for("main.ai_wellness"))


@bp.post("/ai-wellness/report")
@login_required
def ai_wellness_report():
    """Let a user flag an AI reply as offensive, harmful, inaccurate, or other."""
    form = AiContentReportForm()
    if not form.validate_on_submit():
        if form.csrf_token.errors:
            return _ai_report_response(False, "Security check failed. Please reload the page and try again.", 400)
        return _ai_report_response(False, "Please choose a reason for the report.", 400)

    source = (form.source.data or "").strip()
    if source not in AI_REPORT_SOURCES or form.reason.data not in AI_REPORT_REASON_LABELS:
        return _ai_report_response(False, "That report could not be sent. Please try again.", 400)

    ai_text = ""
    prompt = ""
    if source == "journal":
        entry = (
            db.session.get(AiJournalEntry, form.journal_entry_id.data)
            if form.journal_entry_id.data
            else None
        )
        if entry is None or entry.user_id != current_user.id or entry.role != "assistant":
            return _ai_report_response(False, "That reply could not be found.", 404)
        ai_text = entry.content or ""
        if form.include_prompt.data:
            prev = (
                AiJournalEntry.query.filter(
                    AiJournalEntry.user_id == current_user.id,
                    AiJournalEntry.role == "user",
                    AiJournalEntry.created_at == entry.created_at,
                )
                .order_by(AiJournalEntry.id.desc())
                .first()
            )
            prompt = prev.content if prev else ""
    else:
        ai_text = (form.ai_text.data or "").strip()
        if form.include_prompt.data and source == "free_text":
            prompt = (form.prompt_text.data or "").strip()
    ai_text = ai_text.strip()
    if not ai_text:
        return _ai_report_response(False, "There was no AI reply to report.", 400)

    now = datetime.utcnow()
    recent_hour = AIContentReport.query.filter(
        AIContentReport.user_id == current_user.id, AIContentReport.created_at >= now - timedelta(hours=1)
    ).count()
    recent_day = AIContentReport.query.filter(
        AIContentReport.user_id == current_user.id, AIContentReport.created_at >= now - timedelta(hours=24)
    ).count()
    if recent_hour >= AI_REPORT_MAX_PER_HOUR or recent_day >= AI_REPORT_MAX_PER_DAY:
        return _ai_report_response(
            False,
            f"You've sent a lot of reports recently. Please try again later, or email {DELETION_CONTACT_EMAIL}.",
            429,
        )

    db.session.add(
        AIContentReport(
            user_id=current_user.id,
            source=source,
            reason=form.reason.data,
            note=(form.note.data or "").strip()[:1000] or None,
            ai_text=ai_text[:AI_REPORT_TEXT_MAX],
            user_prompt=(prompt[:AI_REPORT_PROMPT_MAX] or None) if prompt else None,
            status="pending",
            created_at=now,
        )
    )
    db.session.commit()
    log_visit_event("ai_content_reported", {"reason": form.reason.data, "source": source})
    return _ai_report_response(True, "Thanks for reporting this reply. Our team will review it.")


@bp.post("/admin/ai-reports/<int:report_id>/close")
@login_required
def admin_ai_report_close(report_id: int):
    """Admin: mark an AI content report as reviewed/closed."""
    if not require_admin():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return redirect(url_for("main.admin"))
    if not FlaskForm().validate_on_submit():
        flash("Security check failed. Please reload and try again.", "danger")
        return redirect(url_for("main.admin_overview"))
    rep = db.session.get(AIContentReport, report_id)
    if rep is None or rep.status != "pending":
        flash("That report was already handled.", "info")
        return redirect(url_for("main.admin_overview") + "#ai-reports")
    rep.status = "closed"
    rep.closed_at = datetime.utcnow()
    rep.admin_note = ((request.form.get("admin_note") or "").strip()[:255]) or "Reviewed"
    db.session.add(AuditLog(admin_user_id=current_user.id, action="ai_report_closed", target_user_id=None))
    db.session.commit()
    flash(f"AI report #{report_id} closed.", "success")
    return redirect(url_for("main.admin_overview") + "#ai-reports")


@bp.post("/ai-wellness/journal-consent")
@login_required
def ai_wellness_journal_consent():
    form = AiJournalConsentForm()
    if form.validate_on_submit():
        want = bool(form.ai_journal_consent.data)
        current_user.ai_journal_consent = want
        current_user.ai_journal_consent_at = datetime.utcnow() if want else None
        db.session.commit()
        log_visit_event("ai_journal_consent_set", {"enabled": want})
        if want:
            flash(
                "Journaling is on. Successful AI Wellness exchanges will be saved privately to your account.",
                "success",
            )
        else:
            flash(
                "Journaling is off. New messages will not be stored. Existing entries remain until you clear them.",
                "info",
            )
    else:
        flash("Could not update journal preference.", "warning")
    return redirect(url_for("main.ai_wellness"))


@bp.post("/ai-wellness/journal-clear")
@login_required
def ai_wellness_journal_clear():
    form = AiJournalClearForm()
    if form.validate_on_submit():
        deleted = (
            AiJournalEntry.query.filter_by(user_id=current_user.id).delete(
                synchronize_session=False
            )
        )
        db.session.commit()
        log_visit_event("ai_journal_cleared", {"deleted": int(deleted or 0)})
        flash("Your AI journal history has been cleared.", "success")
    else:
        flash("Could not clear journal history.", "warning")
    return redirect(url_for("main.ai_wellness"))



def _ai_daily_limit() -> int:
    try:
        return max(0, int(current_app.config.get("AI_DAILY_LIMIT") or 20))
    except (TypeError, ValueError):
        return 20


def _utc_date_key(now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    return f"{now.year:04d}-{now.month:02d}-{now.day:02d}"


def _ai_usage_counts(user_id: int) -> tuple[int, int, int]:
    """Return (used_today, daily_limit, remaining) for successful AI generations."""
    limit = _ai_daily_limit()
    day = _utc_date_key()
    row = AiUsageDaily.query.filter_by(user_id=user_id, utc_date=day).first()
    used = int(row.count) if row else 0
    remaining = max(0, limit - used)
    return used, limit, remaining


def _ai_quota_ok(user_id: int) -> bool:
    _used, _limit, remaining = _ai_usage_counts(user_id)
    return remaining > 0


def _increment_ai_usage(user_id: int) -> None:
    day = _utc_date_key()
    row = AiUsageDaily.query.filter_by(user_id=user_id, utc_date=day).first()
    if not row:
        row = AiUsageDaily(user_id=user_id, utc_date=day, count=0)
        db.session.add(row)
    row.count = int(row.count or 0) + 1
    row.updated_at = datetime.utcnow()


def _maybe_store_ai_journal(
    *,
    user_prompt: str,
    assistant_reply: str,
    kind: str,
) -> None:
    """Persist user+assistant rows only when the user has opted in."""
    if not bool(getattr(current_user, "ai_journal_consent", False)):
        return
    prompt = (user_prompt or "").strip()
    reply = (assistant_reply or "").strip()
    if not reply:
        return
    now = datetime.utcnow()
    if prompt:
        db.session.add(
            AiJournalEntry(
                user_id=current_user.id,
                created_at=now,
                role="user",
                kind=kind,
                content=prompt,
            )
        )
    db.session.add(
        AiJournalEntry(
            user_id=current_user.id,
            created_at=now,
            role="assistant",
            kind=kind,
            content=reply,
        )
    )


def _utc_day_start(now: datetime | None = None) -> datetime:
    now = now or datetime.utcnow()
    return datetime(now.year, now.month, now.day)


def _check_in_email_batches_today(user_id: int) -> int:
    """Count notification batches already attempted today (UTC)."""
    start = _utc_day_start()
    return (
        CheckInOnMeRequest.query.filter(
            CheckInOnMeRequest.user_id == user_id,
            CheckInOnMeRequest.notify_email_at >= start,
            CheckInOnMeRequest.notify_email_status.in_(("sent", "partial", "failed")),
        ).count()
    )


MAX_CHECK_IN_EMAIL_BATCHES_PER_DAY = 3


@bp.route("/connections", methods=["GET", "POST"])
@login_required
def connections():
    add_form = TrustedContactForm()
    if add_form.validate_on_submit():
        db.session.add(
            TrustedContact(
                user_id=current_user.id,
                label=add_form.label.data.strip(),
                contact_email=(add_form.contact_email.data or "").strip() or None,
                phone=(add_form.phone.data or "").strip() or None,
                notes=(add_form.notes.data or "").strip() or None,
                email_on_check_in=bool(add_form.email_on_check_in.data),
            )
        )
        db.session.commit()
        log_visit_event(
            "trusted_contact_added",
            {"email_on_check_in": bool(add_form.email_on_check_in.data)},
        )
        flash("Contact saved.", "success")
        return redirect(url_for("main.connections"))

    ping_form = CheckInOnMeForm()
    consent_form = NotifyContactsEmailForm()
    consent_form.notify_contacts_email.data = bool(
        getattr(current_user, "notify_contacts_email", False)
    )
    contacts = (
        TrustedContact.query.filter_by(user_id=current_user.id)
        .order_by(TrustedContact.created_at.desc())
        .all()
    )
    recent_pings = (
        CheckInOnMeRequest.query.filter_by(user_id=current_user.id)
        .order_by(CheckInOnMeRequest.created_at.desc())
        .limit(20)
        .all()
    )
    batches_today = _check_in_email_batches_today(current_user.id)
    return render_template(
        "connections.html",
        add_form=add_form,
        ping_form=ping_form,
        consent_form=consent_form,
        contacts=contacts,
        recent_pings=recent_pings,
        mail_enabled=mail_enabled(),
        email_batches_today=batches_today,
        email_batches_limit=MAX_CHECK_IN_EMAIL_BATCHES_PER_DAY,
    )


@bp.post("/connections/email-consent")
@login_required
def connections_email_consent():
    form = NotifyContactsEmailForm()
    if form.validate_on_submit():
        want = bool(form.notify_contacts_email.data)
        current_user.notify_contacts_email = want
        current_user.notify_contacts_email_at = datetime.utcnow() if want else None
        db.session.commit()
        log_visit_event("notify_contacts_email_set", {"enabled": want})
        if want:
            flash(
                "Email consent saved. Contacts you mark for check-in email can be notified when you record a request.",
                "success",
            )
        else:
            flash("Email notifications to contacts are turned off.", "info")
    else:
        flash("Could not update email consent.", "warning")
    return redirect(url_for("main.connections"))


@bp.post("/connections/check-in-on-me")
@login_required
def connections_check_in_on_me():
    form = CheckInOnMeForm()
    if not form.validate_on_submit():
        for err in form.message.errors:
            flash(err, "danger")
        if not form.message.errors:
            flash("Could not save that request.", "warning")
        return redirect(url_for("main.connections"))

    msg = (form.message.data or "").strip() or None
    row = CheckInOnMeRequest(user_id=current_user.id, message=msg)
    db.session.add(row)
    db.session.flush()

    status = "none"
    sent_count = 0
    notify_at = None

    master_on = bool(getattr(current_user, "notify_contacts_email", False))
    if not master_on:
        status = "no_consent"
        flash(
            "Recorded in your private log. Turn on email consent and mark contacts if you want BMW to email them.",
            "success",
        )
    elif not mail_enabled():
        status = "disabled"
        notify_at = datetime.utcnow()
        flash(
            "Recorded. Email sending is disabled on this server (MAIL_ENABLED=0); your contacts were not emailed.",
            "warning",
        )
    else:
        eligible = (
            TrustedContact.query.filter_by(
                user_id=current_user.id, email_on_check_in=True
            )
            .filter(TrustedContact.contact_email.isnot(None))
            .filter(TrustedContact.contact_email != "")
            .all()
        )
        recipients = [
            (c.contact_email or "").strip()
            for c in eligible
            if (c.contact_email or "").strip()
        ]
        if not recipients:
            status = "no_recipients"
            flash(
                "Recorded. No contacts are marked for check-in email (or they have no email address).",
                "success",
            )
        else:
            used = _check_in_email_batches_today(current_user.id)
            if used >= MAX_CHECK_IN_EMAIL_BATCHES_PER_DAY:
                status = "rate_limited"
                notify_at = datetime.utcnow()
                flash(
                    f"Recorded. Daily email limit reached ({MAX_CHECK_IN_EMAIL_BATCHES_PER_DAY} batches per UTC day); contacts were not emailed.",
                    "warning",
                )
            else:
                result = send_check_in_notifications(
                    display_name=current_user.display_name or "A BMW user",
                    user_message=msg,
                    recipients=recipients,
                )
                notify_at = datetime.utcnow()
                if result.get("disabled"):
                    status = "disabled"
                    flash(
                        "Recorded. Email sending is disabled on this server; contacts were not emailed.",
                        "warning",
                    )
                else:
                    sent_count = len(result.get("sent") or [])
                    failed = result.get("failed") or []
                    if sent_count and not failed:
                        status = "sent"
                        flash(
                            f"Recorded and emailed {sent_count} trusted contact(s).",
                            "success",
                        )
                    elif sent_count and failed:
                        status = "partial"
                        flash(
                            f"Recorded. Emailed {sent_count} contact(s); {len(failed)} failed — try again later or reach out directly.",
                            "warning",
                        )
                    else:
                        status = "failed"
                        flash(
                            "Recorded in your log, but email delivery failed. Please contact people directly if you need support now.",
                            "warning",
                        )

    row.notify_email_status = status
    row.notify_email_sent_count = sent_count
    row.notify_email_at = notify_at
    db.session.commit()
    log_visit_event(
        "check_in_on_me_requested",
        {
            "has_message": bool(msg),
            "notify_email_status": status,
            "notify_email_sent_count": sent_count,
        },
    )
    return redirect(url_for("main.connections"))


@bp.post("/connections/contact/email-toggle")
@login_required
def connections_contact_email_toggle():
    cid = request.form.get("contact_id", type=int)
    if not cid:
        flash("Invalid request.", "warning")
        return redirect(url_for("main.connections"))
    tc = TrustedContact.query.filter_by(id=cid, user_id=current_user.id).first()
    if not tc:
        abort(404)
    # Checkbox present => True; absent => False (HTML forms omit unchecked boxes)
    want = request.form.get("email_on_check_in") in ("1", "on", "true", "yes")
    tc.email_on_check_in = want
    tc.updated_at = datetime.utcnow()
    db.session.commit()
    log_visit_event(
        "trusted_contact_email_toggle",
        {"contact_id": cid, "email_on_check_in": want},
    )
    flash(
        f"{'Will' if want else 'Will not'} email {tc.label} on check-in requests"
        + (" (also needs master consent)." if want else "."),
        "success",
    )
    return redirect(url_for("main.connections"))


@bp.post("/connections/contact/delete")
@login_required
def connections_delete_contact():
    cid = request.form.get("contact_id", type=int)
    if not cid:
        flash("Invalid request.", "warning")
        return redirect(url_for("main.connections"))
    tc = TrustedContact.query.filter_by(id=cid, user_id=current_user.id).first()
    if not tc:
        abort(404)
    db.session.delete(tc)
    db.session.commit()
    log_visit_event("trusted_contact_removed", {"contact_id": cid})
    flash("Contact removed.", "info")
    return redirect(url_for("main.connections"))


@bp.get("/history")
@login_required
def history():
    state = get_user_state()
    return render_template(
        "history.html",
        assessments=state["assessments"],
        checkins=state["checkins"],
        completions=state["completions"],
        insights=state["insights"],
        wellness_score=state["wellness_score"],
        wellness_label=state["wellness_label"],
        streak_days=state["streak_days"],
        last7_count=state["last7_count"],
    )


@bp.get("/screenshare")
@login_required
def screenshare():
    if not current_app.config.get("BMAT_SCREENSHARE_ENABLED"):
        return render_template(
            "screenshare_disabled.html",
            reason=(
                "Private Session (screen share) is disabled under the Waitress production "
                "server because Socket.IO is not available on this entry path. Use "
                "bmat_run.py (socketio.run) in a controlled environment, or set "
                "BMAT_SCREENSHARE_ENABLED=1 only when that process is running."
            ),
        )
    suggested_room = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12].upper()
    return render_template("screenshare.html", suggested_room=suggested_room)


# ------------------ Admin / Clinical (Ethical Mode) ------------------
def require_admin():
    if not current_user.is_admin:
        flash("Admin access required.", "danger")
        return False
    return True


def require_clinical():
    """Admin or therapist may use clinical tools (after ethical ack)."""
    if not getattr(current_user, "is_clinical", False):
        flash("Clinical access required.", "danger")
        return False
    return True


def _clinical_ack_redirect():
    """Send staff without ethical ack to the acknowledgment gate."""
    return redirect(url_for("main.admin"))


@bp.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    # Therapists: acknowledgment only, then clinical roster (no broad admin tools).
    if getattr(current_user, "is_therapist", False) and not current_user.is_admin:
        if request.method == "POST":
            session["admin_ack"] = True
            log_admin("clinical_acknowledged")
            return redirect(url_for("main.admin_clinical"))
        if not session.get("admin_ack"):
            return render_template("admin_ack.html")
        return redirect(url_for("main.admin_clinical"))

    if not require_admin():
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        session["admin_ack"] = True
        log_admin("admin_acknowledged")
        return redirect(url_for("main.admin_overview"))

    if not session.get("admin_ack"):
        return render_template("admin_ack.html")
    return redirect(url_for("main.admin_overview"))


@bp.get("/admin/overview")
@login_required
def admin_overview():
    if not require_admin():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return redirect(url_for("main.admin"))

    users = User.query.count()
    assessments = Assessment.query.count()
    checkins = CheckIn.query.count()
    item9_flags = Assessment.query.filter(Assessment.kind == "PHQ9", Assessment.item9_score.isnot(None), Assessment.item9_score > 0).count()
    high_sev = Assessment.query.filter(((Assessment.kind == "PHQ9") & (Assessment.total_score >= 20)) | ((Assessment.kind == "GAD7") & (Assessment.total_score >= 15))).count()
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)
    visits_24h = VisitEvent.query.filter(VisitEvent.event_name == "page_view", VisitEvent.created_at >= last_24h).count()
    unique_sessions_7d = db.session.query(func.count(func.distinct(VisitSession.session_id))).filter(VisitSession.last_seen_at >= last_7d).scalar() or 0
    unique_sessions_30d = db.session.query(func.count(func.distinct(VisitSession.session_id))).filter(VisitSession.last_seen_at >= last_30d).scalar() or 0
    signup_completed_30d = VisitEvent.query.filter(
        VisitEvent.event_name == "signup_completed",
        VisitEvent.created_at >= last_30d,
    ).count()

    deletion_requests = (
        DeletionRequest.query.order_by(
            (DeletionRequest.status == "pending").desc(), DeletionRequest.created_at.desc()
        )
        .limit(25)
        .all()
    )
    deletion_pending = DeletionRequest.query.filter_by(status="pending").count()
    pending_emails = {r.email for r in deletion_requests if r.status == "pending" and r.email}
    deletion_has_account = (
        {u.email for u in User.query.filter(User.email.in_(pending_emails)).all()} if pending_emails else set()
    )

    ai_reports = (
        AIContentReport.query.order_by(
            (AIContentReport.status == "pending").desc(), AIContentReport.created_at.desc()
        )
        .limit(25)
        .all()
    )
    ai_reports_pending = AIContentReport.query.filter_by(status="pending").count()

    log_admin("admin_overview_viewed")
    return render_template("admin_overview.html", deletion_requests=deletion_requests,
                           ai_reports=ai_reports, ai_reports_pending=ai_reports_pending,
                           ai_report_reasons=AI_REPORT_REASON_LABELS,
                           deletion_pending=deletion_pending, deletion_has_account=deletion_has_account, stats={
        "users": users,
        "assessments": assessments,
        "checkins": checkins,
        "item9_flags": item9_flags,
        "high_severity": high_sev,
        "visits_24h": visits_24h,
        "sessions_7d": unique_sessions_7d,
        "sessions_30d": unique_sessions_30d,
        "signup_completed_30d": signup_completed_30d,
    })


@bp.get("/admin/analytics")
@login_required
def admin_analytics():
    if not require_admin():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return redirect(url_for("main.admin"))

    now = datetime.utcnow()
    since_30d = now - timedelta(days=30)
    since_7d = now - timedelta(days=7)
    since_24h = now - timedelta(hours=24)

    total_events_30d = VisitEvent.query.filter(VisitEvent.created_at >= since_30d).count()
    page_views_30d = VisitEvent.query.filter(
        VisitEvent.event_name == "page_view",
        VisitEvent.created_at >= since_30d,
    ).count()
    unique_sessions_30d = db.session.query(func.count(func.distinct(VisitSession.session_id))).filter(
        VisitSession.last_seen_at >= since_30d
    ).scalar() or 0
    unique_sessions_7d = db.session.query(func.count(func.distinct(VisitSession.session_id))).filter(
        VisitSession.last_seen_at >= since_7d
    ).scalar() or 0
    unique_sessions_24h = db.session.query(func.count(func.distinct(VisitSession.session_id))).filter(
        VisitSession.last_seen_at >= since_24h
    ).scalar() or 0

    # Daily page-view trend for last 14 days (simple table-friendly structure).
    rows = (
        db.session.query(func.date(VisitEvent.created_at), func.count(VisitEvent.id))
        .filter(VisitEvent.event_name == "page_view", VisitEvent.created_at >= (now - timedelta(days=14)))
        .group_by(func.date(VisitEvent.created_at))
        .order_by(func.date(VisitEvent.created_at).asc())
        .all()
    )
    page_view_daily = [{"day": str(day), "count": int(count)} for day, count in rows]

    top_pages = (
        db.session.query(VisitEvent.path, func.count(VisitEvent.id).label("n"))
        .filter(
            VisitEvent.event_name == "page_view",
            VisitEvent.created_at >= since_30d,
            VisitEvent.path.isnot(None),
        )
        .group_by(VisitEvent.path)
        .order_by(func.count(VisitEvent.id).desc())
        .limit(10)
        .all()
    )
    top_pages = [{"path": path or "-", "count": int(n)} for path, n in top_pages]

    top_events = (
        db.session.query(VisitEvent.event_name, func.count(VisitEvent.id).label("n"))
        .filter(VisitEvent.created_at >= since_30d)
        .group_by(VisitEvent.event_name)
        .order_by(func.count(VisitEvent.id).desc())
        .limit(12)
        .all()
    )
    top_events = [{"event_name": event_name, "count": int(n)} for event_name, n in top_events]

    log_admin("admin_analytics_viewed")
    return render_template(
        "admin_analytics.html",
        stats={
            "total_events_30d": total_events_30d,
            "page_views_30d": page_views_30d,
            "sessions_30d": unique_sessions_30d,
            "sessions_7d": unique_sessions_7d,
            "sessions_24h": unique_sessions_24h,
        },
        page_view_daily=page_view_daily,
        top_pages=top_pages,
        top_events=top_events,
    )


@bp.get("/admin/users")
@login_required
def admin_users():
    if not require_admin():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return redirect(url_for("main.admin"))

    reveal = request.args.get("reveal") == "1"
    users = User.query.order_by(User.created_at.desc()).all()
    display = []
    for u in users:
        display.append({
            "id": u.id,
            "email": u.email if reveal else mask_email(u.email),
            "display_name": u.display_name,
            "role": u.role,
            "created_at": u.created_at,
        })
    admin_count = User.query.filter_by(role="admin").count()
    log_admin("admin_users_viewed")
    return render_template("admin_users.html", users=display, reveal=reveal, admin_count=admin_count)


@bp.route("/admin/users/new", methods=["GET", "POST"])
@login_required
def admin_user_create():
    if not require_admin():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return redirect(url_for("main.admin"))

    form = AdminCreateUserForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash("That email is already registered.", "warning")
        else:
            user = User(
                email=email,
                display_name=form.display_name.data.strip(),
                role=form.role.data if form.role.data in ("user", "admin", "therapist") else "user",
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            log_admin("admin_user_created", target_user_id=user.id)
            flash("User created.", "success")
            return redirect(url_for("main.admin_users"))

    log_admin("admin_user_create_viewed")
    return render_template("admin_user_create.html", form=form)


@bp.post("/admin/users/<int:user_id>/role")
@login_required
def admin_user_set_role(user_id: int):
    if not require_admin():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return redirect(url_for("main.admin"))

    new_role = (request.form.get("role") or "").strip()
    if new_role not in ("user", "admin", "therapist"):
        flash("Invalid role.", "danger")
        return redirect(url_for("main.admin_users"))

    u = User.query.get_or_404(user_id)
    if u.role == new_role:
        flash("No change needed.", "info")
        return redirect(url_for("main.admin_users"))

    if u.role == "admin" and new_role != "admin":
        admin_count = User.query.filter_by(role="admin").count()
        if admin_count <= 1:
            flash("Cannot remove the only administrator.", "danger")
            return redirect(url_for("main.admin_users"))

    u.role = new_role
    db.session.commit()
    log_admin(f"admin_user_role_{new_role}", target_user_id=user_id)
    flash("User role updated.", "success")
    return redirect(url_for("main.admin_users"))


@bp.get("/admin/user/<int:user_id>")
@login_required
def admin_user_detail(user_id: int):
    if not require_admin():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return redirect(url_for("main.admin"))

    if request.args.get("confirm") != "1":
        return render_template("admin_user_confirm.html", user_id=user_id)

    log_admin("admin_view_user_details", target_user_id=user_id)
    u = User.query.get_or_404(user_id)
    assessments = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).all()
    checkins = CheckIn.query.filter_by(user_id=user_id).order_by(CheckIn.created_at.desc()).all()
    return render_template("admin_user_detail.html", u=u, assessments=assessments, checkins=checkins)


@bp.get("/admin/risk")
@login_required
def admin_risk():
    if not require_admin():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return redirect(url_for("main.admin"))

    flags = Assessment.query.join(User, User.id == Assessment.user_id).filter(
        ((Assessment.kind == "PHQ9") & (Assessment.item9_score.isnot(None)) & (Assessment.item9_score > 0))
        | ((Assessment.kind == "PHQ9") & (Assessment.total_score >= 20))
        | ((Assessment.kind == "GAD7") & (Assessment.total_score >= 15))
    ).order_by(Assessment.created_at.desc()).all()

    reveal = request.args.get("reveal") == "1" and request.args.get("confirm") == "1"
    rows = []
    for a in flags:
        rows.append(
            {
                "user_id": a.user_id,
                "email": a.user.email if reveal else mask_email(a.user.email),
                "kind": a.kind,
                "total_score": a.total_score,
                "severity": a.severity,
                "item9_score": a.item9_score,
                "created_at": a.created_at,
            }
        )

    if reveal:
        log_admin("admin_risk_flags_pii_revealed")
    log_admin("admin_risk_flags_viewed")
    return render_template("admin_risk.html", flags=rows, reveal=reveal)


@bp.get("/clinic")
@bp.get("/clinic/dashboard")
@bp.get("/admin/clinical")
@login_required
def admin_clinical():
    if not require_clinical():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return _clinical_ack_redirect()

    rows = []
    needs_attention_total = 0
    for u in User.query.filter_by(role="user").order_by(User.id.asc()).all():
        latest_phq = Assessment.query.filter_by(user_id=u.id, kind="PHQ9").order_by(Assessment.created_at.desc()).first()
        latest_gad = Assessment.query.filter_by(user_id=u.id, kind="GAD7").order_by(Assessment.created_at.desc()).first()
        latest_ci = CheckIn.query.filter_by(user_id=u.id).order_by(CheckIn.created_at.desc()).first()
        ws, wl = calculate_wellness_score(latest_phq, latest_gad, latest_ci)
        item9 = latest_phq.item9_score if latest_phq else None
        open_rev = ClinicalReview.query.filter_by(user_id=u.id, resolved_at=None).count()
        open_esc = ClinicalReview.query.filter_by(
            user_id=u.id, resolved_at=None, review_type="escalation"
        ).count()
        needs_attention = open_esc > 0
        if needs_attention:
            needs_attention_total += 1
        rows.append(
            {
                "user": u,
                "wellness_score": ws,
                "wellness_label": wl,
                "latest_phq": latest_phq,
                "latest_gad": latest_gad,
                "latest_checkin": latest_ci,
                "item9": item9,
                "open_reviews": open_rev,
                "open_escalations": open_esc,
                "needs_attention": needs_attention,
            }
        )

    log_admin("admin_clinical_viewed")
    return render_template(
        "admin_clinical.html",
        rows=rows,
        needs_attention_total=needs_attention_total,
    )


@bp.get("/admin/clinical/user/<int:user_id>")
@login_required
def admin_clinical_user(user_id: int):
    if not require_clinical():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return _clinical_ack_redirect()
    if request.args.get("confirm") != "1":
        return render_template("admin_clinical_confirm.html", user_id=user_id)

    u = User.query.get_or_404(user_id)
    state = _admin_user_state(user_id)
    reviews = ClinicalReview.query.filter_by(user_id=user_id).order_by(ClinicalReview.created_at.desc()).all()
    review_admins = {r.admin_user_id: User.query.get(r.admin_user_id) for r in reviews if r.admin_user_id}
    log_admin("admin_clinical_user_viewed", target_user_id=user_id)
    return render_template(
        "admin_clinical_user.html",
        u=u,
        state=state,
        reviews=reviews,
        review_admins=review_admins,
    )


@bp.post("/admin/clinical/user/<int:user_id>/review")
@login_required
def admin_clinical_review_add(user_id: int):
    if not require_clinical():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return _clinical_ack_redirect()
    User.query.get_or_404(user_id)
    note = (request.form.get("note") or "").strip()
    if not note:
        flash("Add a note before saving.", "warning")
        return redirect(url_for("main.admin_clinical_user", user_id=user_id, confirm=1))
    db.session.add(ClinicalReview(user_id=user_id, admin_user_id=current_user.id, note=note, review_type="note"))
    db.session.commit()
    log_admin("admin_clinical_review_added", target_user_id=user_id)
    flash("Review note saved.", "success")
    return redirect(url_for("main.admin_clinical_user", user_id=user_id, confirm=1))


@bp.post("/admin/clinical/review/<int:review_id>/resolve")
@login_required
def admin_clinical_review_resolve(review_id: int):
    if not require_clinical():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return _clinical_ack_redirect()
    r = ClinicalReview.query.get_or_404(review_id)
    uid = r.user_id
    if r.resolved_at:
        flash("Already resolved.", "info")
        return redirect(url_for("main.admin_clinical_user", user_id=uid, confirm=1))
    r.resolved_at = datetime.utcnow()
    db.session.commit()
    log_admin("admin_clinical_review_resolved", target_user_id=uid)
    flash("Marked resolved.", "success")
    return redirect(url_for("main.admin_clinical_user", user_id=uid, confirm=1))


@bp.get("/admin/clinical/user/<int:user_id>/report.pdf")
@login_required
def admin_clinical_report_pdf(user_id: int):
    if not require_clinical():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return _clinical_ack_redirect()

    u = User.query.get_or_404(user_id)
    state = _admin_user_state(user_id)
    pdf_bytes = build_clinical_progress_pdf_bytes(
        display_name=u.display_name,
        masked_email=mask_email(u.email),
        user_id=u.id,
        generated_at=datetime.utcnow(),
        wellness_score=state["wellness_score"],
        wellness_label=state["wellness_label"],
        assessments=state["assessments"],
        checkins=state["checkins"],
    )
    log_admin("admin_clinical_pdf_export", target_user_id=user_id)
    fname = f"bmw_progress_user{user_id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@bp.get("/admin/export/<string:table_name>")
@login_required
def admin_export(table_name: str):
    if not require_admin():
        return redirect(url_for("main.dashboard"))
    if not session.get("admin_ack"):
        return redirect(url_for("main.admin"))

    include_pii = request.args.get("pii") == "1"

    output = io.StringIO()
    writer = csv.writer(output)

    if table_name == "users":
        rows = User.query.order_by(User.id.asc()).all()
        writer.writerow(["id", "email", "display_name", "role", "created_at"])
        for r in rows:
            email = r.email if include_pii else mask_email(r.email)
            writer.writerow([r.id, email, r.display_name, r.role, r.created_at.isoformat()])
    elif table_name == "assessments":
        rows = Assessment.query.order_by(Assessment.id.asc()).all()
        writer.writerow(["id", "user_id", "kind", "total_score", "severity", "item9_score", "created_at"])
        for r in rows:
            writer.writerow([r.id, r.user_id, r.kind, r.total_score, r.severity, r.item9_score, r.created_at.isoformat()])
    elif table_name == "checkins":
        rows = CheckIn.query.order_by(CheckIn.id.asc()).all()
        writer.writerow(["id", "user_id", "mood", "stress", "sleep_hours", "note", "created_at"])
        for r in rows:
            writer.writerow([r.id, r.user_id, r.mood, r.stress, r.sleep_hours, r.note or "", r.created_at.isoformat()])
    elif table_name == "audit_log":
        rows = AuditLog.query.order_by(AuditLog.id.asc()).all()
        writer.writerow(["id", "admin_user_id", "action", "target_user_id", "created_at"])
        for r in rows:
            writer.writerow([r.id, r.admin_user_id, r.action, r.target_user_id, r.created_at.isoformat()])
    elif table_name == "action_completions":
        rows = ActionCompletion.query.order_by(ActionCompletion.id.asc()).all()
        writer.writerow(["id", "user_id", "action_key", "action_title", "completed_date", "created_at"])
        for r in rows:
            writer.writerow([r.id, r.user_id, r.action_key, r.action_title, r.completed_date.isoformat(), r.created_at.isoformat()])
    elif table_name == "visit_session":
        rows = VisitSession.query.order_by(VisitSession.id.asc()).all()
        writer.writerow(
            [
                "id",
                "session_id",
                "user_id",
                "is_authenticated",
                "ip_hash",
                "user_agent_hash",
                "referrer_host",
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "first_seen_at",
                "last_seen_at",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r.id,
                    r.session_id,
                    r.user_id,
                    r.is_authenticated,
                    r.ip_hash or "",
                    r.user_agent_hash or "",
                    r.referrer_host or "",
                    r.utm_source or "",
                    r.utm_medium or "",
                    r.utm_campaign or "",
                    r.first_seen_at.isoformat(),
                    r.last_seen_at.isoformat(),
                ]
            )
    elif table_name == "visit_event":
        rows = VisitEvent.query.order_by(VisitEvent.id.asc()).all()
        writer.writerow(
            ["id", "session_id", "user_id", "event_name", "path", "method", "status_code", "meta_json", "created_at"]
        )
        for r in rows:
            writer.writerow(
                [
                    r.id,
                    r.session_id,
                    r.user_id,
                    r.event_name,
                    r.path or "",
                    r.method or "",
                    r.status_code if r.status_code is not None else "",
                    r.meta_json or "",
                    r.created_at.isoformat(),
                ]
            )
    elif table_name == "trusted_contact":
        rows = TrustedContact.query.order_by(TrustedContact.id.asc()).all()
        writer.writerow(["id", "user_id", "label", "contact_email", "phone", "notes", "email_on_check_in", "created_at", "updated_at"])
        for r in rows:
            email = (r.contact_email or "")
            if email and not include_pii:
                email = mask_email(email)
            phone = (r.phone or "")
            if phone and not include_pii:
                phone = "***"
            notes = (r.notes or "")
            if notes and not include_pii:
                notes = "[redacted]"
            writer.writerow(
                [
                    r.id,
                    r.user_id,
                    r.label,
                    email,
                    phone,
                    notes,
                    int(bool(getattr(r, "email_on_check_in", False))),
                    r.created_at.isoformat(),
                    r.updated_at.isoformat() if r.updated_at else "",
                ]
            )
    elif table_name == "check_in_on_me_request":
        rows = CheckInOnMeRequest.query.order_by(CheckInOnMeRequest.id.asc()).all()
        writer.writerow(["id", "user_id", "message", "created_at", "notify_email_status", "notify_email_sent_count", "notify_email_at"])
        for r in rows:
            msg = (r.message or "")
            if msg and not include_pii:
                msg = "[redacted]"
            nat = r.notify_email_at.isoformat() if getattr(r, "notify_email_at", None) else ""
            writer.writerow([
                r.id,
                r.user_id,
                msg,
                r.created_at.isoformat(),
                getattr(r, "notify_email_status", None) or "",
                int(getattr(r, "notify_email_sent_count", 0) or 0),
                nat,
            ])
    elif table_name == "clinical_review":
        rows = ClinicalReview.query.order_by(ClinicalReview.id.asc()).all()
        writer.writerow(
            ["id", "user_id", "admin_user_id", "review_type", "reason_code", "note", "created_at", "resolved_at"]
        )
        for r in rows:
            note = (r.note or "")
            if note and not include_pii:
                note = "[redacted]"
            res = r.resolved_at.isoformat() if r.resolved_at else ""
            writer.writerow(
                [
                    r.id,
                    r.user_id,
                    r.admin_user_id if r.admin_user_id is not None else "system",
                    getattr(r, "review_type", None) or "note",
                    getattr(r, "reason_code", None) or "",
                    note,
                    r.created_at.isoformat(),
                    res,
                ]
            )
    else:
        flash("Invalid dataset.", "danger")
        return redirect(url_for("main.admin_overview"))

    log_admin(f"admin_export_{table_name}")
    csv_bytes = output.getvalue().encode("utf-8")
    return Response(csv_bytes, mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={table_name}_export.csv"})


@bp.get("/backup")
@bp.get("/backup/")
def bmw_backup_download():
    """Public download of the latest no-secrets BMW source zip."""
    from flask import send_file, abort
    import os
    static_backup = os.path.join(current_app.static_folder, "backup")
    latest = os.path.join(static_backup, "latest.zip")
    if not os.path.exists(latest):
        abort(404)
    real = os.path.realpath(latest)
    if not os.path.isfile(real):
        abort(404)
    return send_file(real, as_attachment=True, download_name="bmw-backup.zip", max_age=0)



# ---------------------------------------------------------------------------
# Public developer downloads: /bmw/dev/android (Play release kit, no login)
# Files live outside static in <instance>/dev-downloads/android/:
#   bmw-play-kit-public.zip  + bmw-play-kit-public.json (version, sha256, size, published)
# ---------------------------------------------------------------------------
DEV_ANDROID_KIT_NAME = "bmw-play-kit-public.zip"
_dev_kit_sha_cache: dict = {}


def _dev_android_dir() -> str:
    return os.path.join(current_app.instance_path, "dev-downloads", "android")


def _dev_android_kit_info() -> dict | None:
    path = os.path.join(_dev_android_dir(), DEV_ANDROID_KIT_NAME)
    if not os.path.isfile(path):
        return None
    st = os.stat(path)
    meta = {}
    try:
        with open(os.path.join(_dev_android_dir(), "bmw-play-kit-public.json"), "r", encoding="utf-8") as fh:
            meta = json.load(fh) or {}
    except Exception:
        meta = {}
    sha = meta.get("sha256") if int(meta.get("size") or -1) == st.st_size else None
    if not sha:
        key = (st.st_size, st.st_mtime)
        sha = _dev_kit_sha_cache.get(key)
        if not sha:
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            sha = h.hexdigest()
            _dev_kit_sha_cache.clear()
            _dev_kit_sha_cache[key] = sha
    size = st.st_size
    if size >= 1024 * 1024:
        size_h = f"{size / (1024 * 1024):.1f} MB"
    else:
        size_h = f"{size / 1024:.0f} KB"
    return {
        "path": path,
        "filename": DEV_ANDROID_KIT_NAME,
        "size": size,
        "size_human": size_h,
        "sha256": sha,
        "version": meta.get("version") or "1.0.0 (1)",
        "published": meta.get("published") or datetime.fromtimestamp(st.st_mtime).strftime("%B %d, %Y"),
    }


@bp.get("/dev")
@bp.get("/dev/")
def dev_index():
    return redirect(url_for("main.dev_android"))


@bp.get("/dev/android")
@bp.get("/dev/android/")
def dev_android():
    """Public page for the BMW Android Play release kit (no login)."""
    info = _dev_android_kit_info()
    return render_template("dev_android.html", kit=info)


@bp.get("/dev/android/<path:filename>")
def dev_android_download(filename):
    from flask import abort
    if filename != DEV_ANDROID_KIT_NAME:
        abort(404)
    info = _dev_android_kit_info()
    if not info:
        abort(404)
    return send_file(
        info["path"],
        mimetype="application/zip",
        as_attachment=True,
        download_name=DEV_ANDROID_KIT_NAME,
        conditional=True,
        max_age=300,
    )
