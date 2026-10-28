"""Waitress production entry with /bmw ScriptNameMiddleware.

Compatible with Apache headers:
  RequestHeader set X-Script-Name "/bmw"
  RequestHeader set X-Forwarded-Prefix "/bmw"

If Apache already strips /bmw before proxying, APPLICATION_ROOT=/bmw
(or the default below) still sets SCRIPT_NAME so url_for / cookies stay correct.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Waitress production gate: keep screenshare off unless explicitly enabled.
os.environ.setdefault("BMAT_SCREENSHARE_ENABLED", "0")

from bmat import create_app
from bmat.middleware import ScriptNameMiddleware, application_root_from_env

_flask_app = create_app()
_root = application_root_from_env() or "/bmw"
app = ScriptNameMiddleware(_flask_app, default_script_name=_root)

if __name__ == "__main__":
    host = (os.getenv("BMAT_HOST") or "127.0.0.1").strip()
    try:
        port = int((os.getenv("BMAT_PORT") or "5000").strip())
        threads = int((os.getenv("BMAT_WAITRESS_THREADS") or "16").strip())
    except ValueError:
        raise SystemExit("BMAT_PORT and BMAT_WAITRESS_THREADS must be integers.") from None
    if not (1 <= port <= 65535):
        raise SystemExit("BMAT_PORT must be between 1 and 65535.")
    if threads < 1:
        raise SystemExit("BMAT_WAITRESS_THREADS must be at least 1.")
    from waitress import serve

    serve(app, host=host, port=port, threads=threads)
