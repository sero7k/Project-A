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


def joined_chat_rooms_for_profile(game_state: dict[str, Any] | None, profile: dict[str, str] | None = None) -> set[str]:
    if not game_state:
        return {party_muc_name(party_id_for_profile(profile))} if profile else set()
    if profile:
        by_subject = game_state.get("joined_chat_rooms_by_subject")
        if isinstance(by_subject, dict):
            rooms = by_subject.get(profile["subject"], [])
            if isinstance(rooms, list):
                joined = {str(cid) for cid in rooms if cid}
                joined.add(party_muc_name(party_id_for_profile(profile)))
                return joined
        return {party_muc_name(party_id_for_profile(profile))}
    rooms = game_state.get("joined_chat_rooms")
    if isinstance(rooms, list):
        return {str(cid) for cid in rooms if cid}
    return set()


def profile_has_joined_chat_room(game_state: dict[str, Any] | None, profile: dict[str, str], cid: str | None) -> bool:
    return bool(cid) and str(cid) in joined_chat_rooms_for_profile(game_state, profile)


def chat_room_is_available_to_profile(game_state: dict[str, Any] | None, profile: dict[str, str], cid: str | None) -> bool:
    if not cid:
        return False
    room = str(cid)
    current_party_id = party_id_for_profile(profile)
    if room == party_muc_name(current_party_id):
        return True
    room_party_id = party_id_from_muc(room)
    if room_party_id and room_party_id == current_party_id:
        return True
    if game_state and game_state.get("phase") in {"pregame", "core"} and room in {TEAM_MUC_NAME, ALL_MUC_NAME}:
        return True
    return False


def chat_messages_for_room(game_state: dict[str, Any] | None, cid: str | None) -> list[dict[str, Any]]:
    room = str(cid or "")
    if not room:
        return []
    messages = (game_state or {}).get("chat_messages")
    if not isinstance(messages, list):
        return []
    return [
        message
        for message in messages
        if str(message.get("Cid") or message.get("cid") or message.get("RoomID") or message.get("roomID") or "") == room
    ]


def chat_read_ack_payload(body: Any, cid: str = "") -> dict[str, Any]:
    request_body = body if isinstance(body, dict) else {}
    read_cid = (
        cid
        or request_body.get("Cid")
        or request_body.get("cid")
        or request_body.get("RoomId")
        or request_body.get("roomId")
        or request_body.get("ConversationId")
        or request_body.get("conversationId")
        or request_body.get("ConversationID")
        or request_body.get("conversationID")
        or ""
    )
    message_id = (
        request_body.get("MessageId")
        or request_body.get("messageId")
        or request_body.get("MessageID")
        or request_body.get("messageID")
        or request_body.get("LastReadMessageId")
        or request_body.get("lastReadMessageId")
        or request_body.get("Id")
        or request_body.get("id")
        or ""
    )
    return {
        "ok": True,
        "Success": True,
        "success": True,
        "Read": True,
        "read": True,
        "Cid": read_cid,
        "cid": read_cid,
        "MessageId": message_id,
        "messageId": message_id,
        "LastReadMessageId": message_id,
        "lastReadMessageId": message_id,
    }


def chat_unified_room_type(room: str) -> str:
    if room.startswith("ares-party-"):
        return "Party"
    if room == TEAM_MUC_NAME:
        return "Team"
    if room == ALL_MUC_NAME:
        return "All"
    return "Whisper"

