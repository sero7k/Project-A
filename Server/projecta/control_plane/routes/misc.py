"""Small miscellaneous routes."""

from __future__ import annotations


def handle(ctx) -> bool:
    from .. import app as cp

    if ctx.route_path == "/wegame-integration/v1/player-info":
        ctx.write(200, cp.wegame_player_info_payload())
    elif ctx.route_path == "/system/v1/builds":
        ctx.write(200, {"version": cp.CLIENT_VERSION, "builds": []})
    else:
        return False
    return True
