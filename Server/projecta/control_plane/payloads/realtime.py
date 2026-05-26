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


def json_api_event(uri: str, data: Any, event_type: str = "Update") -> dict[str, Any]:
    return {
        "data": data,
        "eventType": event_type,
        "uri": uri,
    }


def rms_resource_messages(service: str, pairs: list[tuple[str, str, Any]]) -> list[dict[str, Any]]:
    messages = []
    for message_id, resource, data in pairs:
        payload = json.dumps(data, separators=(",", ":"))
        notification = {
            "ID": message_id,
            "Id": message_id,
            "id": message_id,
            "Product": "ares",
            "product": "ares",
            "Service": service,
            "service": service,
            "Resource": resource,
            "resource": resource,
            "EventType": "Update",
            "eventType": "Update",
            "Version": 1,
            "version": 1,
            "Timestamp": utc_now(),
            "timestamp": utc_now(),
            "Body": payload,
            "body": payload,
            "Payload": payload,
            "payload": payload,
            "Data": data,
            "data": data,
        }
        messages.append(json_api_event(resource, data))
        rms_uri = "/riot-messaging-service/v1/message" + resource
        messages.append(json_api_event(rms_uri, data))
        messages.append(json_api_event("/riot-messaging-service/v1/message", notification, "Create"))
    return messages


def rms_party_messages(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    profile = profile or default_profile()
    party_id = party_id_for_profile(profile)
    player = party_player_payload(game_state, profile, party_id)
    party = party_payload(game_state, party_id, profile)
    pairs = [
        (stable_token("party-player-update", profile["subject"]), f"/ares-parties/parties/v1/players/{profile['subject']}", player),
        (stable_token("party-update", party_id), f"/ares-parties/parties/v1/parties/{party_id}", party),
        (stable_token("party-player-v1-update", profile["subject"]), f"/v1/players/{profile['subject']}", player),
        (stable_token("party-v1-update", party_id), f"/v1/parties/{party_id}", party),
    ]
    messages = []
    for message_id, resource, data in pairs:
        payload = json.dumps(data, separators=(",", ":"))
        notification = {
            "ID": message_id,
            "Id": message_id,
            "id": message_id,
            "Product": "ares",
            "product": "ares",
            "Service": "ares-parties",
            "service": "ares-parties",
            "Resource": resource,
            "resource": resource,
            "EventType": "Update",
            "eventType": "Update",
            "Version": 1,
            "version": 1,
            "Timestamp": utc_now(),
            "timestamp": utc_now(),
            "Body": payload,
            "body": payload,
            "Payload": payload,
            "payload": payload,
            "Data": data,
            "data": data,
        }
        messages.append(json_api_event(resource, data))
        if resource.startswith("/ares-parties/"):
            rms_uri = "/riot-messaging-service/v1/message" + resource
        else:
            rms_uri = "/riot-messaging-service/v1/message/ares-parties/parties" + resource
        messages.append(json_api_event(rms_uri, data))
        messages.append(json_api_event("/riot-messaging-service/v1/message", notification, "Create"))
    return messages


def rms_match_messages(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    profile = profile or default_profile()
    if not game_state:
        return []
    if game_state.get("phase") == "pregame":
        player = pregame_player_payload(game_state, profile)
        match = pregame_match_payload(game_state, profile)
        return rms_resource_messages(
            "ares-pregame",
            [
                (stable_token("pregame-player-update", profile["subject"], MATCH_ID), f"/ares-pregame/pregame/v1/players/{profile['subject']}", player),
                (stable_token("pregame-match-update", MATCH_ID), f"/ares-pregame/pregame/v1/matches/{MATCH_ID}", match),
            ],
        )
    if game_state.get("phase") == "core":
        player = core_game_player_payload(game_state, profile)
        match = core_game_match_payload(game_state, profile)
        return rms_resource_messages(
            "ares-core-game",
            [
                (stable_token("core-player-update", profile["subject"], MATCH_ID), f"/ares-core-game/core-game/v1/players/{profile['subject']}", player),
                (stable_token("core-match-update", MATCH_ID), f"/ares-core-game/core-game/v1/matches/{MATCH_ID}", match),
            ],
        )
    return []


def riot_messaging_messages_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    messages = []
    messages.extend(rms_party_messages(game_state, profile))
    messages.extend(rms_match_messages(game_state, profile))
    messages.extend(session_events(game_state, profile))
    return {
        "Messages": messages,
        "messages": messages,
        "Events": messages,
        "events": messages,
        "OutOfSync": False,
        "outOfSync": False,
    }


def chat_presence_events(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    return [
        json_api_event("/chat/v4/presences", presences_payload(game_state, profile)),
    ]




def session_events(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    profile = profile or default_profile()
    session = session_payload(game_state, profile)
    return [
        json_api_event(f"/session/v1/sessions/{profile['subject']}", session),
        json_api_event("/riot-messaging-service/v1/session", riot_messaging_session_payload(profile)),
    ]




_LOCAL_NAMES = {
    name
    for name, value in globals().items()
    if callable(value) and getattr(value, "__module__", None) == __name__
}
