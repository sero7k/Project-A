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


def friends_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    updates = (game_state or {}).get("presence_by_profile")
    if not isinstance(updates, dict):
        updates = {}
    friends = []
    for friend in friend_profiles_for_profile(profile):
        if friend["subject"] == profile["subject"]:
            continue
        presence = presence_payload(game_state, friend, updates.get(friend["key"]))
        friends.append(friend_payload(friend, presence))
    return {"Friends": friends, "friends": friends}


def friend_payload(friend: dict[str, str], presence: dict[str, Any] | None = None) -> dict[str, Any]:
    presence = presence or presence_payload(None, friend)
    return {
        "Cid": "",
        "cid": "",
        "Pid": friend["chat_pid"],
        "pid": friend["chat_pid"],
        "Subject": friend["subject"],
        "subject": friend["subject"],
        "Puuid": friend["subject"],
        "puuid": friend["subject"],
        "Name": friend["game_name"],
        "name": friend["game_name"],
        "GameName": friend["game_name"],
        "gameName": friend["game_name"],
        "game_name": friend["game_name"],
        "GameTag": friend["tag_line"],
        "gameTag": friend["tag_line"],
        "game_tag": friend["tag_line"],
        "TagLine": friend["tag_line"],
        "tagLine": friend["tag_line"],
        "DisplayName": friend["display_name"],
        "displayName": friend["display_name"],
        "Note": "",
        "note": "",
        "Group": "general",
        "group": "general",
        "DisplayGroup": "general",
        "displayGroup": "general",
        "Priority": "",
        "priority": "",
        "Presence": presence,
        "presence": presence,
        "FriendPresence": presence,
        "friendPresence": presence,
    }




def profile_from_social_body(body: Any) -> dict[str, str] | None:
    if not isinstance(body, dict):
        return None
    for key in (
        "Subject",
        "subject",
        "Puuid",
        "puuid",
        "PlayerSubject",
        "playerSubject",
        "FriendSubject",
        "friendSubject",
    ):
        value = body.get(key)
        if isinstance(value, str) and value:
            account = ACCOUNT_STORE.get_account_by_subject(value)
            if account:
                return profile_from_account(account)
    for key in ("Pid", "pid", "Jid", "jid", "JID", "FriendPid", "friendPid"):
        value = body.get(key)
        if isinstance(value, str) and value:
            subject = subject_from_chat_pid(value)
            account = ACCOUNT_STORE.get_account_by_subject(subject)
            if account:
                return profile_from_account(account)
    nested_keys = ("Player", "player", "Friend", "friend", "Target", "target", "Request", "request")
    for key in nested_keys:
        nested = body.get(key)
        if isinstance(nested, dict):
            profile = profile_from_social_body(nested)
            if profile:
                return profile
    game_name, tag_line = alias_fields_from_body(body, {"game_name": "", "tag_line": ""})
    if game_name and tag_line:
        account = ACCOUNT_STORE.find_account_by_alias(game_name, tag_line)
        if account:
            return profile_from_account(account)
    for key in ("DisplayName", "displayName", "Name", "name"):
        value = body.get(key)
        if isinstance(value, str) and "#" in value:
            game_name, tag_line = value.rsplit("#", 1)
            account = ACCOUNT_STORE.find_account_by_alias(game_name, tag_line)
            if account:
                return profile_from_account(account)
    return None


