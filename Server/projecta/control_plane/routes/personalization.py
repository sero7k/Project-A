"""Personalization and loadout routes."""

from __future__ import annotations

import re


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    if not re.match(r"^/personalization/v[12]/players/[^/]+/playerloadout$", route_path):
        return False

    profile = ctx.current_profile()
    loadouts = ctx.game_state.setdefault("player_loadout_by_profile", {})
    if ctx.command in {"PUT", "POST", "PATCH"} and ctx.json_body:
        persisted_loadout = cp.player_loadout_payload(ctx.json_body, profile)
        loadouts[profile["key"]] = persisted_loadout
        try:
            cp.ACCOUNT_STORE.save_player_loadout(profile["key"], persisted_loadout)
        except Exception:
            pass
    loadout = loadouts.get(profile["key"]) or ctx.game_state.get("player_loadout")
    if not loadout:
        try:
            loadout = cp.ACCOUNT_STORE.get_player_loadout(profile["key"])
        except Exception:
            loadout = None
    ctx.write(200, cp.player_loadout_payload(loadout, profile), localize=False)
    return True
