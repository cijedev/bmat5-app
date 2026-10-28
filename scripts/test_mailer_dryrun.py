#!/usr/bin/env python3
"""Dry-run / optional live smoke for Phase 5 mailer.

Usage (from app root, with venv if present):
  MAIL_ENABLED=0 python scripts/test_mailer_dryrun.py
  MAIL_ENABLED=1 MAIL_TO=you@example.com python scripts/test_mailer_dryrun.py --send
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="Actually SMTP-send (requires MAIL_TO)")
    args = parser.parse_args()

    os.environ.setdefault("BMAT_ENV", "development")
    os.environ.setdefault("SECRET_KEY", "dev-phase5-mailer-test-key")
    os.environ.setdefault("MAIL_ENABLED", os.getenv("MAIL_ENABLED") or "0")
    os.environ.setdefault("MAIL_FROM", os.getenv("MAIL_FROM") or "noreply@cije.live")
    os.environ.setdefault("MAIL_SMTP_HOST", "127.0.0.1")
    os.environ.setdefault("MAIL_SMTP_PORT", "25")

    from bmat import create_app
    from bmat.mailer import build_check_in_email, mail_enabled, send_check_in_notifications

    app = create_app()
    with app.app_context():
        subj, body = build_check_in_email(
            display_name="Smoke Tester",
            user_message="Please check in when you can.",
        )
        assert "Smoke Tester" in subj
        assert "PHQ" not in body and "GAD" not in body
        assert "cije.live/bmw" in body
        print("subject:", subj)
        print("--- body ---")
        print(body)
        print("---")
        print("mail_enabled:", mail_enabled())

        if not args.send:
            print("dry-run OK (pass --send with MAIL_TO=... to live-send)")
            return 0

        to_addr = (os.getenv("MAIL_TO") or "").strip()
        if not to_addr:
            print("MAIL_TO required with --send", file=sys.stderr)
            return 2
        if not mail_enabled():
            print("Set MAIL_ENABLED=1 for --send", file=sys.stderr)
            return 2
        result = send_check_in_notifications(
            display_name="Smoke Tester",
            user_message="Please check in when you can.",
            recipients=[to_addr],
        )
        print("result:", result)
        return 0 if result.get("sent") else 1


if __name__ == "__main__":
    raise SystemExit(main())
