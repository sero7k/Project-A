"""Store, wallet, entitlement, CAP, and payment routes."""

from __future__ import annotations

import re


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    if re.match(r"^/store/v[12]/storefront(?:/[^/]+)?/?$", route_path):
        ctx.write(200, cp.store_v2_storefront_payload())
    elif re.match(r"^/store/v1/wallet/[^/]+$", route_path):
        ctx.write(200, cp.wallet_payload(ctx.game_state, ctx.current_profile()))
    elif route_path in {"/store/v1/offers", "/store/v1/offers/"}:
        ctx.write(200, cp.store_offers_payload())
    elif re.match(r"^/store/v1/entitlements/[^/]+/[^/]+$", route_path):
        ctx.write(200, cp.store_entitlements_payload(route_path.rsplit("/", 1)[-1], ctx.game_state, ctx.current_profile()))
    elif re.match(r"^/entitlements/[0-9a-fA-F-]{36}/[0-9a-fA-F-]{36}/?$", route_path):
        parts = [part for part in route_path.split("/") if part]
        ctx.write(200, cp.store_entitlements_payload(parts[1], ctx.game_state, ctx.current_profile()), localize=False)
    elif re.match(r"^/cap/v1/wallets(?:/[^/]+)?/?$", route_path):
        ctx.write(200, cp.wallet_payload(ctx.game_state, ctx.current_profile()))
    elif re.match(r"^/cap/v1/orders(?:/.*)?$", route_path):
        if ctx.command == "POST":
            ctx.write(200, cp.purchase_initialized_payload())
        else:
            ctx.write(200, {"Orders": [], "orders": []})
    elif re.match(r"^/cap/v1/entitlements(?:/.*)?$", route_path):
        parts = [part for part in route_path.split("/") if part]
        item_type_id = parts[-1] if len(parts) >= 4 else ""
        if re.fullmatch(r"[0-9a-fA-F-]{36}", item_type_id):
            ctx.write(200, cp.store_entitlements_payload(item_type_id, ctx.game_state, ctx.current_profile()))
        else:
            ctx.write(200, cp.all_store_entitlements_payload(ctx.game_state, ctx.current_profile()))
    elif route_path == "/payments/v1/initialize-purchase":
        ctx.write(200, cp.purchase_initialized_payload())
    else:
        return False
    return True
