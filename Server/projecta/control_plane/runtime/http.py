"""HTTP and WebSocket runtime for the Project A control-plane server."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import socket
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .route_dispatch import build_route_context, dispatch_http_route


def _sync_app_globals() -> None:
    from .. import app as cp

    globals().update({name: value for name, value in vars(cp).items() if not name.startswith("_")})


_sync_app_globals()


class DualProtocolHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler_cls: type[BaseHTTPRequestHandler], ssl_context: ssl.SSLContext):
        self.ssl_context = ssl_context
        super().__init__(server_address, handler_cls)

    def get_request(self) -> tuple[socket.socket, tuple[str, int]]:
        sock, addr = self.socket.accept()
        first = sock.recv(1, socket.MSG_PEEK)
        if first == b"\x16":
            sock = self.ssl_context.wrap_socket(sock, server_side=True)
        return sock, addr


class ProbeHandler(BaseHTTPRequestHandler):
    def __getattribute__(self, name: str) -> Any:
        if name.startswith("_"):
            _sync_app_globals()
        return super().__getattribute__(name)

    server_version = "RNetProbe/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _read_body(self) -> bytes:
        length = int(self.headers.get("content-length") or "0")
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _profile_from_request(self, path: str = "", body: dict[str, Any] | None = None) -> dict[str, str]:
        token = ""
        auth = self.headers.get("authorization") or ""
        if auth.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8", "replace")
                token = decoded.rsplit(":", 1)[-1]
            except Exception:
                token = ""
        elif auth.lower().startswith("bearer "):
            bearer = auth.split(" ", 1)[1].strip()
            # Prefer exact tokens issued by this local server. They include a
            # digest suffix, so prefix-only parsing is deliberately a fallback.
            for known_profile in profiles_from_game_state(getattr(self.server, "game_state", None)):
                if bearer in {
                    account_token("access-token", known_profile),
                    account_token("entitlements-token", known_profile),
                }:
                    token = known_profile["key"]
                    break
            for bare, prefix in (
                ("local-access-token", "local-access-token-"),
                ("local-entitlements-token", "local-entitlements-token-"),
            ):
                if token:
                    break
                if bearer == bare:
                    token = getattr(self.server, "default_account_login", DEFAULT_PROFILE_KEY)
                    break
                if bearer.startswith(prefix):
                    token = bearer[len(prefix) :]
                    break
            if not token:
                token = bearer
        elif auth and not auth.lower().startswith(("digest ", "negotiate ", "ntlm ")):
            token = auth.strip()

        if not token:
            for header_name in (
                "x-project-a-account",
                "x-local-account",
                "x-riot-local-account",
                "x-rnet-auth-token",
                "x-remoting-auth-token",
            ):
                header_value = self.headers.get(header_name)
                if header_value:
                    token = header_value.strip()
                    break

        if not token:
            try:
                params = parse_qs(urlparse(self.path).query)
            except Exception:
                params = {}
            for name in ("account", "login", "riotName", "riot_name", "gameName", "game_name"):
                values = params.get(name)
                if values:
                    token = values[0]
                    if name in {"riotName", "riot_name", "gameName", "game_name"}:
                        tag = (params.get("tagLine") or params.get("tag_line") or params.get("tag") or [""])[0]
                        if tag:
                            token = f"{token}#{tag}"
                    break

        if not token and isinstance(body, dict):
            game_name, tag_line = alias_fields_from_body(body, {"game_name": "", "tag_line": ""})
            if game_name and tag_line:
                token = f"{game_name}#{tag_line}"

        if not token:
            subject_match = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", path)
            if subject_match:
                account = ACCOUNT_STORE.get_account_by_subject(subject_match.group(0))
                if account:
                    token = account.account_key

        if not token and isinstance(body, dict):
            for field in ("Subject", "subject", "puuid", "Puuid"):
                raw = body.get(field)
                if isinstance(raw, str):
                    account = ACCOUNT_STORE.get_account_by_subject(raw)
                    if account:
                        token = account.account_key
                if token:
                    break

        return profile_by_login(token or getattr(self.server, "default_account_login", DEFAULT_PROFILE_KEY))

    def _current_profile(self) -> dict[str, str]:
        return getattr(self, "profile", default_profile())

    def _access_token_payload(self) -> dict[str, Any]:
        return client_payloads.access_token_payload(self._current_profile())

    def _entitlements_token_payload(self) -> dict[str, Any]:
        owned = all_store_entitlements_payload(getattr(self.server, "game_state", None), self._current_profile())
        return client_payloads.entitlements_token_payload(self._current_profile(), owned)

    def _write(self, status: int, body: Any, content_type: str = "application/json", localize: bool = True) -> None:
        if localize and isinstance(body, (dict, list)):
            body = localize_payload(body, self._current_profile())
        if isinstance(body, (dict, list)):
            raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
        elif isinstance(body, str):
            raw = body.encode("utf-8")
        else:
            raw = bytes(body)
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(raw)))
        self.send_header("connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)
        self._record_response(status, raw, content_type)
        persist_state = getattr(self.server, "persist_state", None)
        if callable(persist_state):
            persist_state()

    def _base_url(self) -> str:
        host = self.headers.get("host") or f"127.0.0.1:{self.server.server_address[1]}"
        return f"http://{host}"

    def _config_payload(self) -> dict[str, Any]:
        base = self._base_url()
        return client_payloads.config_payload(base, client_version=CLIENT_VERSION, feedback_locale=PLAYER_FEEDBACK_LOCALE, feedback_shard=PLAYER_FEEDBACK_SHARD)

    def _process_control_payload(self) -> dict[str, Any]:
        return client_payloads.process_control_payload(self.headers)

    def _plugin_manager_payload(self) -> dict[str, Any]:
        return client_payloads.plugin_manager_payload(CLIENT_VERSION)

    def _record(self, body: bytes) -> None:
        parsed = urlparse(self.path)
        body_text = body.decode("utf-8", "replace")
        auth = self.headers.get("authorization")
        auth_decoded = None
        if auth and auth.lower().startswith("basic "):
            try:
                auth_decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8", "replace")
            except Exception as exc:  # pragma: no cover - diagnostic path
                auth_decoded = f"<decode failed: {exc}>"
        entry = {
            "ts": time.time(),
            "client": self.client_address[0],
            "client_port": self.client_address[1],
            "profile_id": self._current_profile()["key"],
            "subject": self._current_profile()["subject"],
            "method": self.command,
            "path": parsed.path,
            "query": parsed.query,
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "auth_decoded": auth_decoded,
            "body": body_text[:64000],
            "body_length": len(body_text),
            "body_truncated": len(body_text) > 64000,
        }
        with self.server.log_lock:
            with self.server.request_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")

    def _record_response(self, status: int, body: bytes, content_type: str) -> None:
        parsed = urlparse(self.path)
        body_text = body.decode("utf-8", "replace")
        entry = {
            "ts": time.time(),
            "client": self.client_address[0],
            "client_port": self.client_address[1],
            "profile_id": self._current_profile()["key"],
            "subject": self._current_profile()["subject"],
            "response": True,
            "path": parsed.path,
            "status": status,
            "content_type": content_type,
            "body": body_text[:12000],
            "body_length": len(body_text),
            "body_truncated": len(body_text) > 12000,
        }
        with self.server.log_lock:
            with self.server.request_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")

    def _record_ws(self, direction: str, payload: Any) -> None:
        entry = {
            "ts": time.time(),
            "client": self.client_address[0],
            "client_port": self.client_address[1],
            "profile_id": self._current_profile()["key"],
            "subject": self._current_profile()["subject"],
            "websocket": True,
            "direction": direction,
            "payload": payload,
        }
        with self.server.log_lock:
            with self.server.request_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")

    def _ws_read_exact(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self.rfile.read(n - len(data))
            if not chunk:
                raise ConnectionError("websocket closed while reading")
            data += chunk
        return data

    def _ws_read_frame(self) -> tuple[int, bytes]:
        header = self._ws_read_exact(2)
        opcode = header[0] & 0x0F
        masked = bool(header[1] & 0x80)
        length = header[1] & 0x7F
        if length == 126:
            length = int.from_bytes(self._ws_read_exact(2), "big")
        elif length == 127:
            length = int.from_bytes(self._ws_read_exact(8), "big")
        mask = self._ws_read_exact(4) if masked else b""
        payload = self._ws_read_exact(length) if length else b""
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    def _ws_write_frame(self, opcode: int, payload: bytes) -> None:
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(length)
        elif length <= 0xFFFF:
            header.append(126)
            header += length.to_bytes(2, "big")
        else:
            header.append(127)
            header += length.to_bytes(8, "big")
        self.wfile.write(bytes(header) + payload)
        self.wfile.flush()

    def _ws_send_json(self, message: list[Any]) -> None:
        lock = getattr(self, "ws_write_lock", None)
        if lock is None:
            self._record_ws("out", message)
            self._ws_write_frame(1, json.dumps(message, separators=(",", ":")).encode("utf-8"))
            return
        with lock:
            self._record_ws("out", message)
            self._ws_write_frame(1, json.dumps(message, separators=(",", ":")).encode("utf-8"))

    def _ws_send_wampv1_event(self, topic: str, event: Any) -> None:
        self._ws_send_json([8, topic, event])

    def _broadcast_wampv1_event(self, topic: str, event: Any) -> None:
        with self.server.ws_lock:
            clients = list(self.server.ws_clients)
        for client in clients:
            if topic not in getattr(client, "ws_topics", set()):
                continue
            try:
                client._ws_send_wampv1_event(topic, event)
            except Exception as exc:
                client._record_ws("broadcast-failed", {"topic": topic, "error": str(exc)})

    def _broadcast_chat_message_event(self, cid: str, event: Any) -> None:
        topic = "OnJsonApiEvent_chat_v5_messages"
        game_state = self.server.game_state
        with self.server.ws_lock:
            clients = list(self.server.ws_clients)
        for client in clients:
            if topic not in getattr(client, "ws_topics", set()):
                continue
            client_profile = getattr(client, "profile", None) or default_profile()
            if not profile_has_joined_chat_room(game_state, client_profile, cid):
                continue
            try:
                client._ws_send_wampv1_event(topic, event)
            except Exception as exc:
                client._record_ws("chat-broadcast-failed", {"topic": topic, "cid": cid, "error": str(exc)})

    def _broadcast_chat_conversation_update(self, cid: str) -> None:
        topic = "OnJsonApiEvent_chat_v5_conversations"
        game_state = self.server.game_state
        with self.server.ws_lock:
            clients = list(self.server.ws_clients)
        for client in clients:
            if topic not in getattr(client, "ws_topics", set()):
                continue
            client_profile = getattr(client, "profile", None) or default_profile()
            if not profile_has_joined_chat_room(game_state, client_profile, cid):
                continue
            try:
                client._ws_send_wampv1_event(
                    topic,
                    json_api_event("/chat/v5/conversations", chat_conversations_payload(game_state, client_profile), "Update"),
                )
            except Exception as exc:
                client._record_ws("chat-conversation-broadcast-failed", {"topic": topic, "cid": cid, "error": str(exc)})

    def _ws_clients_for_profile(self, profile: dict[str, str]) -> list["ProbeHandler"]:
        subject = profile.get("subject")
        with self.server.ws_lock:
            clients = list(self.server.ws_clients)
        return [
            client
            for client in clients
            if (getattr(client, "profile", None) or default_profile()).get("subject") == subject
        ]

    def _send_wampv1_event_to_profile(
        self,
        profile: dict[str, str],
        topic: str,
        event: Any,
        required_topics: set[str] | None = None,
    ) -> None:
        for client in self._ws_clients_for_profile(profile):
            topics = getattr(client, "ws_topics", set())
            if topic not in topics:
                continue
            if required_topics and not required_topics.issubset(topics):
                continue
            try:
                client._ws_send_wampv1_event(topic, event)
            except Exception as exc:
                client._record_ws("profile-broadcast-failed", {"topic": topic, "error": str(exc)})

    def _activate_chat_room(self, cid: str | None) -> None:
        if not cid:
            return
        profile = self._current_profile()
        game_state = self.server.game_state
        join_chat_room(game_state, cid, profile)
        self._send_wampv1_event_to_profile(
            profile,
            "OnJsonApiEvent_chat_v5_conversations",
            json_api_event("/chat/v5/conversations", chat_conversations_payload(game_state, profile), "Create"),
        )
        participants = chat_participants_payload(game_state, cid, profile)
        for uri in chat_participants_uri_variants(cid):
            self._send_wampv1_event_to_profile(
                profile,
                "OnJsonApiEvent_chat_v5_participants",
                json_api_event(uri, participants, "Create"),
                {"OnJsonApiEvent_chat_v5_conversations"},
            )
        self._send_wampv1_event_to_profile(
            profile,
            "OnJsonApiEvent_chat_v5_participants",
            json_api_event(chat_participants_uri(), chat_participants_payload(game_state, None, profile), "Update"),
            {"OnJsonApiEvent_chat_v5_conversations"},
        )

    def _broadcast_social_roster_update(self) -> None:
        game_state = self.server.game_state
        with self.server.ws_lock:
            clients = list(self.server.ws_clients)
        for client in clients:
            topics = getattr(client, "ws_topics", set())
            client_profile = getattr(client, "profile", None) or default_profile()
            rooms = chat_room_infos(game_state, client_profile)
            try:
                if "OnJsonApiEvent_chat_v5_conversations" in topics:
                    client._ws_send_wampv1_event(
                        "OnJsonApiEvent_chat_v5_conversations",
                        json_api_event("/chat/v5/conversations", chat_conversations_payload(game_state, client_profile), "Update"),
                    )
                if "OnJsonApiEvent_chat_v5_participants" in topics and "OnJsonApiEvent_chat_v5_conversations" in topics:
                    for room in rooms:
                        cid = str(room.get("cid") or room.get("Cid") or "")
                        if cid:
                            participants = chat_participants_payload(game_state, cid, client_profile)
                            for uri in chat_participants_uri_variants(cid):
                                client._ws_send_wampv1_event(
                                    "OnJsonApiEvent_chat_v5_participants",
                                    json_api_event(uri, participants, "Update"),
                                )
                    client._ws_send_wampv1_event(
                        "OnJsonApiEvent_chat_v5_participants",
                        json_api_event(chat_participants_uri(), chat_participants_payload(game_state, None, client_profile), "Update"),
                    )
                if "OnJsonApiEvent_chat_v4_presences" in topics:
                    client._ws_send_wampv1_event(
                        "OnJsonApiEvent_chat_v4_presences",
                        json_api_event("/chat/v4/presences", presences_payload(game_state, client_profile), "Update"),
                    )
                if "OnJsonApiEvent_chat_v3_friends" in topics:
                    client._ws_send_wampv1_event(
                        "OnJsonApiEvent_chat_v3_friends",
                        json_api_event("/chat/v3/friends", friends_payload(game_state, client_profile), "Update"),
                    )
            except Exception as exc:
                client._record_ws("social-roster-broadcast-failed", {"error": str(exc)})

    def _broadcast_presence_update(self) -> None:
        game_state = self.server.game_state
        with self.server.ws_lock:
            clients = list(self.server.ws_clients)
        for client in clients:
            topics = getattr(client, "ws_topics", set())
            if "OnJsonApiEvent_chat_v4_presences" not in topics:
                continue
            client_profile = getattr(client, "profile", None) or default_profile()
            try:
                client._ws_send_wampv1_event(
                    "OnJsonApiEvent_chat_v4_presences",
                    json_api_event("/chat/v4/presences", presences_payload(game_state, client_profile), "Update"),
                )
            except Exception as exc:
                client._record_ws("presence-broadcast-failed", {"error": str(exc)})

    def _send_friend_request_event(
        self,
        record: FriendRequestRecord,
        profile: dict[str, str],
        event_type: str,
    ) -> None:
        full_payload = friend_request_payload(record, profile)
        if event_type == "Delete":
            request_payload = friend_request_remove_event_payload(record, profile)
        else:
            request_payload = friend_request_add_event_payload(record, profile)
        subject = str(full_payload.get("Subject") or full_payload.get("subject") or "").strip()
        uri = f"/chat/v4/friendrequests/{subject}" if subject else "/chat/v4/friendrequests"
        self._send_wampv1_event_to_profile(
            profile,
            "OnJsonApiEvent_chat_v4_friendrequests",
            json_api_event(uri, request_payload, event_type),
        )

    def _broadcast_friend_request_created(self, record: FriendRequestRecord) -> None:
        sender = profile_by_key(record.sender_account_key)
        receiver = profile_by_key(record.receiver_account_key)
        self._send_friend_request_event(record, sender, "Create")
        self._send_friend_request_event(record, receiver, "Create")
        self._broadcast_friend_request_snapshot(record)

    def _broadcast_friend_request_removed(self, record: FriendRequestRecord) -> None:
        sender = profile_by_key(record.sender_account_key)
        receiver = profile_by_key(record.receiver_account_key)
        self._send_friend_request_event(record, sender, "Delete")
        self._send_friend_request_event(record, receiver, "Delete")
        self._broadcast_friend_request_snapshot(record)

    def _send_friend_request_snapshot(self, profile: dict[str, str]) -> None:
        self._send_wampv1_event_to_profile(
            profile,
            "OnJsonApiEvent_chat_v4_friendrequests",
            json_api_event("/chat/v4/friendrequests", friend_requests_payload(profile), "Update"),
        )

    def _broadcast_friend_request_snapshot(self, record: FriendRequestRecord) -> None:
        self._send_friend_request_snapshot(profile_by_key(record.sender_account_key))
        self._send_friend_request_snapshot(profile_by_key(record.receiver_account_key))

    def _broadcast_friend_request_response(self, profile: dict[str, str], payload: dict[str, Any]) -> None:
        request_id = payload.get("ID") or payload.get("Id") or payload.get("id")
        if (
            payload.get("Accepted")
            or payload.get("accepted")
            or payload.get("ReciprocalAccepted")
            or payload.get("reciprocalAccepted")
        ):
            sender_subject = str(payload.get("SenderSubject") or payload.get("senderSubject") or "").strip()
            receiver_subject = str(payload.get("ReceiverSubject") or payload.get("receiverSubject") or "").strip()
            profiles: list[dict[str, str]] = []
            for subject in (sender_subject, receiver_subject):
                account = ACCOUNT_STORE.get_account_by_subject(subject) if subject else None
                if account:
                    candidate = profile_from_account(account)
                    if all(existing["subject"] != candidate["subject"] for existing in profiles):
                        profiles.append(candidate)
            if not profiles:
                profiles.append(profile)
            for candidate in profiles:
                self._send_friend_request_snapshot(candidate)
            self._broadcast_social_roster_update()
            return
        if payload.get("AutoAccepted") or payload.get("autoAccepted") or payload.get("AlreadyFriends") or payload.get("alreadyFriends"):
            self._broadcast_social_roster_update()
            return
        if payload.get("ReciprocalPending") or payload.get("reciprocalPending"):
            request_id = payload.get("ID") or payload.get("Id") or payload.get("id")
            record = pending_friend_request_for_identifier(profile, str(request_id)) if request_id else None
            if record:
                self._broadcast_friend_request_snapshot(record)
            return
        if request_id:
            record = pending_friend_request_for_identifier(profile, str(request_id))
            if record:
                self._broadcast_friend_request_created(record)
                return
        self._broadcast_social_roster_update()

    def _send_backend_state_to_profile(self, profile: dict[str, str]) -> None:
        game_state = self.server.game_state
        party_ok = backend_ready(game_state, profile, "party")
        pregame_ok = backend_ready(game_state, profile, "pregame")
        core_ok = backend_ready(game_state, profile, "core")
        session_payloads = session_events(game_state, profile)
        party_payloads = rms_party_messages(game_state, profile) if party_ok else []
        match_payloads = rms_match_messages(game_state, profile) if pregame_ok or core_ok else []
        for client in self._ws_clients_for_profile(profile):
            topics = getattr(client, "ws_topics", set())
            try:
                if "OnJsonApiEvent_riot-messaging-service_v1_message" in topics:
                    for event in session_payloads:
                        client._ws_send_wampv1_event("OnJsonApiEvent_riot-messaging-service_v1_message", event)
                    for event in match_payloads:
                        client._ws_send_wampv1_event("OnJsonApiEvent_riot-messaging-service_v1_message", event)
                    for event in party_payloads:
                        client._ws_send_wampv1_event("OnJsonApiEvent_riot-messaging-service_v1_message", event)
                for topic in sorted(topics):
                    if topic.startswith("OnJsonApiEvent_session_v1"):
                        for event in session_payloads:
                            client._ws_send_wampv1_event(topic, event)
                    elif core_ok and (topic.startswith("OnJsonApiEvent_core-game_v1") or topic.startswith("OnJsonApiEvent_ares-core-game")):
                        for event in match_payloads:
                            if "/core-game/" in str(event.get("uri") or ""):
                                client._ws_send_wampv1_event(topic, event)
                    elif pregame_ok and (topic.startswith("OnJsonApiEvent_pregame_v1") or topic.startswith("OnJsonApiEvent_ares-pregame")):
                        for event in match_payloads:
                            if "/pregame/" in str(event.get("uri") or ""):
                                client._ws_send_wampv1_event(topic, event)
                    elif party_ok and (topic.startswith("OnJsonApiEvent_parties_v1") or topic.startswith("OnJsonApiEvent_ares-parties")):
                        for event in party_payloads:
                            client._ws_send_wampv1_event(topic, event)
            except Exception as exc:
                client._record_ws("backend-state-profile-failed", {"error": str(exc)})

    def _broadcast_backend_state_update(self) -> None:
        game_state = self.server.game_state
        with self.server.ws_lock:
            clients = list(self.server.ws_clients)
        for client in clients:
            profile = getattr(client, "profile", None) or default_profile()
            self._send_backend_state_to_profile(profile)

    def _ws_send_subscription_seed(self, topic: str) -> None:
        game_state = self.server.game_state
        profile = self._current_profile()
        party_ok = backend_ready(game_state, profile, "party")
        pregame_ok = backend_ready(game_state, profile, "pregame")
        core_ok = backend_ready(game_state, profile, "core")
        session_payloads = session_events(game_state, profile)
        party_payloads = rms_party_messages(game_state, profile) if party_ok else []
        match_payloads = rms_match_messages(game_state, profile) if pregame_ok or core_ok else []
        if topic == "OnJsonApiEvent_riot-messaging-service_v1_message":
            for event in session_payloads:
                self._ws_send_wampv1_event(topic, event)
            for event in match_payloads:
                self._ws_send_wampv1_event(topic, event)
            for event in party_payloads:
                self._ws_send_wampv1_event(topic, event)
        elif topic == "OnJsonApiEvent_chat_v1_session":
            self._ws_send_wampv1_event(topic, json_api_event("/chat/v1/session", chat_session_payload(profile)))
        elif topic == "OnJsonApiEvent_chat_v3_friends":
            self._ws_send_wampv1_event(topic, json_api_event("/chat/v3/friends", friends_payload(game_state, profile)))
        elif topic == "OnJsonApiEvent_chat_v4_friendrequests":
            self._ws_send_wampv1_event(
                topic,
                json_api_event("/chat/v4/friendrequests", friend_requests_payload(profile)),
            )
        elif topic == "OnJsonApiEvent_chat_v4_presences":
            for event in chat_presence_events(game_state, profile):
                self._ws_send_wampv1_event(topic, event)
        elif topic == "OnJsonApiEvent_chat_v5_conversations":
            self._ws_send_wampv1_event(topic, json_api_event("/chat/v5/conversations", chat_conversations_payload(game_state, profile)))
            if "OnJsonApiEvent_chat_v5_participants" in self.ws_topics:
                for room in chat_room_infos(game_state, profile):
                    cid = str(room.get("cid") or room.get("Cid") or "")
                    if cid:
                        participants = chat_participants_payload(game_state, cid, profile)
                        for uri in chat_participants_uri_variants(cid):
                            self._ws_send_wampv1_event(
                                "OnJsonApiEvent_chat_v5_participants",
                                json_api_event(uri, participants),
                            )
                self._ws_send_wampv1_event(
                    "OnJsonApiEvent_chat_v5_participants",
                    json_api_event(chat_participants_uri(), chat_participants_payload(game_state, None, profile)),
                )
        elif topic == "OnJsonApiEvent_chat_v5_participants":
            if "OnJsonApiEvent_chat_v5_conversations" in self.ws_topics:
                for room in chat_room_infos(game_state, profile):
                    cid = str(room.get("cid") or room.get("Cid") or "")
                    if cid:
                        participants = chat_participants_payload(game_state, cid, profile)
                        for uri in chat_participants_uri_variants(cid):
                            self._ws_send_wampv1_event(
                                topic,
                                json_api_event(uri, participants),
                            )
                self._ws_send_wampv1_event(topic, json_api_event(chat_participants_uri(), chat_participants_payload(game_state, None, profile)))
        elif topic == "OnJsonApiEvent_chat_v5_messages":
            with self.server.chat_lock:
                rooms = joined_chat_rooms_for_profile(game_state, profile)
                messages = [
                    message
                    for message in self.server.chat_messages
                    if str(message.get("Cid") or message.get("cid") or "") in rooms
                ]
            self._ws_send_wampv1_event(topic, json_api_event("/chat/v5/messages", chat_messages_payload(game_state, messages)))
        elif topic == "OnJsonApiEvent_riot-messaging-service_v1_session":
            self._ws_send_wampv1_event(topic, json_api_event("/riot-messaging-service/v1/session", riot_messaging_session_payload(profile)))
        elif topic.startswith("OnJsonApiEvent_session_v1"):
            for event in session_events(game_state, profile):
                self._ws_send_wampv1_event(topic, event)
        elif party_ok and (topic.startswith("OnJsonApiEvent_parties_v1") or topic.startswith("OnJsonApiEvent_ares-parties")):
            for event in rms_party_messages(game_state, profile):
                self._ws_send_wampv1_event(topic, event)
        elif core_ok and (topic.startswith("OnJsonApiEvent_core-game_v1") or topic.startswith("OnJsonApiEvent_ares-core-game")):
            for event in rms_match_messages(game_state, profile):
                if "/core-game/" in event.get("uri", ""):
                    self._ws_send_wampv1_event(topic, event)
        elif pregame_ok and (topic.startswith("OnJsonApiEvent_pregame_v1") or topic.startswith("OnJsonApiEvent_ares-pregame")):
            for event in rms_match_messages(game_state, profile):
                if "/pregame/" in event.get("uri", ""):
                    self._ws_send_wampv1_event(topic, event)

    def _handle_wamp_message(self, message: Any) -> None:
        if not isinstance(message, list) or not message:
            return
        msg_type = message[0]
        if msg_type == 0:  # WAMPv1 WELCOME, client should not send this.
            self._record_ws("wampv1-unexpected-welcome", message)
        elif msg_type == 1 and len(message) >= 3 and isinstance(message[2], dict):  # WAMPv2 HELLO
            self._ws_send_json(
                [
                    2,
                    1,
                    {
                        "roles": {
                            "broker": {"features": {}},
                            "dealer": {"features": {}},
                        }
                    },
                ]
            )
        elif msg_type == 1:  # WAMPv1 PREFIX
            self._record_ws("wampv1-prefix", message)
        elif msg_type == 2 and len(message) >= 3:  # WAMPv1 CALL
            self._ws_send_json([3, message[1], {}])
        elif msg_type == 5 and len(message) >= 2 and isinstance(message[1], str):  # WAMPv1 SUBSCRIBE
            self._record_ws("wampv1-subscribe", message[1])
            self.ws_topics.add(message[1])
            self._ws_send_subscription_seed(message[1])
        elif msg_type == 6 and len(message) >= 2 and isinstance(message[1], str):  # WAMPv1 UNSUBSCRIBE
            self._record_ws("wampv1-unsubscribe", message[1])
            self.ws_topics.discard(message[1])
        elif msg_type == 7:  # WAMPv1 PUBLISH
            self._record_ws("wampv1-publish", message)
        elif msg_type == 32 and len(message) >= 3:  # WAMPv2 SUBSCRIBE
            if len(message) >= 4 and isinstance(message[3], str):
                self.ws_topics.add(message[3])
            self._ws_send_json([33, message[1], self.server.next_ws_id()])
        elif msg_type == 34 and len(message) >= 2:  # UNSUBSCRIBE
            self._ws_send_json([35, message[1]])
        elif msg_type == 48 and len(message) >= 4:  # CALL
            self._ws_send_json([50, message[1], {}, [], {}])
        elif msg_type == 64 and len(message) >= 3:  # REGISTER
            self._ws_send_json([65, message[1], self.server.next_ws_id()])
        elif msg_type == 66 and len(message) >= 2:  # UNREGISTER
            self._ws_send_json([67, message[1]])
        elif msg_type == 6:  # GOODBYE
            self._ws_send_json([6, {}, "wamp.close.goodbye"])
            self._ws_write_frame(8, b"")
        else:
            self._record_ws("unhandled", message)

    def _handle_websocket(self) -> None:
        key = self.headers.get("sec-websocket-key")
        if not key:
            self._write(400, {"error": "missing sec-websocket-key"})
            return
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        self.send_response(101, "Switching Protocols")
        self.send_header("upgrade", "websocket")
        self.send_header("connection", "Upgrade")
        self.send_header("sec-websocket-accept", accept)
        protocol = self.headers.get("sec-websocket-protocol")
        if protocol:
            self.send_header("sec-websocket-protocol", protocol)
        self.end_headers()
        self.ws_topics = set()
        self.ws_write_lock = threading.Lock()
        with self.server.ws_lock:
            self.server.ws_clients.add(self)
        try:
            self._ws_send_json([0, stable_token("wamp-session", self._current_profile()["subject"]), 1, "project-a-control-plane"])

            while True:
                try:
                    opcode, payload = self._ws_read_frame()
                except (ConnectionError, OSError, ssl.SSLError):
                    return
                if opcode == 8:  # close
                    self._ws_write_frame(8, payload)
                    return
                if opcode == 9:  # ping
                    self._ws_write_frame(10, payload)
                    continue
                if opcode != 1:
                    self._record_ws("in-binary-or-control", {"opcode": opcode, "length": len(payload)})
                    continue
                text = payload.decode("utf-8", "replace")
                try:
                    message = json.loads(text)
                except json.JSONDecodeError:
                    self._record_ws("in-text", text)
                    continue
                self._record_ws("in", message)
                self._handle_wamp_message(message)
        finally:
            with self.server.ws_lock:
                self.server.ws_clients.discard(self)

    def _json_body(self, body: bytes) -> Any:
        if not body:
            return {}
        try:
            parsed = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, (dict, list)) else {}

    def _bump_party(self) -> None:
        self.server.game_state["party_version"] = int(self.server.game_state.get("party_version", 1)) + 1

    def _bump_match(self) -> None:
        self.server.game_state["match_version"] = int(self.server.game_state.get("match_version", 1)) + 1

    def _handle(self) -> None:
        body = self._read_body()
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)
        json_body = self._json_body(body)
        self.profile = self._profile_from_request(path, json_body)
        with self.server.profile_lock:
            new_profile = self.profile["key"] not in self.server.seen_profiles
            self.server.seen_profiles.add(self.profile["key"])
            self.server.game_state["active_profile_keys"] = sorted(self.server.seen_profiles)
        self._record(body)
        game_state = self.server.game_state
        if self.headers.get("upgrade", "").lower() == "websocket":
            self._handle_websocket()
            return
        if new_profile:
            self._broadcast_social_roster_update()
        if maybe_advance_matchmaking_state(
            game_state,
            self._current_profile(),
            getattr(self.server, "matchmaking_delay_seconds", 0.0),
        ):
            self._bump_party()
            self._bump_match()
            self._broadcast_backend_state_update()

        ctx = build_route_context(self, path, parsed, query_params, json_body, body)
        if dispatch_http_route(ctx):
            return

        self._write(404, {"HTTPStatus": 404, "ErrorCode": "NOT_FOUND", "Message": f"No local route for {path}", "errorCode": "NOT_FOUND", "errorMessage": f"No local route for {path}", "path": path})

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()
