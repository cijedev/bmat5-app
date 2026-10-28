from __future__ import annotations

import os
from typing import Callable


class ScriptNameMiddleware:
    """Honor reverse-proxy prefix so the app can live under /bmw (or similar).

    Priority for SCRIPT_NAME:
      1. X-Script-Name
      2. X-Forwarded-Prefix
      3. default_script_name (from APPLICATION_ROOT)
      4. existing SCRIPT_NAME

    When Apache already strips the prefix before proxying, only SCRIPT_NAME is set
    (PATH_INFO is left alone). If PATH_INFO still begins with the script name,
    it is stripped so Flask routing stays correct.
    """

    def __init__(self, app: Callable, default_script_name: str | None = None):
        self.app = app
        self.default_script_name = (default_script_name or "").rstrip("/") or None

    def __call__(self, environ, start_response):
        script_name = (
            (environ.get("HTTP_X_SCRIPT_NAME") or "").strip()
            or (environ.get("HTTP_X_FORWARDED_PREFIX") or "").strip()
            or (self.default_script_name or "")
            or (environ.get("SCRIPT_NAME") or "").strip()
        )
        script_name = script_name.rstrip("/")
        if script_name and not script_name.startswith("/"):
            script_name = "/" + script_name

        if script_name:
            environ["SCRIPT_NAME"] = script_name
            path_info = environ.get("PATH_INFO") or ""
            if path_info == script_name or path_info.startswith(script_name + "/"):
                environ["PATH_INFO"] = path_info[len(script_name):] or "/"

        return self.app(environ, start_response)


def application_root_from_env() -> str:
    root = (os.getenv("APPLICATION_ROOT") or "").strip().rstrip("/")
    if root and not root.startswith("/"):
        root = "/" + root
    return root
