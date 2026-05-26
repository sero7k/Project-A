"""Small route-dispatch facade for keeping HTTP handlers modular."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RouteContext:
    handler: Any
    path: str
    route_path: str
    parsed: Any
    query_params: dict[str, list[str]]
    json_body: Any
    raw_body: bytes

    @property
    def command(self) -> str:
        return self.handler.command

    @property
    def server(self) -> Any:
        return self.handler.server

    @property
    def game_state(self) -> dict[str, Any]:
        return self.handler.server.game_state

    def current_profile(self) -> dict[str, str]:
        return self.handler._current_profile()

    def set_profile(self, profile: dict[str, str]) -> None:
        self.handler.profile = profile

    def write(self, status: int, body: Any, content_type: str = "application/json", *, localize: bool = True) -> None:
        self.handler._write(status, body, content_type, localize)

    def bump_party(self) -> None:
        self.handler._bump_party()

    def bump_match(self) -> None:
        self.handler._bump_match()

    def broadcast_presence_update(self) -> None:
        self.handler._broadcast_presence_update()

    def broadcast_social_roster_update(self) -> None:
        self.handler._broadcast_social_roster_update()

    def broadcast_backend_state_update(self) -> None:
        self.handler._broadcast_backend_state_update()

    def send_backend_state_to_profile(self, profile: dict[str, str]) -> None:
        self.handler._send_backend_state_to_profile(profile)

    def broadcast_friend_request_response(self, profile: dict[str, str], payload: dict[str, Any]) -> None:
        self.handler._broadcast_friend_request_response(profile, payload)

    def broadcast_friend_request_snapshot(self, record: Any) -> None:
        self.handler._broadcast_friend_request_snapshot(record)

    def broadcast_friend_request_removed(self, record: Any) -> None:
        self.handler._broadcast_friend_request_removed(record)

    def send_wampv1_event_to_profile(
        self,
        profile: dict[str, str],
        topic: str,
        event: Any,
        required_topics: set[str] | None = None,
    ) -> None:
        self.handler._send_wampv1_event_to_profile(profile, topic, event, required_topics)

    def activate_chat_room(self, cid: str | None) -> None:
        self.handler._activate_chat_room(cid)

    def broadcast_chat_message_event(self, cid: str, event: Any) -> None:
        self.handler._broadcast_chat_message_event(cid, event)

    def broadcast_chat_conversation_update(self, cid: str) -> None:
        self.handler._broadcast_chat_conversation_update(cid)