def chat_muc_message_payload(message: dict[str, Any]) -> dict[str, Any]:
    room = chat_message_room(message)
    message_id = str(message.get("Id") or message.get("ID") or message.get("id") or "")
    body = str(message.get("Body") or message.get("body") or message.get("DisplayMessage") or message.get("message") or "")
    pid = str(message.get("Pid") or message.get("pid") or message.get("Sender") or message.get("sender") or "")
    subject = str(message.get("Subject") or message.get("subject") or message.get("SenderSubject") or message.get("senderSubject") or subject_from_chat_pid(pid))
    game_name = str(message.get("GameName") or message.get("gameName") or message.get("game_name") or message.get("Name") or message.get("name") or "")
    game_tag = str(message.get("GameTag") or message.get("gameTag") or message.get("game_tag") or message.get("TagLine") or message.get("tagLine") or "")
    display_name = str(message.get("DisplayName") or message.get("displayName") or f"{game_name}#{game_tag}".strip("#"))
    timestamp = str(message.get("Time") or message.get("time") or message.get("Timestamp") or message.get("timestamp") or utc_now())
    muc_type = chat_muc_type_value(message.get("MUCType") or message.get("Type") or message.get("type"))
    message_type = chat_text_room_type_value(message.get("MessageType") or message.get("messageType") or muc_type)
    read = bool(message.get("Read", message.get("read", True)))
    return {
        "Body": body,
        "body": body,
        "Pid": pid,
        "pid": pid,
        "Time": timestamp,
        "time": timestamp,
        "Cid": room,
        "cid": room,
        "Id": message_id,
        "id": message_id,
        "Name": game_name,
        "name": game_name,
        "Read": read,
        "read": read,
        "GameName": game_name,
        "gameName": game_name,
        "game_name": game_name,
        "GameTag": game_tag,
        "gameTag": game_tag,
        "game_tag": game_tag,
        "TagLine": game_tag,
        "tagLine": game_tag,
        "MessageType": message_type,
        "messageType": message_type,
        "Type": muc_type,
        "type": muc_type,
        "Subject": subject,
        "subject": subject,
        "SenderSubject": subject,
        "senderSubject": subject,
        "DisplayName": display_name,
        "displayName": display_name,
    }

def chat_unified_message_payload(message: dict[str, Any]) -> dict[str, Any]:
    muc = chat_muc_message_payload(message)
    room = muc["Cid"]
    body = muc["Body"]
    message_id = muc["Id"]
    display_name = str(message.get("SenderDisplayName") or message.get("senderDisplayName") or muc["DisplayName"])
    message_parts = chat_message_parts_payload(message.get("MessageParts") or message.get("messageParts"), body)
    timestamp = str(message.get("Timestamp") or message.get("timestamp") or message.get("Time") or message.get("time") or utc_now())
    room_type = chat_unified_room_type(room)
    team = "Blue" if room_type == "Team" else ""
    notification_shown = bool(message.get("bNotificationShown", message.get("notificationShown", False)))
    return {
        "SenderDisplayName": display_name,
        "senderDisplayName": display_name,
        "SenderSubject": muc["SenderSubject"],
        "senderSubject": muc["SenderSubject"],
        "ContentType": "Text",
        "contentType": "Text",
        "DisplayMessage": body,
        "displayMessage": body,
        "MessageParts": message_parts,
        "messageParts": message_parts,
        "Timestamp": timestamp,
        "timestamp": timestamp,
        "RoomType": room_type,
        "roomType": room_type,
        "Team": team,
        "team": team,
        "ConversationID": room,
        "ConversationId": room,
        "conversationID": room,
        "conversationId": room,
        "MessageID": message_id,
        "messageID": message_id,
        "MessageId": message_id,
        "messageId": message_id,
        "Id": message_id,
        "id": message_id,
        "RecipientDisplayName": "",
        "recipientDisplayName": "",
        "bRead": muc["Read"],
        "BRead": muc["Read"],
        "read": muc["Read"],
        "bNotificationShown": notification_shown,
        "notificationShown": notification_shown,
        "EmojiMapping": None,
        "emojiMapping": None,
        "Body": body,
        "body": body,
        "Pid": muc["Pid"],
        "pid": muc["Pid"],
        "Subject": muc["Subject"],
        "subject": muc["Subject"],
        "GameName": muc["GameName"],
        "gameName": muc["GameName"],
        "TagLine": muc["TagLine"],
        "tagLine": muc["TagLine"],
        "Product": "ares",
        "product": "ares",
    }


