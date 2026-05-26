"""Extracted payload helpers configured by app.py wrappers."""

from __future__ import annotations

import base64
import json
import time
import uuid
from typing import Any
from urllib.parse import quote


def configure(deps: dict[str, Any]) -> None:
    local_names = globals().get("_LOCAL_NAMES", set())
    for name, value in deps.items():
        if name not in local_names:
            globals()[name] = value


def presence_private_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    current_party_id = party_id_for_profile(profile)
    profiles = party_profiles(game_state, current_party_id, profile)
    state = active_party_state(game_state)
    current_loop_state = loop_state(game_state)
    custom_team = custom_team_for_profile(game_state, profile)
    team_id = team_id_for_custom_team(custom_team)
    provisioning_flow = active_provisioning_flow(game_state)
    owner_subject = profiles[0]["subject"] if profiles else profile["subject"]
    queue_entry_time = str((game_state or {}).get("matchmaking_presence_started_at") or "0001.01.01-00.00.00")
    return {
        "isValid": True,
        "sessionLoopState": current_loop_state,
        "partyOwnerSessionLoopState": current_loop_state,
        "customGameName": "",
        "customGameTeam": custom_team if state != "DEFAULT" else "",
        "partyOwnerMatchMap": (game_state or {}).get("map", ""),
        "partyOwnerMatchCurrentTeam": team_id if state != "DEFAULT" else "",
        "partyOwnerMatchScoreAllyTeam": 0,
        "partyOwnerMatchScoreEnemyTeam": 0,
        "partyOwnerProvisioningFlow": provisioning_flow if state != "DEFAULT" else "Invalid",
        "provisioningFlow": provisioning_flow if state != "DEFAULT" else "Invalid",
        "matchMap": (game_state or {}).get("map", ""),
        "partyId": current_party_id,
        "isPartyOwner": profile["subject"] == owner_subject,
        "partyName": "",
        "partyState": state,
        "partyAccessibility": (game_state or {}).get("party_accessibility", "CLOSED"),
        "maxPartySize": 5,
        "queueId": (game_state or {}).get("queue", ""),
        "partyLFM": False,
        "partyClientVersion": CLIENT_VERSION,
        "partySize": len(profiles),
        "partyVersion": int((game_state or {}).get("party_version", 1)),
        "queueEntryTime": queue_entry_time,
        "playerCardId": DEFAULT_PLAYER_CARD_ID,
        "playerTitleId": DEFAULT_PLAYER_TITLE_ID,
        "isIdle": False,
        "tournamentId": "",
    }


