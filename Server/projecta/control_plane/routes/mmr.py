"""MMR routes."""

from __future__ import annotations

import re


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    if re.match(r"^/mmr/v1/players/[^/]+/competitiveupdates$", route_path) or re.match(r"^/ares-mmr/mmr/v1/players/[^/]+/competitiveupdates$", route_path):
        ctx.write(200, cp.competitive_updates_payload(ctx.current_profile()))
    elif route_path.startswith("/mmr/v1/players/") or route_path.startswith("/ares-mmr/mmr/v1/players/"):
        current = ctx.current_profile()
        ctx.write(200, {"Subject": current["subject"], "Version": 0, "QueueSkills": {}, "LatestCompetitiveUpdate": {}})
    else:
        return False
    return True
