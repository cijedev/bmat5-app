from __future__ import annotations

import mimetypes
import os
import sys
from flask import Flask
from dotenv import load_dotenv

from .extensions import csrf, db, login_manager, socketio
from .bootstrap import ensure_admin_bootstrap
from .middleware import application_root_from_env


WEAK_SECRET_KEYS = frozenset(
    {
        "",
        "dev-change-me",
        "dev-change-me",
        "changeme",
        "change-me",
        "change_me",
        "secret",
        "secret-key",
        "secret_key",
        "your-secret-key",
        "your_secret_key",
        "bmat-dev-secret",
        "bmat-secret",
        "dev",
        "development",
        "test",
        "testing",
        "password",
    }
)


def _env_name() -> str:
    return (
        (os.getenv("BMAT_ENV") or os.getenv("FLASK_ENV") or "")
        .strip()
        .lower()
    )


def _is_development() -> bool:
    name = _env_name()
    if name in ("development", "dev", "local"):
        return True
    debug = (os.getenv("FLASK_DEBUG") or "").strip().lower()
    return debug in ("1", "true", "yes")


def _is_weak_secret(secret: str | None) -> bool:
    key = (secret or "").strip()
    if not key:
        return True
    if key.lower() in WEAK_SECRET_KEYS:
        return True
    if len(key) < 16:
        return True
    return False


def _require_production_secret() -> str:
    secret = os.getenv("SECRET_KEY")
    if _is_weak_secret(secret):
        sys.stderr.write(
            "FATAL: SECRET_KEY is missing or weak. Set a strong SECRET_KEY "
            "(at least 16 characters; not a placeholder like dev-change-me/changeme) "
            "before starting outside development.\n"
            "Hint: BMAT_ENV=development allows a local/dev key for testing only.\n"
        )
        raise SystemExit(2)
    return (secret or "").strip()


def _cors_origins(*, is_dev: bool):
    raw = (os.getenv("BMAT_CORS_ORIGINS") or os.getenv("BMAT_CORS_ORIGINS") or "").strip()
    if raw:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        if origins == ["*"] and not is_dev:
            sys.stderr.write(
                "FATAL: BMAT_CORS_ORIGINS=* is not allowed outside development.\n"
            )
            raise SystemExit(2)
        return origins
    if is_dev:
        return "*"
    return []


def create_app() -> Flask:
    load_dotenv()

    mimetypes.add_type("video/mp4", ".mp4", strict=True)
    mimetypes.add_type(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
        strict=True,
    )
    mimetypes.add_type(
        "application/vnd.openxmlformats-officedocument.presentationml.slideshow",
        ".ppsx",
        strict=True,
    )
    mimetypes.add_type("application/manifest+json", ".webmanifest", strict=True)

    is_dev = _is_development()
    app = Flask(__name__, instance_relative_config=True)

    if is_dev:
        secret = (os.getenv("SECRET_KEY") or "dev-change-me").strip()
        app.config["SECRET_KEY"] = secret or "dev-change-me"
    else:
        app.config["SECRET_KEY"] = _require_production_secret()

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(app.instance_path, 'bmat.db')}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["WTF_CSRF_TIME_LIMIT"] = None
    app.config["OPENAI_API_KEY"] = (os.getenv("OPENAI_API_KEY") or "").strip()
    # OpenAI-compatible base URL (Groq: https://api.groq.com/openai/v1). Empty = official OpenAI.
    app.config["OPENAI_BASE_URL"] = (os.getenv("OPENAI_BASE_URL") or "").strip()
    app.config["OPENAI_MODEL"] = (
        os.getenv("OPENAI_MODEL") or os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile"
    ).strip()
    try:
        app.config["AI_DAILY_LIMIT"] = int(os.getenv("AI_DAILY_LIMIT") or "20")
    except ValueError:
        app.config["AI_DAILY_LIMIT"] = 20

    # Phase 5: local Postfix / Mailbaby relay via SMTP to localhost
    app.config["MAIL_ENABLED"] = (os.getenv("MAIL_ENABLED") or "0").strip()
    app.config["MAIL_FROM"] = (os.getenv("MAIL_FROM") or "noreply@cije.live").strip()
    app.config["MAIL_SMTP_HOST"] = (os.getenv("MAIL_SMTP_HOST") or "127.0.0.1").strip()
    try:
        app.config["MAIL_SMTP_PORT"] = int(os.getenv("MAIL_SMTP_PORT") or "25")
    except ValueError:
        app.config["MAIL_SMTP_PORT"] = 25

    app_root = application_root_from_env()
    if app_root:
        app.config["APPLICATION_ROOT"] = app_root
        app.config["SESSION_COOKIE_PATH"] = app_root

    screenshare_env = (os.getenv("BMAT_SCREENSHARE_ENABLED") or "").strip().lower()
    if screenshare_env in ("1", "true", "yes", "on"):
        app.config["BMAT_SCREENSHARE_ENABLED"] = True
    elif screenshare_env in ("0", "false", "no", "off"):
        app.config["BMAT_SCREENSHARE_ENABLED"] = False
    else:
        # Default: on in development (socketio.run); off under Waitress/production.
        app.config["BMAT_SCREENSHARE_ENABLED"] = is_dev

    app.config["BMAT_IS_DEVELOPMENT"] = is_dev
    app.config["BMAT_CORS_ORIGINS"] = _cors_origins(is_dev=is_dev)

    # Color scheme: default | beach (templates use data-theme=COLOR_SCHEME)
    _scheme = (os.getenv("COLOR_SCHEME") or "beach").strip().lower()
    if _scheme not in ("default", "beach"):
        _scheme = "beach"
    app.config["COLOR_SCHEME"] = _scheme


    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "media", "slideshows"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    cors = app.config["BMAT_CORS_ORIGINS"]
    socketio.init_app(app, cors_allowed_origins=cors if cors != [] else [])

    from .routes import bp
    import bmat.sockets  # noqa: F401
    app.register_blueprint(bp)

    with app.app_context():
        from . import models  # noqa
        from .schema_migrate import ensure_additive_columns

        db.create_all()
        ensure_additive_columns()
        ensure_admin_bootstrap()

    return app
