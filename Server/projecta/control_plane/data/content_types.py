"""Ares content type IDs and item-type mappings."""

from __future__ import annotations


ARES_CONTENT_TYPES = [
    "EquippableSkin",
    "EquippableSkinLevel",
    "EquippableSkinChroma",
    "EquippableCharm",
    "Character",
    "CharacterRole",
    "Contract",
    "EquippableAttachment",
    "Equippable",
    "Map",
    "Socket",
    "Spray",
    "GameMode",
    "Currency",
    "EquippableCharmLevel",
    "SprayLevel",
    "PlayerCard",
    "PremiumContract",
    "Mission",
    "StorefrontItem",
    "PlayerTitle",
    "Season",
    "ContractChapter",
    "Invalid",
    "Count",
]
ARES_CONTENT_TYPE_INDEX = {name: idx for idx, name in enumerate(ARES_CONTENT_TYPES)}
CLIENT_CONTENT_TYPE_IDS = dict(ARES_CONTENT_TYPE_INDEX)

ITEM_TYPE_CONTENT_TYPE_NAMES = {
    "51c9eb99-3e6b-4658-801f-a5a7fd64bb9d": "Contract",
    "e7c63390-eda7-46e0-bb7a-a6abdacd2433": "EquippableSkin",
    "3ad1b2b2-acdb-4524-852f-954a76ddae0a": "EquippableSkinLevel",
    "ac3c307a-368f-4db8-940d-68914b26d89a": "EquippableSkinChroma",
    "3f296c07-64c3-494c-923b-fe692a4fa1bd": "EquippableCharm",
    "6520634c-bd1e-4fc4-81af-cac5dc723105": "EquippableCharmLevel",
    "01bb38e1-da47-4e6a-9b3d-945fe4655707": "Character",
    "dd3bf334-87f3-40bd-b043-682a57a8dc3a": "Spray",
    "d5f120f8-ff8c-4aac-92ea-f2b5acbe9475": "SprayLevel",
    "bcef87d6-209b-46c6-8b19-fbe40bd95abc": "PlayerCard",
    "de7caa6b-adf7-4588-bbd1-143831e786c6": "PlayerTitle",
}


def content_type_id_for_item_type(item_type_id: str) -> int:
    content_type_name = ITEM_TYPE_CONTENT_TYPE_NAMES.get(str(item_type_id).lower())
    if not content_type_name:
        return CLIENT_CONTENT_TYPE_IDS["Invalid"]
    return CLIENT_CONTENT_TYPE_IDS.get(content_type_name, CLIENT_CONTENT_TYPE_IDS["Invalid"])
