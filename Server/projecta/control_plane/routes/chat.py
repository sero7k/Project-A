"""Chat, conversations, participants, messages, and presence routes."""

from __future__ import annotations

from urllib.parse import unquote


def _cid_from_body(body: object) -> str:
    request_body = body if isinstance(body, dict) else {}
    return str(
        request_body.get("Cid")
        or request_body.get("cid")
        or request_body.get("ConversationID")
        or request_body.get("ConversationId")
        or request_body.get("conversationID")
        or request_body.get("conversationId")
        or request_body.get("RoomID")
        or request_body.get("RoomId")
        or request_body.get("roomID")
        or request_body.get("roomId")
        or request_body.get("Room")
        or request_body.get("room")
        or ""
    )


def _merge_stored_messages(cp, messages: list[dict], cid: str) -> list[dict]:
    try:
        stored_messages = cp.ACCOUNT_STORE.chat_messages_for_room(cid, 100)
        known_ids = {str(message.get("ID") or message.get("id") or message.get("messageID") or "") for message in messages}
        for stored_message in stored_messages:
            stored_id = str(stored_message.get("ID") or stored_message.get("id") or stored_message.get("messageID") or "")
            if stored_id not in known_ids:
                messages.append(stored_message)
    except Exception:
        pass
    return messages


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    game_state = ctx.game_state
    json_body = ctx.json_body

    if route_path == "/chat/v1/session":
        ctx.write(200, cp.chat_session_payload(ctx.current_profile()), localize=False)
    elif route_path == "/chat/v2/me":
        profile = ctx.current_profile()
        updates = game_state.setdefault("presence_by_profile", {})
        if ctx.command in {"PUT", "POST", "PATCH"} and json_body:
            if isinstance(json_body, dict):
                update = {
                    key: json_body[key]
                    for key in ("actor", "basic", "details", "location", "msg", "shared", "state", "summary")
                    if key in json_body
                }
                private_value = json_body.get("private")
                if not isinstance(private_value, str) or not private_value:
                    private_value = json_body.get("Private")
                if isinstance(private_value, str) and private_value:
                    update["private"] = private_value
                private_jwt = json_body.get("privateJwt")
                if private_jwt is None:
                    private_jwt = json_body.get("PrivateJwt")
                if private_jwt is not None:
                    update["privateJwt"] = private_jwt
                product_value = (
                    json_body.get("product")
                    or json_body.get("Product")
                    or json_body.get("presenceProduct")
                    or json_body.get("PresenceProduct")
                )
                if isinstance(product_value, str) and product_value:
                    update["product"] = product_value
                updates[profile["key"]] = update
        presence = cp.presence_payload(game_state, profile, updates.get(profile["key"]))
        ctx.broadcast_presence_update()
        ctx.write(200, presence, localize=False)
    elif route_path == "/chat/v4/presences":
        ctx.write(200, cp.presences_payload(game_state, ctx.current_profile()), localize=False)
    elif route_path.rstrip("/") == "/chat/v5/conversations/read":
        ctx.write(200, cp.chat_read_ack_payload(json_body))
    elif route_path.rstrip("/") == "/chat/v5/conversations":
        if ctx.command == "DELETE":
            profile = ctx.current_profile()
            cid = _cid_from_body(json_body)
            payload = cp.chat_conversation_for_cid_payload(game_state, cid, profile)
            left = cp.leave_chat_room(game_state, cid, profile)
            ctx.send_wampv1_event_to_profile(
                profile,
                "OnJsonApiEvent_chat_v5_conversations",
                cp.json_api_event("/chat/v5/conversations", payload, "Delete"),
            )
            empty_participants = {
                "Cid": cid,
                "cid": cid,
                "MUCParticipants": [],
                "mucParticipants": [],
                "Participants": [],
                "participants": [],
                "MUCParticipant": None,
                "mucParticipant": None,
                "Participant": None,
                "participant": None,
            }
            for uri in cp.chat_participants_uri_variants(cid):
                ctx.send_wampv1_event_to_profile(
                    profile,
                    "OnJsonApiEvent_chat_v5_participants",
                    cp.json_api_event(uri, empty_participants, "Delete" if left else "Update"),
                    {"OnJsonApiEvent_chat_v5_conversations"},
                )
            ctx.write(200, {"ok": True, "left": left, "Cid": cid, "cid": cid}, localize=False)
        elif ctx.command == "POST":
            profile = ctx.current_profile()
            request_body = json_body if isinstance(json_body, dict) else {}
            cid = _cid_from_body(request_body)
            room_cid = str(cid or cp.party_muc_name(cp.party_id_for_profile(profile)))
            password = request_body.get("Password") or request_body.get("password") or request_body.get("Token") or request_body.get("token")
            if not cp.chat_room_token_is_valid(room_cid, str(password) if password else None, profile):
                ctx.write(403, {"HTTPStatus": 403, "ErrorCode": "Invalid", "Message": "Invalid room token", "errorCode": "Invalid", "errorMessage": "Invalid room token", "type": "Invalid"})
                return True
            if not cp.chat_room_is_available_to_profile(game_state, profile, room_cid):
                ctx.write(404, {"HTTPStatus": 404, "ErrorCode": "RoomUnavailable", "Message": "Room unavailable", "errorCode": "RoomUnavailable", "errorMessage": "Room unavailable", "type": "RoomUnavailable"})
                return True
            joined_now = cp.join_chat_room(game_state, room_cid, profile)
            payload = cp.chat_conversation_for_cid_payload(game_state, room_cid, profile)
            room_cid = str(payload.get("cid") or payload.get("Cid") or room_cid or "")
            ctx.write(200, payload, localize=False)
            if room_cid:
                participants = cp.chat_participants_payload(game_state, room_cid, profile)
                association_payload = cp.chat_conversations_payload(game_state, profile)
                association_payload.update(
                    {
                        "Conversation": payload.get("Conversation") or payload,
                        "conversation": payload.get("conversation") or payload,
                        "MUCInfo": payload.get("MUCInfo") or payload,
                        "mucInfo": payload.get("mucInfo") or payload,
                    }
                )
                event_type = "Create" if joined_now else "Update"
                ctx.send_wampv1_event_to_profile(
                    profile,
                    "OnJsonApiEvent_chat_v5_conversations",
                    cp.json_api_event("/chat/v5/conversations", association_payload, event_type),
                )
                for uri in cp.chat_participants_uri_variants(room_cid):
                    ctx.send_wampv1_event_to_profile(
                        profile,
                        "OnJsonApiEvent_chat_v5_participants",
                        cp.json_api_event(uri, participants, event_type),
                        {"OnJsonApiEvent_chat_v5_conversations"},
                    )
                ctx.send_wampv1_event_to_profile(
                    profile,
                    "OnJsonApiEvent_chat_v5_participants",
                    cp.json_api_event(cp.chat_participants_uri(), cp.chat_participants_payload(game_state, None, profile), "Update"),
                    {"OnJsonApiEvent_chat_v5_conversations"},
                )
        else:
            ctx.write(200, cp.chat_conversations_payload(game_state, ctx.current_profile()), localize=False)
    elif route_path.startswith("/chat/v5/conversations/"):
        profile = ctx.current_profile()
        suffix = route_path[len("/chat/v5/conversations/") :].strip("/")
        if suffix.endswith("/read"):
            cid = unquote(suffix[: -len("/read")].strip("/"))
            ctx.write(200, cp.chat_read_ack_payload(json_body, cid), localize=False)
        elif suffix.endswith("/messages"):
            cid = unquote(suffix[: -len("/messages")].strip("/"))
            with ctx.server.chat_lock:
                messages = [message for message in ctx.server.chat_messages if message.get("Cid") == cid or message.get("cid") == cid]
            ctx.write(200, cp.chat_messages_payload(game_state, _merge_stored_messages(cp, messages, cid)), localize=False)
        else:
            cid = unquote(suffix)
            ctx.write(200, cp.chat_conversation_for_cid_payload(game_state, cid, profile), localize=False)
    elif route_path.rstrip("/") == "/chat/v5/participants":
        cid = (ctx.query_params.get("cid") or ctx.query_params.get("Cid") or [None])[0]
        ctx.write(200, cp.chat_participants_payload(game_state, cid, ctx.current_profile()), localize=False)
    elif route_path.rstrip("/") == "/chat/v5/messages":
        if ctx.command == "POST":
            profile = ctx.current_profile()
            message = cp.chat_message_payload(json_body, profile)
            cid = str(message.get("Cid") or message.get("cid") or "")
            if not cp.profile_has_joined_chat_room(game_state, profile, cid):
                if cp.chat_room_is_available_to_profile(game_state, profile, cid):
                    ctx.activate_chat_room(cid)
                else:
                    ctx.write(404, {"HTTPStatus": 404, "ErrorCode": "RoomUnavailable", "Message": "Room unavailable", "errorCode": "RoomUnavailable", "errorMessage": "Room unavailable", "type": "RoomUnavailable"})
                    return True
            with ctx.server.chat_lock:
                ctx.server.chat_messages.append(message)
                game_state["chat_messages"] = list(ctx.server.chat_messages)
            try:
                cp.ACCOUNT_STORE.append_chat_message(message)
            except Exception:
                pass
            event = cp.json_api_event("/chat/v5/messages", cp.chat_messages_payload(game_state, [message]), "Update")
            ctx.broadcast_chat_message_event(cid, event)
            ctx.broadcast_chat_conversation_update(cid)
            ctx.write(200, cp.chat_message_response_payload(message), localize=False)
        else:
            cid = (ctx.query_params.get("cid") or ctx.query_params.get("Cid") or [None])[0]
            with ctx.server.chat_lock:
                messages = list(ctx.server.chat_messages)
            if cid:
                messages = [message for message in messages if message.get("Cid") == cid or message.get("cid") == cid]
                messages = _merge_stored_messages(cp, messages, cid)
            ctx.write(200, cp.chat_messages_payload(game_state, messages), localize=False)
    elif route_path.startswith("/chat/v5/messages/") and route_path.endswith("/read"):
        ctx.write(200, {"ok": True})
    else:
        return False
    return True
