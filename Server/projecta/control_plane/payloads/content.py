from __future__ import annotations

from typing import Any, Callable

from ..common.assets import (
    asset_class_name,
    asset_class_object_path,
    asset_default_object_name,
    asset_reference_name,
    blueprint_asset,
)
from ..data.content_types import CLIENT_CONTENT_TYPE_IDS, ARES_CONTENT_TYPE_INDEX, content_type_id_for_item_type


def required_entitlement_payload(item_type_id: str, item_id: str) -> dict[str, Any]:
    content_type_id = content_type_id_for_item_type(item_type_id)
    return {
        "TypeID": item_type_id,
        "typeID": item_type_id,
        "Type": item_type_id,
        "type": item_type_id,
        "ContentTypeID": content_type_id,
        "contentTypeID": content_type_id,
        "AresContentType": content_type_id,
        "aresContentType": content_type_id,
        "ServiceID": item_id,
        "serviceID": item_id,
        "ServiceId": item_id,
        "serviceId": item_id,
        "ItemTypeID": item_type_id,
        "itemTypeID": item_type_id,
        "ItemTypeUUID": item_type_id,
        "itemTypeUUID": item_type_id,
        "ItemTypeId": item_type_id,
        "itemTypeId": item_type_id,
        "ItemID": item_id,
        "itemID": item_id,
        "InstanceID": item_id,
        "instanceID": item_id,
        "EntitlementIdentifier": item_id,
        "entitlementIdentifier": item_id,
    }


def content_data_payload(item_id: str, name: str, asset: str) -> dict[str, Any]:
    asset_path = asset_class_object_path(asset)
    asset_class = asset_class_name(asset)
    asset_name = asset_default_object_name(asset)
    return {
        "ID": item_id,
        "Id": item_id,
        "UUID": item_id,
        "Uuid": item_id,
        "uuid": item_id,
        "Guid": item_id,
        "guid": item_id,
        "Name": name,
        "name": name,
        "DisplayName": name,
        "displayName": name,
        "AssetName": asset_name,
        "assetName": asset_name,
        "ClassName": asset_class,
        "className": asset_class,
        "AssetClassName": asset_class,
        "assetClassName": asset_class,
        "AssetPath": asset_path,
        "assetPath": asset_path,
        "DataAsset": asset_path,
        "dataAsset": asset_path,
        "DataAssetPath": asset_path,
        "dataAssetPath": asset_path,
        "DataAssetID": item_id,
        "dataAssetID": item_id,
        "DataAssetId": item_id,
        "dataAssetId": item_id,
        "IsEnabled": True,
        "isEnabled": True,
    }


def compact_content_data_payload(item_id: str, name: str, asset: str) -> dict[str, Any]:
    asset_path = asset_class_object_path(asset)
    asset_class = asset_class_name(asset)
    asset_name = asset_default_object_name(asset)
    return {
        "ID": item_id,
        "Guid": item_id,
        "guid": item_id,
        "UUID": item_id,
        "Uuid": item_id,
        "uuid": item_id,
        "Name": name,
        "name": name,
        "AssetName": asset_name,
        "assetName": asset_name,
        "ClassName": asset_class,
        "className": asset_class,
        "AssetClassName": asset_class,
        "assetClassName": asset_class,
        "AssetPath": asset_path,
        "assetPath": asset_path,
        "DataAsset": asset_path,
        "dataAsset": asset_path,
        "DataAssetPath": asset_path,
        "dataAssetPath": asset_path,
        "DataAssetID": item_id,
        "dataAssetID": item_id,
        "DataAssetId": item_id,
        "dataAssetId": item_id,
        "IsEnabled": True,
        "isEnabled": True,
    }


def content_asset(item_id: str, name: str, content_type: str, asset_path: str = "") -> dict[str, Any]:
    asset = asset_path or item_id
    asset_class = asset_class_name(asset)
    asset_name = asset_default_object_name(asset)
    asset_object = asset_class_object_path(asset)
    type_id = CLIENT_CONTENT_TYPE_IDS.get(content_type, ARES_CONTENT_TYPE_INDEX["Invalid"])
    data = content_data_payload(item_id, name, asset)
    payload = {
        "ID": item_id,
        "Id": item_id,
        "UUID": item_id,
        "Uuid": item_id,
        "uuid": item_id,
        "Guid": item_id,
        "guid": item_id,
        "Name": name,
        "name": name,
        "DisplayName": name,
        "displayName": name,
        "ContentType": content_type,
        "contentType": content_type,
        "TypeID": type_id,
        "typeID": type_id,
        "ContentTypeID": type_id,
        "contentTypeID": type_id,
        "ServiceID": item_id,
        "serviceID": item_id,
        "ServiceId": item_id,
        "serviceId": item_id,
        "AssetName": asset_name,
        "assetName": asset_name,
        "ClassName": asset_class,
        "className": asset_class,
        "AssetClassName": asset_class,
        "assetClassName": asset_class,
        "DataAssetID": item_id,
        "dataAssetID": item_id,
        "DataAssetId": item_id,
        "dataAssetId": item_id,
        "DataAsset": asset_object,
        "dataAsset": asset_object,
        "AssetPath": asset_object,
        "assetPath": asset_object,
        "IsEnabled": True,
        "isEnabled": True,
        "Item": item_id,
        "item": item_id,
        "ItemID": item_id,
        "itemID": item_id,
        "Content": data,
        "content": data,
        "Levels": [],
        "levels": [],
        "RequiredEntitlement": None,
        "requiredEntitlement": None,
    }
    return payload


