from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    IntegerField,
    FloatField,
    TextAreaField,
    SelectMultipleField,
    SelectField,
    BooleanField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional
from wtforms.widgets import CheckboxInput, Input, ListWidget

from .cultural import TONE_LABELS, TONE_PRESETS


class RangeInput(Input):
    input_type = "range"


TAG_CHOICES = [
    ("rest", "Rest & calm (breathing, grounding)"),
    ("sleep", "Sleep wind-down"),
    ("support", "Support & coping skills"),
    ("boundaries", "Boundaries & communication"),
]

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")

class SignupForm(FlaskForm):
    display_name = StringField("Display name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=10)])
    age_confirm = BooleanField(
        "I confirm I am 18 or older",
        validators=[DataRequired(message="You must be 18 or older to create a BMW account.")],
    )
    submit = SubmitField("Create account")


class AdminCreateUserForm(FlaskForm):
    display_name = StringField("Display name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=10)])
    role = SelectField("Role", choices=[("user", "User"), ("therapist", "Therapist"), ("admin", "Administrator")], default="user")
    submit = SubmitField("Create user")

class CheckInForm(FlaskForm):
    mood = IntegerField(
        "Mood",
        widget=RangeInput(),
        validators=[DataRequired(), NumberRange(min=1, max=10)],
        render_kw={"min": 1, "max": 10, "step": 1, "class": "form-range bmat-checkin-range w-100"},
    )
    stress = IntegerField(
        "Stress",
        widget=RangeInput(),
        validators=[DataRequired(), NumberRange(min=1, max=10)],
        render_kw={"min": 1, "max": 10, "step": 1, "class": "form-range bmat-checkin-range w-100"},
    )
    sleep_hours = FloatField("Sleep (hours)", validators=[DataRequired(), NumberRange(min=0, max=24)])
    note = TextAreaField("Anything you want to note?", default="1. ")
    submit = SubmitField("Save check-in")


class TrustedContactForm(FlaskForm):
    label = StringField("Name or label", validators=[DataRequired(), Length(min=1, max=120)])
    contact_email = StringField("Email (optional)", validators=[Optional(), Email()])
    phone = StringField("Phone (optional)", validators=[Optional(), Length(max=40)])
    notes = TextAreaField("Private notes (optional)", validators=[Optional(), Length(max=800)])
    email_on_check_in = BooleanField(
        "Email this contact when I request a check-in (requires master consent below)",
        default=False,
    )
    submit = SubmitField("Add contact")


class NotifyContactsEmailForm(FlaskForm):
    notify_contacts_email = BooleanField(
        "Allow BMW to email my trusted contacts when I request a check-in",
        default=False,
    )
    submit = SubmitField("Save email consent")


class CheckInOnMeForm(FlaskForm):
    message = TextAreaField(
        "Optional note",
        validators=[Optional(), Length(max=500)],
        render_kw={
            "rows": 3,
            "placeholder": "Optional note included in the email if you have consent enabled (no clinical scores)",
        },
    )
    submit = SubmitField("Record check-in request")


class PersonalizationForm(FlaskForm):
    emphasize_tags = SelectMultipleField(
        "Show me more of",
        choices=TAG_CHOICES,
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )
    steer_clear_tags = SelectMultipleField(
        "Show me less of (when it is safe to soften)",
        choices=TAG_CHOICES,
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )
    submit = SubmitField("Save preferences")


class AiWellnessForm(FlaskForm):
    message = TextAreaField(
        "What's on your mind?",
        validators=[DataRequired(), Length(min=2, max=3000)],
        render_kw={
            "rows": 6,
            "placeholder": "A few sentences about your day, mood, or something you’re sitting with…",
        },
    )
    submit = SubmitField("Get a supportive reflection")


class CulturalPrefsForm(FlaskForm):
    tone_preset = SelectField(
        "Language tone",
        choices=[(k, TONE_LABELS[k]) for k in TONE_PRESETS],
        validators=[DataRequired()],
    )
    highlight_representation = BooleanField(
        "Show optional diverse voices & wellness media picks on my care plan",
        default=True,
    )
    submit = SubmitField("Save cultural preferences")

class AiJournalConsentForm(FlaskForm):
    ai_journal_consent = BooleanField(
        "Save my AI Wellness messages as a private journal on my account",
        default=False,
    )
    submit = SubmitField("Save journal preference")


class AiJournalClearForm(FlaskForm):
    submit = SubmitField("Clear journal history")



class DeletionRequestForm(FlaskForm):
    email = StringField("Email on your BMW account", validators=[DataRequired(), Email(), Length(max=255)])
    reason = TextAreaField(
        "Reason (optional)",
        validators=[Optional(), Length(max=1000)],
        render_kw={"rows": 3, "placeholder": "Optional — helps us improve BMW"},
    )
    # Honeypot: real users never see or fill this field.
    website = StringField("Leave this field empty", validators=[Optional(), Length(max=200)])
    confirm = BooleanField(
        "I understand my BMW account and its data will be permanently deleted.",
        validators=[DataRequired(message="Please confirm to continue.")],
    )
    submit = SubmitField("Request account deletion")


class DeleteAccountNowForm(FlaskForm):
    password = PasswordField("Re-enter your password", validators=[DataRequired()])
    confirm = BooleanField(
        "I understand this permanently deletes my account and all of its data right now. This cannot be undone.",
        validators=[DataRequired(message="Please confirm to continue.")],
    )
    submit = SubmitField("Delete my account now")


AI_REPORT_REASONS = [
    ("offensive", "Offensive or hateful"),
    ("harmful", "Harmful or unsafe advice"),
    ("inaccurate", "Inaccurate or misleading"),
    ("other", "Something else"),
]


class AiContentReportForm(FlaskForm):
    """Report/flag an AI Wellness reply (Google Play AI-generated content policy)."""

    reason = SelectField("What's wrong with this reply?", choices=AI_REPORT_REASONS, validators=[DataRequired()])
    note = TextAreaField(
        "Details (optional)",
        validators=[Optional(), Length(max=1000)],
        render_kw={"rows": 2, "maxlength": 1000, "placeholder": "Optional — tell us what was wrong"},
    )
    source = StringField(validators=[DataRequired(), Length(max=20)])
    ai_text = TextAreaField(validators=[Optional(), Length(max=20000)])
    prompt_text = TextAreaField(validators=[Optional(), Length(max=20000)])
    journal_entry_id = IntegerField(validators=[Optional()])
    include_prompt = BooleanField("Include my message so reviewers have context", default=False)
    submit = SubmitField("Send report")
