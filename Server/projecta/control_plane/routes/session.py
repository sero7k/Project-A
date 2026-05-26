"""Session and heartbeat routes."""

from __future__ import annotations

import re


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    if re.match(r"^/session/v\d+/sessions/[^/]+/heartbeat$", route_path):
        profile = ctx.current_profile()
        sessions = ctx.game_state.setdefault("session_by_profile", {})
        if isinstance(sessions, dict):
            heartbeat = ctx.json_body if isinstance(ctx.json_body, dict) else {}
            sessions[profile["key"]] = {
                "last_heartbeat": cp.utc_now(),
                "client_loop_state": heartbeat.get("LoopState") or heartbeat.get("loopState") or "",
                "client_loop_state_metadata": heartbeat.get("LoopStateMetadata") or heartbeat.get("loopStateMetadata") or "",
            }
        ctx.broadcast_presence_update()
        ctx.write(200, cp.session_payload(ctx.game_state, profile), localize=False)
    elif route_path.startswith("/session/v"):
        ctx.write(200, cp.session_payload(ctx.game_state, ctx.current_profile()), localize=False)
    else:
        return False
    return True
