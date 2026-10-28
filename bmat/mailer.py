"""Outbound email via local Postfix (SMTP to localhost).

Configured with MAIL_ENABLED, MAIL_FROM, MAIL_SMTP_HOST, MAIL_SMTP_PORT.
Never include clinical scores or PHI beyond display name + optional user message.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Iterable

from flask import current_app

logger = logging.getLogger(__name__)

APP_HOME_URL = "https://cije.live/bmw/"


def mail_enabled() -> bool:
    raw = (current_app.config.get("MAIL_ENABLED") or os.getenv("MAIL_ENABLED") or "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def mail_from() -> str:
    return (
        current_app.config.get("MAIL_FROM")
        or os.getenv("MAIL_FROM")
        or "noreply@cije.live"
    ).strip()


def _smtp_host_port() -> tuple[str, int]:
    host = (
        current_app.config.get("MAIL_SMTP_HOST")
        or os.getenv("MAIL_SMTP_HOST")
        or "127.0.0.1"
    ).strip()
    port_raw = (
        current_app.config.get("MAIL_SMTP_PORT")
        or os.getenv("MAIL_SMTP_PORT")
        or "25"
    )
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        port = 25
    return host, port


def build_check_in_email(*, display_name: str, user_message: str | None) -> tuple[str, str]:
    """Return (subject, plain-text body). No PHQ/GAD or clinical data."""
    name = (display_name or "A Better Mental Wellness user").strip() or "A Better Mental Wellness user"
    subject = f"Check-in request from {name} via Better Mental Wellness"
    lines = [
        f"{name} asked Better Mental Wellness (BMW) to let you know they would like a check-in.",
        "",
    ]
    note = (user_message or "").strip()
    if note:
        lines.extend(["Their note:", note, ""])
    lines.extend(
        [
            "This is not a crisis hotline and BMW is not a substitute for emergency services.",
            "If you are worried about their safety, contact them directly or local emergency services.",
            "",
            "Please reach out to them in whatever way you normally would.",
            "",
            f"Learn more about BMW: {APP_HOME_URL}",
            "",
            "— Better Mental Wellness on cije.live",
        ]
    )
    return subject, "\n".join(lines)


def send_plain_email(*, to_addr: str, subject: str, body: str) -> None:
    """Send one plain-text message via local SMTP. Raises on failure."""
    to_addr = (to_addr or "").strip()
    if not to_addr:
        raise ValueError("empty recipient")
    if not mail_enabled():
        raise RuntimeError("MAIL_ENABLED is off")

    msg = EmailMessage()
    msg["From"] = mail_from()
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    host, port = _smtp_host_port()
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.send_message(msg)


def send_check_in_notifications(
    *,
    display_name: str,
    user_message: str | None,
    recipients: Iterable[str],
) -> dict:
    """
    Send check-in emails to each recipient.

    Returns dict with keys: sent (list), failed (list of {email, error}), skipped (bool if mail disabled).
    """
    result: dict = {"sent": [], "failed": [], "skipped": False, "disabled": False}
    addrs = []
    seen = set()
    for raw in recipients:
        addr = (raw or "").strip()
        if not addr:
            continue
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        addrs.append(addr)

    if not addrs:
        return result

    if not mail_enabled():
        result["skipped"] = True
        result["disabled"] = True
        return result

    subject, body = build_check_in_email(display_name=display_name, user_message=user_message)
    for addr in addrs:
        try:
            send_plain_email(to_addr=addr, subject=subject, body=body)
            result["sent"].append(addr)
        except Exception as exc:  # noqa: BLE001 — fail soft per recipient
            logger.exception("check-in email failed for %s", addr)
            result["failed"].append({"email": addr, "error": str(exc)[:200]})
    return result
