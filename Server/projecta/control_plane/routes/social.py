"""Friends and friend-request routes."""

from __future__ import annotations

import re


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    game_state = ctx.game_state
    json_body = ctx.json_body

    if route_path == "/chat/v3/friends":
        profile = ctx.current_profile()
        if ctx.command == "DELETE":
            target = cp.profile_from_social_body(json_body)
            if not target:
                query_body = {
                    "pid": (ctx.query_params.get("pid") or ctx.query_params.get("Pid") or [""])[0],
                    "subject": (ctx.query_params.get("subject") or ctx.query_params.get("Subject") or [""])[0],
                }
                target = cp.profile_from_social_body(query_body)
            if target:
                cp.ACCOUNT_STORE.remove_friend(profile["key"], target["key"])
                ctx.broadcast_social_roster_update()
            ctx.write(200, cp.friends_payload(game_state, profile), localize=False)
        elif ctx.command in {"POST", "PUT", "PATCH"}:
            status, payload = cp.create_friend_request_response(
                profile,
                json_body,
                game_state,
                getattr(ctx.server, "auto_accept_friends", False),
            )
            if status == 200:
                ctx.broadcast_friend_request_response(profile, payload)
            ctx.write(status, payload, localize=False)
        else:
            ctx.write(200, cp.friends_payload(game_state, profile), localize=False)
    elif re.match(r"^/chat/v4/friendrequests/[^/]+/(accept|decline|reject)$", route_path):
        profile = ctx.current_profile()
        parts = [part for part in route_path.split("/") if part]
        request_ref = parts[3] if len(parts) >= 4 else ""
        action = parts[4] if len(parts) >= 5 else ""
        if action == "accept":
            pending = cp.pending_friend_request_for_identifier(profile, request_ref)
            request = cp.ACCOUNT_STORE.accept_friend_request(profile["key"], pending.request_id if pending else request_ref)
            if not request:
                ctx.write(404, {"HTTPStatus": 404, "ErrorCode": "NOT_FOUND", "Message": "Friend request not found", "errorCode": "NOT_FOUND", "errorMessage": "Friend request not found"})
            else:
                ctx.broadcast_friend_request_snapshot(request)
                ctx.broadcast_social_roster_update()
                ctx.write(200, cp.friend_request_response_payload(request, profile), localize=False)
        else:
            request = cp.pending_friend_request_for_identifier(profile, request_ref)
            ok = cp.ACCOUNT_STORE.decline_friend_request(profile["key"], request.request_id if request else request_ref)
            if ok:
                if request:
                    ctx.broadcast_friend_request_removed(request)
                ctx.broadcast_social_roster_update()
            ctx.write(200, {"ok": ok})
    elif route_path == "/chat/v4/friendrequests":
        profile = ctx.current_profile()
        if ctx.command in {"POST", "PUT", "PATCH"}:
            status, payload = cp.create_friend_request_response(
                profile,
                json_body,
                game_state,
                getattr(ctx.server, "auto_accept_friends", False),
            )
            if status == 200:
                ctx.broadcast_friend_request_response(profile, payload)
            ctx.write(status, payload, localize=False)
        else:
            ctx.write(200, cp.friend_requests_payload(profile), localize=False)
    elif route_path.startswith("/friends/v1/friends"):
        profile = ctx.current_profile()
        if ctx.command == "DELETE":
            target = cp.profile_from_social_body(json_body)
            if target:
                cp.ACCOUNT_STORE.remove_friend(profile["key"], target["key"])
                ctx.broadcast_social_roster_update()
            ctx.write(200, cp.friends_payload(game_state, profile), localize=False)
        elif ctx.command in {"POST", "PUT", "PATCH"}:
            status, payload = cp.create_friend_request_response(
                profile,
                json_body,
                game_state,
                getattr(ctx.server, "auto_accept_friends", False),
            )
            if status == 200:
                ctx.broadcast_friend_request_response(profile, payload)
            ctx.write(status, payload, localize=False)
        else:
            ctx.write(200, cp.friends_payload(game_state, profile), localize=False)
    elif re.match(r"^/friends/v1/requests/[^/]+/(accept|decline|reject)$", route_path):
        profile = ctx.current_profile()
        parts = [part for part in route_path.split("/") if part]
        request_ref = parts[3] if len(parts) >= 4 else ""
        action = parts[4] if len(parts) >= 5 else ""
        if action == "accept":
            pending = cp.pending_friend_request_for_identifier(profile, request_ref)
            request = cp.ACCOUNT_STORE.accept_friend_request(profile["key"], pending.request_id if pending else request_ref)
            if not request:
                ctx.write(404, {"HTTPStatus": 404, "ErrorCode": "NOT_FOUND", "Message": "Friend request not found", "errorCode": "NOT_FOUND", "errorMessage": "Friend request not found"})
            else:
                ctx.broadcast_friend_request_snapshot(request)
                ctx.broadcast_social_roster_update()
                ctx.write(200, cp.friend_request_response_payload(request, profile), localize=False)
        else:
            request = cp.pending_friend_request_for_identifier(profile, request_ref)
            ok = cp.ACCOUNT_STORE.decline_friend_request(profile["key"], request.request_id if request else request_ref)
            if ok:
                if request:
                    ctx.broadcast_friend_request_removed(request)
                ctx.broadcast_social_roster_update()
            ctx.write(200, {"ok": ok})
    elif route_path.startswith("/friends/v1/requests"):
        profile = ctx.current_profile()
        if ctx.command in {"POST", "PUT", "PATCH"}:
            status, payload = cp.create_friend_request_response(
                profile,
                json_body,
                game_state,
                getattr(ctx.server, "auto_accept_friends", False),
            )
            if status == 200:
                ctx.broadcast_friend_request_response(profile, payload)
            ctx.write(status, payload, localize=False)
        else:
            ctx.write(200, cp.friend_requests_payload(profile), localize=False)
    else:
        return False
    return True
