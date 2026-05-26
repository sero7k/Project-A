from __future__ import annotations

from typing import Any, Callable

from ..domain.state_helpers import first_string


def loadout_name_for_equippable(
    equippable_id: str,
    fallback_name: str,
    default_loadout_rows: list[tuple[str, str, str, str, str]],
) -> str:
    for name, equip_id, _skin_id, _skin_level_id, _chroma_id in default_loadout_rows:
        if equip_id.lower() == str(equippable_id).lower():
            return name
    return fallback_name


def normalize_loadout_gun(
    gun: dict[str, Any],
    fallback_name: str,
    default_loadout_rows: list[tuple[str, str, str, str, str]],
) -> dict[str, str] | None:
    equip_id = first_string(gun, "ID", "Id", "iD", "id", "EquippableID", "EquippableId", "equippableID", "equippableId")
    skin_id = first_string(gun, "SkinID", "SkinId", "skinID", "skinId")
    skin_level_id = first_string(gun, "SkinLevelID", "SkinLevelId", "skinLevelID", "skinLevelId")
    chroma_id = first_string(gun, "ChromaID", "ChromaId", "chromaID", "chromaId")
    if not equip_id or not skin_id:
        return None
    return {
        "name": loadout_name_for_equippable(equip_id, fallback_name, default_loadout_rows),
        "equippable_id": equip_id,
        "skin_id": skin_id,
        "skin_level_id": skin_level_id,
        "chroma_id": chroma_id,
    }


def loadout_content_rows(
    game_state: dict[str, Any] | None,
    default_loadout_rows: list[tuple[str, str, str, str, str]],
    allow_unverified_default_loadout: bool,
) -> list[dict[str, str]]:
    rows = []
    if allow_unverified_default_loadout:
        rows.extend(
            {
                "name": name,
                "equippable_id": equip_id,
                "skin_id": skin_id,
                "skin_level_id": skin_level_id,
                "chroma_id": chroma_id,
            }
            for name, equip_id, skin_id, skin_level_id, chroma_id in default_loadout_rows
        )
    if game_state:
        loadouts: list[Any] = []
        if isinstance(game_state.get("player_loadout"), dict):
            loadouts.append(game_state["player_loadout"])
        by_profile = game_state.get("player_loadout_by_profile")
        if isinstance(by_profile, dict):
            loadouts.extend(value for value in by_profile.values() if isinstance(value, dict))
        for loadout in loadouts:
            guns = loadout.get("Guns") or loadout.get("guns") or loadout.get("GunLoadout") or loadout.get("gunLoadout") or []
            for index, gun in enumerate(guns):
                if isinstance(gun, dict):
                    row = normalize_loadout_gun(gun, f"Weapon {index + 1}", default_loadout_rows)
                    if row:
                        rows.append(row)
    deduped: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["equippable_id"], row["skin_id"], row.get("skin_level_id", ""), row.get("chroma_id", ""))
        deduped.setdefault(key, row)
    return list(deduped.values())


def add_gun_aliases(gun: dict[str, Any]) -> dict[str, Any]:
    gun = dict(gun)
    aliases = [
        ("ID", ("Id", "iD", "id")),
        ("SkinID", ("SkinId", "skinID", "skinId")),
        ("SkinLevelID", ("SkinLevelId", "skinLevelID", "skinLevelId")),
        ("ChromaID", ("ChromaId", "chromaID", "chromaId")),
        ("CharmInstanceID", ("CharmInstanceId", "charmInstanceID", "charmInstanceId")),
        ("CharmID", ("CharmId", "charmID", "charmId")),
        ("CharmLevelID", ("CharmLevelId", "charmLevelID", "charmLevelId")),
        ("Attachments", ("attachments",)),
    ]
    for canonical, names in aliases:
        value = gun.get(canonical)
        if value is None:
            for name in names:
                if name in gun:
                    value = gun[name]
                    break
        if value is not None:
            gun.setdefault(canonical, value)
            for name in names:
                gun.setdefault(name, value)
    return gun


def default_loadout_guns(
    default_loadout_rows: list[tuple[str, str, str, str, str]],
    allow_unverified_default_loadout: bool,
) -> list[dict[str, Any]]:
    if not allow_unverified_default_loadout:
        return []
    guns = []
    for name, equip_id, skin_id, skin_level_id, chroma_id in default_loadout_rows:
        guns.append(
            add_gun_aliases(
                {
                    "ID": equip_id,
                    "Name": name,
                    "name": name,
                    "SkinID": skin_id,
                    "SkinLevelID": skin_level_id,
                    "ChromaID": chroma_id,
                    "Attachments": [],
                }
            )
        )
    return guns


