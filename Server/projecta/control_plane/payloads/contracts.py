"""Contract and contract-definition payload builders."""

from __future__ import annotations

from typing import Any

from ..common.assets import asset_class_object_path, asset_reference_name


def contract_chapter_payload(chapter: dict[str, Any]) -> dict[str, Any]:
    asset_path = asset_class_object_path(chapter["asset"])
    ui_data_path = asset_class_object_path(chapter["ui_data"])
    asset_name = asset_reference_name(chapter["asset"])
    return {
        "ID": chapter["id"],
        "Id": chapter["id"],
        "UUID": chapter["id"],
        "Uuid": chapter["id"],
        "Guid": chapter["id"],
        "guid": chapter["id"],
        "Name": chapter["name"],
        "name": chapter["name"],
        "DataAsset": asset_path,
        "dataAsset": asset_path,
        "DataAssetPath": asset_path,
        "dataAssetPath": asset_path,
        "UIData": ui_data_path,
        "uiData": ui_data_path,
        "UIDataPath": ui_data_path,
        "uiDataPath": ui_data_path,
        "AssetName": asset_name,
        "assetName": asset_name,
        "AssetPath": asset_path,
        "assetPath": asset_path,
    }


def contract_model_payload(contract_id: str, level_count: int = 10) -> dict[str, Any]:
    progression_state = {
        "TotalProgressionEarned": 0,
        "totalProgressionEarned": 0,
        "HighestRewardedLevel": {},
        "highestRewardedLevel": {},
    }
    return {
        "ID": contract_id,
        "Id": contract_id,
        "ContractDefinitionID": contract_id,
        "contractDefinitionID": contract_id,
        "ContractDefinitionId": contract_id,
        "contractDefinitionId": contract_id,
        "ContractProgression": progression_state,
        "contractProgression": progression_state,
        "ProgressionLevelReached": 0,
        "progressionLevelReached": 0,
        "ProgressionTowardsNextLevel": 0,
        "progressionTowardsNextLevel": 0,
        "LevelCount": level_count,
        "levelCount": level_count,
    }


def remap_contract_payload(value: Any, contract_id: str, name: str, local_story_contract_id: str) -> Any:
    if isinstance(value, dict):
        return {key: remap_contract_payload(item, contract_id, name, local_story_contract_id) for key, item in value.items()}
    if isinstance(value, list):
        return [remap_contract_payload(item, contract_id, name, local_story_contract_id) for item in value]
    if value == local_story_contract_id:
        return contract_id
    if value in {"Inactive Contract", "Local Story Contract"}:
        return name
    return value


def default_character_contract_models(local_character_contract_rows: list[dict[str, Any]], local_story_contract_id: str, level_count: int = 10) -> list[dict[str, Any]]:
    _ = local_story_contract_id
    return [contract_model_payload(row["id"], level_count) for row in local_character_contract_rows]


def contracts_payload(profile: dict[str, str], state: dict[str, Any], *, local_story_contract_id: str, local_character_contract_rows: list[dict[str, Any]]) -> dict[str, Any]:
    version = int(state.get("Version") or state.get("version") or 0)
    contracts = state.get("Contracts") if isinstance(state.get("Contracts"), list) else []
    if not contracts:
        contracts = [contract_model_payload(local_story_contract_id)]
        contracts.extend(default_character_contract_models(local_character_contract_rows, local_story_contract_id))
    missions = state.get("Missions") if isinstance(state.get("Missions"), list) else []
    processed = state.get("ProcessedMatches") if isinstance(state.get("ProcessedMatches"), list) else []
    active_special = str(state.get("ActiveSpecialContract") or local_story_contract_id)
    return {
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "Version": version,
        "version": version,
        "Contracts": contracts,
        "contracts": contracts,
        "ProcessedMatches": processed,
        "processedMatches": processed,
        "ActiveSpecialContract": active_special,
        "activeSpecialContract": active_special,
        "Missions": missions,
        "missions": missions,
    }


