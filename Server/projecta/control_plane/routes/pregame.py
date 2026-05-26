"""Pregame routes."""

from __future__ import annotations

import re


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    game_state = ctx.game_state
    if re.match(r"^/pregame/v1/players/[^/]+/fixsession$", route_path):
        if game_state.get("phase") not in {"pregame", "core"}:
            game_state["phase"] = "pregame"
        if game_state.get("party_state") == "SOLO_EXPERIENCE_STARTING":
            game_state["pregame_state"] = "provisioned"
        ctx.bump_match()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.pregame_player_payload(game_state, ctx.current_profile()), localize=False)
    elif route_path.startswith("/pregame/v1/players/"):
        profile = ctx.current_profile()
        if game_state.get("phase") in {"pregame", "core"} and cp.mark_backend_ready(game_state, profile, "pregame"):
            ctx.send_backend_state_to_profile(profile)
        if game_state.get("phase") in {"pregame", "core"}:
            ctx.write(200, cp.pregame_player_payload(game_state, profile), localize=False)
        else:
            ctx.write(200, cp.inactive_match_player_payload(profile), localize=False)
    elif route_path == "/pregame/v1/matches/" or route_path == "/pregame/v1/matches":
        if game_state.get("phase") in {"pregame", "core"}:
            ctx.write(200, cp.pregame_match_payload(game_state, ctx.current_profile()), localize=False)
        else:
            ctx.write(200, cp.inactive_match_payload())
    elif route_path == "/pregame/v1/matches//chattoken":
        ctx.write(200, cp.chat_token_payload(cp.TEAM_MUC_NAME))
    elif route_path == "/pregame/v1/matches//teamvoicetoken":
        ctx.write(200, cp.voice_token_payload(cp.TEAM_VOICE_ID))
    elif route_path == "/pregame/v1/matches//voicetoken":
        ctx.write(200, cp.voice_token_payload(cp.TEAM_VOICE_ID))
    elif re.match(r"^/pregame/v1/matches/[^/]+/chattoken$", route_path):
        ctx.write(200, cp.chat_token_payload(cp.TEAM_MUC_NAME))
    elif re.match(r"^/pregame/v1/matches/[^/]+/teamvoicetoken$", route_path):
        ctx.write(200, cp.voice_token_payload(cp.TEAM_VOICE_ID))
    elif re.match(r"^/pregame/v1/matches/[^/]+/voicetoken$", route_path):
        ctx.write(200, cp.voice_token_payload(cp.TEAM_VOICE_ID))
    elif re.match(r"^/pregame/v1/matches/[^/]+/select/[^/]+$", route_path):
        character_id = route_path.rsplit("/", 1)[-1]
        game_state["phase"] = "pregame"
        cp.set_character_for_profile(game_state, ctx.current_profile(), character_id, "selected")
        ctx.bump_match()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.pregame_match_payload(game_state, ctx.current_profile()), localize=False)
    elif re.match(r"^/pregame/v1/matches/[^/]+/lock/[^/]+$", route_path):
        character_id = route_path.rsplit("/", 1)[-1]
        profile = ctx.current_profile()
        game_state["phase"] = "pregame"
        cp.set_character_for_profile(game_state, profile, character_id, "locked")
        current_party_profiles = cp.party_profiles(game_state, cp.party_id_for_profile(profile), profile)
        if all(cp.character_state_for_profile(game_state, member_profile) == "locked" for member_profile in current_party_profiles):
            cp.transition_locked_match_to_core(game_state, current_party_profiles)
            ctx.bump_party()
        else:
            game_state["pregame_state"] = "character_select_finished"
        ctx.bump_match()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.pregame_match_payload(game_state, profile), localize=False)
    elif re.match(r"^/pregame/v1/matches/[^/]+/(quit|cheatquit)$", route_path):
        game_state["phase"] = "menus"
        game_state["party_state"] = "DEFAULT"
        game_state["provisioning_flow"] = cp.DEFAULT_PROVISIONING_FLOW
        game_state["queue"] = cp.DEFAULT_QUEUE
        ctx.bump_party()
        ctx.bump_match()
        ctx.broadcast_backend_state_update()
        ctx.write(200, {"ok": True})
    elif re.match(r"^/pregame/v1/matches/[^/]+/(start|cheatstart)$", route_path):
        profile = ctx.current_profile()
        current_party_profiles = cp.party_profiles(game_state, cp.party_id_for_profile(profile), profile)
        cp.ensure_character_selections(game_state, "locked", current_party_profiles)
        cp.transition_locked_match_to_core(game_state, current_party_profiles)
        ctx.bump_party()
        ctx.bump_match()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.core_game_match_payload(game_state, profile), localize=False)
    elif route_path.startswith("/pregame/v1/matches/"):
        if game_state.get("phase") in {"pregame", "core"}:
            ctx.write(200, cp.pregame_match_payload(game_state, ctx.current_profile()), localize=False)
        else:
            ctx.write(200, cp.inactive_match_payload())
    else:
        return False
    return True
