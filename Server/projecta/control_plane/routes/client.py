"""Bootstrap, auth, config, local account, and RMS routes."""

from __future__ import annotations


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    game_state = ctx.game_state
    json_body = ctx.json_body

    if route_path in {"/local/v1/account", "/local/v1/accounts/me"}:
        ctx.write(200, cp.local_account_payload(ctx.current_profile()), localize=False)
    elif route_path == "/local/v1/accounts":
        if ctx.command in {"POST", "PUT", "PATCH"}:
            request_body = json_body if isinstance(json_body, dict) else {}
            account_key = str(request_body.get("account_key") or request_body.get("accountKey") or request_body.get("key") or request_body.get("login") or "").strip()
            game_name, tag_line = cp.alias_fields_from_body(request_body, {"game_name": account_key or "Player", "tag_line": "LOCAL"})
            profile = cp.register_local_profile(account_key or f"{game_name}-{tag_line}", game_name, tag_line, request_body.get("subject") if isinstance(request_body.get("subject"), str) else None)
            ctx.set_profile(profile)
            ctx.write(201, cp.local_account_payload(profile), localize=False)
        else:
            accounts = [cp.local_account_payload(cp.profile_from_account(account)) for account in cp.ACCOUNT_STORE.known_accounts()]
            ctx.write(200, {"Accounts": accounts, "accounts": accounts}, localize=False)
    elif route_path.startswith("/v1/config/"):
        ctx.write(200, ctx.handler._config_payload())
    elif route_path.rstrip("/") == "/metadata/v1":
        ctx.write(200, cp.patchline_metadata_payload())
    elif route_path == "/process-control/v1/process":
        ctx.write(200, ctx.handler._process_control_payload())
    elif route_path == "/process-control/v1/process/quit":
        ctx.write(200, {"ok": True})
    elif route_path == "/plugin-manager/v1/status":
        ctx.write(200, ctx.handler._plugin_manager_payload())
    elif route_path == "/riotclient/region-locale":
        ctx.write(200, cp.region_locale_payload())
    elif route_path == "/product-integration/v1/app-repair/apply":
        ctx.write(200, cp.application_repair_payload(json_body))
    elif route_path == "/latency/v1/ingest":
        ctx.write(200, {"Success": True, "success": True})
    elif (agg_stats_args := cp.agg_stats_args_from_route(route_path)) is not None:
        queue_id, tier = agg_stats_args
        ctx.write(200, cp.agg_stats_payload(queue_id, tier, ctx.current_profile()), localize=False)
    elif route_path in {"/rso-auth/v1/authorization/userinfo", "/userinfo"}:
        ctx.write(200, cp.userinfo_payload(ctx.current_profile()), localize=False)
    elif route_path == "/rso-auth/v1/authorization/access-token":
        ctx.write(200, ctx.handler._access_token_payload())
    elif route_path == "/entitlements/v1/token":
        ctx.write(200, ctx.handler._entitlements_token_payload())
    elif route_path == "/riot-messaging-service/v1/session":
        ctx.write(200, cp.riot_messaging_session_payload(ctx.current_profile()), localize=False)
    elif route_path == "/riot-messaging-service/v1/out-of-sync":
        ctx.write(200, {"OutOfSync": False, "outOfSync": False, "Messages": [], "messages": []})
    elif route_path.startswith("/riot-messaging-service/v1/message"):
        ctx.write(200, cp.riot_messaging_messages_payload(game_state, ctx.current_profile()), localize=False)
    else:
        return False
    return True