def item_progression_definitions_payload(loadout_rows: list[dict[str, str]], *, item_type_skin_level: str, item_type_skin_chroma: str) -> list[dict[str, Any]]:
    definitions = []
    for row in loadout_rows:
        for item_key, item_type, name_suffix in [
            ("skin_level_id", item_type_skin_level, "Level"),
            ("chroma_id", item_type_skin_chroma, "Chroma"),
        ]:
            item_id = row.get(item_key)
            if not item_id:
                continue
            definitions.append(
                {
                    "ID": item_id,
                    "Id": item_id,
                    "UUID": item_id,
                    "Uuid": item_id,
                    "uuid": item_id,
                    "Guid": item_id,
                    "guid": item_id,
                    "ItemID": item_id,
                    "itemID": item_id,
                    "ItemId": item_id,
                    "itemId": item_id,
                    "ItemTypeID": item_type,
                    "itemTypeID": item_type,
                    "ItemTypeId": item_type,
                    "itemTypeId": item_type,
                    "Name": f"{row['name']} {name_suffix}",
                    "name": f"{row['name']} {name_suffix}",
                    "Levels": [],
                    "levels": [],
                    "RequiredContracts": [],
                    "requiredContracts": [],
                    "RequiredEntitlements": [],
                    "requiredEntitlements": [],
                    "Rewards": [],
                    "rewards": [],
                }
            )
    return definitions


def contract_definition_payload(*, local_story_contract_id: str, local_currency_id: str, item_type_contract: str, local_contract_asset: str) -> dict[str, Any]:
    contract_name = "Local Story Contract"
    contract_asset_path = asset_class_object_path(local_contract_asset)
    contract_asset_name = asset_reference_name(local_contract_asset)
    progression_schedule = {
        "ID": local_story_contract_id,
        "ProgressionCurrencyID": local_currency_id,
        "ProgressionDeltaPerLevel": [0 for _ in range(10)],
    }
    premium_details = {
        "Entitlement": {
            "ItemTypeID": item_type_contract,
            "ItemID": local_story_contract_id,
        },
        "PurchaseCurrencyID": local_currency_id,
        "PurchaseCost": 0,
    }
    return {
        "ID": local_story_contract_id,
        "Name": contract_name,
        "ContractType": "Story",
        "ProgressionSchedule": progression_schedule,
        "AlternateProgressionSchedules": [],
        "RewardSchedules": [],
        "PremiumContractDetails": premium_details,
        "DataAsset": contract_asset_path,
        "dataAsset": contract_asset_path,
        "DataAssetPath": contract_asset_path,
        "dataAssetPath": contract_asset_path,
        "AssetName": contract_asset_name,
        "assetName": contract_asset_name,
        "AssetPath": contract_asset_path,
        "assetPath": contract_asset_path,
        "UIData": asset_class_object_path("/Game/Contracts/NPE/Contract_NPE_UIData.Contract_NPE_UIData_C"),
        "uiData": asset_class_object_path("/Game/Contracts/NPE/Contract_NPE_UIData.Contract_NPE_UIData_C"),
        "UIDataPath": asset_class_object_path("/Game/Contracts/NPE/Contract_NPE_UIData.Contract_NPE_UIData_C"),
        "uiDataPath": asset_class_object_path("/Game/Contracts/NPE/Contract_NPE_UIData.Contract_NPE_UIData_C"),
        "Id": local_story_contract_id,
        "UUID": local_story_contract_id,
        "Uuid": local_story_contract_id,
        "uuid": local_story_contract_id,
        "Guid": local_story_contract_id,
        "guid": local_story_contract_id,
        "name": contract_name,
        "contractType": "Story",
        "Levels": [],
        "levels": [],
    }


