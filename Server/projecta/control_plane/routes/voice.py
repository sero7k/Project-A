"""Voice chat routes."""

from __future__ import annotations


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    if route_path == "/voice-chat/v2/sessions":
        if ctx.command == "GET":
            ctx.write(200, cp.voice_sessions_payload(ctx.game_state, ctx.current_profile()), localize=False)
        else:
            ctx.write(200, cp.voice_session_payload(ctx.game_state, ctx.current_profile()), localize=False)
    elif route_path.startswith("/voice-chat/v2/sessions/"):
        ctx.write(200, cp.voice_session_participants_payload(ctx.game_state, ctx.current_profile()), localize=False)
    elif route_path in {"/voice-chat/v2/devices/capture", "/voice-chat/v2/devices/render"}:
        ctx.write(200, [])
    elif route_path == "/voice-chat/v2/settings":
        ctx.write(200, {"inputMode": "push_to_talk", "muted": False, "volume": 1.0})
    elif route_path == "/voice-chat/v1/audio-properties":
        ctx.write(200, {})
    elif route_path == "/voice-chat/v1/push-to-talk":
        ctx.write(200, {"ok": True})
    else:
        return False
    return True