def chat_room_infos(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    room_profile = profile or default_profile()
    current_party_id = party_id_for_profile(room_profile)
    profiles = party_profiles(game_state, current_party_id, room_profile)
    participant_pids = [profile["chat_pid"] for profile in profiles]
    joined_rooms = joined_chat_rooms_for_profile(game_state, room_profile)
    party_room = party_muc_name(current_party_id)
    rooms = [
        {
            "Cid": party_room,
            "cid": party_room,
            "id": party_room,
            "RoomID": party_room,
            "roomID": party_room,
            "RoomId": party_room,
            "roomId": party_room,
            "type": "groupchat",
            "Type": "groupchat",
            "RoomType": "GroupChat",
            "roomType": "GroupChat",
            "name": "Party",
            "Name": "Party",
            "mucName": party_room,
            "MUCName": party_room,
            "room": party_room,
            "Room": party_room,
            "message_history": True,
            "ConnectionWasInitiated": True,
            "connectionWasInitiated": True,
            "ConnectionWasConfirmed": True,
            "connectionWasConfirmed": True,
            "Subject": room_profile["subject"],
            "subject": room_profile["subject"],
            "TeamId": "",
            "TeamID": "",
            "teamId": "",
            "Side": "",
            "side": "",
            "uiState": {"hidden": False, "changedSinceHidden": False},
            "unreadCount": 0,
            "unread_count": 0,
            "muted": False,
            "Muted": False,
            "participants": participant_pids,
            "Participants": participant_pids,
        },
    ]
    if game_state and game_state.get("phase") in {"pregame", "core"}:
        rooms.extend(
            [
                {
                    "Cid": TEAM_MUC_NAME,
                    "cid": TEAM_MUC_NAME,
                    "id": TEAM_MUC_NAME,
                    "RoomID": TEAM_MUC_NAME,
                    "roomID": TEAM_MUC_NAME,
                    "RoomId": TEAM_MUC_NAME,
                    "roomId": TEAM_MUC_NAME,
                    "type": "groupchat",
                    "Type": "groupchat",
                    "RoomType": "GroupChat",
                    "roomType": "GroupChat",
                    "name": "Team",
                    "Name": "Team",
                    "mucName": TEAM_MUC_NAME,
                    "MUCName": TEAM_MUC_NAME,
                    "room": TEAM_MUC_NAME,
                    "Room": TEAM_MUC_NAME,
                    "message_history": True,
                    "ConnectionWasInitiated": True,
                    "connectionWasInitiated": True,
                    "ConnectionWasConfirmed": True,
                    "connectionWasConfirmed": True,
                    "Subject": room_profile["subject"],
                    "subject": room_profile["subject"],
                    "TeamId": "Blue",
                    "TeamID": "Blue",
                    "teamId": "Blue",
                    "Side": "Blue",
                    "side": "Blue",
                    "uiState": {"hidden": False, "changedSinceHidden": False},
                    "unreadCount": 0,
                    "unread_count": 0,
                    "muted": False,
                    "Muted": False,
                    "participants": participant_pids,
                    "Participants": participant_pids,
                },
                {
                    "Cid": ALL_MUC_NAME,
                    "cid": ALL_MUC_NAME,
                    "id": ALL_MUC_NAME,
                    "RoomID": ALL_MUC_NAME,
                    "roomID": ALL_MUC_NAME,
                    "RoomId": ALL_MUC_NAME,
                    "roomId": ALL_MUC_NAME,
                    "type": "groupchat",
                    "Type": "groupchat",
                    "RoomType": "GroupChat",
                    "roomType": "GroupChat",
                    "name": "All",
                    "Name": "All",
                    "mucName": ALL_MUC_NAME,
                    "MUCName": ALL_MUC_NAME,
                    "room": ALL_MUC_NAME,
                    "Room": ALL_MUC_NAME,
                    "message_history": True,
                    "ConnectionWasInitiated": True,
                    "connectionWasInitiated": True,
                    "ConnectionWasConfirmed": True,
                    "connectionWasConfirmed": True,
                    "Subject": room_profile["subject"],
                    "subject": room_profile["subject"],
                    "TeamId": "",
                    "TeamID": "",
                    "teamId": "",
                    "Side": "",
                    "side": "",
                    "uiState": {"hidden": False, "changedSinceHidden": False},
                    "unreadCount": 0,
                    "unread_count": 0,
                    "muted": False,
                    "Muted": False,
                    "participants": participant_pids,
                    "Participants": participant_pids,
                },
            ]
        )
    filtered_rooms = []
    for room in rooms:
        room_cid = str(room.get("cid") or room.get("Cid") or "")
        room.update(
            {
                "ConversationID": room_cid,
                "ConversationId": room_cid,
                "conversationID": room_cid,
                "conversationId": room_cid,
                "ConnectionState": "Connected",
                "connectionState": "Connected",
                "Group": room.get("name") or "Party",
                "group": room.get("name") or "Party",
                "DisplayGroup": room.get("Name") or "Party",
                "displayGroup": room.get("Name") or "Party",
                "ParticipantName": room_profile["display_name"],
                "participantName": room_profile["display_name"],
                "Product": "ares",
                "product": "ares",
            }
        )
        if room_cid not in joined_rooms:
            continue
        participants = chat_participants_for_room(game_state, room["cid"], room_profile)
        room_messages = chat_messages_for_room(game_state, room_cid)
        muc_messages = [chat_muc_message_payload(message) for message in room_messages]
        unified_messages = [chat_unified_message_payload(message) for message in room_messages]
        last_message = muc_messages[-1] if muc_messages else None
        last_unified_message = unified_messages[-1] if unified_messages else None
        room["MUCParticipants"] = participants
        room["mucParticipants"] = participants
        room["Messages"] = muc_messages
        room["messages"] = muc_messages
        room["UnifiedChatMessages"] = unified_messages
        room["AddedMessages"] = muc_messages
        room["LastMessage"] = last_message
        room["lastMessage"] = last_message
        room["MUCMessage"] = last_message
        room["UnifiedChatMessage"] = last_unified_message
        filtered_rooms.append(room)
    return filtered_rooms


def join_chat_room(game_state: dict[str, Any], cid: str | None, profile: dict[str, str] | None = None) -> bool:
    if not cid:
        return False
    if profile:
        by_subject = game_state.setdefault("joined_chat_rooms_by_subject", {})
        if isinstance(by_subject, dict):
            rooms = by_subject.setdefault(profile["subject"], [])
            if isinstance(rooms, list) and cid not in rooms:
                rooms.append(cid)
                return True
            return False
    rooms = game_state.setdefault("joined_chat_rooms", [])
    if isinstance(rooms, list) and cid not in rooms:
        rooms.append(cid)
        return True
    return False


def leave_chat_room(game_state: dict[str, Any], cid: str | None, profile: dict[str, str] | None = None) -> bool:
    if not cid:
        return False
    if profile:
        by_subject = game_state.setdefault("joined_chat_rooms_by_subject", {})
        if isinstance(by_subject, dict):
            rooms = by_subject.get(profile["subject"], [])
            if isinstance(rooms, list) and cid in rooms:
                rooms.remove(cid)
                return True
            return False
    rooms = game_state.setdefault("joined_chat_rooms", [])
    if isinstance(rooms, list) and cid in rooms:
        rooms.remove(cid)
        return True
    return False


def sync_party_chat_room(
    game_state: dict[str, Any],
    profile: dict[str, str],
    previous_party_id: str | None,
    new_party_id: str | None,
) -> bool:
    if not new_party_id:
        return False
    previous_cid = party_muc_name(previous_party_id) if previous_party_id else ""
    new_cid = party_muc_name(new_party_id)
    if previous_cid and previous_cid != new_cid:
        leave_chat_room(game_state, previous_cid, profile)
        return True
    return False


def chat_conversation_list(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    return chat_room_infos(game_state, profile)


def chat_conversations_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    conversations = chat_conversation_list(game_state, profile)
    return {
        "Conversations": conversations,
        "conversations": conversations,
        "MUCInfos": conversations,
        "mucInfos": conversations,
        "Scopes": [],
        "scopes": [],
    }


def chat_conversation_for_cid_payload(
    game_state: dict[str, Any] | None = None,
    cid: str | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    rooms = chat_room_infos(game_state, profile)
    if cid:
        rooms = [room for room in rooms if room.get("Cid") == cid or room.get("cid") == cid]
    room = rooms[0] if rooms else {}
    payload = dict(room)
    payload.update(
        {
            "MUCInfo": room,
            "mucInfo": room,
            "Conversation": room,
            "conversation": room,
        }
    )
    return payload


def chat_participants_for_room(
    game_state: dict[str, Any] | None = None,
    cid: str | None = None,
    profile: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    profile = profile or default_profile()
    room = cid or party_muc_name(party_id_for_profile(profile))
    room_party_id = party_id_from_muc(room) or party_id_for_profile(profile)
    participants = []
    for participant_profile in party_profiles(game_state, room_party_id, profile):
        participant = {
            "Cid": room,
            "cid": room,
            "CID": room,
            "RoomID": room,
            "roomID": room,
            "RoomId": room,
            "roomId": room,
            "Pid": participant_profile["chat_pid"],
            "pid": participant_profile["chat_pid"],
            "PID": participant_profile["chat_pid"],
            "Jid": participant_profile["chat_full_pid"],
            "jid": participant_profile["chat_full_pid"],
            "JID": participant_profile["chat_full_pid"],
            "puuid": participant_profile["subject"],
            "Puuid": participant_profile["subject"],
            "Subject": participant_profile["subject"],
            "subject": participant_profile["subject"],
            "Name": participant_profile["game_name"],
            "name": participant_profile["game_name"],
            "Nick": participant_profile["display_name"],
            "nick": participant_profile["display_name"],
            "GameName": participant_profile["game_name"],
            "gameName": participant_profile["game_name"],
            "game_name": participant_profile["game_name"],
            "GameTag": participant_profile["tag_line"],
            "gameTag": participant_profile["tag_line"],
            "game_tag": participant_profile["tag_line"],
            "TagLine": participant_profile["tag_line"],
            "tagLine": participant_profile["tag_line"],
            "DisplayName": participant_profile["display_name"],
            "displayName": participant_profile["display_name"],
            "display_name": participant_profile["display_name"],
            "region": DEFAULT_REGION,
            "resource": CHAT_RESOURCE,
            "Resource": CHAT_RESOURCE,
            "Product": "ares",
            "product": "ares",
            "Affiliation": "member",
            "affiliation": "member",
            "Presence": presence_payload(game_state, participant_profile),
            "presence": presence_payload(game_state, participant_profile),
            "muted": False,
            "Muted": False,
            "role": "participant",
            "Role": "participant",
        }
        participants.append(participant)
    return participants


def chat_muc_participants_for_room(game_state: dict[str, Any] | None = None, cid: str | None = None) -> list[dict[str, Any]]:
    return chat_participants_for_room(game_state, cid)


def chat_participants_payload(
    game_state: dict[str, Any] | None = None,
    cid: str | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    rooms = chat_room_infos(game_state, profile)
    if cid:
        rooms = [room for room in rooms if room.get("Cid") == cid or room.get("cid") == cid]
    room_ids = [str(room.get("cid") or room.get("Cid") or "") for room in rooms if room.get("cid") or room.get("Cid")]
    participants = []
    for room in rooms:
        room_participants = chat_participants_for_room(game_state, room["cid"], profile)
        participants.extend(room_participants)
    first_participant = participants[0] if participants else None
    resolved_cid = str(cid or (room_ids[0] if len(room_ids) == 1 else ""))
    if not resolved_cid and first_participant:
        resolved_cid = str(first_participant.get("cid") or first_participant.get("Cid") or "")
    return {
        "Cid": resolved_cid,
        "cid": resolved_cid,
        "CID": resolved_cid,
        "ConversationID": resolved_cid,
        "ConversationId": resolved_cid,
        "conversationID": resolved_cid,
        "conversationId": resolved_cid,
        "RoomID": resolved_cid,
        "RoomId": resolved_cid,
        "roomID": resolved_cid,
        "roomId": resolved_cid,
        "Room": resolved_cid,
        "room": resolved_cid,
        "Cids": room_ids,
        "cids": room_ids,
        "ConversationIDs": room_ids,
        "conversationIDs": room_ids,
        "RoomIDs": room_ids,
        "roomIDs": room_ids,
        "MUCParticipants": participants,
        "mucParticipants": participants,
        "MUCParticipant": first_participant,
        "mucParticipant": first_participant,
        "Participants": participants,
        "participants": participants,
        "Participant": first_participant,
        "participant": first_participant,
    }


def chat_participants_uri(cid: str | None = None) -> str:
    base = "/chat/v5/participants"
    if cid:
        return f"{base}?cid={cid}"
    return base


def chat_participants_uri_variants(cid: str | None = None) -> list[str]:
    if not cid:
        return [chat_participants_uri(None)]
    encoded = quote(str(cid), safe="")
    variants = [
        chat_participants_uri(cid),
        f"/chat/v5/participants?cid={encoded}",
        f"/chat/v5/participants/?cid={cid}",
        f"/chat/v5/participants/?cid={encoded}",
    ]
    unique: list[str] = []
    for uri in variants:
        if uri not in unique:
            unique.append(uri)
    return unique




def chat_messages_payload(game_state: dict[str, Any] | None = None, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    messages = messages or []
    muc_messages = [chat_muc_message_payload(message) for message in messages]
    unified_messages = [chat_unified_message_payload(message) for message in messages]
    first = muc_messages[0] if muc_messages else None
    last = muc_messages[-1] if muc_messages else None
    first_unified = unified_messages[0] if unified_messages else None
    cid = ""
    if first:
        cid = str(first.get("Cid") or first.get("cid") or first.get("ConversationID") or first.get("conversationID") or "")
    return {
        "Cid": cid,
        "cid": cid,
        "ConversationID": cid,
        "conversationID": cid,
        "ConversationId": cid,
        "conversationId": cid,
        "RoomID": cid,
        "roomID": cid,
        "RoomId": cid,
        "roomId": cid,
        "messages": muc_messages,
        "Messages": muc_messages,
        "MUCMessage": first,
        "UnifiedChatMessages": unified_messages,
        "UnifiedChatMessage": first_unified,
        "AddedMessages": muc_messages,
        "LastMessage": last,
        "lastMessage": last,
    }


def chat_message_response_payload(message: dict[str, Any]) -> dict[str, Any]:
    muc = chat_muc_message_payload(message)
    unified = chat_unified_message_payload(message)
    payload = dict(muc)
    payload.update(
        {
            "ConversationID": muc["Cid"],
            "ConversationId": muc["Cid"],
            "conversationID": muc["Cid"],
            "conversationId": muc["Cid"],
            "RoomID": muc["Cid"],
            "RoomId": muc["Cid"],
            "roomID": muc["Cid"],
            "roomId": muc["Cid"],
            "DisplayMessage": unified["DisplayMessage"],
            "displayMessage": unified["DisplayMessage"],
            "Message": unified["DisplayMessage"],
            "message": unified["DisplayMessage"],
            "Content": unified["DisplayMessage"],
            "content": unified["DisplayMessage"],
            "ContentType": "Text",
            "contentType": "Text",
            "MessageParts": unified["MessageParts"],
            "messageParts": unified["MessageParts"],
            "SenderDisplayName": unified["SenderDisplayName"],
            "senderDisplayName": unified["SenderDisplayName"],
            "Timestamp": unified["Timestamp"],
            "timestamp": unified["Timestamp"],
            "Product": "ares",
            "product": "ares",
            "UnifiedChatMessage": unified,
            "unifiedChatMessage": unified,
        }
    )
    payload.update(chat_messages_payload(None, [message]))
    return payload


def chat_message_payload(body: Any, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    room = chat_message_body_value(
        body,
        "ConversationID",
        "ConversationId",
        "conversationID",
        "conversationId",
        "RoomID",
        "RoomId",
        "roomID",
        "roomId",
        "Cid",
        "cid",
        "Room",
        "room",
    ) or party_muc_name(party_id_for_profile(profile))
    text = chat_message_text(body)
    request_type = chat_muc_type_value(chat_message_body_value(body, "Type", "type") or "groupchat")
    message_type = chat_text_room_type_value(chat_message_body_value(body, "MessageType", "messageType") or request_type)
    message_id = str(uuid.uuid4())
    created = utc_now()
    unix_time = int(time.time())
    display_group = "Party" if room.startswith("ares-party-") else "Team" if room == TEAM_MUC_NAME else "All" if room == ALL_MUC_NAME else "Chat"
    message_parts = chat_message_parts_payload(
        body.get("MessageParts") or body.get("messageParts") or body.get("Parts") or body.get("parts") if isinstance(body, dict) else None,
        text,
    )
    payload = {
        "Id": message_id,
        "id": message_id,
        "ConversationID": room,
        "ConversationId": room,
        "conversationID": room,
        "conversationId": room,
        "RoomID": room,
        "roomID": room,
        "RoomId": room,
        "roomId": room,
        "Room": room,
        "room": room,
        "RoomType": message_type,
        "roomType": message_type,
        "Cid": room,
        "cid": room,
        "From": profile["chat_pid"],
        "from": profile["chat_pid"],
        "Sender": profile["chat_pid"],
        "sender": profile["chat_pid"],
        "SenderSubject": profile["subject"],
        "senderSubject": profile["subject"],
        "Pid": profile["chat_pid"],
        "pid": profile["chat_pid"],
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "Name": profile["game_name"],
        "name": profile["game_name"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "SenderDisplayName": profile["display_name"],
        "senderDisplayName": profile["display_name"],
        "GameName": profile["game_name"],
        "gameName": profile["game_name"],
        "GameTag": profile["tag_line"],
        "gameTag": profile["tag_line"],
        "TagLine": profile["tag_line"],
        "tagLine": profile["tag_line"],
        "resource": CHAT_RESOURCE,
        "Resource": CHAT_RESOURCE,
        "Product": "ares",
        "product": "ares",
        "Group": display_group,
        "group": display_group,
        "Team": "",
        "team": "",
        "DisplayGroup": display_group,
        "displayGroup": display_group,
        "Note": "",
        "note": "",
        "Summary": text,
        "summary": text,
        "Body": text,
        "body": text,
        "DisplayMessage": text,
        "displayMessage": text,
        "Message": text,
        "message": text,
        "Content": text,
        "content": text,
        "ContentType": "Text",
        "contentType": "Text",
        "MessageParts": message_parts,
        "messageParts": message_parts,
        "Type": request_type,
        "type": request_type,
        "MUCType": request_type,
        "mucType": request_type,
        "MessageType": message_type,
        "messageType": message_type,
        "Read": True,
        "read": True,
        "TimeStamp": created,
        "timeStamp": created,
        "Timestamp": created,
        "timestamp": created,
        "Time": created,
        "time": created,
        "UnixTime": unix_time,
        "unixTime": unix_time,
        "CreatedDatetime": created,
        "createdDatetime": created,
    }
    unified_message = {
        "Id": message_id,
        "id": message_id,
        "MessageID": message_id,
        "messageID": message_id,
        "MessageId": message_id,
        "messageId": message_id,
        "ConversationID": room,
        "ConversationId": room,
        "conversationID": room,
        "conversationId": room,
        "RoomID": room,
        "RoomId": room,
        "roomID": room,
        "roomId": room,
        "RoomType": display_group,
        "roomType": display_group,
        "Team": "Blue" if display_group == "Team" else "",
        "team": "Blue" if display_group == "Team" else "",
        "Cid": room,
        "cid": room,
        "SenderSubject": profile["subject"],
        "senderSubject": profile["subject"],
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "Pid": profile["chat_pid"],
        "pid": profile["chat_pid"],
        "Sender": profile["chat_pid"],
        "sender": profile["chat_pid"],
        "SenderDisplayName": profile["display_name"],
        "senderDisplayName": profile["display_name"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "GameName": profile["game_name"],
        "gameName": profile["game_name"],
        "TagLine": profile["tag_line"],
        "tagLine": profile["tag_line"],
        "DisplayMessage": text,
        "displayMessage": text,
        "Message": text,
        "message": text,
        "Body": text,
        "body": text,
        "Content": text,
        "content": text,
        "ContentType": "Text",
        "contentType": "Text",
        "MessageParts": message_parts,
        "messageParts": message_parts,
        "Timestamp": created,
        "timestamp": created,
        "TimeStamp": created,
        "timeStamp": created,
        "UnixTime": unix_time,
        "unixTime": unix_time,
        "Type": request_type,
        "type": request_type,
        "RoomTypeValue": message_type,
        "roomTypeValue": message_type,
        "RecipientDisplayName": "",
        "recipientDisplayName": "",
        "bRead": True,
        "BRead": True,
        "read": True,
        "bNotificationShown": False,
        "notificationShown": False,
        "EmojiMapping": None,
        "emojiMapping": None,
        "Product": "ares",
        "product": "ares",
    }
    payload["UnifiedChatMessage"] = unified_message
    payload["unifiedChatMessage"] = unified_message
    return payload




_LOCAL_NAMES = {
    name
    for name, value in globals().items()
    if callable(value) and getattr(value, "__module__", None) == __name__
}
