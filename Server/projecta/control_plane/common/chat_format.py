"""Pure chat message and route-value normalization helpers."""

from __future__ import annotations

from typing import Any


def chat_muc_type_value(value: Any) -> str:
    normalized = str(value or "").strip()
    if normalized.lower() in {"", "chat", "groupchat", "group_chat", "group-chat", "group"}:
        return "groupchat"
    return normalized


def chat_text_room_type_value(value: Any) -> str:
    normalized = str(value or "").strip()
    lowered = normalized.lower()
    if lowered in {"", "chat", "groupchat", "group_chat", "group-chat", "group"}:
        return "GroupChat"
    if lowered in {"friendchat", "friend_chat", "friend-chat"}:
        return "FriendChat"
    if lowered in {"directmessage", "direct_message", "direct-message", "whisper"}:
        return "DirectMessage"
    return normalized


def chat_message_room(message: dict[str, Any]) -> str:
    return str(
        message.get("Cid")
        or message.get("cid")
        or message.get("ConversationID")
        or message.get("conversationID")
        or message.get("RoomID")
        or message.get("roomID")
        or ""
    )


def chat_message_part_payload(part: Any, fallback_text: str) -> dict[str, Any]:
    raw = part if isinstance(part, dict) else {}
    part_type = str(raw.get("Type") or raw.get("type") or "Text")
    text = str(
        raw.get("MessageText")
        or raw.get("messageText")
        or raw.get("Content")
        or raw.get("content")
        or raw.get("Text")
        or raw.get("text")
        or raw.get("Body")
        or raw.get("body")
        or fallback_text
    )
    notification_target = str(raw.get("NotificationTarget") or raw.get("notificationTarget") or "")
    emoji_key = str(raw.get("EmojiKey") or raw.get("emojiKey") or "")
    return {
        "Type": part_type,
        "type": part_type,
        "ContentType": part_type,
        "contentType": part_type,
        "MessageText": text,
        "messageText": text,
        "NotificationTarget": notification_target,
        "notificationTarget": notification_target,
        "EmojiKey": emoji_key,
        "emojiKey": emoji_key,
        "Content": text,
        "content": text,
        "Text": text,
        "text": text,
    }


def chat_message_parts_payload(parts: Any, fallback_text: str) -> list[dict[str, Any]]:
    if isinstance(parts, list) and parts:
        return [chat_message_part_payload(part, fallback_text) for part in parts]
    return [chat_message_part_payload({}, fallback_text)]


def subject_from_chat_pid(raw: str | None) -> str:
    value = str(raw or "").strip()
    if "/" in value:
        value = value.split("/", 1)[0]
    if "@" in value:
        value = value.split("@", 1)[0]
    return value


def chat_message_body_value(body: Any, *keys: str) -> str:
    if not isinstance(body, dict):
        return ""
    for key in keys:
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
    nested = body.get("MUCMessage") or body.get("mucMessage") or body.get("Message") or body.get("message")
    if isinstance(nested, dict):
        value = chat_message_body_value(nested, *keys)
        if value:
            return value
    return ""


def chat_message_text(body: Any) -> str:
    value = chat_message_body_value(body, "Message", "message", "Body", "body", "Text", "text", "Content", "content")
    if value:
        return value
    if isinstance(body, dict):
        for key in ("MessageParts", "messageParts", "Parts", "parts"):
            parts = body.get(key)
            if not isinstance(parts, list):
                continue
            for part in parts:
                if isinstance(part, dict):
                    value = chat_message_body_value(part, "Text", "text", "Content", "content", "Body", "body")
                    if value:
                        return value
    return ""
