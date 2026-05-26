"""Local account and alias routes."""

from __future__ import annotations


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    json_body = ctx.json_body

    if route_path.rstrip("/") == "/local-accounts/v1/accounts":
        if ctx.command in {"POST", "PUT", "PATCH"}:
            request_body = json_body if isinstance(json_body, dict) else {}
            game_name, tag_line = cp.alias_fields_from_body(request_body, {"game_name": "Player", "tag_line": "LOCAL"})
            account_key = (
                request_body.get("account_key")
                or request_body.get("accountKey")
                or request_body.get("key")
                or cp.normalize_account_key(f"{game_name}-{tag_line}")
            )
            key, hint = cp.login_key_and_hint(f"{game_name}#{tag_line}")
            account_key = cp.normalize_account_key(str(account_key or key))
            hint = dict(hint or {})
            hint["key"] = account_key
            subject = request_body.get("subject") or request_body.get("Subject")
            if isinstance(subject, str) and subject:
                hint["subject"] = subject
            try:
                record = cp.ACCOUNT_STORE.get_or_create_account(account_key, hint)
                record = cp.ACCOUNT_STORE.update_alias(record.account_key, game_name, tag_line)
            except ValueError as exc:
                ctx.write(409, {"errorCode": "ALIAS_NOT_AVAILABLE", "errorMessage": str(exc), "isSuccess": False}, localize=False)
                return True
            profile = cp.profile_from_account(record)
            cp.seed_persisted_profile_defaults(profile)
            ctx.write(200, {"Account": cp.alias_payload(profile), "account": cp.alias_payload(profile), "isSuccess": True}, localize=False)
        else:
            accounts = [cp.alias_payload(cp.profile_from_account(record)) for record in cp.ACCOUNT_STORE.known_accounts()]
            ctx.write(200, {"Accounts": accounts, "accounts": accounts}, localize=False)
    elif route_path == "/player-account/aliases/v1/eligibility":
        profile = ctx.current_profile()
        game_name, tag_line = cp.alias_fields_from_body(json_body, profile)
        ctx.write(200, cp.alias_availability_payload(game_name, tag_line, profile["key"]))
    elif route_path == "/player-account/aliases/v1/active":
        profile = ctx.current_profile()
        if ctx.command in {"POST", "PUT", "PATCH"}:
            status, payload, profile = cp.update_alias_response(profile, json_body)
            if status == 200:
                ctx.set_profile(profile)
                ctx.broadcast_social_roster_update()
            ctx.write(status, payload, localize=False)
        else:
            ctx.write(200, cp.alias_payload(profile))
    elif route_path in {"/player-account/aliases/v1/aliases", "/player-account/aliases/v1/validity"}:
        profile = ctx.current_profile()
        if route_path.endswith("/aliases") and ctx.command in {"POST", "PUT", "PATCH"}:
            status, payload, profile = cp.update_alias_response(profile, json_body)
            if status == 200:
                ctx.set_profile(profile)
                ctx.broadcast_social_roster_update()
            ctx.write(status, payload, localize=False)
        elif route_path.endswith("/validity"):
            game_name, tag_line = cp.alias_fields_from_body(json_body, profile)
            ctx.write(200, cp.alias_availability_payload(game_name, tag_line, profile["key"]))
        else:
            ctx.write(200, cp.alias_payload(profile))
    elif route_path in {"/aliases/v1/active", "/aliases/v1/aliases", "/aliases/v1/validity"}:
        profile = ctx.current_profile()
        if route_path.endswith(("/active", "/aliases")) and ctx.command in {"POST", "PUT", "PATCH"}:
            status, payload, profile = cp.update_alias_response(profile, json_body)
            if status == 200:
                ctx.set_profile(profile)
                ctx.broadcast_social_roster_update()
            ctx.write(status, payload, localize=False)
        elif route_path.endswith("/validity"):
            game_name, tag_line = cp.alias_fields_from_body(json_body, profile)
            ctx.write(200, cp.alias_availability_payload(game_name, tag_line, profile["key"]))
        else:
            ctx.write(200, cp.alias_payload(profile))
    else:
        return False
    return True
