from __future__ import annotations

from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False, default="Anonymous")
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # user|admin|therapist
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Phase 5 email consent: master toggle for notifying trusted contacts
    notify_contacts_email = db.Column(db.Boolean, nullable=False, default=False)
    notify_contacts_email_at = db.Column(db.DateTime, nullable=True)
    # Phase 8 follow-up: optional AI journaling (default off)
    ai_journal_consent = db.Column(db.Boolean, nullable=False, default=False)
    ai_journal_consent_at = db.Column(db.DateTime, nullable=True)
    # Oct 2026: when the user ticked "I am 18 or older" at sign-up (NULL for older accounts).
    age_confirmed_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_therapist(self) -> bool:
        return self.role == "therapist"

    @property
    def is_clinical(self) -> bool:
        """Admin or therapist — may access clinical tools after ethical ack."""
        return self.role in ("admin", "therapist")


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


class Assessment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    user = db.relationship("User", backref=db.backref("assessments", lazy=True))
    kind = db.Column(db.String(10), nullable=False)  # PHQ9|GAD7
    total_score = db.Column(db.Integer, nullable=False)
    severity = db.Column(db.String(40), nullable=False)
    item9_score = db.Column(db.Integer, nullable=True)
    responses_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    user = db.relationship("User", backref=db.backref("checkins", lazy=True))
    mood = db.Column(db.Integer, nullable=False)
    stress = db.Column(db.Integer, nullable=False)
    sleep_hours = db.Column(db.Float, nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ActionCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    user = db.relationship("User", backref=db.backref("action_completions", lazy=True))
    action_key = db.Column(db.String(120), nullable=False, index=True)
    action_title = db.Column(db.String(255), nullable=False)
    completed_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "action_key", "completed_date", name="uq_action_completion_daily"),
    )


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(120), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class UserPreference(db.Model):
    """Phase 4 + 7: JSON blob for topic prefs, learned completion patterns, and cultural tone (per user)."""
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    user = db.relationship("User", backref=db.backref("preference", uselist=False))
    data_json = db.Column(db.Text, nullable=False, default="{}")
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class VisitSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    user = db.relationship("User", backref=db.backref("visit_sessions", lazy=True))
    is_authenticated = db.Column(db.Boolean, nullable=False, default=False)
    ip_hash = db.Column(db.String(64), nullable=True)
    user_agent_hash = db.Column(db.String(64), nullable=True)
    referrer_host = db.Column(db.String(255), nullable=True)
    utm_source = db.Column(db.String(120), nullable=True)
    utm_medium = db.Column(db.String(120), nullable=True)
    utm_campaign = db.Column(db.String(120), nullable=True)
    first_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class VisitEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), db.ForeignKey("visit_session.session_id"), nullable=False, index=True)
    session = db.relationship("VisitSession", backref=db.backref("events", lazy=True))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    user = db.relationship("User", backref=db.backref("visit_events", lazy=True))
    event_name = db.Column(db.String(80), nullable=False, index=True)
    path = db.Column(db.String(255), nullable=True)
    method = db.Column(db.String(10), nullable=True)
    status_code = db.Column(db.Integer, nullable=True)
    meta_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class TrustedContact(db.Model):
    """Phase 5: trusted people; optional email_on_check_in with master consent."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    user = db.relationship("User", backref=db.backref("trusted_contacts", lazy=True))
    label = db.Column(db.String(120), nullable=False)
    contact_email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    email_on_check_in = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CheckInOnMeRequest(db.Model):
    """Logged when the user records a 'check in on me' intent; optional email notify with consent."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    user = db.relationship("User", backref=db.backref("check_in_on_me_requests", lazy=True))
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    # Email batch outcome: none|disabled|no_consent|no_recipients|rate_limited|sent|partial|failed
    notify_email_status = db.Column(db.String(40), nullable=True)
    notify_email_sent_count = db.Column(db.Integer, nullable=False, default=0)
    notify_email_at = db.Column(db.DateTime, nullable=True)


class ClinicalReview(db.Model):
    """Phase 6: clinical workflow note / escalation for a user; not visible to the end user.

    admin_user_id is None for system-generated escalations.
    review_type: note (manual) | escalation (automated or flagged).
    reason_code: stable key for escalation dedupe (e.g. phq_item9).
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True, index=True)
    review_type = db.Column(db.String(40), nullable=False, default="note", index=True)
    reason_code = db.Column(db.String(80), nullable=True, index=True)


class AiUsageDaily(db.Model):
    """Phase 8: per-user successful AI generation counts per UTC calendar day."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    user = db.relationship("User", backref=db.backref("ai_usage_daily", lazy=True))
    utc_date = db.Column(db.String(10), nullable=False, index=True)  # YYYY-MM-DD
    count = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "utc_date", name="uq_ai_usage_daily_user_date"),
    )


class AiJournalEntry(db.Model):
    """Phase 8: optional private AI journal rows; only written when user consents."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    user = db.relationship("User", backref=db.backref("ai_journal_entries", lazy=True))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    role = db.Column(db.String(20), nullable=False)  # user|assistant|system_note
    kind = db.Column(db.String(40), nullable=False)  # free_text|score_insight
    content = db.Column(db.Text, nullable=False)
    meta_json = db.Column(db.Text, nullable=True)



class DeletionRequest(db.Model):
    """Account deletion requests (Google Play account-deletion requirement).

    source: web_form (public /delete-account form) | in_app (user deleted their own account).
    status: pending | completed | closed.
    Deliberately no FK to user: requests must survive the account being deleted, and the
    public form must not reveal whether an email has an account. On completion the email
    is replaced with a masked form so the record keeps no full address.
    """

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=True, index=True)
    reason = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(20), nullable=False, default="web_form")
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    ip_hash = db.Column(db.String(64), nullable=True, index=True)
    notify_email_status = db.Column(db.String(40), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    admin_note = db.Column(db.String(255), nullable=True)


class AIContentReport(db.Model):
    """User report/flag of an AI Wellness reply (Google Play AI-generated content policy).

    user_id is a plain integer (no FK) so reports never block account deletion; the shared
    purge_user_account() deletes a user's reports together with the rest of their data.
    ai_text is the reported AI reply (truncated). user_prompt is only stored when the user
    chose to include their own message for context.
    reason: offensive | harmful | inaccurate | other. status: pending | closed.
    """

    __tablename__ = "ai_content_report"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    source = db.Column(db.String(20), nullable=False, default="free_text")  # free_text|score_insight|journal
    reason = db.Column(db.String(20), nullable=False, index=True)
    note = db.Column(db.Text, nullable=True)
    ai_text = db.Column(db.Text, nullable=False)
    user_prompt = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    admin_note = db.Column(db.String(255), nullable=True)
