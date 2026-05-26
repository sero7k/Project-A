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


def voice_token_payload(room: str | None = None) -> dict[str, Any]:
    room = room or VOICE_ROOM_ID
    token = stable_token("voice-token", room)
    return {
        "Token": token,
        "token": token,
        "Room": room,
        "room": room,
        "VoiceRoomID": room,
        "voiceRoomID": room,
    }


def voice_session_participants_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
    party_id: str | None = None,
) -> dict[str, Any]:
    profile = profile or default_profile()
    party_id = party_id or party_id_for_profile(profile)
    participants = [
        {
            "Subject": profile["subject"],
            "subject": profile["subject"],
            "Muted": False,
            "muted": False,
            "Volume": 1.0,
            "volume": 1.0,
        }
        for profile in party_profiles(game_state, party_id, profile)
    ]
    return {"Participants": participants, "participants": participants}


def voice_session_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    party_id = party_id_for_profile(profile)
    voice_room = party_voice_room_id(party_id)
    participants = voice_session_participants_payload(game_state, profile, party_id)
    return {
        "SessionID": voice_room,
        "sessionID": voice_room,
        "RoomID": voice_room,
        "roomID": voice_room,
        "Participants": participants["Participants"],
        "participants": participants["participants"],
    }


def voice_sessions_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    return [voice_session_payload(game_state, profile)]




_LOCAL_NAMES = {
    name
    for name, value in globals().items()
    if callable(value) and getattr(value, "__module__", None) == __name__
}
