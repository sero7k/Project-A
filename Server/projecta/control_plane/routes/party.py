"""Party, custom-game, party invite, and party matchmaking routes."""

from __future__ import annotations

import re
from urllib.parse import unquote


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    game_state = ctx.game_state
    json_body = ctx.json_body


    if route_path in {"/v1/customgames", "/parties/v1/customgames", "/parties/v1/parties/customgames"}:
        ctx.write(200, cp.custom_games_payload(game_state, ctx.current_profile()), localize=False)
    elif re.match(r"^/parties/v1/players/[^/]+/startsoloexperience(?:v2)?$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_for_profile(profile)
        cp.configure_solo_experience(game_state, json_body if isinstance(json_body, dict) else {})
        game_state["phase"] = "pregame"
        game_state["party_state"] = "SOLO_EXPERIENCE_STARTING"
        game_state["pregame_state"] = "character_select_finished"
        current_party_profiles = cp.party_profiles(game_state, party_id, profile)
        cp.ensure_character_selections(game_state, "locked", current_party_profiles)
        cp.prime_backend_state_for_phase(game_state, current_party_profiles, "pregame")
        ctx.bump_party()
        ctx.bump_match()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/players/[^/]+/joinparty/[0-9a-fA-F-]{36}$", route_path):
        profile = ctx.current_profile()
        previous_party_id = cp.party_id_for_profile(profile)
        party_id = route_path.rsplit("/", 1)[-1]
        cp.ACCOUNT_STORE.join_party(profile["key"], party_id)
        cp.sync_party_chat_room(game_state, profile, previous_party_id, party_id)
        ctx.bump_party()
        ctx.broadcast_backend_state_update()
        ctx.broadcast_social_roster_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/players/[^/]+/invites/[0-9a-fA-F-]{36}/accept$", route_path):
        profile = ctx.current_profile()
        previous_party_id = cp.party_id_for_profile(profile)
        invite_id = route_path.split("/")[-2]
        invite = cp.ACCOUNT_STORE.accept_party_invite(profile["key"], invite_id)
        party_id = invite.party_id if invite else cp.party_id_for_profile(profile)
        cp.sync_party_chat_room(game_state, profile, previous_party_id, party_id)
        ctx.bump_party()
        ctx.broadcast_backend_state_update()
        ctx.broadcast_social_roster_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/players/[^/]+/invites(/decline)?$", route_path):
        profile = ctx.current_profile()
        if route_path.endswith("/decline"):
            invite_id = (
                json_body.get("ID")
                or json_body.get("Id")
                or json_body.get("id")
                or json_body.get("InvitationID")
                or json_body.get("invitationID")
                if isinstance(json_body, dict)
                else None
            )
            if invite_id:
                cp.ACCOUNT_STORE.decline_party_invite(profile["key"], str(invite_id))
        ctx.write(200, cp.invites_payload(profile))
    elif route_path.rstrip("/") in {"/v1/customgames", "/customgames/v1/customgames", "/parties/v1/customgames"}:
        ctx.write(200, cp.custom_games_payload(game_state, ctx.current_profile()), localize=False)
    elif route_path.startswith("/parties/v1/players/"):
        profile = ctx.current_profile()
        if cp.mark_backend_ready(game_state, profile, "party"):
            ctx.send_backend_state_to_profile(profile)
        ctx.write(200, cp.party_player_payload(game_state, profile, cp.party_id_for_profile(profile)), localize=False)
    elif route_path.startswith("/parties/v1/parties/") and route_path.endswith("/customgameconfigs"):
        profile = ctx.current_profile()
        if cp.mark_backend_ready(game_state, profile, "party"):
            ctx.send_backend_state_to_profile(profile)
        ctx.write(200, cp.custom_game_configs_payload(game_state))
    elif re.match(r"^/parties/v1/parties/[^/]+/invites/[0-9a-fA-F-]{36}/accept$", route_path):
        profile = ctx.current_profile()
        previous_party_id = cp.party_id_for_profile(profile)
        invite_id = cp.invite_id_from_route(route_path)
        invite = cp.ACCOUNT_STORE.accept_party_invite(profile["key"], str(invite_id)) if invite_id else None
        party_id = invite.party_id if invite else cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        cp.sync_party_chat_room(game_state, profile, previous_party_id, party_id)
        ctx.bump_party()
        ctx.broadcast_backend_state_update()
        ctx.broadcast_social_roster_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/invites/[0-9a-fA-F-]{36}/(decline|reject)$", route_path):
        profile = ctx.current_profile()
        invite_id = cp.invite_id_from_route(route_path)
        if invite_id:
            cp.ACCOUNT_STORE.decline_party_invite(profile["key"], invite_id)
        ctx.write(200, cp.invites_payload(profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/(join|request)$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        cp.ACCOUNT_STORE.join_party(profile["key"], party_id)
        ctx.bump_party()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/leave$", route_path):
        profile = ctx.current_profile()
        party_id = cp.ACCOUNT_STORE.leave_party(profile["key"])
        ctx.bump_party()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/invites/name/[^/]+/tag/[^/]+$", route_path) or re.match(r"^/parties/v1/parties/[^/]+/invites$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        invitee_key = cp.account_key_from_invite_route(route_path) or cp.account_key_from_invite_body(json_body)
        if invitee_key:
            invite = cp.ACCOUNT_STORE.create_party_invite(profile["key"], invitee_key, party_id)
            ctx.broadcast_social_roster_update()
            ctx.write(200, cp.invite_payload(invite), localize=False)
        else:
            ctx.write(404, {"HTTPStatus": 404, "ErrorCode": "PLAYER_NOT_FOUND", "Message": "Invite target was not found.", "errorCode": "PLAYER_NOT_FOUND", "errorMessage": "Invite target was not found."})
    elif re.match(r"^/parties/v1/parties/[^/]+/invites(/decline)?$", route_path):
        ctx.write(200, cp.invites_payload(ctx.current_profile()), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/(?:customgamemembership|customgame)/[^/]+$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        game_state["phase"] = "custom"
        game_state["party_state"] = "CUSTOM_GAME_SETUP"
        team = route_path.rsplit("/", 1)[-1]
        request_body = json_body if isinstance(json_body, dict) else {}
        subject = cp.subject_from_team_request(request_body, profile["subject"])
        cp.set_custom_team_for_subject(game_state, str(subject), team)
        ctx.bump_party()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/muctoken$", route_path):
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(ctx.current_profile())
        ctx.write(200, cp.chat_token_payload(cp.party_muc_name(party_id)))
    elif re.match(r"^/parties/v1/parties/[^/]+/voicetoken$", route_path):
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(ctx.current_profile())
        ctx.write(200, cp.voice_token_payload(cp.party_voice_room_id(party_id)))
    elif re.match(r"^/parties/v1/parties/[^/]+/makecustomgame$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        request_body = json_body if isinstance(json_body, dict) else {}
        settings = cp.request_settings_from_body(request_body) if request_body else {}
        has_map = bool(cp.first_string(settings, "Map", "map", "MapID", "mapID", "mapId"))
        has_mode = bool(cp.first_string(settings, "Mode", "mode", "ModeID", "modeID", "modeId", "GameMode", "gameMode", "GameModeID", "gameModeID", "gameModeId"))
        cp.update_state_from_json(game_state, request_body)
        game_state["phase"] = "custom"
        game_state["party_state"] = "CUSTOM_GAME_SETUP"
        game_state["pregame_state"] = ""
        game_state["provisioning_flow"] = cp.DEFAULT_PROVISIONING_FLOW
        game_state["queue"] = cp.DEFAULT_QUEUE
        if not has_map:
            game_state["map"] = cp.DEFAULT_MAP
        if not has_mode:
            game_state["mode"] = cp.DEFAULT_MODE
        ctx.bump_party()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/makedefault", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        game_state["phase"] = "menus"
        game_state["party_state"] = "DEFAULT"
        game_state["pregame_state"] = ""
        game_state["provisioning_flow"] = cp.DEFAULT_PROVISIONING_FLOW
        game_state["queue"] = cp.DEFAULT_QUEUE
        ctx.bump_party()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/customgamesettings$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        cp.update_state_from_json(game_state, json_body)
        game_state["phase"] = "custom"
        game_state["party_state"] = "CUSTOM_GAME_SETUP"
        game_state["pregame_state"] = ""
        game_state["provisioning_flow"] = cp.DEFAULT_PROVISIONING_FLOW
        game_state["queue"] = cp.DEFAULT_QUEUE
        game_state["map"] = str(game_state.get("map") or cp.DEFAULT_MAP)
        game_state["mode"] = str(game_state.get("mode") or cp.DEFAULT_MODE)
        ctx.bump_party()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/startcustomgame$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        game_state["phase"] = "pregame"
        game_state["party_state"] = "CUSTOM_GAME_STARTING"
        game_state["pregame_state"] = "character_select_active"
        game_state["provisioning_flow"] = cp.DEFAULT_PROVISIONING_FLOW
        current_party_profiles = cp.party_profiles(game_state, party_id, profile)
        cp.ensure_character_selections(game_state, "", current_party_profiles)
        cp.prime_backend_state_for_phase(game_state, current_party_profiles, "pregame")
        ctx.bump_party()
        ctx.bump_match()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/startsoloexperience(?:v2)?$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        cp.configure_solo_experience(game_state, json_body if isinstance(json_body, dict) else {})
        game_state["phase"] = "pregame"
        game_state["party_state"] = "SOLO_EXPERIENCE_STARTING"
        game_state["pregame_state"] = "character_select_finished"
        current_party_profiles = cp.party_profiles(game_state, party_id, profile)
        cp.ensure_character_selections(game_state, "locked", current_party_profiles)
        cp.prime_backend_state_for_phase(game_state, current_party_profiles, "pregame")
        ctx.bump_party()
        ctx.bump_match()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/queue(?:/[^/]+)?$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        queue_body = dict(json_body) if isinstance(json_body, dict) else {}
        if not route_path.endswith("/queue") and "QueueID" not in queue_body and "queueID" not in queue_body:
            queue_body["QueueID"] = unquote(route_path.rsplit("/", 1)[-1])
        cp.enter_matchmaking(game_state, queue_body, profile, immediate_pregame=True)
        ctx.bump_party()
        ctx.bump_match()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/matchmaking/join(?:/[^/]+)?$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        queue_body = dict(json_body) if isinstance(json_body, dict) else {}
        if not route_path.endswith("/join") and "QueueID" not in queue_body and "queueID" not in queue_body:
            queue_body["QueueID"] = unquote(route_path.rsplit("/", 1)[-1])
        cp.enter_matchmaking(game_state, queue_body, profile, immediate_pregame=True)
        ctx.bump_party()
        ctx.bump_match()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/matchmaking/leave$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        game_state["party_state"] = "DEFAULT"
        ctx.bump_party()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif re.match(r"^/parties/v1/parties/[^/]+/(accessibility|lookingForMore|name|cheats|balance)$", route_path):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        if route_path.endswith("/accessibility") and isinstance(json_body, dict):
            new_accessibility = json_body.get("Accessibility") or json_body.get("accessibility") or "CLOSED"
            game_state["party_accessibility"] = new_accessibility
        ctx.bump_party()
        ctx.broadcast_backend_state_update()
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif route_path.startswith("/parties/v1/parties/"):
        profile = ctx.current_profile()
        party_id = cp.party_id_from_route(route_path) or cp.party_id_for_profile(profile)
        ctx.write(200, cp.party_payload(game_state, party_id, profile), localize=False)
    elif route_path == "/parties/v1/parties":
        profile = ctx.current_profile()
        ctx.write(200, cp.party_payload(game_state, cp.party_id_for_profile(profile), profile), localize=False)
    else:
        return False
    return True
