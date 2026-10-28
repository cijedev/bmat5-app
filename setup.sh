#!/usr/bin/env bash
# BMW first-time setup on Linux / macOS (venv, pip, .env).
# Usage: chmod +x setup.sh && ./setup.sh
# Non-interactive: ADMIN_EMAIL=... ADMIN_PASSWORD=... ./setup.sh --non-interactive
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required on PATH."
  exit 1
fi
exec python3 "$ROOT/scripts/setup_bmat.py" "$@"