def content_data_struct(item: dict[str, Any]) -> dict[str, Any]:
    item_id = str(item.get("ID") or item.get("ItemID") or "")
    asset_ref = str(item.get("AssetPath") or item.get("AssetName") or item_id)
    name = str(item.get("DTOName") or asset_reference_name(asset_ref) or item.get("Name") or item.get("DisplayName") or item_id)
    asset_class = asset_class_name(asset_ref)
    asset_name = asset_default_object_name(asset_ref)
    asset_path = asset_class_object_path(asset_ref)
    return {
        "ID": item_id,
        "Id": item_id,
        "UUID": item_id,
        "Uuid": item_id,
        "Name": name,
        "Guid": item_id,
        "AssetName": asset_name,
        "ClassName": asset_class,
        "AssetClassName": asset_class,
        "PrimaryAssetName": asset_reference_name(asset_ref),
        "AssetPath": asset_path,
        "IsEnabled": True,
        "isEnabled": True,
        "DevelopmentOnly": False,
    }


def content_dto_struct(item: dict[str, Any]) -> dict[str, Any]:
    item_id = str(item.get("ID") or item.get("ItemID") or "")
    asset_ref = str(item.get("AssetPath") or item.get("AssetName") or item_id)
    name = str(item.get("DTOName") or asset_reference_name(asset_ref) or item.get("Name") or item.get("DisplayName") or item_id)
    asset_class = asset_class_name(asset_ref)
    asset_name = asset_default_object_name(asset_ref)
    return {
        "Name": name,
        "AssetName": asset_name,
        "ClassName": asset_class,
        "AssetClassName": asset_class,
        "PrimaryAssetName": asset_reference_name(asset_ref),
        "ID": item_id,
        "IsEnabled": True,
    }


def season_content_struct(item_id: str, name: str, season_type: str = "act") -> dict[str, Any]:
    return {
        "ID": item_id,
        "Name": name,
        "Type": season_type,
        "StartTime": "2020-01-01T00:00:00.000Z",
        "EndTime": "2030-01-01T00:00:00.000Z",
        "DevelopmentOnly": False,
    }


