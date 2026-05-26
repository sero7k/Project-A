"""Content-service routes."""

from __future__ import annotations


def handle(ctx) -> bool:
    from .. import app as cp

    if ctx.route_path != "/content-service/v2/content":
        return False
    ctx.write(200, cp.content_service_payload(ctx.game_state), localize=False)
    return True
