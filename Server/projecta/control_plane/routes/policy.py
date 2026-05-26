"""Policy, preferences, and legal routes."""

from __future__ import annotations


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    if route_path.startswith("/player-preferences/v1/data-json/"):
        ctx.write(200, {})
    elif route_path == "/anti-addiction/v1/products/ares/policies/shutdown/anti-addiction-state":
        ctx.write(200, cp.anti_addiction_state_payload("shutdown"))
    elif route_path == "/anti-addiction/v1/products/ares/policies/playtime/anti-addiction-state":
        ctx.write(200, cp.anti_addiction_state_payload("playTime"))
    elif route_path == "/anti-addiction/v1/products/ares/policies/warningMessage/anti-addiction-state":
        ctx.write(200, cp.anti_addiction_state_payload("warningMessage"))
    elif route_path.startswith("/eula/v1/") or route_path.startswith("/legal/v1/"):
        ctx.write(200, {"content": "", "version": cp.CLIENT_VERSION, "locale": "en_US"})
    else:
        return False
    return True