def content_listing(
    item: dict[str, Any],
    item_type_id: str | None = None,
    levels: list[Any] | None = None,
    required_entitlement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    listing = dict(item)
    item_id = str(item.get("ID") or item.get("ItemID") or "")
    content_type = str(item.get("ContentType") or item.get("contentType") or "")
    content_type_id = int(item.get("ContentTypeID") or CLIENT_CONTENT_TYPE_IDS.get(content_type, 0) or 0)
    asset_ref = str(item.get("AssetPath") or item.get("DataAsset") or item.get("AssetName") or item_id)
    asset_class = asset_class_name(asset_ref)
    asset_name = asset_default_object_name(asset_ref)
    asset_path = asset_class_object_path(asset_ref)
    item_model = {
        "ID": item_id,
        "Id": item_id,
        "UUID": item_id,
        "Uuid": item_id,
        "uuid": item_id,
        "ItemID": item_id,
        "itemID": item_id,
        "ContentType": content_type,
        "contentType": content_type,
        "ContentTypeID": content_type_id,
        "contentTypeID": content_type_id,
        "Type": content_type,
        "type": content_type,
        "TypeID": content_type_id,
        "typeID": content_type_id,
        "AssetName": asset_name,
        "assetName": asset_name,
        "ClassName": asset_class,
        "className": asset_class,
        "AssetClassName": asset_class,
        "assetClassName": asset_class,
        "AssetPath": asset_path,
        "assetPath": asset_path,
    }
    if required_entitlement is None and item_type_id and item_id:
        required_entitlement = required_entitlement_payload(item_type_id, item_id)
    content = content_data_payload(
        item_id,
        str(item.get("Name") or item.get("DisplayName") or item_id),
        asset_ref,
    )
    levels = levels or []
    listing.update(
        {
            "Item": item_model,
            "item": item_model,
            "ItemID": item_id,
            "itemID": item_id,
            "Content": content,
            "content": content,
            "Levels": levels,
            "levels": levels,
            "RequiredEntitlement": required_entitlement,
            "requiredEntitlement": required_entitlement,
        }
    )
    return listing


def content_listing_bucket(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket = []
    passthrough_keys = (
        "EquippableID", "equippableID", "Equippable", "equippable", "SkinID", "skinID", "SkinId", "skinId",
        "SkinLevelID", "skinLevelID", "SkinLevelId", "skinLevelId", "SkinLevels", "skinLevels", "SkinLevelIDs",
        "skinLevelIDs", "DefaultSkinLevelID", "defaultSkinLevelID", "DefaultSkinLevelId", "defaultSkinLevelId",
        "BaseLevelID", "baseLevelID", "BaseLevelId", "baseLevelId", "DefaultChromaID", "defaultChromaID",
        "DefaultChromaId", "defaultChromaId", "ChromaIDs", "chromaIDs", "Chromas", "chromas", "CharacterID",
        "characterID", "CharacterId", "characterId", "DeveloperName", "developerName", "CharacterAsset", "characterAsset",
        "CharacterAssetPath", "characterAssetPath", "UIData", "uiData", "UIDataAsset", "uiDataAsset", "UIDataPath",
        "uiDataPath", "CharacterSelectFXC", "characterSelectFXC", "CharacterSelectFXCAsset", "characterSelectFXCAsset",
        "RoleID", "roleID", "RoleId", "roleId", "Role", "role", "RoleAsset", "roleAsset", "RolePath", "rolePath",
        "RoleUIData", "roleUIData", "RoleUIDataPath", "roleUIDataPath", "ContractDefinitionID", "contractDefinitionID",
        "ContractDefinitionId", "contractDefinitionId", "ContractType", "contractType", "IsPlayableCharacter", "isPlayableCharacter",
        "AvailableForTest", "availableForTest",
    )
    for item in items:
        item_id = str(item.get("ItemID") or item.get("ID") or "")
        content_type = str(item.get("ContentType") or item.get("contentType") or "")
        content_type_id = int(item.get("ContentTypeID") or item.get("TypeID") or CLIENT_CONTENT_TYPE_IDS.get(content_type, 0) or 0)
        asset_ref = str(item.get("AssetPath") or item.get("DataAsset") or item.get("AssetName") or item_id)
        asset_class = asset_class_name(asset_ref)
        asset_name = asset_default_object_name(asset_ref)
        asset_path = asset_class_object_path(asset_ref)
        display_name = str(item.get("Name") or item.get("DisplayName") or item_id)
        item_model = {
            "ID": item_id,
            "Guid": item_id,
            "UUID": item_id,
            "Uuid": item_id,
            "ItemID": item_id,
            "ContentType": content_type,
            "ContentTypeID": content_type_id,
            "TypeID": content_type_id,
            "Name": display_name,
            "AssetName": asset_name,
            "ClassName": asset_class,
            "AssetClassName": asset_class,
            "AssetPath": asset_path,
            "DataAsset": asset_path,
            "DataAssetPath": asset_path,
        }
        required_entitlement = item.get("RequiredEntitlement")
        if isinstance(required_entitlement, dict):
            required_entitlement = {
                "ItemID": required_entitlement.get("ItemID") or required_entitlement.get("itemID") or item_id,
                "ItemTypeID": required_entitlement.get("ItemTypeID") or required_entitlement.get("TypeID"),
                "TypeID": required_entitlement.get("TypeID") or required_entitlement.get("ItemTypeID"),
                "Type": required_entitlement.get("Type") or required_entitlement.get("ItemTypeID") or required_entitlement.get("TypeID"),
                "ServiceID": required_entitlement.get("ServiceID") or required_entitlement.get("ItemID") or item_id,
                "InstanceID": required_entitlement.get("InstanceID") or item_id,
            }
        raw_levels = item.get("Levels", [])
        levels: list[dict[str, Any]] = []
        if isinstance(raw_levels, list):
            for level in raw_levels:
                if isinstance(level, dict):
                    levels.append(level)
                elif isinstance(level, str) and level:
                    levels.append(
                        {
                            "ID": level,
                            "Guid": level,
                            "UUID": level,
                            "Uuid": level,
                            "ItemID": level,
                            "ContentType": "EquippableSkinLevel",
                            "ContentTypeID": CLIENT_CONTENT_TYPE_IDS["EquippableSkinLevel"],
                            "TypeID": CLIENT_CONTENT_TYPE_IDS["EquippableSkinLevel"],
                        }
                    )
        entry = {
            "Item": item_model,
            "item": item_model,
            "ItemData": item_model,
            "itemData": item_model,
            "ItemModel": item_model,
            "itemModel": item_model,
            "ID": item_id,
            "Id": item_id,
            "Guid": item_id,
            "guid": item_id,
            "UUID": item_id,
            "Uuid": item_id,
            "uuid": item_id,
            "ItemID": item_id,
            "itemID": item_id,
            "ServiceID": item_id,
            "serviceID": item_id,
            "ServiceId": item_id,
            "serviceId": item_id,
            "Name": display_name,
            "name": display_name,
            "DisplayName": display_name,
            "displayName": display_name,
            "ContentType": content_type,
            "contentType": content_type,
            "ContentTypeID": content_type_id,
            "contentTypeID": content_type_id,
            "TypeID": content_type_id,
            "typeID": content_type_id,
            "AssetName": asset_name,
            "assetName": asset_name,
            "ClassName": asset_class,
            "className": asset_class,
            "AssetClassName": asset_class,
            "assetClassName": asset_class,
            "AssetPath": asset_path,
            "assetPath": asset_path,
            "Content": compact_content_data_payload(item_id, display_name, asset_path),
            "content": compact_content_data_payload(item_id, display_name, asset_path),
            "Levels": levels,
            "levels": levels,
            "RequiredEntitlement": required_entitlement,
            "requiredEntitlement": required_entitlement,
            "IsEnabled": True,
            "isEnabled": True,
            "DevelopmentOnly": False,
            "developmentOnly": False,
        }
        for key in passthrough_keys:
            if key in item:
                entry[key] = item[key]
        bucket.append(entry)
    return bucket


def full_content_listing_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        entry = content_listing_bucket([item])[0]
        type_raw = item.get("ContentTypeID")
        if type_raw is None:
            type_raw = item.get("TypeID")
        if type_raw is not None:
            by_type.setdefault(str(type_raw), []).append(entry)
        type_name = str(item.get("ContentType") or item.get("contentType") or "")
        if type_name:
            by_name.setdefault(type_name, []).append(entry)
    payload = {"ByType": by_type}
    for key, value in by_type.items():
        payload[key] = value
    for key, value in by_name.items():
        payload[key] = value
    return payload


def row_asset(row: dict[str, str], key: str, fallback: str, default_loadout_asset_paths: dict[str, dict[str, str]]) -> str:
    asset_path = default_loadout_asset_paths.get(row.get("name", ""), {}).get(key, fallback)
    return asset_path if asset_path.startswith("BlueprintGeneratedClass'") else blueprint_asset(asset_path)


def content_service_payload(
    game_state: dict[str, Any] | None,
    *,
    config: dict[str, Any],
    loadout_content_rows: Callable[[dict[str, Any] | None], list[dict[str, str]]],
) -> dict[str, Any]:
    DEFAULT_PLAYER_CARD_ID = config["DEFAULT_PLAYER_CARD_ID"]
    DEFAULT_PLAYER_CARD_ASSET = config["DEFAULT_PLAYER_CARD_ASSET"]
    ITEM_TYPE_PLAYER_CARD = config["ITEM_TYPE_PLAYER_CARD"]
    DEFAULT_PLAYER_TITLE_ID = config["DEFAULT_PLAYER_TITLE_ID"]
    DEFAULT_PLAYER_TITLE_ASSET = config["DEFAULT_PLAYER_TITLE_ASSET"]
    ITEM_TYPE_PLAYER_TITLE = config["ITEM_TYPE_PLAYER_TITLE"]
    LOCAL_MAP_ROWS = config["LOCAL_MAP_ROWS"]
    LOCAL_MODE_ROWS = config["LOCAL_MODE_ROWS"]
    LOCAL_CHARACTER_ROLE_ROWS = config["LOCAL_CHARACTER_ROLE_ROWS"]
    LOCAL_AGENT_ROWS = config["LOCAL_AGENT_ROWS"]
    LOCAL_CHARACTER_ROLE_BY_SLUG = config["LOCAL_CHARACTER_ROLE_BY_SLUG"]
    DEFAULT_SPRAY_PREROUND_ID = config["DEFAULT_SPRAY_PREROUND_ID"]
    DEFAULT_SPRAY_PREROUND_ASSET = config["DEFAULT_SPRAY_PREROUND_ASSET"]
    DEFAULT_SPRAY_MIDROUND_ID = config["DEFAULT_SPRAY_MIDROUND_ID"]
    DEFAULT_SPRAY_MIDROUND_ASSET = config["DEFAULT_SPRAY_MIDROUND_ASSET"]
    ITEM_TYPE_SPRAY = config["ITEM_TYPE_SPRAY"]
    LOCAL_CURRENCY_ROWS = config["LOCAL_CURRENCY_ROWS"]
    LOCAL_SEASON_ID = config["LOCAL_SEASON_ID"]
    LOCAL_SEASON_ASSET = config["LOCAL_SEASON_ASSET"]
    LOCAL_STORY_CONTRACT_ID = config["LOCAL_STORY_CONTRACT_ID"]
    LOCAL_CONTRACT_ASSET = config["LOCAL_CONTRACT_ASSET"]
    ITEM_TYPE_CONTRACT = config["ITEM_TYPE_CONTRACT"]
    LOCAL_CHARACTER_CONTRACT_ROWS = config["LOCAL_CHARACTER_CONTRACT_ROWS"]
    ITEM_TYPE_CHARACTER = config["ITEM_TYPE_CHARACTER"]
    ITEM_TYPE_SKIN = config["ITEM_TYPE_SKIN"]
    ITEM_TYPE_SKIN_LEVEL = config["ITEM_TYPE_SKIN_LEVEL"]
    ITEM_TYPE_SKIN_CHROMA = config["ITEM_TYPE_SKIN_CHROMA"]
    DEFAULT_LOADOUT_ASSET_PATHS = config["DEFAULT_LOADOUT_ASSET_PATHS"]

    def row_asset_for_payload(row: dict[str, str], key: str, fallback: str) -> str:
        return row_asset(row, key, fallback, DEFAULT_LOADOUT_ASSET_PATHS)

    cards = [content_listing(content_asset(DEFAULT_PLAYER_CARD_ID, "Ether Explosion", "PlayerCard", DEFAULT_PLAYER_CARD_ASSET), ITEM_TYPE_PLAYER_CARD)]
    titles = [content_listing(content_asset(DEFAULT_PLAYER_TITLE_ID, "Default Title", "PlayerTitle", DEFAULT_PLAYER_TITLE_ASSET), ITEM_TYPE_PLAYER_TITLE)]
    maps = []
    for row in LOCAL_MAP_ROWS:
        map_entry = content_asset(row["path"], row["name"], "Map", row["asset"])
        map_entry.update(
            {
                "ServiceID": row["id"], "serviceID": row["id"], "ServiceId": row["id"], "serviceId": row["id"],
                "MapID": row["path"], "mapID": row["path"], "MapId": row["path"], "mapId": row["path"],
                "MapPath": row["path"], "mapPath": row["path"], "UIData": row["ui_data"], "uiData": row["ui_data"],
                "UIDataPath": asset_class_object_path(row["ui_data"]), "uiDataPath": asset_class_object_path(row["ui_data"]),
            }
        )
        maps.append(content_listing(map_entry))
    modes = []
    for row in LOCAL_MODE_ROWS:
        mode_entry = content_asset(row["path"], row["name"], "GameMode", row["asset"])
        mode_entry.update(
            {
                "ServiceID": row["id"], "serviceID": row["id"], "ServiceId": row["id"], "serviceId": row["id"],
                "Mode": row["path"], "mode": row["path"], "ModeID": row["path"], "modeID": row["path"],
                "ModeId": row["path"], "modeId": row["path"], "GameMode": row["path"], "gameMode": row["path"],
                "GameModeID": row["path"], "gameModeID": row["path"], "UIData": row["ui_data"], "uiData": row["ui_data"],
                "UIDataPath": asset_class_object_path(row["ui_data"]), "uiDataPath": asset_class_object_path(row["ui_data"]),
            }
        )
        modes.append(content_listing(mode_entry))
    role_by_slug = {row["slug"]: row for row in LOCAL_CHARACTER_ROLE_ROWS}
    character_roles = []
    for row in LOCAL_CHARACTER_ROLE_ROWS:
        role = content_asset(row["id"], row["name"], "CharacterRole", row["asset"])
        role.update({"UIData": row["ui_data"], "uiData": row["ui_data"], "UIDataAsset": row["ui_data"], "uiDataAsset": row["ui_data"], "UIDataPath": asset_class_object_path(row["ui_data"]), "uiDataPath": asset_class_object_path(row["ui_data"])})
        character_roles.append(content_listing(role))
    characters = []
    for row in LOCAL_AGENT_ROWS:
        character = content_asset(row["id"], row["name"], "Character", row["asset"])
        role_row = role_by_slug.get(LOCAL_CHARACTER_ROLE_BY_SLUG.get(row["slug"], ""))
        character.update(
            {
                "CharacterID": row["id"], "characterID": row["id"], "CharacterId": row["id"], "characterId": row["id"],
                "DeveloperName": row["slug"], "developerName": row["slug"], "CharacterAsset": row["character_asset"],
                "characterAsset": row["character_asset"], "CharacterAssetPath": asset_class_object_path(row["character_asset"]),
                "characterAssetPath": asset_class_object_path(row["character_asset"]), "UIData": row["ui_data"], "uiData": row["ui_data"],
                "UIDataAsset": row["ui_data"], "uiDataAsset": row["ui_data"], "UIDataPath": asset_class_object_path(row["ui_data"]),
                "uiDataPath": asset_class_object_path(row["ui_data"]), "CharacterSelectFXC": row["select_fxc"],
                "characterSelectFXC": row["select_fxc"], "CharacterSelectFXCAsset": row["select_fxc"],
                "characterSelectFXCAsset": row["select_fxc"], "IsPlayableCharacter": True, "isPlayableCharacter": True,
                "AvailableForTest": True, "availableForTest": True,
            }
        )
        if role_row:
            character.update(
                {
                    "RoleID": role_row["id"], "roleID": role_row["id"], "RoleId": role_row["id"], "roleId": role_row["id"],
                    "Role": role_row["asset"], "role": role_row["asset"], "RoleAsset": role_row["asset"], "roleAsset": role_row["asset"],
                    "RolePath": asset_class_object_path(role_row["asset"]), "rolePath": asset_class_object_path(role_row["asset"]),
                    "RoleUIData": role_row["ui_data"], "roleUIData": role_row["ui_data"],
                    "RoleUIDataPath": asset_class_object_path(role_row["ui_data"]), "roleUIDataPath": asset_class_object_path(role_row["ui_data"]),
                }
            )
        characters.append(content_listing(character, ITEM_TYPE_CHARACTER))
    sprays = [
        content_listing(content_asset(DEFAULT_SPRAY_PREROUND_ID, "Chicken", "Spray", DEFAULT_SPRAY_PREROUND_ASSET), ITEM_TYPE_SPRAY),
        content_listing(content_asset(DEFAULT_SPRAY_MIDROUND_ID, "Salt", "Spray", DEFAULT_SPRAY_MIDROUND_ASSET), ITEM_TYPE_SPRAY),
    ]
    currencies = [content_listing(content_asset(row["id"], row["name"], "Currency", row["asset"])) for row in LOCAL_CURRENCY_ROWS]
    seasons = [content_listing(content_asset(LOCAL_SEASON_ID, "Local Season", "Season", LOCAL_SEASON_ASSET))]
    contracts: list[dict[str, Any]] = []
    story_contract = content_asset(LOCAL_STORY_CONTRACT_ID, "Local Story Contract", "Contract", LOCAL_CONTRACT_ASSET)
    story_contract.update({"ContractDefinitionID": LOCAL_STORY_CONTRACT_ID, "contractDefinitionID": LOCAL_STORY_CONTRACT_ID, "ContractDefinitionId": LOCAL_STORY_CONTRACT_ID, "contractDefinitionId": LOCAL_STORY_CONTRACT_ID, "ContractType": "Story", "contractType": "Story", "UIData": asset_class_object_path("/Game/Contracts/NPE/Contract_NPE_UIData.Contract_NPE_UIData_C"), "uiData": asset_class_object_path("/Game/Contracts/NPE/Contract_NPE_UIData.Contract_NPE_UIData_C"), "UIDataPath": asset_class_object_path("/Game/Contracts/NPE/Contract_NPE_UIData.Contract_NPE_UIData_C"), "uiDataPath": asset_class_object_path("/Game/Contracts/NPE/Contract_NPE_UIData.Contract_NPE_UIData_C")})
    contracts.append(content_listing(story_contract, ITEM_TYPE_CONTRACT))
    for row in LOCAL_CHARACTER_CONTRACT_ROWS:
        contract = content_asset(row["id"], f"{row['name']} Contract", "Contract", row["asset"])
        contract.update({"ContractDefinitionID": row["id"], "contractDefinitionID": row["id"], "ContractDefinitionId": row["id"], "contractDefinitionId": row["id"], "ContractType": "Special", "contractType": "Special", "UIData": asset_class_object_path(row["ui_data"]), "uiData": asset_class_object_path(row["ui_data"]), "UIDataPath": asset_class_object_path(row["ui_data"]), "uiDataPath": asset_class_object_path(row["ui_data"])})
        contracts.append(content_listing(contract, ITEM_TYPE_CONTRACT))
    equips = []
    skins = []
    skin_levels = []
    chromas = []
    for row in loadout_content_rows(game_state):
        equip = content_listing(content_asset(row["equippable_id"], row["name"], "Equippable", row_asset_for_payload(row, "equippable", f"/Game/Equippables/{row['name']}/{row['name']}_PrimaryAsset")))
        skin = content_listing(content_asset(row["skin_id"], f"Standard {row['name']}", "EquippableSkin", row_asset_for_payload(row, "skin", f"/Game/Equippables/{row['name']}/Skins/Standard/{row['name']}_Standard_PrimaryAsset")), ITEM_TYPE_SKIN, [row["skin_level_id"]])
        level = content_listing(content_asset(row["skin_level_id"], f"Standard {row['name']} Level", "EquippableSkinLevel", row_asset_for_payload(row, "level", f"/Game/Equippables/{row['name']}/Skins/Standard/{row['name']}_Standard_Lv1_PrimaryAsset")), ITEM_TYPE_SKIN_LEVEL)
        chroma = content_listing(content_asset(row["chroma_id"], f"Standard {row['name']} Chroma", "EquippableSkinChroma", row_asset_for_payload(row, "chroma", f"/Game/Equippables/{row['name']}/Skins/Standard/Chromas/Standard/{row['name']}_Standard_Standard_PrimaryAsset")), ITEM_TYPE_SKIN_CHROMA)
        skin.update({"EquippableID": row["equippable_id"], "equippableID": row["equippable_id"], "Equippable": row["equippable_id"], "equippable": row["equippable_id"], "SkinLevels": [row["skin_level_id"]], "skinLevels": [row["skin_level_id"]], "Chromas": [row["chroma_id"]], "chromas": [row["chroma_id"]]})
        level.update({"EquippableID": row["equippable_id"], "equippableID": row["equippable_id"], "SkinID": row["skin_id"], "skinID": row["skin_id"], "SkinId": row["skin_id"], "skinId": row["skin_id"], "BaseLevel": True, "baseLevel": True})
        chroma.update({"EquippableID": row["equippable_id"], "equippableID": row["equippable_id"], "SkinID": row["skin_id"], "skinID": row["skin_id"], "SkinId": row["skin_id"], "skinId": row["skin_id"], "SkinLevelID": row["skin_level_id"], "skinLevelID": row["skin_level_id"], "SkinLevelId": row["skin_level_id"], "skinLevelId": row["skin_level_id"]})
        chroma_entry = content_listing_bucket([chroma])[0]
        skin.update({"Levels": [row["skin_level_id"]], "levels": [row["skin_level_id"]], "SkinLevels": [row["skin_level_id"]], "skinLevels": [row["skin_level_id"]], "SkinLevelIDs": [row["skin_level_id"]], "skinLevelIDs": [row["skin_level_id"]], "DefaultSkinLevelID": row["skin_level_id"], "defaultSkinLevelID": row["skin_level_id"], "DefaultSkinLevelId": row["skin_level_id"], "defaultSkinLevelId": row["skin_level_id"], "BaseLevelID": row["skin_level_id"], "baseLevelID": row["skin_level_id"], "BaseLevelId": row["skin_level_id"], "baseLevelId": row["skin_level_id"], "DefaultChromaID": row["chroma_id"], "defaultChromaID": row["chroma_id"], "DefaultChromaId": row["chroma_id"], "defaultChromaId": row["chroma_id"], "ChromaIDs": [row["chroma_id"]], "chromaIDs": [row["chroma_id"]], "Chromas": [chroma_entry], "chromas": [chroma_entry]})
        equips.append(equip)
        skins.append(skin)
        skin_levels.append(level)
        chromas.append(chroma)
    full_listing = cards + titles + maps + modes + character_roles + characters + sprays + currencies + seasons + contracts + equips + skins + skin_levels + chromas
    canonical_full_content_dto = {
        "Characters": [content_dto_struct(item) for item in characters], "CharacterRoles": [content_dto_struct(item) for item in character_roles],
        "Maps": [content_dto_struct(item) for item in maps], "Chromas": [content_dto_struct(item) for item in chromas],
        "Skins": [content_dto_struct(item) for item in skins], "SkinLevels": [content_dto_struct(item) for item in skin_levels],
        "Attachments": [], "Equips": [content_dto_struct(item) for item in equips], "Themes": [],
        "GameModes": [content_dto_struct(item) for item in modes], "Currencies": [content_dto_struct(item) for item in currencies],
        "Sprays": [content_dto_struct(item) for item in sprays], "SprayLevels": [], "Charms": [], "CharmLevels": [],
        "PlayerCards": [content_dto_struct(item) for item in cards], "PlayerTitles": [content_dto_struct(item) for item in titles],
    }
    supported_content_type_names = ["Contract", "Equippable", "EquippableSkin", "EquippableSkinLevel", "EquippableSkinChroma", "Character", "CharacterRole", "Map", "Spray", "GameMode", "Currency", "PlayerCard", "PlayerTitle", "Season"]
    content_types = [{"ID": CLIENT_CONTENT_TYPE_IDS[name], "Id": CLIENT_CONTENT_TYPE_IDS[name], "TypeID": CLIENT_CONTENT_TYPE_IDS[name], "typeID": CLIENT_CONTENT_TYPE_IDS[name], "Name": name, "name": name} for name in supported_content_type_names]
    player_card_mapping = {DEFAULT_PLAYER_CARD_ID: content_listing_bucket(cards)[0]}
    player_title_mapping = {DEFAULT_PLAYER_TITLE_ID: content_listing_bucket(titles)[0]}
    spray_mapping = {spray["ItemID"]: spray for spray in content_listing_bucket(sprays)}
    equippable_mapping = {equip["ItemID"]: equip for equip in content_listing_bucket(equips)}
    skin_mapping = {skin["ItemID"]: skin for skin in content_listing_bucket(skins)}
    skin_level_entries = content_listing_bucket(skin_levels)
    skin_level_mapping = {level["ItemID"]: level for level in skin_level_entries}
    skin_level_mapping_by_skin_id = {}
    skin_level_mapping_by_equippable_skin = {}
    for level in skin_level_entries:
        equippable_id = level.get("EquippableID") or level.get("equippableID")
        skin_id = level.get("SkinID") or level.get("skinID") or level.get("SkinId") or level.get("skinId")
        if skin_id:
            skin_level_mapping[str(skin_id)] = level
            skin_level_mapping_by_skin_id[str(skin_id)] = level
        if equippable_id and skin_id:
            composite_key = f"{equippable_id}:{skin_id}"
            skin_level_mapping[composite_key] = level
            skin_level_mapping_by_equippable_skin.setdefault(str(equippable_id), {})[str(skin_id)] = level
    chroma_mapping = {chroma["ItemID"]: chroma for chroma in content_listing_bucket(chromas)}
    currency_mapping = {currency["ItemID"]: currency for currency in content_listing_bucket(currencies)}
    season_mapping = {season["ItemID"]: season for season in content_listing_bucket(seasons)}
    character_entries = content_listing_bucket(characters)
    character_role_entries = content_listing_bucket(character_roles)
    map_entries = content_listing_bucket(maps)
    mode_entries = content_listing_bucket(modes)
    spray_entries = content_listing_bucket(sprays)
    equip_entries = content_listing_bucket(equips)
    skin_entries = content_listing_bucket(skins)
    skin_level_entries = content_listing_bucket(skin_levels)
    chroma_entries = content_listing_bucket(chromas)
    card_entries = content_listing_bucket(cards)
    title_entries = content_listing_bucket(titles)
    currency_entries = content_listing_bucket(currencies)
    season_entries = content_listing_bucket(seasons)
    contract_entries = content_listing_bucket(contracts)
    full_listing_payload = {
        **full_content_listing_payload(full_listing),
        "Characters": character_entries, "CharacterRoles": character_role_entries, "Equips": equip_entries, "Attachments": [],
        "Skins": skin_entries, "SkinLevels": skin_level_entries, "Chromas": chroma_entries, "Maps": map_entries,
        "Themes": [], "GameModes": mode_entries, "Currencies": currency_entries, "Sprays": spray_entries,
        "SprayLevels": [], "Charms": [], "CharmLevels": [], "PlayerCards": card_entries, "PlayerTitles": title_entries,
        "Contracts": contract_entries, "StorefrontItems": [], "Missions": [], "Seasons": season_entries,
    }
    payload = {
        "Characters": character_entries, "characters": character_entries, "CharacterRoles": character_role_entries, "characterRoles": character_role_entries,
        "Maps": map_entries, "maps": map_entries, "GameModes": mode_entries, "gameModes": mode_entries, "Sprays": spray_entries, "sprays": spray_entries,
        "SprayLevels": [], "sprayLevels": [], "Equips": equip_entries, "equips": equip_entries, "Equippables": equip_entries, "equippables": equip_entries,
        "Skins": skin_entries, "skins": skin_entries, "SkinLevels": skin_level_entries, "skinLevels": skin_level_entries, "Chromas": chroma_entries, "chromas": chroma_entries,
        "Charms": [], "charms": [], "CharmLevels": [], "charmLevels": [], "PlayerCards": card_entries, "playerCards": card_entries,
        "PlayerTitles": title_entries, "playerTitles": title_entries, "Currencies": currency_entries, "currencies": currency_entries,
        "Seasons": [season_content_struct(LOCAL_SEASON_ID, "Local Season")], "seasons": season_entries, "Contracts": contract_entries, "contracts": contract_entries,
        "Themes": [], "themes": [], "Attachments": [], "attachments": [], "Bundles": [], "bundles": [], "StorefrontItems": [], "storefrontItems": [],
        "ContentTypes": content_types, "contentTypes": content_types, "PlayerCardMapping": player_card_mapping, "playerCardMapping": player_card_mapping,
        "PlayerTitleMapping": player_title_mapping, "playerTitleMapping": player_title_mapping, "SprayMapping": spray_mapping, "sprayMapping": spray_mapping,
        "EquippableMapping": equippable_mapping, "equippableMapping": equippable_mapping, "SkinMapping": skin_mapping, "skinMapping": skin_mapping,
        "SkinLevelMapping": skin_level_mapping, "skinLevelMapping": skin_level_mapping, "SkinLevelMappingBySkinID": skin_level_mapping_by_skin_id,
        "skinLevelMappingBySkinID": skin_level_mapping_by_skin_id, "SkinLevelMappingByEquippableAndSkin": skin_level_mapping_by_equippable_skin,
        "skinLevelMappingByEquippableAndSkin": skin_level_mapping_by_equippable_skin, "ChromaMapping": chroma_mapping, "chromaMapping": chroma_mapping,
        "CurrencyMapping": currency_mapping, "currencyMapping": currency_mapping, "SeasonMapping": season_mapping, "seasonMapping": season_mapping,
        "FullContentListing": full_listing_payload, "fullContentListing": full_listing_payload, "FullContentListingDTO": canonical_full_content_dto,
        "fullContentListingDTO": canonical_full_content_dto, "FullListing": full_listing_payload, "fullListing": full_listing_payload,
        "Items": content_listing_bucket(full_listing), "items": content_listing_bucket(full_listing),
    }
    return payload
