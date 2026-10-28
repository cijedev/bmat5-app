from __future__ import annotations

import os
os.environ.setdefault("BMAT_SCREENSHARE_ENABLED", "1")

from bmat import create_app
from bmat.extensions import socketio

app = create_app()

if __name__ == "__main__":
    # Threading mode works on Windows without eventlet/gevent.
    socketio.run(app, host="0.0.0.0", port=5030, debug=True)
