"""SQLite-friendly additive schema evolution (ALTER TABLE IF missing).

Preserves existing data; safe to run on every startup after db.create_all().
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from .extensions import db

logger = logging.getLogger(__name__)

# New tables (e.g. deletion_request and ai_content_report, added Oct 2026) are created by db.create_all() on
# startup; it only creates missing tables and never alters or drops existing ones.
# List columns here when a later change adds a column to an existing table.
# table -> list of (column_name, SQL type + constraints for ADD COLUMN)
_ADDITIVE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "user": [
        ("notify_contacts_email", "BOOLEAN NOT NULL DEFAULT 0"),
        ("notify_contacts_email_at", "DATETIME"),
        ("ai_journal_consent", "BOOLEAN NOT NULL DEFAULT 0"),
        ("ai_journal_consent_at", "DATETIME"),
        ("age_confirmed_at", "DATETIME"),
    ],
    "trusted_contact": [
        ("email_on_check_in", "BOOLEAN NOT NULL DEFAULT 0"),
    ],
    "check_in_on_me_request": [
        ("notify_email_status", "VARCHAR(40)"),
        ("notify_email_sent_count", "INTEGER NOT NULL DEFAULT 0"),
        ("notify_email_at", "DATETIME"),
    ],
    "clinical_review": [
        ("review_type", "VARCHAR(40) NOT NULL DEFAULT 'note'"),
        ("reason_code", "VARCHAR(80)"),
    ],
    "deletion_request": [
        ("notify_email_status", "VARCHAR(40)"),
        ("processed_at", "DATETIME"),
        ("admin_note", "VARCHAR(255)"),
    ],
}


def ensure_additive_columns() -> None:
    """Add missing columns without wiping the DB."""
    bind = db.engine
    insp = inspect(bind)
    existing_tables = set(insp.get_table_names())

    for table, cols in _ADDITIVE_COLUMNS.items():
        if table not in existing_tables:
            continue
        have = {c["name"] for c in insp.get_columns(table)}
        for col_name, col_ddl in cols:
            if col_name in have:
                continue
            ddl = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_ddl}"
            logger.info("schema migrate: %s", ddl)
            with bind.begin() as conn:
                conn.execute(text(ddl))

    _ensure_clinical_review_nullable_admin()


def _ensure_clinical_review_nullable_admin() -> None:
    """Allow system escalations (admin_user_id NULL). SQLite needs a table rebuild."""
    bind = db.engine
    insp = inspect(bind)
    if "clinical_review" not in set(insp.get_table_names()):
        return

    cols = {c["name"]: c for c in insp.get_columns("clinical_review")}
    admin_col = cols.get("admin_user_id")
    if not admin_col:
        return
    # already nullable
    if admin_col.get("nullable", False):
        return

    dialect = bind.dialect.name
    if dialect != "sqlite":
        logger.info("schema migrate: ALTER clinical_review.admin_user_id DROP NOT NULL")
        with bind.begin() as conn:
            conn.execute(text("ALTER TABLE clinical_review ALTER COLUMN admin_user_id DROP NOT NULL"))
        return

    logger.info("schema migrate: rebuild clinical_review for nullable admin_user_id")
    with bind.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(
            text(
                """
                CREATE TABLE clinical_review__new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    admin_user_id INTEGER,
                    note TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    resolved_at DATETIME,
                    review_type VARCHAR(40) NOT NULL DEFAULT 'note',
                    reason_code VARCHAR(80),
                    FOREIGN KEY(user_id) REFERENCES user (id),
                    FOREIGN KEY(admin_user_id) REFERENCES user (id)
                )
                """
            )
        )
        # Copy existing rows; review_type/reason_code may already exist after additive migrate.
        have = set(cols.keys())
        select_review_type = "review_type" if "review_type" in have else "'note'"
        select_reason = "reason_code" if "reason_code" in have else "NULL"
        conn.execute(
            text(
                f"""
                INSERT INTO clinical_review__new
                    (id, user_id, admin_user_id, note, created_at, resolved_at, review_type, reason_code)
                SELECT id, user_id, admin_user_id, note, created_at, resolved_at,
                       COALESCE({select_review_type}, 'note'), {select_reason}
                FROM clinical_review
                """
            )
        )
        conn.execute(text("DROP TABLE clinical_review"))
        conn.execute(text("ALTER TABLE clinical_review__new RENAME TO clinical_review"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_clinical_review_user_id ON clinical_review (user_id)"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_clinical_review_admin_user_id ON clinical_review (admin_user_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_clinical_review_created_at ON clinical_review (created_at)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_clinical_review_resolved_at ON clinical_review (resolved_at)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_clinical_review_review_type ON clinical_review (review_type)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_clinical_review_reason_code ON clinical_review (reason_code)")
        )
        conn.execute(text("PRAGMA foreign_keys=ON"))
