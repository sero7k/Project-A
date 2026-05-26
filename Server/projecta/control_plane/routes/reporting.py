"""Reporting and match-history/detail routes."""

from __future__ import annotations


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    if route_path.rstrip("/") == "/player-reporting/v1/report":
        ctx.write(200, cp.player_report_payload(ctx.json_body, ctx.current_profile()), localize=False)
    elif route_path.startswith("/match-history/v1/history/"):
        ctx.write(200, cp.match_history_payload(ctx.current_profile()))
    elif route_path.startswith("/match-details/v1/matches/") or route_path.startswith("/ares-match-details/match-details/v1/matches/"):
        ctx.write(200, cp.match_details_payload())
    else:
        return False
    return True