def item_id_object(item_id: str) -> dict[str, str]:
    return {"ID": item_id, "Id": item_id, "iD": item_id, "id": item_id}


def normalize_item_id_object(value: Any, default_item_id: str) -> dict[str, str]:
    item_id = default_item_id
    if isinstance(value, dict):
        for key in ("ID", "Id", "iD", "id", "ItemID", "itemID", "Guid", "guid", "UUID", "uuid"):
            raw = value.get(key)
            if isinstance(raw, str) and raw:
                item_id = raw
                break
    return item_id_object(item_id)


def player_loadout_payload(
    loadout: dict[str, Any] | None,
    profile: dict[str, str],
    identity_factory: Callable[[dict[str, str] | None], dict[str, Any]],
    default_loadout_rows: list[tuple[str, str, str, str, str]],
    allow_unverified_default_loadout: bool,
    default_player_card_id: str,
    default_player_title_id: str,
) -> dict[str, Any]:
    payload = dict(loadout) if isinstance(loadout, dict) else {}
    if not payload.get("Subject"):
        payload["Subject"] = profile["subject"]
    if not payload.get("subject"):
        payload["subject"] = profile["subject"]
    if not payload.get("Version"):
        payload["Version"] = int(payload.get("version", 0) or 0)
    if not payload.get("version"):
        payload["version"] = int(payload.get("Version", 0) or 0)
    payload.setdefault("Guns", payload.get("guns", []))
    if not payload.get("Guns") and not payload.get("guns"):
        payload["Guns"] = default_loadout_guns(default_loadout_rows, allow_unverified_default_loadout)
    if isinstance(payload["Guns"], list):
        payload["Guns"] = [add_gun_aliases(gun) if isinstance(gun, dict) else gun for gun in payload["Guns"]]
    payload.setdefault("guns", payload.get("Guns", []))
    if isinstance(payload["guns"], list):
        payload["guns"] = [add_gun_aliases(gun) if isinstance(gun, dict) else gun for gun in payload["guns"]]
    payload["Guns"] = payload["guns"] = payload["Guns"] or payload["guns"]
    payload.setdefault("Sprays", payload.get("sprays", []))
    payload.setdefault("sprays", payload.get("Sprays", []))
    identity = payload.get("Identity") if isinstance(payload.get("Identity"), dict) else payload.get("identity")
    identity = dict(identity) if isinstance(identity, dict) else identity_factory(profile)
    if not identity.get("Subject"):
        identity["Subject"] = profile["subject"]
    identity["subject"] = identity.get("subject") or identity["Subject"]
    if not identity.get("PlayerTitleID"):
        identity["PlayerTitleID"] = default_player_title_id
    identity["playerTitleID"] = identity.get("playerTitleID") or identity["PlayerTitleID"]
    identity["PlayerCardID"] = identity.get("PlayerCardID") or default_player_card_id
    identity["playerCardID"] = identity.get("playerCardID") or identity["PlayerCardID"]
    payload["Identity"] = identity
    payload["identity"] = identity
    player_card = normalize_item_id_object(payload.get("PlayerCard") or payload.get("playerCard"), default_player_card_id)
    player_title = normalize_item_id_object(payload.get("PlayerTitle") or payload.get("playerTitle"), default_player_title_id)
    payload["PlayerCard"] = player_card
    payload["playerCard"] = player_card
    payload["PlayerTitle"] = player_title
    payload["playerTitle"] = player_title
    payload.setdefault("GunLoadout", payload["Guns"])
    payload.setdefault("gunLoadout", payload["guns"])
    payload.setdefault("SprayLoadout", payload["Sprays"])
    payload.setdefault("sprayLoadout", payload["sprays"])
    payload.setdefault("PlayerLoadout", {"Guns": payload["Guns"], "Sprays": payload["Sprays"], "Identity": payload["Identity"]})
    payload.setdefault("playerLoadout", {"guns": payload["guns"], "sprays": payload["sprays"], "identity": payload["identity"]})
    payload.setdefault("Incognito", False)
    payload.setdefault("incognito", False)
    return payload
