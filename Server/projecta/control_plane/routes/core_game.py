"""Core-game routes."""

from __future__ import annotations

import re


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    game_state = ctx.game_state
    if re.match(r"^/core-game/v1/players/[^/]+/fixsession$", route_path):
        game_state["phase"] = "core"
        game_state["pregame_state"] = "provisioned"
        profile = ctx.current_profile()
        current_party_profiles = cp.party_profiles(game_state, cp.party_id_for_profile(profile), profile)
        cp.prime_backend_state_for_phase(game_state, current_party_profiles, "core")
        ctx.bump_match()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.core_game_player_payload(game_state, profile), localize=False)
    elif re.match(r"^/core-game/v1/players/[^/]+/disassociate/", route_path):
        ctx.write(200, {"ok": True})
    elif route_path.startswith("/core-game/v1/players/"):
        profile = ctx.current_profile()
        if game_state.get("phase") == "core" and cp.mark_backend_ready(game_state, profile, "core"):
            ctx.send_backend_state_to_profile(profile)
        if game_state.get("phase") == "core":
            ctx.write(200, cp.core_game_player_payload(game_state, profile), localize=False)
        else:
            ctx.write(200, cp.inactive_match_player_payload(profile), localize=False)
    elif re.match(r"^/core-game/v1/matches/[^/]+/allchatmuctoken$", route_path):
        ctx.write(200, cp.chat_token_payload(cp.ALL_MUC_NAME))
    elif re.match(r"^/core-game/v1/matches/[^/]+/teamchatmuctoken$", route_path):
        ctx.write(200, cp.chat_token_payload(cp.TEAM_MUC_NAME))
    elif re.match(r"^/core-game/v1/matches/[^/]+/teamvoicetoken$", route_path):
        ctx.write(200, cp.voice_token_payload(cp.TEAM_VOICE_ID))
    elif route_path in {"/core-game/v1/provisionfailures", "/core-game/v1/provisionversionfailures"}:
        ctx.write(200, {"ok": True})
    elif route_path in {"/ares-core-game/core-game/v1/provisionfailures", "/ares-core-game/core-game/v1/provisionversionfailures"}:
        ctx.write(200, {"ok": True})
    elif re.match(r"^/core-game/v1/matches/[^/]+/rematch/", route_path):
        ctx.write(200, {"ok": True})
    elif route_path.startswith("/core-game/v1/matches/"):
        if game_state.get("phase") == "core":
            ctx.write(200, cp.core_game_match_payload(game_state, ctx.current_profile()), localize=False)
        elif game_state.get("phase") == "pregame" and game_state.get("pregame_state") == "provisioned":
            game_state["phase"] = "core"
            ctx.bump_match()
            ctx.broadcast_backend_state_update()
            ctx.write(200, cp.core_game_match_payload(game_state, ctx.current_profile()), localize=False)
        else:
            ctx.write(200, cp.inactive_match_payload())
    else:
        return False
    return True