def presence_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
    update: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = profile or default_profile()
    private_raw = json.dumps(presence_private_payload(game_state, profile), separators=(",", ":")).encode("utf-8")
    online = profile_is_online(game_state, profile)
    state_value = "chat" if online else "offline"
    basic_value = "chat" if online else "offline"
    private_value = base64.b64encode(private_raw).decode("ascii")
    payload = {
        "actor": "",
        "availability": "online" if online else "offline",
        "basic": basic_value,
        "details": "",
        "game_name": profile["game_name"],
        "game_tag": profile["tag_line"],
        "GameName": profile["game_name"],
        "GameTag": profile["tag_line"],
        "TagLine": profile["tag_line"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "display_name": profile["display_name"],
        "location": "",
        "Msg": "",
        "msg": "",
        "name": profile["game_name"],
        "patchline": "live",
        "pid": profile["chat_pid"],
        "platform": "PC",
        "Private": private_value,
        "private": private_value,
        "PrivateJwt": "",
        "privateJwt": "",
        "product": "ares",
        "Product": "ares",
        "presenceProduct": "ares",
        "puuid": profile["subject"],
        "region": "na",
        "resource": CHAT_RESOURCE,
        "online": online,
        "State": state_value,
        "state": state_value,
        "Summary": "",
        "summary": "",
        "Time": int(time.time() * 1000),
        "time": int(time.time() * 1000),
    }
    if update:
        for key in ("actor", "basic", "details", "location", "msg", "shared", "state", "summary"):
            if key in update:
                payload[key] = update[key]
        if isinstance(update.get("private"), str) and update.get("private"):
            payload["Private"] = update["private"]
            payload["private"] = update["private"]
        if update.get("privateJwt") is not None:
            payload["PrivateJwt"] = update["privateJwt"]
            payload["privateJwt"] = update["privateJwt"]
        shared = update.get("shared")
        if isinstance(shared, dict) and isinstance(shared.get("product"), str):
            payload["product"] = shared["product"]
            payload["Product"] = shared["product"]
            payload["presenceProduct"] = shared["product"]
        elif isinstance(update.get("product"), str) and update.get("product"):
            payload["product"] = update["product"]
            payload["Product"] = update["product"]
            payload["presenceProduct"] = update["product"]
        payload["Time"] = int(time.time() * 1000)
        payload["time"] = int(time.time() * 1000)
    state_alias = str(payload.get("state") or payload.get("State") or state_value).upper()
    product_alias = str(payload.get("product") or payload.get("Product") or "ares").upper()
    payload["Basic"] = state_alias
    payload["PresenceState"] = state_alias
    payload["presenceState"] = state_alias
    payload["PresenceProduct"] = product_alias
    return payload


def presences_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    updates = (game_state or {}).get("presence_by_profile")
    if not isinstance(updates, dict):
        updates = {}
    presences = [presence_payload(game_state, item, updates.get(item["key"])) for item in presence_roster_profiles(game_state, profile)]
    return {
        "Presences": presences,
        "presences": presences,
    }




def session_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    current_loop_state = loop_state(game_state)
    match_id = active_match_id(game_state)
    if game_state and game_state.get("phase") == "pregame" and game_state.get("pregame_state") == "provisioned":
        current_loop_state = "INGAME"
    client_id = stable_token("client", profile["subject"], CLIENT_VERSION)
    session_id = stable_token("session", profile["subject"], current_loop_state, match_id)
    return {
        "Subject": profile["subject"],
        "CXNState": "CONNECTED",
        "ClientID": client_id,
        "ClientVersion": CLIENT_VERSION,
        "LoopState": current_loop_state,
        "LoopStateMetadata": match_id,
        "Version": 1,
        "LastHeartbeatTime": utc_now(),
        "ExpiredTime": "0001-01-01T00:00:00.000Z",
        "HeartbeatIntervalMillis": 30000,
        "PlaytimeNotification": "",
        "RestrictionType": "",
        "puuid": profile["subject"],
        "subject": profile["subject"],
        "cxnState": "CONNECTED",
        "clientID": client_id,
        "clientId": client_id,
        "clientVersion": CLIENT_VERSION,
        "loopState": current_loop_state,
        "loopStateMetadata": match_id,
        "state": "connected",
        "sessionId": session_id,
    }




def chat_session_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "federated": True,
        "game_name": profile["game_name"],
        "game_tag": profile["tag_line"],
        "loaded": True,
        "Loaded": True,
        "name": profile["game_name"],
        "pid": profile["chat_pid"],
        "Pid": profile["chat_pid"],
        "puuid": profile["subject"],
        "Puuid": profile["subject"],
        "region": "na",
        "Region": "na",
        "resource": CHAT_RESOURCE,
        "Resource": CHAT_RESOURCE,
        "state": "connected",
        "State": "connected",
        "connected": True,
        "Connected": True,
        "GameName": profile["game_name"],
        "gameName": profile["game_name"],
        "GameTag": profile["tag_line"],
        "gameTag": profile["tag_line"],
        "TagLine": profile["tag_line"],
        "tagLine": profile["tag_line"],
        "Name": profile["game_name"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
    }


def riot_messaging_session_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "state": "connected",
        "connected": True,
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "Puuid": profile["subject"],
        "puuid": profile["subject"],
        "Pid": profile["chat_pid"],
        "pid": profile["chat_pid"],
        "GameName": profile["game_name"],
        "gameName": profile["game_name"],
        "TagLine": profile["tag_line"],
        "tagLine": profile["tag_line"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
    }




_LOCAL_NAMES = {
    name
    for name, value in globals().items()
    if callable(value) and getattr(value, "__module__", None) == __name__
}
