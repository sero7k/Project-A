"""Matchmaking queue routes."""

from __future__ import annotations

import re
from urllib.parse import unquote


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    if route_path == "/matchmaking/v1/queues/configs":
        ctx.write(200, cp.queue_configs_payload())
    elif route_path.startswith("/matchmaking/v1/queues/"):
        match = re.match(r"^/matchmaking/v1/queues/([^/]+)(?:/[^/]+)?/?$", route_path)
        queue = cp.queue_config_by_id(unquote(match.group(1))) if match else None
        ctx.write(200, cp.queue_config_response(queue) if queue else cp.queue_configs_payload())
    else:
        return False
    return True