def character_contract_definition_payload(contract_row: dict[str, Any], *, local_currency_id: str, item_type_contract: str) -> dict[str, Any]:
    contract_id = contract_row["id"]
    contract_asset_path = asset_class_object_path(contract_row["asset"])
    contract_asset_name = asset_reference_name(contract_row["asset"])
    ui_data_path = asset_class_object_path(contract_row["ui_data"])
    levels = [contract_chapter_payload(chapter) for chapter in contract_row["chapters"]]
    reward_schedules = [
        {
            "ID": chapter["id"],
            "Prerequisites": {"RequiredEntitlements": []},
            "RewardsPerLevel": [],
        }
        for chapter in contract_row["chapters"]
    ]
    return {
        "ID": contract_id,
        "Id": contract_id,
        "UUID": contract_id,
        "Uuid": contract_id,
        "uuid": contract_id,
        "Guid": contract_id,
        "guid": contract_id,
        "Name": f"{contract_row['name']} Contract",
        "name": f"{contract_row['name']} Contract",
        "ContractType": "Special",
        "contractType": "Special",
        "ProgressionSchedule": {
            "ID": contract_id,
            "ProgressionCurrencyID": local_currency_id,
            "ProgressionDeltaPerLevel": [0 for _ in range(10)],
        },
        "AlternateProgressionSchedules": [],
        "RewardSchedules": reward_schedules,
        "PremiumContractDetails": {
            "Entitlement": {
                "ItemTypeID": item_type_contract,
                "ItemID": contract_id,
            },
            "PurchaseCurrencyID": local_currency_id,
            "PurchaseCost": 0,
        },
        "DataAsset": contract_asset_path,
        "dataAsset": contract_asset_path,
        "DataAssetPath": contract_asset_path,
        "dataAssetPath": contract_asset_path,
        "AssetName": contract_asset_name,
        "assetName": contract_asset_name,
        "AssetPath": contract_asset_path,
        "assetPath": contract_asset_path,
        "UIData": ui_data_path,
        "uiData": ui_data_path,
        "UIDataPath": ui_data_path,
        "uiDataPath": ui_data_path,
        "Levels": levels,
        "levels": levels,
        "ContractChapters": levels,
        "contractChapters": levels,
    }


def contract_definitions_payload(*, item_progressions: list[dict[str, Any]], story_definition: dict[str, Any], character_definitions: list[dict[str, Any]], local_story_contract_id: str) -> dict[str, Any]:
    definitions = [story_definition]
    definitions.extend(character_definitions)
    return {
        "ContractDefinitions": definitions,
        "contractDefinitions": definitions,
        "ActiveStoryContractID": local_story_contract_id,
        "activeStoryContractID": local_story_contract_id,
        "ActiveStoryContractId": local_story_contract_id,
        "activeStoryContractId": local_story_contract_id,
        "ActiveStoryContractDefinition": story_definition,
        "activeStoryContractDefinition": story_definition,
        "NPEContractID": local_story_contract_id,
        "npeContractID": local_story_contract_id,
        "NPEContractId": local_story_contract_id,
        "npeContractId": local_story_contract_id,
        "ItemProgressionDefinitions": item_progressions,
        "itemProgressionDefinitions": item_progressions,
        "Definitions": definitions,
        "definitions": definitions,
    }


def active_story_contract_definition_payload(*, story_definition: dict[str, Any], character_definitions: list[dict[str, Any]], local_story_contract_id: str) -> dict[str, Any]:
    payload = dict(story_definition)
    definitions = [story_definition]
    definitions.extend(character_definitions)
    payload.update({
        "ContractDefinitions": definitions,
        "contractDefinitions": definitions,
        "Definitions": definitions,
        "definitions": definitions,
        "ActiveContractID": local_story_contract_id,
        "activeContractID": local_story_contract_id,
        "ActiveContractId": local_story_contract_id,
        "activeContractId": local_story_contract_id,
        "ActiveStoryContractID": local_story_contract_id,
        "activeStoryContractID": local_story_contract_id,
        "ActiveStoryContractId": local_story_contract_id,
        "activeStoryContractId": local_story_contract_id,
        "ActiveStoryContractDefinition": story_definition,
        "activeStoryContractDefinition": story_definition,
    })
    return payload
