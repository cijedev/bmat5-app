from __future__ import annotations

from flask import request
from flask_login import current_user
from flask_socketio import join_room, leave_room, emit, disconnect

from .extensions import socketio

# Simple in-memory room registry for single-process development.
# For production: use Redis (message queue) + sticky sessions.
ROOMS: dict[str, dict[str, str | None]] = {}  # room -> {"broadcaster_sid": sid|None}

_BLOCKED_ROOMS = frozenset({
    "BMW123", "BMW", "TEST", "ROOM", "123456", "DEFAULT", "DEMO", "SHARE",
})


@socketio.on("connect")
def on_connect(_auth=None):
    """Require an authenticated Flask-Login session before Socket.IO use."""
    if not current_user.is_authenticated:
        return False
    return True


def _require_auth() -> bool:
    if not current_user.is_authenticated:
        disconnect()
        return False
    return True


@socketio.on("webrtc_join")
def webrtc_join(data):
    if not _require_auth():
        return
    data = data or {}
    room = (data.get("room") or "").strip()
    role = (data.get("role") or "").strip()
    if not room:
        return
    if room.upper() in _BLOCKED_ROOMS or len(room) < 8:
        emit("webrtc_error", {"error": "Use a non-guessable room code (8+ characters)."})
        return

    join_room(room)
    ROOMS.setdefault(room, {"broadcaster_sid": None})

    if role == "broadcaster":
        ROOMS[room]["broadcaster_sid"] = request.sid
        emit("webrtc_ready", {}, to=room)
    elif role == "viewer":
        bc = ROOMS[room].get("broadcaster_sid")
        if bc:
            emit("webrtc_ready", {}, to=bc)


@socketio.on("webrtc_leave")
def webrtc_leave(data):
    if not _require_auth():
        return
    data = data or {}
    room = (data.get("room") or "").strip()
    if not room:
        return
    leave_room(room)

    if room in ROOMS and ROOMS[room].get("broadcaster_sid") == request.sid:
        emit("webrtc_end", {}, to=room)
        ROOMS[room]["broadcaster_sid"] = None


@socketio.on("webrtc_offer")
def webrtc_offer(data):
    if not _require_auth():
        return
    data = data or {}
    room = (data.get("room") or "").strip()
    sdp = data.get("sdp")
    if room and sdp:
        emit("webrtc_offer", {"sdp": sdp}, to=room, include_self=False)


@socketio.on("webrtc_answer")
def webrtc_answer(data):
    if not _require_auth():
        return
    data = data or {}
    room = (data.get("room") or "").strip()
    sdp = data.get("sdp")
    if room and sdp:
        emit("webrtc_answer", {"sdp": sdp}, to=room, include_self=False)


@socketio.on("webrtc_ice")
def webrtc_ice(data):
    if not _require_auth():
        return
    data = data or {}
    room = (data.get("room") or "").strip()
    candidate = data.get("candidate")
    if room and candidate:
        emit("webrtc_ice", {"candidate": candidate}, to=room, include_self=False)
