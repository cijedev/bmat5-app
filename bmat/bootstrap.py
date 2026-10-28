from __future__ import annotations

import os
from flask import current_app
from .extensions import db
from .models import User

def ensure_admin_bootstrap() -> None:
    """Create an admin account once using env vars.
    ADMIN_EMAIL, ADMIN_PASSWORD, optional ADMIN_NAME
    """
    email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    pw = os.getenv("ADMIN_PASSWORD") or ""
    name = (os.getenv("ADMIN_NAME") or "Admin").strip() or "Admin"

    if not email or not pw:
        return

    existing = User.query.filter_by(email=email).first()
    if existing:
        if existing.role != "admin":
            existing.role = "admin"
            db.session.commit()
        return

    admin = User(email=email, display_name=name, role="admin")
    admin.set_password(pw)
    db.session.add(admin)
    db.session.commit()
    current_app.logger.info("Admin created via bootstrap.")