def friend_request_payload(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    sender = profile_by_key(record.sender_account_key)
    receiver = profile_by_key(record.receiver_account_key)
    current_profile = current_profile or default_profile()
    other = sender if current_profile["key"] == receiver["key"] else receiver
    inbound = current_profile["key"] == receiver["key"]
    subscription = FRIEND_REQUEST_SUBSCRIPTION_INBOUND if inbound else FRIEND_REQUEST_SUBSCRIPTION_OUTBOUND
    direction = "inbound" if inbound else "outbound"
    return {
        "ID": record.request_id,
        "Id": record.request_id,
        "id": record.request_id,
        "Subject": other["subject"],
        "subject": other["subject"],
        "Puuid": other["subject"],
        "puuid": other["subject"],
        "Pid": other["chat_pid"],
        "pid": other["chat_pid"],
        "SenderSubject": sender["subject"],
        "senderSubject": sender["subject"],
        "ReceiverSubject": receiver["subject"],
        "receiverSubject": receiver["subject"],
        "GameName": other["game_name"],
        "gameName": other["game_name"],
        "game_name": other["game_name"],
        "TagLine": other["tag_line"],
        "tagLine": other["tag_line"],
        "GameTag": other["tag_line"],
        "game_tag": other["tag_line"],
        "DisplayName": other["display_name"],
        "displayName": other["display_name"],
        "Name": other["game_name"],
        "name": other["game_name"],
        "Note": "",
        "note": "",
        "Subscription": subscription,
        "subscription": subscription,
        "Direction": direction,
        "direction": direction,
    }


def friend_request_wire_item(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    payload = friend_request_payload(record, current_profile)
    return {
        "game_name": payload["game_name"],
        "game_tag": payload["game_tag"],
        "Name": payload["Name"],
        "Note": payload["Note"],
        "Pid": payload["Pid"],
        "Subscription": payload["Subscription"],
    }


def friend_request_model_aliases(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    payload = friend_request_payload(record, current_profile)
    return {
        "ID": payload["ID"],
        "Id": payload["ID"],
        "id": payload["ID"],
        "Subject": payload["Subject"],
        "subject": payload["Subject"],
        "Puuid": payload["Puuid"],
        "puuid": payload["Puuid"],
        "GameName": payload["GameName"],
        "gameName": payload["GameName"],
        "TagLine": payload["TagLine"],
        "tagLine": payload["TagLine"],
        "GameTag": payload["GameTag"],
        "gameTag": payload["GameTag"],
        "DisplayName": payload["DisplayName"],
        "displayName": payload["DisplayName"],
        "Subscription": payload["Subscription"],
        "subscription": payload["Subscription"],
        "Direction": payload["Direction"],
        "direction": payload["Direction"],
    }


def friend_requests_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    inbound = [friend_request_payload(record, profile) for record in ACCOUNT_STORE.friend_requests_for_account(profile["key"], inbound=True)]
    outbound = [friend_request_payload(record, profile) for record in ACCOUNT_STORE.friend_requests_for_account(profile["key"], inbound=False)]
    requests = inbound + outbound
    inbound_wire = [friend_request_wire_item(record, profile) for record in ACCOUNT_STORE.friend_requests_for_account(profile["key"], inbound=True)]
    outbound_wire = [friend_request_wire_item(record, profile) for record in ACCOUNT_STORE.friend_requests_for_account(profile["key"], inbound=False)]
    requests_wire = inbound_wire + outbound_wire
    inbound_group = {"Requests": inbound_wire, "requests": inbound_wire}
    outbound_group = {"Requests": outbound_wire, "requests": outbound_wire}
    requests_group = {"Requests": requests_wire, "requests": requests_wire}
    return {
        "InboundFriendRequests": inbound_group,
        "inboundFriendRequests": inbound,
        "OutboundFriendRequests": outbound_group,
        "outboundFriendRequests": outbound,
        "FriendRequests": requests_group,
        "friendRequests": requests,
        "Requests": requests_wire,
        "requests": requests_wire,
    }


def friend_request_response_payload(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    payload = friend_request_payload(record, current_profile)
    response = dict(payload)
    response["FriendRequest"] = payload
    response["friendRequest"] = payload
    response["Request"] = payload
    response["request"] = payload
    return response


def friend_request_add_event_payload(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    payload = friend_request_payload(record, current_profile)
    return {
        "game_name": payload["game_name"],
        "game_tag": payload["game_tag"],
        "Name": payload["Name"],
        "Note": payload["Note"],
        "Pid": payload["Pid"],
        "Subscription": payload["Subscription"],
    }


def friend_request_remove_event_payload(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    payload = friend_request_payload(record, current_profile)
    return {
        "Pid": payload["Pid"],
    }


def pending_friend_request_for_id(profile: dict[str, str], request_id: str) -> FriendRequestRecord | None:
    for record in ACCOUNT_STORE.friend_requests_for_account(profile["key"], inbound=True):
        if record.request_id == request_id:
            return record
    for record in ACCOUNT_STORE.friend_requests_for_account(profile["key"], inbound=False):
        if record.request_id == request_id:
            return record
    return None


def pending_friend_request_for_identifier(profile: dict[str, str], identifier: str) -> FriendRequestRecord | None:
    match = pending_friend_request_for_id(profile, identifier)
    if match:
        return match
    identifier = str(identifier or "").strip().lower()
    if not identifier:
        return None
    for inbound in (True, False):
        for record in ACCOUNT_STORE.friend_requests_for_account(profile["key"], inbound=inbound):
            payload = friend_request_payload(record, profile)
            candidates = {
                str(payload.get("Subject") or "").lower(),
                str(payload.get("subject") or "").lower(),
                str(payload.get("Pid") or "").lower(),
                str(payload.get("pid") or "").lower(),
                str(payload.get("Puuid") or "").lower(),
                str(payload.get("puuid") or "").lower(),
                str(payload.get("DisplayName") or "").lower(),
                str(payload.get("displayName") or "").lower(),
            }
            if identifier in candidates:
                return record
    return None


def inbound_friend_request_from_target(profile: dict[str, str], target: dict[str, str]) -> FriendRequestRecord | None:
    for record in ACCOUNT_STORE.friend_requests_for_account(profile["key"], inbound=True):
        if record.sender_account_key == target["key"]:
            return record
    return None


def create_friend_request_response(
    profile: dict[str, str],
    body: Any,
    game_state: dict[str, Any] | None = None,
    auto_accept: bool = False,
) -> tuple[int, dict[str, Any]]:
    target = profile_from_social_body(body)
    if not target:
        return 404, {"HTTPStatus": 404, "ErrorCode": "NOT_FOUND", "Message": "Player not found", "errorCode": "NOT_FOUND", "errorMessage": "Player not found"}
    if target["subject"] == profile["subject"]:
        return 400, {"HTTPStatus": 400, "ErrorCode": "ADDING_SELF_FAIL", "Message": "Cannot add yourself", "errorCode": "ADDING_SELF_FAIL", "errorMessage": "Cannot add yourself"}
    reciprocal = inbound_friend_request_from_target(profile, target)
    if reciprocal:
        accepted = ACCOUNT_STORE.accept_friend_request(profile["key"], reciprocal.request_id)
        if accepted:
            presence = presence_payload(game_state, target)
            friend = friend_payload(target, presence)
            response = friend_request_response_payload(accepted, profile)
            response.update(
                {
                    "Accepted": True,
                    "accepted": True,
                    "ReciprocalAccepted": True,
                    "reciprocalAccepted": True,
                    "AutoAccepted": False,
                    "autoAccepted": False,
                    "Friend": friend,
                    "friend": friend,
                    "Friends": [friend],
                    "friends": [friend],
                }
            )
            return 200, response
        return 404, {"HTTPStatus": 404, "ErrorCode": "FRIEND_REQUEST_NOT_FOUND", "Message": "Friend request not found", "errorCode": "FRIEND_REQUEST_NOT_FOUND", "errorMessage": "Friend request not found"}
    request = ACCOUNT_STORE.create_friend_request(profile["key"], target["key"])
    if request:
        response = friend_request_response_payload(request, profile)
        response.update(
            {
                "Accepted": False,
                "accepted": False,
                "AutoAccepted": False,
                "autoAccepted": False,
            }
        )
        if auto_accept:
            ACCOUNT_STORE.add_friend(profile["key"], target["key"])
            presence = presence_payload(game_state, target)
            friend = friend_payload(target, presence)
            response.update(
                {
                    "Accepted": True,
                    "accepted": True,
                    "AutoAccepted": True,
                    "autoAccepted": True,
                    "Friend": friend,
                    "friend": friend,
                    "Friends": [friend],
                    "friends": [friend],
                }
            )
        return 200, response
    presence = presence_payload(game_state, target)
    friend = friend_payload(target, presence)
    return 200, {
        "ok": True,
        "alreadyFriends": True,
        "AlreadyFriends": True,
        "Friend": friend,
        "friend": friend,
        "Friends": [friend],
        "friends": [friend],
        "Subject": target["subject"],
        "subject": target["subject"],
        "Pid": target["chat_pid"],
        "pid": target["chat_pid"],
        "GameName": target["game_name"],
        "gameName": target["game_name"],
        "TagLine": target["tag_line"],
        "tagLine": target["tag_line"],
        "GameTag": target["tag_line"],
        "game_tag": target["tag_line"],
        "DisplayName": target["display_name"],
        "displayName": target["display_name"],
    }




_LOCAL_NAMES = {
    name
    for name, value in globals().items()
    if callable(value) and getattr(value, "__module__", None) == __name__
}
