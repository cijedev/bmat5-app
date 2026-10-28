#!/usr/bin/env python3
"""
Retention cleanup for analytics tables.

Default behavior:
  - Delete VisitEvent rows older than 90 days
  - Delete VisitSession rows older than 180 days (only if they have no events)

Usage:
  python scripts/cleanup_analytics.py
  python scripts/cleanup_analytics.py --events-days 60 --sessions-days 120 --dry-run
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup BMW analytics retention data")
    parser.add_argument("--events-days", type=int, default=90, help="Delete events older than this many days")
    parser.add_argument(
        "--sessions-days",
        type=int,
        default=180,
        help="Delete sessions older than this many days (no events attached)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show counts without deleting")
    args = parser.parse_args()

    if args.events_days < 1 or args.sessions_days < 1:
        raise SystemExit("events-days and sessions-days must be >= 1")

    import sys

    sys.path.insert(0, str(ROOT))
    from bmat import create_app
    from bmat.extensions import db
    from bmat.models import VisitEvent, VisitSession

    app = create_app()
    with app.app_context():
        cutoff_events = datetime.now() - timedelta(days=args.events_days)
        cutoff_sessions = datetime.now() - timedelta(days=args.sessions_days)

        old_events_q = VisitEvent.query.filter(VisitEvent.created_at < cutoff_events)
        old_events_count = old_events_q.count()

        stale_sessions_q = (
            VisitSession.query.outerjoin(VisitEvent, VisitSession.session_id == VisitEvent.session_id)
            .filter(VisitSession.last_seen_at < cutoff_sessions)
            .group_by(VisitSession.id)
            .having(func.count(VisitEvent.id) == 0)
        )
        stale_sessions = stale_sessions_q.with_entities(VisitSession.id).all()
        stale_session_ids = [row[0] for row in stale_sessions]
        stale_sessions_count = len(stale_session_ids)

        print(f"Old events: {old_events_count}")
        print(f"Stale sessions (no events): {stale_sessions_count}")
        print(f"Dry run: {args.dry_run}")

        if args.dry_run:
            return 0

        # Delete events first; then sessions that no longer have events.
        deleted_events = old_events_q.delete(synchronize_session=False)
        deleted_sessions = 0
        if stale_session_ids:
            deleted_sessions = (
                VisitSession.query.filter(VisitSession.id.in_(stale_session_ids)).delete(synchronize_session=False)
            )
        db.session.commit()
        print(f"Deleted events: {deleted_events}")
        print(f"Deleted sessions: {deleted_sessions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
