"""Contracts and contract-definition routes."""

from __future__ import annotations

import re


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    if ctx.command in {"POST", "PUT", "PATCH"} and re.match(r"^/contracts/v1/contracts/[^/]+/special/[^/]+$", route_path):
        profile = ctx.current_profile()
        contract_id = route_path.rstrip("/").rsplit("/", 1)[-1]
        cp.set_active_special_contract(ctx.game_state, profile, contract_id)
        payload = cp.contracts_payload(profile, ctx.game_state)
        payload.update(cp.purchase_response_payload(ctx.json_body, route_path))
        ctx.write(200, payload, localize=False)
    elif ctx.command in {"POST", "PUT", "PATCH"} and (
        re.match(r"^/contracts/v1/contracts/[^/]+/(unlock|upgrade)$", route_path)
        or re.match(r"^/contracts/v1/item-upgrades/[^/]+(?:/[^/]+)?/?$", route_path)
    ):
        ctx.write(200, cp.purchase_response_payload(ctx.json_body, route_path), localize=False)
    elif re.match(r"^/contracts/v1/contracts/[^/]+$", route_path):
        ctx.write(200, cp.contracts_payload(ctx.current_profile(), ctx.game_state), localize=False)
    elif re.match(r"^/contracts/v1/item-upgrades(/[^/]+)?/?$", route_path):
        progressions = cp.contract_definitions_payload(ctx.game_state)["ItemProgressionDefinitions"]
        ctx.write(200, {"ItemUpgrades": progressions, "Upgrades": progressions, "itemUpgrades": progressions})
    elif route_path == "/contract-definitions/v2/definitions/story":
        story = cp.contract_definition_payload()
        payload = cp.active_story_contract_definition_payload(ctx.game_state)
        payload["ContractDefinitions"] = [story]
        payload["contractDefinitions"] = [story]
        payload["Definitions"] = [story]
        payload["definitions"] = [story]
        payload["ActiveStoryContractDefinition"] = story
        payload["activeStoryContractDefinition"] = story
        ctx.write(200, payload)
    elif route_path.startswith("/contract-definitions/v2/definitions"):
        ctx.write(200, cp.contract_definitions_payload(ctx.game_state))
    elif route_path.startswith("/contract-definitions/v2/item-upgrades"):
        progressions = cp.contract_definitions_payload(ctx.game_state)["ItemProgressionDefinitions"]
        ctx.write(200, {"ItemUpgrades": progressions, "Upgrades": progressions, "itemUpgrades": progressions})
    else:
        return False
    return True
