#!/usr/bin/env python3
"""Local Riot/RNet probe server for Project A client initialization.

This accepts both HTTP and HTTPS on the same localhost port, logs requests as
JSONL, and returns permissive stub payloads for the Riot Client endpoints the
client references in its string table.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import ssl
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from .accounts import (
        DEFAULT_DATABASE_URL,
        AccountRecord,
        MemoryAccountStore,
        PostgresAccountStore,
        account_from_hint,
        normalize_account_key,
    )
except ImportError:
    from accounts import (
        DEFAULT_DATABASE_URL,
        AccountRecord,
        MemoryAccountStore,
        PostgresAccountStore,
        account_from_hint,
        normalize_account_key,
    )


def blueprint_asset(object_path: str) -> str:
    asset_name = object_path.rsplit("/", 1)[-1]
    return f"BlueprintGeneratedClass'{object_path}.{asset_name}_C'"


ACCOUNT_STORE: MemoryAccountStore | PostgresAccountStore = MemoryAccountStore()


PLAYER_UUID = "11111111-1111-1111-1111-111111111111"
PARTY_ID = "22222222-2222-2222-2222-222222222222"
GAME_NAME = "DevPlayer"
TAG_LINE = "LOCAL"
CHAT_PID = f"{PLAYER_UUID}@pvp.net"
CHAT_RESOURCE = "rnet-probe"
CHAT_FULL_PID = f"{CHAT_PID}/{CHAT_RESOURCE}"
CLIENT_VERSION = "release-0.45-shipping-13-404591"
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
MATCH_ID = "33333333-3333-3333-3333-333333333333"
GAME_POD_ID = "local-gamepod"
DEFAULT_MAP = "/Game/Maps/Poveglia/Range"
DEFAULT_MODE = "/Game/GameModes/ShootingRange/ShootingRangeGameMode.ShootingRangeGameMode_C"
DEFAULT_QUEUE = "custom"
SHOOTING_RANGE_QUEUE = "ShootingRange"
DEFAULT_PROVISIONING_FLOW = "CustomGame"
SHOOTING_RANGE_PROVISIONING_FLOW = "ShootingRange"
PROVISIONING_FLOW_IDS = {
    "ShootingRange": 1,
    "SkillTest": 2,
    "CustomGame": 3,
    "Matchmaking": 4,
    "NewPlayerExperience": 5,
}
DEFAULT_CHARACTER_ID = "eb93336a-449b-9c1b-0a54-a891f7921d69"
DEFAULT_PLAYER_CARD_ID = "8cf33945-4a2a-1da8-02de-a6858a04f07d"
DEFAULT_PLAYER_TITLE_ID = "e59aa87c-4cbf-517a-5983-6e81511be9b7"
DEFAULT_PLAYER_CARD_ASSET = blueprint_asset("/Game/Personalization/PlayerCards/Default/EtherExplosion/PlayerCard_EtherExplosion_PrimaryAsset")
DEFAULT_PLAYER_TITLE_ASSET = blueprint_asset("/Game/Personalization/Titles/PlayerTitle_Default_PrimaryAsset")
DEFAULT_SPRAY_PREROUND_ID = "35138b9a-5d96-4fbd-8e2d-a2440225f93a"
DEFAULT_SPRAY_MIDROUND_ID = "8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a"
DEFAULT_SPRAY_PREROUND_ASSET = blueprint_asset("/Game/Personalization/Sprays/Chicken/Spray_Chicken_PrimaryAsset")
DEFAULT_SPRAY_MIDROUND_ASSET = blueprint_asset("/Game/Personalization/Sprays/Salt/Spray_Salt_PrimaryAsset")
DEFAULT_MAP_ASSET = blueprint_asset("/Game/Maps/Poveglia/Poveglia_PrimaryAsset")
DEFAULT_MODE_ASSET = blueprint_asset("/Game/GameModes/ShootingRange/ShootingRangeGameMode_PrimaryAsset")
LOCAL_CURRENCY_ID = "85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741"
LOCAL_CURRENCY_ASSET = blueprint_asset("/Game/Currencies/Currency_AresPoints_DataAsset")
LOCAL_UPGRADE_TOKEN_ID = "6f0f9a79-3df2-5e16-bbdc-8c38e9c751b1"
LOCAL_UPGRADE_TOKEN_ASSET = blueprint_asset("/Game/Currencies/Currency_UpgradeToken_DataAsset")
LOCAL_RECRUITMENT_TOKEN_ID = "62fc60a0-97c9-5588-85cf-3b2f1e0a0464"
LOCAL_RECRUITMENT_TOKEN_ASSET = blueprint_asset("/Game/Currencies/Currency_RecruitmentToken_DataAsset")
LOCAL_BUNDLE_ID = "77258665-71d1-4623-bc72-44db9bd5b3b3"
LOCAL_ORDER_ID = "local-order-0001"
LOCAL_STORY_CONTRACT_ID = "3365454b-4d9a-4b0e-b3d0-7f8c1f9d7e1a"
LOCAL_CONTRACT_ASSET = blueprint_asset("/Game/Contracts/NPE/Contract_NPE_DataAsset")
DEFAULT_LOCALE = "en_US"
DEFAULT_WEB_LANGUAGE = "en-us"
DEFAULT_REGION = "na"
PLAYER_FEEDBACK_LOCALE = "en_GB"
PLAYER_FEEDBACK_SHARD = "NA1"
PARTY_MUC_NAME = f"ares-party-{PARTY_ID}@conference.pvp.net"
TEAM_MUC_NAME = f"ares-team-{MATCH_ID}@conference.pvp.net"
ALL_MUC_NAME = f"ares-all-{MATCH_ID}@conference.pvp.net"
VOICE_ROOM_ID = f"voice-{PARTY_ID}"
TEAM_VOICE_ID = f"voice-{MATCH_ID}"
ITEM_TYPE_CONTRACT = "51c9eb99-3e6b-4658-801f-a5a7fd64bb9d"
ITEM_TYPE_SKIN = "e7c63390-eda7-46e0-bb7a-a6abdacd2433"
ITEM_TYPE_SKIN_LEVEL = "3ad1b2b2-acdb-4524-852f-954a76ddae0a"
ITEM_TYPE_SKIN_CHROMA = "ac3c307a-368f-4db8-940d-68914b26d89a"
ITEM_TYPE_CHARM = "3f296c07-64c3-494c-923b-fe692a4fa1bd"
ITEM_TYPE_CHARM_LEVEL = "6520634c-bd1e-4fc4-81af-cac5dc723105"
ITEM_TYPE_CHARACTER = "01bb38e1-da47-4e6a-9b3d-945fe4655707"
ITEM_TYPE_SPRAY = "dd3bf334-87f3-40bd-b043-682a57a8dc3a"
ITEM_TYPE_SPRAY_LEVEL = "d5f120f8-ff8c-4aac-92ea-f2b5acbe9475"
ITEM_TYPE_PLAYER_CARD = "bcef87d6-209b-46c6-8b19-fbe40bd95abc"
ITEM_TYPE_PLAYER_TITLE = "de7caa6b-adf7-4588-bbd1-143831e786c6"

CHARACTER_CONTENT = [
    ("Phoenix", "Phoenix", "eb93336a-449b-9c1b-0a54-a891f7921d69"),
    ("Jett", "Wushu", "add6443a-41bd-e414-f6ad-e58d267f4e95"),
    ("Viper", "Pandemic", "707eab51-4836-f488-046a-cda6bf494859"),
    ("Breach", "Breach", "5f8d3a7f-467b-97f3-062c-13acf203c006"),
    ("Sova", "Hunter", "320b2a48-4d9b-a075-30f1-1f93a9b638fa"),
    ("Sage", "Thorne", "569fdd95-4d10-43ab-ca70-79becc718b46"),
    ("Cypher", "Gumshoe", "117ed9e3-49f3-6512-3ccf-0cada7e3823b"),
    ("Omen", "Wraith", "8e253930-4c05-31dd-1b6c-968525494517"),
    ("Brimstone", "Sarge", "9f0d8ba9-4140-b941-57d3-a7ad57c6b417"),
]


DEFAULT_LOADOUT_ROWS = [
    ("Odin", "63e6c2b6-4a8e-869c-3d4c-e38355226584", "f454efd1-49cb-372f-7096-d394df615308", "d91fb318-4e40-b4c9-8c0b-bb9da28bac55", "2f93861d-4b2f-2175-af0c-3ba0c736e257"),
    ("Ares", "55d8a0f4-4274-ca67-fe2c-06ab45efdf58", "5305d9c4-4f46-fbf4-9e9a-dea772c263b5", "0f5f60f4-4c94-e4b2-ceab-e2b4e8b41784", "b33de820-4061-8b85-31ce-808f1a2c58f5"),
    ("Vandal", "9c82e19d-4575-0200-1a81-3eacf00cf872", "27f21d97-4c4b-bd1c-1f08-31830ab0be84", "1ab72e66-4da3-33a0-164f-908113e075a4", "19629ae1-4996-ae98-7742-24a240d41f99"),
    ("Bulldog", "ae3de142-4d85-2547-dd26-4e90bed35cf7", "724a7f42-4315-eccf-0e76-77bdd3ec2e09", "c8e6ac70-48ef-9d96-d964-a88e8890b885", "bf35f404-4a14-6953-ced2-5bafd21639a0"),
    ("Phantom", "ee8e8d15-496b-07ac-e5f6-8fae5d4c7b1a", "337cb216-4a6e-d85d-88c2-f29ab317784c", "871e73ed-452d-eb5a-3d6b-1d87060f35ce", "52221ba2-4e4c-ec76-8c81-3483506d5242"),
    ("Judge", "ec845bf4-4f79-ddda-a3da-0db3774b2794", "acd26127-48ff-8b9e-7ba6-b989af8a4b24", "6942d8d1-4370-a144-2140-22a6d2be2697", "b71ae8d6-44bb-aa4c-0d2a-dc9ed9e66410"),
    ("Bucky", "910be174-449b-c412-ab22-d0873436b21b", "70c97fb2-4d79-d4bb-5173-a1888cd4bfd9", "2f5078c7-4381-492d-cc00-9f96966ba1ec", "3d8ffcfe-4786-0180-42d7-e1be18dd1cab"),
    ("Frenzy", "44d4e95c-4157-0037-81b2-17841bf2e8e3", "f06657f3-48b6-6314-7235-a9a2749df5b9", "80fabd74-4438-a2dd-0c39-42ab449f9ec6", "dc99ed5a-4d75-87a0-c921-75963ea3c1e1"),
    ("Classic", "29a0cfab-485b-f5d5-779a-b59f85e204a8", "24aee897-4cdc-b0fd-e596-1ba90fa6d1b2", "51cbccad-487c-50ed-2ffd-c88b4240fab3", "4b2d5b4f-4955-4208-286c-abadec250cdd"),
    ("Ghost", "1baa85b4-4c70-1284-64bb-6481dfc3bb4e", "1c63b43b-43c4-04e4-01c9-7aa1bffa5ac1", "0a7e786c-444e-6a80-8bda-e2b714d68332", "947a28b6-4e0f-61fb-e795-bc9a5e7b7129"),
    ("Sheriff", "e336c6b8-418d-9340-d77f-7a9e4cfe0702", "1ef6ba68-4dbe-30c7-6bc8-93a6c6f13f04", "feaf05a1-492f-d154-a9f5-0eb1fe9a603e", "5a59bd61-48a9-af61-c00f-4aa21deca9a8"),
    ("Shorty", "42da8ccc-40d5-affc-beec-15aa47b42eda", "48ad078a-4dae-2b85-a945-f4b6d1efecbb", "a7f92a1c-4465-5ea3-7745-bd876117f4a7", "95608504-4c8b-1408-1612-0f8200421c49"),
    ("Operator", "a03b24d3-4319-996d-0f8c-94bbfba1dfc7", "d1f2920f-469a-3431-ad96-96afbd0017f2", "88cba358-4f4d-4d0e-69fc-b48f4c65cb2d", "4914f50d-49f9-6424-ca80-9486c45a138d"),
    ("Guardian", "4ade7faa-4cf1-8376-95ef-39884480959b", "3bf1e8e0-47e8-f27a-6054-929575f41a54", "414d888a-41ce-fcf0-e545-c49018ec9cf4", "0f934388-418a-a9e7-42a7-21b27402e46c"),
    ("Marshal", "c4883e50-4494-202c-3ec3-6b8a9284f00b", "fd44b2d5-49ee-77ab-fa56-588f3ac0c268", "f0389390-49eb-a43e-27fa-fc9f9f8aa9de", "1afec971-4170-f29b-1c94-07a0eff270ab"),
    ("Spectre", "462080d1-4035-2937-7c09-27aa2a5c27a7", "f01d1307-4299-42f5-2c5e-7dab7e69ab19", "1dc45e18-4a07-c85f-0020-6da4db1486ce", "a9aaccca-4cdc-02ea-1d7e-89bbacecc0e2"),
    ("Stinger", "f7e1b454-4ad4-1063-ec0a-159e56b58941", "940fb417-4a9c-3004-41f5-3e8f1f4178b2", "471fc2a5-47a7-5b12-2895-0899117d2f57", "31bb2115-4c62-d37c-43c4-11b8fee7f212"),
    ("Melee", "2f59173c-4bed-b6c3-2191-dea9b58be9c7", "12cc9ed2-4430-d2fe-3064-f7a19b1ba7c7", "854938f3-4532-b300-d9a2-379d987d7469", "cac83e5c-47a1-3519-5420-1db1fdbc4892"),
]


DEFAULT_LOADOUT_ASSET_PATHS = {
    "Odin": {
        "equippable": "/Game/Equippables/Guns/HvyMachineGuns/HMG/HeavyMachineGunPrimaryAsset",
        "skin": "/Game/Equippables/Guns/HvyMachineGuns/HMG/Standard/HeavyMachineGun_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/HvyMachineGuns/HMG/Standard/HeavyMachineGun_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/HvyMachineGuns/HMG/Standard/Chromas/Standard/HeavyMachineGun_Standard_Standard_PrimaryAsset",
    },
    "Ares": {
        "equippable": "/Game/Equippables/Guns/HvyMachineGuns/LMG/LightMachineGunPrimaryAsset",
        "skin": "/Game/Equippables/Guns/HvyMachineGuns/LMG/Standard/LightMachineGun_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/HvyMachineGuns/LMG/Standard/LightMachineGun_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/HvyMachineGuns/LMG/Standard/Chromas/Standard/LightMachineGun_Standard_Standard_PrimaryAsset",
    },
    "Vandal": {
        "equippable": "/Game/Equippables/Guns/Rifles/AK/AKPrimaryAsset",
        "skin": "/Game/Equippables/Guns/Rifles/AK/Standard/AssaultRifle_AK_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/Rifles/AK/Standard/AssaultRifle_AK_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/Rifles/AK/Standard/Chromas/Standard/AssaultRifle_AK_Standard_Standard_PrimaryAsset",
    },
    "Bulldog": {
        "equippable": "/Game/Equippables/Guns/Rifles/Burst/AssaultRifle_BurstPrimaryAsset",
        "skin": "/Game/Equippables/Guns/Rifles/Burst/Standard/AssaultRifle_Burst_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/Rifles/Burst/Standard/AssaultRifle_Burst_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/Rifles/Burst/Standard/Chromas/Standard/AssaultRifle_Burst_Standard_Standard_PrimaryAsset",
    },
    "Phantom": {
        "equippable": "/Game/Equippables/Guns/Rifles/Carbine/AssaultRifle_ACRPrimaryAsset",
        "skin": "/Game/Equippables/Guns/Rifles/Carbine/Standard/AssaultRifle_ACR_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/Rifles/Carbine/Standard/AssaultRifle_ACR_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/Rifles/Carbine/Standard/Chromas/Standard/AssaultRifle_ACR_Standard_Standard_PrimaryAsset",
    },
    "Judge": {
        "equippable": "/Game/Equippables/Guns/Shotguns/AutoShotgun/AutomaticShotgunPrimaryAsset",
        "skin": "/Game/Equippables/Guns/Shotguns/AutoShotgun/Standard/AutomaticShotgun_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/Shotguns/AutoShotgun/Standard/AutomaticShotgun_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/Shotguns/AutoShotgun/Standard/Chromas/Standard/AutomaticShotgun_Standard_Standard_PrimaryAsset",
    },
    "Bucky": {
        "equippable": "/Game/Equippables/Guns/Shotguns/PumpShotgun/PumpShotgunPrimaryAsset",
        "skin": "/Game/Equippables/Guns/Shotguns/PumpShotgun/Standard/PumpShotgun_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/Shotguns/PumpShotgun/Standard/PumpShotgun_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/Shotguns/PumpShotgun/Standard/Chromas/Standard/PumpShotgun_Standard_Standard_PrimaryAsset",
    },
    "Frenzy": {
        "equippable": "/Game/Equippables/Guns/Sidearms/AutoPistol/AutomaticPistolPrimaryAsset",
        "skin": "/Game/Equippables/Guns/Sidearms/AutoPistol/Standard/AutomaticPistol_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/Sidearms/AutoPistol/Standard/AutomaticPistol_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/Sidearms/AutoPistol/Standard/Chromas/Standard/AutomaticPistol_Standard_Standard_PrimaryAsset",
    },
    "Classic": {
        "equippable": "/Game/Equippables/Guns/Sidearms/BasePistol/BasePistolPrimaryAsset",
        "skin": "/Game/Equippables/Guns/Sidearms/BasePistol/Standard/BasePistol_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/Sidearms/BasePistol/Standard/BasePistol_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/Sidearms/BasePistol/Standard/Chromas/Standard/BasePistol_Standard_Standard_PrimaryAsset",
    },
    "Ghost": {
        "equippable": "/Game/Equippables/Guns/Sidearms/Luger/LugerPistolPrimaryAsset",
        "skin": "/Game/Equippables/Guns/Sidearms/Luger/Standard/LugerPistol_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/Sidearms/Luger/Standard/LugerPistol_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/Sidearms/Luger/Standard/Chromas/Standard/LugerPistol_Standard_Standard_PrimaryAsset",
    },
    "Sheriff": {
        "equippable": "/Game/Equippables/Guns/Sidearms/Revolver/RevolverPistolPrimaryAsset",
        "skin": "/Game/Equippables/Guns/Sidearms/Revolver/Standard/RevolverPistol_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/Sidearms/Revolver/Standard/RevolverPistol_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/Sidearms/Revolver/Standard/Chromas/Standard/RevolverPistol_Standard_Standard_PrimaryAsset",
    },
    "Shorty": {
        "equippable": "/Game/Equippables/Guns/Sidearms/Slim/SawedOffShotgunPrimaryAsset",
        "skin": "/Game/Equippables/Guns/Sidearms/Slim/Standard/SawedOffShotgun_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/Sidearms/Slim/Standard/SawedOffShotgun_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/Sidearms/Slim/Standard/Chromas/Standard/SawedOffShotgun_Standard_Standard_PrimaryAsset",
    },
    "Operator": {
        "equippable": "/Game/Equippables/Guns/SniperRifles/Boltsniper/BoltSniperPrimaryAsset",
        "skin": "/Game/Equippables/Guns/SniperRifles/Boltsniper/Standard/BoltSniper_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/SniperRifles/Boltsniper/Standard/BoltSniper_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/SniperRifles/Boltsniper/Standard/Chromas/Standard/BoltSniper_Standard_Standard_PrimaryAsset",
    },
    "Guardian": {
        "equippable": "/Game/Equippables/Guns/SniperRifles/DMR/DMRPrimaryAsset",
        "skin": "/Game/Equippables/Guns/SniperRifles/DMR/Standard/DMR_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/SniperRifles/DMR/Standard/DMR_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/SniperRifles/DMR/Standard/Chromas/Standard/DMR_Standard_Standard_PrimaryAsset",
    },
    "Marshal": {
        "equippable": "/Game/Equippables/Guns/SniperRifles/Leversniper/LeverSniperPrimaryAsset",
        "skin": "/Game/Equippables/Guns/SniperRifles/Leversniper/Standard/LeverSniperRifle_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/SniperRifles/Leversniper/Standard/LeverSniperRifle_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/SniperRifles/Leversniper/Standard/Chromas/Standard/LeverSniperRifle_Standard_Standard_PrimaryAsset",
    },
    "Spectre": {
        "equippable": "/Game/Equippables/Guns/SubMachineGuns/Vector/VectorPrimaryAsset",
        "skin": "/Game/Equippables/Guns/SubMachineGuns/Vector/Standard/Vector_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/SubMachineGuns/Vector/Standard/Vector_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/SubMachineGuns/Vector/Standard/Chromas/Standard/Vector_Standard_Standard_PrimaryAsset",
    },
    "Stinger": {
        "equippable": "/Game/Equippables/Guns/SubMachineGuns/MP5/MP5PrimaryAsset",
        "skin": "/Game/Equippables/Guns/SubMachineGuns/MP5/Standard/SubMachineGun_MP5_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Guns/SubMachineGuns/MP5/Standard/SubMachineGun_MP5_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Guns/SubMachineGuns/MP5/Standard/Chromas/Standard/SubMachineGun_MP5_Standard_Standard_PrimaryAsset",
    },
    "Melee": {
        "equippable": "/Game/Equippables/Melee/Melee_PrimaryAsset",
        "skin": "/Game/Equippables/Melee/Standard/Melee_Base_Standard_PrimaryAsset",
        "level": "/Game/Equippables/Melee/Standard/Melee_Base_Standard_Lv1_PrimaryAsset",
        "chroma": "/Game/Equippables/Melee/Standard/Chromas/Standard/Melee_Base_Standard_Standard_PrimaryAsset",
    },
}


LOCAL_PROFILES = {
    "developer": {
        "key": "developer",
        "subject": PLAYER_UUID,
        "game_name": GAME_NAME,
        "tag_line": TAG_LINE,
    },
    "developer2": {
        "key": "developer2",
        "subject": "55555555-5555-5555-5555-555555555555",
        "game_name": "DevPlayer2",
        "tag_line": "LOCAL2",
    },
}
PROFILE_ALIASES = {
    "developer": "developer",
    "developer1": "developer",
    "dev1": "developer",
    "player1": "developer",
    "p1": "developer",
    "developer2": "developer2",
    "dev2": "developer2",
    "player2": "developer2",
    "p2": "developer2",
}


def canonical_profile_key(key: str | None) -> str:
    raw = normalize_account_key(key)
    raw = PROFILE_ALIASES.get(raw, raw)
    return normalize_account_key(raw)


def configure_account_store(
    database_url: str | None = None,
    *,
    allow_memory_db: bool = False,
    migrate: bool = True,
) -> MemoryAccountStore | PostgresAccountStore:
    global ACCOUNT_STORE
    if allow_memory_db:
        ACCOUNT_STORE = MemoryAccountStore()
    else:
        ACCOUNT_STORE = PostgresAccountStore(database_url or DEFAULT_DATABASE_URL)
    if migrate:
        ACCOUNT_STORE.migrate()
    return ACCOUNT_STORE


def profile_from_account(account: AccountRecord) -> dict[str, str]:
    profile = {
        "key": account.account_key,
        "subject": account.subject,
        "game_name": account.game_name,
        "tag_line": account.tag_line,
    }
    profile["chat_pid"] = f"{profile['subject']}@pvp.net"
    profile["chat_full_pid"] = f"{profile['chat_pid']}/{CHAT_RESOURCE}"
    profile["display_name"] = f"{profile['game_name']}#{profile['tag_line']}"
    return profile


def profile_by_key(key: str | None) -> dict[str, str]:
    canonical = canonical_profile_key(key)
    account = ACCOUNT_STORE.get_or_create_account(canonical, LOCAL_PROFILES.get(canonical))
    return profile_from_account(account)


def profile_by_subject(subject: str, fallback_index: int = 0) -> dict[str, str]:
    subject = str(subject or "").strip()
    account = ACCOUNT_STORE.get_account_by_subject(subject)
    if account:
        return profile_from_account(account)
    for key, hint in LOCAL_PROFILES.items():
        if hint["subject"].lower() == subject.lower():
            return profile_by_key(key)
    try:
        suffix = str(uuid.UUID(subject)).split("-")[0][:4].upper()
    except ValueError:
        suffix = hashlib.sha1(subject.encode("utf-8", errors="ignore")).hexdigest()[:4].upper()
    if not suffix:
        suffix = str(fallback_index + 1)
    account = account_from_hint(
        f"subject-{suffix.lower()}",
        {"subject": subject, "game_name": f"DevPlayer{suffix}", "tag_line": f"LOCAL{suffix}"},
    )
    return profile_from_account(account)


def default_profile() -> dict[str, str]:
    return profile_by_key("developer")


def profiles_from_game_state(game_state: dict[str, Any] | None = None) -> list[dict[str, str]]:
    keys = []
    if game_state:
        raw_keys = game_state.get("active_profile_keys")
        if isinstance(raw_keys, list):
            keys = [str(key) for key in raw_keys]
    if not keys:
        keys = ["developer"]
    canonical_keys = []
    for key in keys:
        canonical = canonical_profile_key(key)
        if canonical not in canonical_keys:
            canonical_keys.append(canonical)
    profiles = [profile_by_key(key) for key in canonical_keys]
    return profiles or [default_profile()]


def party_muc_name(party_id: str) -> str:
    return f"ares-party-{party_id}@conference.pvp.net"


def party_voice_room_id(party_id: str) -> str:
    return f"voice-{party_id}"


def party_id_from_muc(cid: str | None) -> str | None:
    if not cid:
        return None
    match = re.match(r"^ares-party-([0-9a-fA-F-]{36})@conference\.pvp\.net$", str(cid))
    return match.group(1).lower() if match else None


def party_id_from_route(route_path: str) -> str | None:
    match = re.match(r"^/parties/v1/parties/([^/]+)", route_path)
    return match.group(1) if match else None


def party_id_for_profile(profile: dict[str, str] | None = None) -> str:
    profile = profile or default_profile()
    return ACCOUNT_STORE.current_party_id(profile["key"])


def party_profiles(
    game_state: dict[str, Any] | None = None,
    party_id: str | None = None,
    profile: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    profile = profile or default_profile()
    party_id = party_id or party_id_for_profile(profile)
    members = [profile_from_account(account) for account in ACCOUNT_STORE.party_members(party_id)]
    if not any(member["subject"].lower() == profile["subject"].lower() for member in members):
        if party_id_for_profile(profile) == party_id:
            members.insert(0, profile)
    if not members and party_id_for_profile(profile) == party_id:
        return [profile]
    return members


def profiles_with_current_first(current: dict[str, str], game_state: dict[str, Any] | None = None) -> list[dict[str, str]]:
    profiles = [current]
    profiles.extend(profile for profile in profiles_from_game_state(game_state) if profile["subject"] != current["subject"])
    return profiles


def social_roster_profiles(game_state: dict[str, Any] | None = None) -> list[dict[str, str]]:
    profiles = profiles_from_game_state(game_state)
    for account in ACCOUNT_STORE.known_accounts():
        profile = profile_from_account(account)
        if all(existing["subject"] != profile["subject"] for existing in profiles):
            profiles.append(profile)
    return profiles


def profile_replacements(profile: dict[str, str]) -> dict[str, str]:
    return {
        f"{GAME_NAME}#{TAG_LINE}": profile["display_name"],
        CHAT_FULL_PID: profile["chat_full_pid"],
        CHAT_PID: profile["chat_pid"],
        PLAYER_UUID: profile["subject"],
        GAME_NAME: profile["game_name"],
        TAG_LINE: profile["tag_line"],
    }


def localize_payload(value: Any, profile: dict[str, str]) -> Any:
    if profile.get("key") == "developer":
        return value
    replacements = profile_replacements(profile)
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [localize_payload(item, profile) for item in value]
    if isinstance(value, dict):
        return {key: localize_payload(item, profile) for key, item in value.items()}
    return value
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


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())


def initial_game_state(game_host: str, game_port: int, phase: str) -> dict[str, Any]:
    state = {
        "phase": phase,
        "party_state": "DEFAULT" if phase == "menus" else "CUSTOM_GAME_SETUP",
        "party_version": 1,
        "match_version": 1,
        "map": DEFAULT_MAP,
        "mode": DEFAULT_MODE,
        "queue": DEFAULT_QUEUE,
        "provisioning_flow": DEFAULT_PROVISIONING_FLOW,
        "character_id": "",
        "character_selection_state": "",
        "game_host": game_host,
        "game_port": game_port,
        "active_profile_keys": [],
        "session_by_profile": {},
        "joined_chat_rooms": [],
        "joined_chat_rooms_by_subject": {},
    }
    if phase == "practice":
        state.update(
            {
                "phase": "core",
                "party_state": "SOLO_EXPERIENCE_STARTING",
                "queue": SHOOTING_RANGE_QUEUE,
                "provisioning_flow": SHOOTING_RANGE_PROVISIONING_FLOW,
                "active_profile_keys": [],
                "character_id": DEFAULT_CHARACTER_ID,
                "character_selection_state": "selected",
                "character_id_by_subject": {PLAYER_UUID: DEFAULT_CHARACTER_ID},
                "character_selection_state_by_subject": {PLAYER_UUID: "selected"},
                "solo_experience_type": SHOOTING_RANGE_PROVISIONING_FLOW,
                "practice_seed": True,
            }
        )
    return state


def loop_state(game_state: dict[str, Any] | None = None) -> str:
    if not game_state:
        return "MENUS"
    if game_state.get("phase") == "pregame":
        return "PREGAME"
    if game_state.get("phase") == "core":
        return "INGAME"
    return "MENUS"


def active_party_state(game_state: dict[str, Any] | None = None) -> str:
    if not game_state:
        return "DEFAULT"
    if game_state.get("phase") == "pregame":
        explicit_state = str(game_state.get("party_state") or "")
        if explicit_state == "SOLO_EXPERIENCE_STARTING":
            return explicit_state
        return "CUSTOM_GAME_STARTING"
    if game_state.get("phase") == "core":
        explicit_state = str(game_state.get("party_state") or "")
        if explicit_state in {"SOLO_EXPERIENCE_STARTING", "MATCHMADE_GAME_STARTING"}:
            return explicit_state
        return "MATCHMADE_GAME_STARTING"
    return str(game_state.get("party_state") or "DEFAULT")


def active_match_id(game_state: dict[str, Any] | None = None) -> str:
    if is_solo_local_travel_pending(game_state):
        return ""
    if game_state and game_state.get("phase") in {"pregame", "core"}:
        return MATCH_ID
    return ""


def custom_team_for_profile(game_state: dict[str, Any] | None, profile: dict[str, str]) -> str:
    team_by_subject = (game_state or {}).get("custom_team_by_subject")
    if isinstance(team_by_subject, dict):
        value = team_by_subject.get(profile["subject"]) or team_by_subject.get(profile["key"])
        if isinstance(value, str) and value:
            return normalize_custom_team(value)
    return "TeamOne"


def normalize_custom_team(team: str | None) -> str:
    normalized = (team or "").strip()
    aliases = {
        "teamone": "TeamOne",
        "one": "TeamOne",
        "blue": "TeamOne",
        "teamtwo": "TeamTwo",
        "two": "TeamTwo",
        "red": "TeamTwo",
        "teamspectate": "TeamSpectate",
        "spectate": "TeamSpectate",
        "spectator": "TeamSpectate",
    }
    if normalized in {"TeamOne", "TeamTwo", "TeamSpectate"}:
        return normalized
    return aliases.get(normalized.lower(), "TeamOne")


def team_id_for_custom_team(team: str) -> str:
    if team == "TeamTwo":
        return "Red"
    if team == "TeamSpectate":
        return "Spectate"
    return "Blue"


def set_custom_team_for_subject(game_state: dict[str, Any], subject: str, team: str) -> None:
    team_by_subject = game_state.setdefault("custom_team_by_subject", {})
    if isinstance(team_by_subject, dict) and subject:
        team_by_subject[subject] = normalize_custom_team(team)


def subject_from_team_request(body: dict[str, Any], fallback: str) -> str:
    for key in (
        "playerToPutOnTeam",
        "PlayerToPutOnTeam",
        "Subject",
        "subject",
        "Puuid",
        "puuid",
        "Player",
        "player",
        "PlayerID",
        "PlayerId",
        "playerID",
        "playerId",
    ):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            nested = subject_from_team_request(value, "")
            if nested:
                return nested
    return fallback


def active_provisioning_flow(game_state: dict[str, Any] | None = None) -> str:
    value = (game_state or {}).get("provisioning_flow")
    return value if isinstance(value, str) and value else DEFAULT_PROVISIONING_FLOW


def character_for_profile(game_state: dict[str, Any], profile: dict[str, str], default: str = "") -> str:
    by_subject = game_state.get("character_id_by_subject")
    if isinstance(by_subject, dict):
        value = by_subject.get(profile["subject"])
        if isinstance(value, str) and value:
            return value
    value = game_state.get("character_id")
    if isinstance(value, str) and value:
        return value
    return default


def character_state_for_profile(game_state: dict[str, Any], profile: dict[str, str]) -> str:
    by_subject = game_state.get("character_selection_state_by_subject")
    if isinstance(by_subject, dict):
        value = by_subject.get(profile["subject"])
        if isinstance(value, str) and value:
            return value
    value = game_state.get("character_selection_state")
    return value if isinstance(value, str) else ""


def set_character_for_profile(game_state: dict[str, Any], profile: dict[str, str], character_id: str, state: str) -> None:
    character_by_subject = game_state.setdefault("character_id_by_subject", {})
    state_by_subject = game_state.setdefault("character_selection_state_by_subject", {})
    if isinstance(character_by_subject, dict):
        character_by_subject[profile["subject"]] = character_id
    if isinstance(state_by_subject, dict):
        state_by_subject[profile["subject"]] = state
    game_state["character_id"] = character_id
    game_state["character_selection_state"] = state


def ensure_character_selections(
    game_state: dict[str, Any],
    state: str,
    profiles: list[dict[str, str]] | None = None,
) -> None:
    for profile in profiles or profiles_from_game_state(game_state):
        character_id = character_for_profile(game_state, profile, DEFAULT_CHARACTER_ID)
        set_character_for_profile(game_state, profile, character_id, state)


def should_auto_start_after_lock(game_state: dict[str, Any]) -> bool:
    flow = active_provisioning_flow(game_state)
    queue = str(game_state.get("queue") or "")
    solo_type = str(game_state.get("solo_experience_type") or "")
    return flow == SHOOTING_RANGE_PROVISIONING_FLOW or queue == SHOOTING_RANGE_QUEUE or solo_type == SHOOTING_RANGE_PROVISIONING_FLOW


def is_solo_local_experience(game_state: dict[str, Any] | None) -> bool:
    if not game_state:
        return False
    flow = active_provisioning_flow(game_state)
    queue = str(game_state.get("queue") or "")
    solo_type = str(game_state.get("solo_experience_type") or "")
    return (
        str(game_state.get("party_state") or "") == "SOLO_EXPERIENCE_STARTING"
        or flow in {SHOOTING_RANGE_PROVISIONING_FLOW, "NewPlayerExperience"}
        or queue == SHOOTING_RANGE_QUEUE
        or solo_type in {SHOOTING_RANGE_PROVISIONING_FLOW, "NewPlayerExperience"}
    )


def is_solo_local_travel_pending(game_state: dict[str, Any] | None) -> bool:
    return bool(
        game_state
        and game_state.get("phase") == "pregame"
        and game_state.get("pregame_state") == "provisioned"
        and is_solo_local_experience(game_state)
    )


def provisioning_flow_id(flow: str | None) -> int:
    return PROVISIONING_FLOW_IDS.get(str(flow or ""), 0)


def update_state_from_json(game_state: dict[str, Any], body: dict[str, Any]) -> None:
    if not isinstance(body, dict):
        return
    settings = body.get("Settings") if isinstance(body.get("Settings"), dict) else body
    for source_key, state_key in [
        ("Map", "map"),
        ("map", "map"),
        ("MapID", "map"),
        ("mapID", "map"),
        ("mapId", "map"),
        ("Mode", "mode"),
        ("mode", "mode"),
        ("ModeID", "mode"),
        ("modeID", "mode"),
        ("modeId", "mode"),
        ("QueueID", "queue"),
        ("queueID", "queue"),
        ("queueId", "queue"),
        ("queue", "queue"),
        ("ProvisioningFlow", "provisioning_flow"),
        ("provisioningFlow", "provisioning_flow"),
        ("ProvisioningFlowID", "provisioning_flow"),
        ("provisioningFlowID", "provisioning_flow"),
        ("ProvisioningFlowId", "provisioning_flow"),
        ("provisioningFlowId", "provisioning_flow"),
    ]:
        value = settings.get(source_key) if isinstance(settings, dict) else None
        if isinstance(value, str) and value:
            game_state[state_key] = value


def configure_solo_experience(game_state: dict[str, Any], body: dict[str, Any]) -> None:
    update_state_from_json(game_state, body)
    game_type = ""
    if isinstance(body, dict):
        game_type = first_string(
            body,
            "gameType",
            "GameType",
            "type",
            "Type",
            "soloExperienceType",
            "SoloExperienceType",
            "SoloExperience",
            "soloExperience",
            "ExperienceType",
            "experienceType",
            "ProvisioningFlow",
            "provisioningFlow",
            "ProvisioningFlowID",
            "provisioningFlowID",
            "ProvisioningFlowId",
            "provisioningFlowId",
        )
    normalized = game_type.replace("_", "").replace("-", "").replace(" ", "").lower()
    if not game_type or normalized in {"shootingrange", "range"}:
        game_type = SHOOTING_RANGE_PROVISIONING_FLOW
        game_state["map"] = DEFAULT_MAP
        game_state["mode"] = DEFAULT_MODE
        game_state["queue"] = SHOOTING_RANGE_QUEUE
        game_state["provisioning_flow"] = SHOOTING_RANGE_PROVISIONING_FLOW
    elif normalized in {"newplayerexperience", "npe"}:
        game_type = "NewPlayerExperience"
        game_state["map"] = DEFAULT_MAP
        game_state["mode"] = DEFAULT_MODE
        game_state["queue"] = SHOOTING_RANGE_QUEUE
        game_state["provisioning_flow"] = game_type
    else:
        game_state["provisioning_flow"] = game_type
    game_state["solo_experience_type"] = game_type


def first_string(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def normalize_loadout_gun(gun: dict[str, Any], fallback_name: str = "Local Weapon") -> dict[str, str] | None:
    equip_id = first_string(gun, "ID", "Id", "iD", "id", "EquippableID", "EquippableId", "equippableID", "equippableId")
    skin_id = first_string(gun, "SkinID", "SkinId", "skinID", "skinId")
    skin_level_id = first_string(gun, "SkinLevelID", "SkinLevelId", "skinLevelID", "skinLevelId")
    chroma_id = first_string(gun, "ChromaID", "ChromaId", "chromaID", "chromaId")
    if not equip_id or not skin_id:
        return None
    return {
        "name": fallback_name,
        "equippable_id": equip_id,
        "skin_id": skin_id,
        "skin_level_id": skin_level_id,
        "chroma_id": chroma_id,
    }


def loadout_content_rows(game_state: dict[str, Any] | None = None) -> list[dict[str, str]]:
    rows = [
        {
            "name": name,
            "equippable_id": equip_id,
            "skin_id": skin_id,
            "skin_level_id": skin_level_id,
            "chroma_id": chroma_id,
        }
        for name, equip_id, skin_id, skin_level_id, chroma_id in DEFAULT_LOADOUT_ROWS
    ]
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
                    row = normalize_loadout_gun(gun, f"Local Weapon {index + 1}")
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


def default_loadout_guns() -> list[dict[str, Any]]:
    guns = []
    for name, equip_id, skin_id, skin_level_id, chroma_id in DEFAULT_LOADOUT_ROWS:
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


def userinfo_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "sub": profile["subject"],
        "acct": {"game_name": profile["game_name"], "tag_line": profile["tag_line"]},
        "country": "USA",
    }


def display_name_players_payload(profiles: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    profiles = profiles or [default_profile()]
    return [
        {
            "Subject": profile["subject"],
            "Name": profile["display_name"],
            "name": profile["display_name"],
            "GameName": profile["game_name"],
            "TagLine": profile["tag_line"],
            "GameTag": profile["tag_line"],
            "gameTag": profile["tag_line"],
            "game_tag": profile["tag_line"],
            "DisplayName": profile["display_name"],
            "display_name": profile["display_name"],
            "subject": profile["subject"],
            "gameName": profile["game_name"],
            "game_name": profile["game_name"],
            "tagLine": profile["tag_line"],
            "tag_line": profile["tag_line"],
            "displayName": profile["display_name"],
        }
        for profile in profiles
    ]


def display_name_payload(profiles: list[dict[str, str]] | None = None) -> dict[str, Any]:
    players = display_name_players_payload(profiles)
    first = players[0]
    return {
        "Subject": first["Subject"],
        "GameName": first["GameName"],
        "TagLine": first["TagLine"],
        "GameTag": first["GameTag"],
        "DisplayName": first["DisplayName"],
        "gameName": first["gameName"],
        "tagLine": first["tagLine"],
        "displayName": first["displayName"],
        "Player": first,
        "Name": first,
        "Names": players,
        "names": players,
        "Players": players,
        "players": players,
    }


def presence_private_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    current_party_id = party_id_for_profile(profile)
    profiles = party_profiles(game_state, current_party_id, profile)
    state = active_party_state(game_state)
    current_loop_state = loop_state(game_state)
    custom_team = custom_team_for_profile(game_state, profile)
    team_id = team_id_for_custom_team(custom_team)
    provisioning_flow = active_provisioning_flow(game_state)
    provisioning_flow_value = provisioning_flow_id(provisioning_flow) if state != "DEFAULT" else 0
    owner_subject = profiles[0]["subject"] if profiles else profile["subject"]
    return {
        "isValid": True,
        "sessionLoopState": current_loop_state,
        "partyOwnerSessionLoopState": current_loop_state,
        "customGameName": "",
        "customGameTeam": custom_team if state != "DEFAULT" else "",
        "partyOwnerMatchMap": (game_state or {}).get("map", ""),
        "partyOwnerMatchCurrentTeam": team_id if state != "DEFAULT" else "",
        "partyOwnerMatchScoreAllyTeam": 0,
        "partyOwnerMatchScoreEnemyTeam": 0,
        "partyOwnerProvisioningFlow": provisioning_flow_value,
        "provisioningFlow": provisioning_flow_value,
        "matchMap": (game_state or {}).get("map", ""),
        "partyId": current_party_id,
        "isPartyOwner": profile["subject"] == owner_subject,
        "partyName": "",
        "partyState": state,
        "partyAccessibility": "CLOSED",
        "maxPartySize": 5,
        "queueId": (game_state or {}).get("queue", ""),
        "partyLFM": False,
        "partyClientVersion": CLIENT_VERSION,
        "partySize": len(profiles),
        "partyVersion": int((game_state or {}).get("party_version", 1)),
        "queueEntryTime": "0001.01.01-00.00.00",
        "playerCardId": DEFAULT_PLAYER_CARD_ID,
        "playerTitleId": DEFAULT_PLAYER_TITLE_ID,
        "isIdle": False,
        "tournamentId": "",
    }


def presence_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
    update: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = profile or default_profile()
    private_raw = json.dumps(presence_private_payload(game_state, profile), separators=(",", ":")).encode("utf-8")
    payload = {
        "actor": None,
        "basic": "chat",
        "details": None,
        "game_name": profile["game_name"],
        "game_tag": profile["tag_line"],
        "GameName": profile["game_name"],
        "GameTag": profile["tag_line"],
        "TagLine": profile["tag_line"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "display_name": profile["display_name"],
        "location": None,
        "msg": "",
        "name": profile["game_name"],
        "patchline": "live",
        "pid": profile["chat_pid"],
        "platform": "PC",
        "private": base64.b64encode(private_raw).decode("ascii"),
        "privateJwt": None,
        "product": "valorant",
        "puuid": profile["subject"],
        "region": "na",
        "resource": CHAT_RESOURCE,
        "state": "chat",
        "summary": "",
        "time": int(time.time() * 1000),
    }
    if update:
        for key in ("actor", "basic", "details", "location", "msg", "shared", "state", "summary"):
            if key in update:
                payload[key] = update[key]
        payload["time"] = int(time.time() * 1000)
    return payload


def presences_payload(game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    updates = (game_state or {}).get("presence_by_profile")
    if not isinstance(updates, dict):
        updates = {}
    presences = [presence_payload(game_state, profile, updates.get(profile["key"])) for profile in social_roster_profiles(game_state)]
    return {
        "Presences": presences,
        "presences": presences,
    }


def friends_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    updates = (game_state or {}).get("presence_by_profile")
    if not isinstance(updates, dict):
        updates = {}
    friends = []
    for friend in social_roster_profiles(game_state):
        if friend["subject"] == profile["subject"]:
            continue
        presence = presence_payload(game_state, friend, updates.get(friend["key"]))
        friends.append(
            {
                "Pid": friend["chat_pid"],
                "pid": friend["chat_pid"],
                "Subject": friend["subject"],
                "subject": friend["subject"],
                "Puuid": friend["subject"],
                "puuid": friend["subject"],
                "Name": friend["game_name"],
                "name": friend["game_name"],
                "GameName": friend["game_name"],
                "gameName": friend["game_name"],
                "game_name": friend["game_name"],
                "GameTag": friend["tag_line"],
                "gameTag": friend["tag_line"],
                "game_tag": friend["tag_line"],
                "TagLine": friend["tag_line"],
                "tagLine": friend["tag_line"],
                "DisplayName": friend["display_name"],
                "displayName": friend["display_name"],
                "Note": "",
                "note": "",
                "Group": "general",
                "group": "general",
                "DisplayGroup": "general",
                "displayGroup": "general",
                "Presence": presence,
                "presence": presence,
            }
        )
    return {"Friends": friends, "friends": friends}


def session_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    current_loop_state = loop_state(game_state)
    match_id = active_match_id(game_state)
    if game_state and game_state.get("phase") == "pregame" and game_state.get("pregame_state") == "provisioned":
        current_loop_state = "INGAME"
    client_id = f"rnet-probe-{profile['key']}"
    session_id = f"local-session-{profile['key']}"
    return {
        "Subject": profile["subject"],
        "CXNState": "CONNECTED",
        "ClientID": client_id,
        "ClientVersion": CLIENT_VERSION,
        "LoopState": current_loop_state,
        "LoopStateMetadata": match_id,
        "Version": 1,
        "LastHeartbeatTime": utc_now(),
        "ExpiredTime": "0001-01-01T00:00:00.000Z",
        "HeartbeatIntervalMillis": 30000,
        "PlaytimeNotification": None,
        "RestrictionType": None,
        "puuid": profile["subject"],
        "subject": profile["subject"],
        "cxnState": "CONNECTED",
        "clientID": client_id,
        "clientId": client_id,
        "clientVersion": CLIENT_VERSION,
        "loopState": current_loop_state,
        "loopStateMetadata": match_id,
        "state": "connected",
        "sessionId": session_id,
    }


def region_locale_payload() -> dict[str, Any]:
    return {
        "region": DEFAULT_REGION,
        "locale": DEFAULT_LOCALE,
        "webLanguage": DEFAULT_WEB_LANGUAGE,
        "webRegion": DEFAULT_REGION,
    }


def anti_addiction_state_payload(policy: str = "shutdown") -> dict[str, Any]:
    return {
        "type": "OK",
        "message": "",
        "metadata": {},
    }


def chat_session_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "federated": True,
        "game_name": profile["game_name"],
        "game_tag": profile["tag_line"],
        "loaded": True,
        "name": profile["game_name"],
        "pid": profile["chat_pid"],
        "puuid": profile["subject"],
        "region": "na",
        "resource": CHAT_RESOURCE,
        "state": "connected",
        "connected": True,
    }


def player_identity_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "Subject": profile["subject"],
        "GameName": profile["game_name"],
        "TagLine": profile["tag_line"],
        "GameTag": profile["tag_line"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "prefDisplayName": profile["display_name"],
        "PlayerCardID": DEFAULT_PLAYER_CARD_ID,
        "PlayerCardId": DEFAULT_PLAYER_CARD_ID,
        "playerCardID": DEFAULT_PLAYER_CARD_ID,
        "playerCardId": DEFAULT_PLAYER_CARD_ID,
        "PlayerTitleID": DEFAULT_PLAYER_TITLE_ID,
        "PlayerTitleId": DEFAULT_PLAYER_TITLE_ID,
        "playerTitleID": DEFAULT_PLAYER_TITLE_ID,
        "playerTitleId": DEFAULT_PLAYER_TITLE_ID,
        "AccountLevel": 1,
        "PreferredLevelBorderID": ZERO_UUID,
        "preferredLevelBorderID": ZERO_UUID,
        "preferredLevelBorderId": ZERO_UUID,
        "Incognito": False,
        "incognito": False,
        "HideAccountLevel": False,
        "hideAccountLevel": False,
    }


def party_member_payload(profile: dict[str, str] | None = None, owner_subject: str | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    owner_subject = owner_subject or profile["subject"]
    return {
        "Subject": profile["subject"],
        "GameName": profile["game_name"],
        "TagLine": profile["tag_line"],
        "GameTag": profile["tag_line"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "prefDisplayName": profile["display_name"],
        "CompetitiveTier": 0,
        "PlayerIdentity": player_identity_payload(profile),
        "SeasonalBadgeInfo": None,
        "IsOwner": profile["subject"] == owner_subject,
        "QueueEligibleRemainingAccountLevels": 0,
        "Pings": [],
        "IsReady": True,
        "IsModerator": False,
        "UseBroadcastHUD": False,
        "PlatformType": "PC",
    }


def custom_game_configs_payload(game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    map_id = (game_state or {}).get("map", DEFAULT_MAP)
    mode_id = (game_state or {}).get("mode", DEFAULT_MODE)
    custom_config = {
        "Name": "Local Custom",
        "QueueID": DEFAULT_QUEUE,
        "Map": map_id,
        "Mode": mode_id,
        "Enabled": True,
    }
    shooting_range_config = {
        "Name": "Shooting Range",
        "QueueID": SHOOTING_RANGE_QUEUE,
        "Map": DEFAULT_MAP,
        "Mode": DEFAULT_MODE,
        "Enabled": True,
    }
    configs = [custom_config, shooting_range_config]
    return {
        "Enabled": True,
        "enabled": True,
        "EnabledMaps": list(dict.fromkeys([map_id, DEFAULT_MAP])),
        "enabledMaps": list(dict.fromkeys([map_id, DEFAULT_MAP])),
        "EnabledModes": list(dict.fromkeys([mode_id, DEFAULT_MODE])),
        "enabledModes": list(dict.fromkeys([mode_id, DEFAULT_MODE])),
        "Queues": [DEFAULT_QUEUE, SHOOTING_RANGE_QUEUE, "v"],
        "queues": [DEFAULT_QUEUE, SHOOTING_RANGE_QUEUE, "v"],
        "CustomGameConfigs": configs,
        "customGameConfigs": configs,
        "GamePodPingServiceInfo": {GAME_POD_ID: {"Host": (game_state or {}).get("game_host", "127.0.0.1")}},
        "gamePodPingServiceInfo": {GAME_POD_ID: {"host": (game_state or {}).get("game_host", "127.0.0.1")}},
    }


def party_player_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
    party_id: str | None = None,
) -> dict[str, Any]:
    profile = profile or default_profile()
    party_id = party_id or party_id_for_profile(profile)
    return {
        "Subject": profile["subject"],
        "GameName": profile["game_name"],
        "TagLine": profile["tag_line"],
        "GameTag": profile["tag_line"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "prefDisplayName": profile["display_name"],
        "Version": int((game_state or {}).get("party_version", 1)),
        "CurrentPartyID": party_id,
        "Invites": [],
        "Requests": [],
        "PlatformInfo": {
            "platformType": "PC",
            "platformOS": "Windows",
            "platformOSVersion": "10.0.19045.1.768.64bit",
            "platformChipset": "Unknown",
        },
    }


def party_payload(
    game_state: dict[str, Any] | None = None,
    party_id: str | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    profile = profile or default_profile()
    party_id = party_id or party_id_for_profile(profile)
    map_id = (game_state or {}).get("map", DEFAULT_MAP)
    mode_id = (game_state or {}).get("mode", DEFAULT_MODE)
    queue_id = (game_state or {}).get("queue", "")
    provisioning_flow = active_provisioning_flow(game_state)
    provisioning_flow_value = provisioning_flow_id(provisioning_flow)
    party_state = active_party_state(game_state)
    is_solo_range = queue_id == SHOOTING_RANGE_QUEUE or provisioning_flow in {SHOOTING_RANGE_PROVISIONING_FLOW, "NewPlayerExperience"}
    max_party_size = 1 if is_solo_range else 10
    profiles = party_profiles(game_state, party_id, profile)
    owner_subject = profiles[0]["subject"] if profiles else profile["subject"]
    team_one = []
    team_two = []
    team_spectate = []
    for profile in profiles:
        team = custom_team_for_profile(game_state, profile)
        team_id = team_id_for_custom_team(team)
        player = {
            "Subject": profile["subject"],
            "GameName": profile["game_name"],
            "TagLine": profile["tag_line"],
            "GameTag": profile["tag_line"],
            "DisplayName": profile["display_name"],
            "displayName": profile["display_name"],
            "prefDisplayName": profile["display_name"],
            "Player": profile["subject"],
            "player": profile["subject"],
            "Puuid": profile["subject"],
            "puuid": profile["subject"],
            "Team": team,
            "team": team,
            "TeamID": team_id,
            "teamID": team_id,
            "teamId": team_id,
        }
        if team == "TeamTwo":
            team_two.append(player)
        elif team == "TeamSpectate":
            team_spectate.append(player)
        else:
            team_one.append(player)
    return {
        "ID": party_id,
        "MUCName": party_muc_name(party_id),
        "VoiceRoomID": party_voice_room_id(party_id),
        "Version": int((game_state or {}).get("party_version", 1)),
        "ClientVersion": CLIENT_VERSION,
        "Members": [party_member_payload(profile, owner_subject) for profile in profiles],
        "State": party_state,
        "PreviousState": "DEFAULT",
        "StateTransitionReason": "",
        "Accessibility": "CLOSED",
        "CustomGameData": {
            "Settings": {
                "Map": map_id if party_state != "DEFAULT" else "",
                "MapID": map_id if party_state != "DEFAULT" else "",
                "MapId": map_id if party_state != "DEFAULT" else "",
                "mapId": map_id if party_state != "DEFAULT" else "",
                "MapUrl": map_id if party_state != "DEFAULT" else "",
                "MapURL": map_id if party_state != "DEFAULT" else "",
                "MapPath": map_id if party_state != "DEFAULT" else "",
                "Mode": mode_id,
                "ModeID": mode_id,
                "ModeId": mode_id,
                "modeId": mode_id,
                "GameMode": mode_id,
                "GameModeID": mode_id,
                "GameModeId": mode_id,
                "gameModeId": mode_id,
                "QueueID": queue_id,
                "queueID": queue_id,
                "QueueId": queue_id,
                "queueId": queue_id,
                "ProvisioningFlow": provisioning_flow,
                "provisioningFlow": provisioning_flow,
                "ProvisioningFlowID": provisioning_flow_value,
                "provisioningFlowID": provisioning_flow_value,
                "ProvisioningFlowId": provisioning_flow_value,
                "provisioningFlowId": provisioning_flow_value,
                "UseBots": False,
                "GamePod": GAME_POD_ID if party_state != "DEFAULT" else "",
                "GamePodID": GAME_POD_ID if party_state != "DEFAULT" else "",
                "gamePodID": GAME_POD_ID if party_state != "DEFAULT" else "",
                "GameRules": {},
            },
            "Membership": {
                "TeamOne": team_one,
                "TeamTwo": team_two,
                "TeamSpectate": team_spectate,
                "teamOne": team_one,
                "teamTwo": team_two,
                "teamSpectate": team_spectate,
                "teamOneCoaches": None,
                "teamTwoCoaches": None,
            },
            "MaxPartySize": max_party_size,
            "maxPartySize": max_party_size,
            "AutobalanceEnabled": False,
            "AutobalanceMinPlayers": 0,
            "HasRecoveryData": False,
        },
        "MatchmakingData": {
            "QueueID": queue_id,
            "queueID": queue_id,
            "PreferredGamePods": [GAME_POD_ID] if queue_id else [],
            "SkillDisparityRRPenalty": 0,
            "ProvisioningFlow": provisioning_flow if party_state != "DEFAULT" else "Invalid",
            "provisioningFlow": provisioning_flow if party_state != "DEFAULT" else "Invalid",
        },
        "Invites": [],
        "Requests": [],
        "QueueEntryTime": "0001-01-01T00:00:00.000Z",
        "ErrorNotification": {"ErrorType": "", "ErroredPlayers": None},
        "RestrictedSeconds": 0,
        "EligibleQueues": [],
        "QueueIneligibilities": [],
        "CheatData": {"GamePodOverride": "", "ForcePostGameProcessing": False},
        "XPBonuses": [],
        "InviteCode": "LOCAL",
    }


def queue_configs_payload() -> dict[str, Any]:
    queues = [
        {
            "QueueID": DEFAULT_QUEUE,
            "queueID": DEFAULT_QUEUE,
            "Name": "Local Custom",
            "GameMode": DEFAULT_MODE,
            "gameMode": DEFAULT_MODE,
            "Enabled": True,
            "enabled": True,
            "TeamSize": 5,
            "MaxPartySize": 10,
            "MinPartySize": 1,
            "Maps": [DEFAULT_MAP],
            "AllowFullPartyBypassSkillRestrictions": True,
            "IsRanked": False,
        },
        {
            "QueueID": SHOOTING_RANGE_QUEUE,
            "queueID": SHOOTING_RANGE_QUEUE,
            "Name": "Shooting Range",
            "GameMode": DEFAULT_MODE,
            "gameMode": DEFAULT_MODE,
            "Enabled": True,
            "enabled": True,
            "TeamSize": 1,
            "MaxPartySize": 1,
            "MinPartySize": 1,
            "Maps": [DEFAULT_MAP],
            "AllowFullPartyBypassSkillRestrictions": True,
            "IsRanked": False,
            "ProvisioningFlow": SHOOTING_RANGE_PROVISIONING_FLOW,
            "provisioningFlow": SHOOTING_RANGE_PROVISIONING_FLOW,
        },
        {
            "QueueID": "v",
            "queueID": "v",
            "Name": "Local Test Queue",
            "GameMode": DEFAULT_MODE,
            "gameMode": DEFAULT_MODE,
            "Enabled": True,
            "enabled": True,
            "TeamSize": 5,
            "MaxPartySize": 10,
            "MinPartySize": 1,
            "Maps": [DEFAULT_MAP],
            "AllowFullPartyBypassSkillRestrictions": True,
            "IsRanked": False,
        },
    ]
    return {"Queues": queues, "queues": queues}


def pregame_player_payload(game_state: dict[str, Any], profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "Subject": profile["subject"],
        "MatchID": MATCH_ID,
        "Version": int(game_state.get("match_version", 1)),
    }


def inactive_match_player_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "Subject": profile["subject"],
        "MatchID": "",
        "Version": 0,
    }


def inactive_match_payload() -> dict[str, Any]:
    return {
        "ID": "",
        "MatchID": "",
        "Version": 0,
        "Teams": [],
        "AllyTeam": None,
        "EnemyTeam": None,
        "ObserverSubjects": [],
        "MatchCoaches": [],
        "PregameState": "",
        "MapID": "",
        "Map": "",
        "MapUrl": "",
        "MapURL": "",
        "Mode": "",
        "ModeID": "",
        "GameMode": "",
        "GameModeID": "",
        "QueueID": "",
        "ProvisioningFlow": "Invalid",
        "ConnectionDetails": None,
        "Players": [],
        "TeamOne": [],
        "TeamTwo": [],
        "TeamSpectate": [],
    }


def pregame_match_payload(game_state: dict[str, Any], profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    map_id = game_state.get("map", DEFAULT_MAP)
    mode_id = game_state.get("mode", DEFAULT_MODE)
    queue_id = game_state.get("queue", DEFAULT_QUEUE)
    provisioning_flow = active_provisioning_flow(game_state)
    provisioning_flow_value = provisioning_flow_id(provisioning_flow)
    pregame_state = str(game_state.get("pregame_state") or "")
    if not pregame_state:
        pregame_state = "provisioned" if game_state.get("phase") == "core" else "character_select_active"
    profiles = party_profiles(game_state, party_id_for_profile(profile), profile)
    all_locked = all(character_state_for_profile(game_state, member_profile) == "locked" for member_profile in profiles)
    if all_locked and pregame_state != "provisioned":
        pregame_state = "character_select_finished" if game_state.get("phase") != "core" else "provisioned"
    provisioning_state = "provisioned" if game_state.get("phase") == "core" or pregame_state == "provisioned" else ""
    players = []
    team_one = []
    team_two = []
    team_spectate = []
    for profile in profiles:
        team = custom_team_for_profile(game_state, profile)
        player = {
            "Subject": profile["subject"],
            "TeamID": team_id_for_custom_team(team),
            "CharacterID": character_for_profile(game_state, profile, ""),
            "CharacterSelectionState": character_state_for_profile(game_state, profile),
            "PregamePlayerState": "joined",
            "CompetitiveTier": 0,
            "PlayerIdentity": player_identity_payload(profile),
            "SeasonalBadgeInfo": None,
            "IsCaptain": profile["subject"] == profiles[0]["subject"],
        }
        players.append(player)
        if team == "TeamTwo":
            team_two.append(player)
        elif team == "TeamSpectate":
            team_spectate.append(player)
        else:
            team_one.append(player)
    ally_team = {"TeamID": "Blue", "Players": team_one or players}
    enemy_team = {"TeamID": "Red", "Players": team_two} if team_two else None
    teams = [ally_team]
    if enemy_team:
        teams.append(enemy_team)
    return {
        "ID": MATCH_ID,
        "MatchID": MATCH_ID,
        "Version": int(game_state.get("match_version", 1)),
        "Teams": teams,
        "AllyTeam": ally_team,
        "EnemyTeam": enemy_team,
        "ObserverSubjects": [],
        "MatchCoaches": [],
        "Players": players,
        "TeamOne": team_one,
        "TeamTwo": team_two,
        "TeamSpectate": team_spectate,
        "EnemyTeamSize": 0,
        "EnemyTeamLockCount": 0,
        "PregameState": pregame_state,
        "LastUpdated": utc_now(),
        "MapID": map_id,
        "Map": map_id,
        "MapUrl": map_id,
        "MapURL": map_id,
        "MapPath": map_id,
        "MapSelectPool": [],
        "BannedMapIDs": [],
        "CastedVotes": None,
        "MapSelectSteps": [],
        "MapSelectStep": 0,
        "Team1": "Blue",
        "GamePodID": GAME_POD_ID,
        "GamePod": GAME_POD_ID,
        "Mode": mode_id,
        "ModeID": mode_id,
        "GameMode": mode_id,
        "GameModeID": mode_id,
        "VoiceSessionID": TEAM_VOICE_ID,
        "MUCName": TEAM_MUC_NAME,
        "QueueID": queue_id,
        "Queue": queue_id,
        "ProvisioningFlowID": provisioning_flow,
        "ProvisioningFlowEnum": provisioning_flow_value,
        "ProvisioningFlow": provisioning_flow,
        "provisioningFlow": provisioning_flow,
        "ProvisioningState": provisioning_state,
        "provisioningState": provisioning_state,
        "IsRanked": False,
        "PhaseTimeRemainingNS": 0,
        "ConnectionDetails": None,
        "DirectConnectSettings": None,
        "IsValid": True,
    }


def core_game_player_payload(game_state: dict[str, Any], profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "Subject": profile["subject"],
        "MatchID": MATCH_ID,
        "Version": int(game_state.get("match_version", 1)),
    }


def core_game_match_payload(game_state: dict[str, Any], profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    host = game_state.get("game_host", "127.0.0.1")
    port = int(game_state.get("game_port", 7777))
    map_id = game_state.get("map", DEFAULT_MAP)
    mode_id = game_state.get("mode", DEFAULT_MODE)
    queue_id = game_state.get("queue", DEFAULT_QUEUE)
    provisioning_flow = active_provisioning_flow(game_state)
    players = []
    team_one = []
    team_two = []
    team_spectate = []
    for member_profile in party_profiles(game_state, party_id_for_profile(profile), profile):
        team = custom_team_for_profile(game_state, member_profile)
        player = {
            "Subject": member_profile["subject"],
            "TeamID": team_id_for_custom_team(team),
            "CharacterID": character_for_profile(game_state, member_profile, DEFAULT_CHARACTER_ID),
            "PlayerIdentity": player_identity_payload(member_profile),
            "SeasonalBadgeInfo": None,
            "IsCoach": False,
        }
        players.append(player)
        if team == "TeamTwo":
            team_two.append(player)
        elif team == "TeamSpectate":
            team_spectate.append(player)
        else:
            team_one.append(player)
    return {
        "MatchID": MATCH_ID,
        "ID": MATCH_ID,
        "Version": int(game_state.get("match_version", 1)),
        "State": "IN_PROGRESS",
        "MapID": map_id,
        "Map": map_id,
        "MapUrl": map_id,
        "MapURL": map_id,
        "MapPath": map_id,
        "MatchMap": map_id,
        "ModeID": mode_id,
        "Mode": mode_id,
        "GameMode": mode_id,
        "GameModeID": mode_id,
        "ProvisioningFlow": provisioning_flow,
        "ProvisioningFlowID": provisioning_flow_id(provisioning_flow),
        "provisioningFlow": provisioning_flow,
        "ProvisioningState": "provisioned",
        "QueueID": queue_id,
        "GamePodID": GAME_POD_ID,
        "GamePod": GAME_POD_ID,
        "AllMUCName": ALL_MUC_NAME,
        "TeamMUCName": TEAM_MUC_NAME,
        "TeamVoiceID": TEAM_VOICE_ID,
        "IsReconnectable": True,
        "ConnectionDetails": {
            "GameServerHosts": [host],
            "GameServerHost": host,
            "gameServerHost": host,
            "GameServerAddress": host,
            "gameServerAddress": host,
            "GameServerPort": port,
            "gameServerPort": port,
            "ServerAddress": host,
            "serverAddress": host,
            "ServerIP": host,
            "serverIP": host,
            "serverIp": host,
            "ServerPort": port,
            "serverPort": port,
            "GamePodID": GAME_POD_ID,
            "gamePodID": GAME_POD_ID,
            "GamePod": GAME_POD_ID,
            "gamePod": GAME_POD_ID,
            "GameServerObfuscatedIP": 0,
            "gameServerObfuscatedIP": 0,
            "GameClientHash": 0,
            "gameClientHash": 0,
            "PlayerKey": "local-player-key",
            "playerKey": "local-player-key",
        },
        "DirectConnectSettings": {
            "PlayerName": profile["game_name"],
            "Team": "Blue",
            "Player": profile["subject"],
            "ServerIP": host,
            "Port": str(port),
        },
        "Players": players,
        "TeamOne": team_one,
        "TeamTwo": team_two,
        "TeamSpectate": team_spectate,
        "MatchmakingData": {
            "QueueID": queue_id,
            "queueID": queue_id,
            "PreferredGamePods": [GAME_POD_ID],
            "GamePodID": GAME_POD_ID,
            "ProvisioningFlow": provisioning_flow,
            "provisioningFlow": provisioning_flow,
        },
        "PostGameDetails": None,
    }


def chat_token_payload(room: str = PARTY_MUC_NAME) -> dict[str, Any]:
    return {
        "Token": "local-chat-token",
        "token": "local-chat-token",
        "Name": room,
        "name": room,
        "Room": room,
        "room": room,
        "Cid": room,
        "cid": room,
        "CID": room,
        "MUCName": room,
        "mucName": room,
        "RoomID": room,
        "roomID": room,
        "RoomId": room,
        "roomId": room,
        "Service": "local-chat",
        "service": "local-chat",
    }


def voice_token_payload(room: str = VOICE_ROOM_ID) -> dict[str, Any]:
    return {
        "Token": "local-voice-token",
        "token": "local-voice-token",
        "Room": room,
        "room": room,
        "VoiceRoomID": room,
        "voiceRoomID": room,
    }


def voice_session_participants_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
    party_id: str | None = None,
) -> dict[str, Any]:
    profile = profile or default_profile()
    party_id = party_id or party_id_for_profile(profile)
    participants = [
        {
            "Subject": profile["subject"],
            "subject": profile["subject"],
            "Muted": False,
            "muted": False,
            "Volume": 1.0,
            "volume": 1.0,
        }
        for profile in party_profiles(game_state, party_id, profile)
    ]
    return {"Participants": participants, "participants": participants}


def voice_session_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    party_id = party_id_for_profile(profile)
    voice_room = party_voice_room_id(party_id)
    participants = voice_session_participants_payload(game_state, profile, party_id)
    return {
        "SessionID": voice_room,
        "sessionID": voice_room,
        "RoomID": voice_room,
        "roomID": voice_room,
        "Participants": participants["Participants"],
        "participants": participants["participants"],
    }


def voice_sessions_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    return [voice_session_payload(game_state, profile)]


def wallet_payload() -> dict[str, Any]:
    balances = {
        LOCAL_CURRENCY_ID: 999999,
        LOCAL_UPGRADE_TOKEN_ID: 999999,
        LOCAL_RECRUITMENT_TOKEN_ID: 999999,
    }
    return {
        "Balances": balances,
        "balances": balances,
    }


def store_offers_payload() -> dict[str, Any]:
    return {
        "Offers": [],
        "offers": [],
        "UpgradeCurrencyOffers": [],
        "upgradeCurrencyOffers": [],
    }


def store_entitlements_payload(item_type_id: str, game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    loadout_rows = loadout_content_rows(game_state)
    typed_items = {
        ITEM_TYPE_PLAYER_CARD: [DEFAULT_PLAYER_CARD_ID],
        ITEM_TYPE_PLAYER_TITLE: [DEFAULT_PLAYER_TITLE_ID],
        ITEM_TYPE_CHARACTER: [agent_id for _, _, agent_id in CHARACTER_CONTENT],
        ITEM_TYPE_SPRAY: [DEFAULT_SPRAY_PREROUND_ID, DEFAULT_SPRAY_MIDROUND_ID],
        ITEM_TYPE_CONTRACT: [],
        ITEM_TYPE_SKIN: [row["skin_id"] for row in loadout_rows],
        ITEM_TYPE_SKIN_LEVEL: [row["skin_level_id"] for row in loadout_rows if row.get("skin_level_id")],
        ITEM_TYPE_SKIN_CHROMA: [row["chroma_id"] for row in loadout_rows if row.get("chroma_id")],
        ITEM_TYPE_CHARM: [],
        ITEM_TYPE_CHARM_LEVEL: [],
        ITEM_TYPE_SPRAY_LEVEL: [],
    }
    owned_item_ids = typed_items.get(item_type_id.lower(), [])
    entitlements = [
        {
            "TypeID": item_type_id,
            "typeID": item_type_id,
            "Type": item_type_id,
            "type": item_type_id,
            "ServiceID": item_type_id,
            "serviceID": item_type_id,
            "ServiceId": item_type_id,
            "serviceId": item_type_id,
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
        for item_id in owned_item_ids
    ]
    return {
        "ItemTypeID": item_type_id,
        "itemTypeID": item_type_id,
        "EntitlementTypeID": item_type_id,
        "entitlementTypeID": item_type_id,
        "EntitlementTypeId": item_type_id,
        "entitlementTypeId": item_type_id,
        "Entitlements": entitlements,
        "entitlements": entitlements,
        "OwnedEntitlements": entitlements,
        "ownedEntitlements": entitlements,
    }


def all_store_entitlements_payload(game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    item_type_ids = [
        ITEM_TYPE_PLAYER_CARD,
        ITEM_TYPE_PLAYER_TITLE,
        ITEM_TYPE_CHARACTER,
        ITEM_TYPE_SPRAY,
        ITEM_TYPE_CONTRACT,
        ITEM_TYPE_SKIN,
        ITEM_TYPE_SKIN_LEVEL,
        ITEM_TYPE_SKIN_CHROMA,
        ITEM_TYPE_CHARM,
        ITEM_TYPE_CHARM_LEVEL,
        ITEM_TYPE_SPRAY_LEVEL,
    ]
    by_type = {item_type_id: store_entitlements_payload(item_type_id, game_state) for item_type_id in item_type_ids}
    entitlements = [entry for payload in by_type.values() for entry in payload["Entitlements"]]
    return {
        "Entitlements": entitlements,
        "entitlements": entitlements,
        "OwnedEntitlements": entitlements,
        "ownedEntitlements": entitlements,
        "EntitlementsByItemType": by_type,
        "entitlementsByItemType": by_type,
    }


def store_v2_storefront_payload() -> dict[str, Any]:
    skins_panel = {
        "SingleItemOffers": [],
        "singleItemOffers": [],
        "SingleItemStoreOffers": [],
        "singleItemStoreOffers": [],
        "SingleItemOffersRemainingDurationInSeconds": 3600,
        "singleItemOffersRemainingDurationInSeconds": 3600,
    }
    featured_bundle = {
        "Bundle": None,
        "bundle": None,
        "Bundles": [],
        "bundles": [],
        "BundleRemainingDurationInSeconds": 0,
        "bundleRemainingDurationInSeconds": 0,
    }
    return {
        "FeaturedBundle": featured_bundle,
        "featuredBundle": featured_bundle,
        "SkinsPanelLayout": skins_panel,
        "skinsPanelLayout": skins_panel,
        "BundleLayout": {"Bundles": [], "bundles": []},
        "bundleLayout": {"Bundles": [], "bundles": []},
        "PersonalizedOffers": [],
        "personalizedOffers": [],
        "UpgradeCurrencyOffers": [],
        "upgradeCurrencyOffers": [],
        "UpgradeCurrencyStore": {"UpgradeCurrencyOffers": [], "upgradeCurrencyOffers": []},
        "upgradeCurrencyStore": {"UpgradeCurrencyOffers": [], "upgradeCurrencyOffers": []},
        "BonusStore": None,
        "bonusStore": None,
        "AccessoryStore": None,
        "accessoryStore": None,
    }


def purchase_initialized_payload() -> dict[str, Any]:
    return {
        "OrderID": LOCAL_ORDER_ID,
        "orderID": LOCAL_ORDER_ID,
        "OrderId": LOCAL_ORDER_ID,
        "orderId": LOCAL_ORDER_ID,
        "Status": "SUCCEEDED",
        "status": "SUCCEEDED",
        "eventType": "OrderCompleted",
        "eventTypeId": "OrderCompleted",
        "Metadata": {},
        "metadata": {},
        "PurchasePrice": {},
        "purchasePrice": {},
        "Success": True,
        "success": True,
    }


def required_entitlement_payload(item_type_id: str, item_id: str) -> dict[str, Any]:
    return {
        "TypeID": item_type_id,
        "typeID": item_type_id,
        "Type": item_type_id,
        "type": item_type_id,
        "ServiceID": item_type_id,
        "serviceID": item_type_id,
        "ServiceId": item_type_id,
        "serviceId": item_type_id,
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
        "AssetName": asset,
        "assetName": asset,
        "AssetPath": asset,
        "assetPath": asset,
        "DataAsset": asset,
        "dataAsset": asset,
        "DataAssetPath": asset,
        "dataAssetPath": asset,
        "DataAssetID": item_id,
        "dataAssetID": item_id,
        "DataAssetId": item_id,
        "dataAssetId": item_id,
        "IsEnabled": True,
        "isEnabled": True,
    }


def compact_content_data_payload(item_id: str, name: str, asset: str) -> dict[str, Any]:
    return {
        "ID": item_id,
        "Guid": item_id,
        "guid": item_id,
        "UUID": item_id,
        "Uuid": item_id,
        "uuid": item_id,
        "Name": name,
        "name": name,
        "AssetName": asset,
        "assetName": asset,
        "AssetPath": asset,
        "assetPath": asset,
        "DataAsset": asset,
        "dataAsset": asset,
        "DataAssetPath": asset,
        "dataAssetPath": asset,
        "DataAssetID": item_id,
        "dataAssetID": item_id,
        "DataAssetId": item_id,
        "dataAssetId": item_id,
        "IsEnabled": True,
        "isEnabled": True,
    }


def content_asset(item_id: str, name: str, content_type: str, asset_path: str = "") -> dict[str, Any]:
    asset = asset_path or item_id
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
        "AssetName": asset,
        "assetName": asset,
        "DataAssetID": item_id,
        "dataAssetID": item_id,
        "DataAssetId": item_id,
        "dataAssetId": item_id,
        "DataAsset": asset,
        "dataAsset": asset,
        "AssetPath": asset,
        "assetPath": asset,
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
    asset_name = str(item.get("AssetName") or item.get("AssetPath") or item_id)
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
        "AssetPath": asset_name,
        "assetPath": asset_name,
    }
    if required_entitlement is None and item_type_id and item_id:
        required_entitlement = required_entitlement_payload(item_type_id, item_id)
    content = content_data_payload(
        item_id,
        str(item.get("Name") or item.get("DisplayName") or item_id),
        asset_name,
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
        "EquippableID",
        "equippableID",
        "Equippable",
        "equippable",
        "SkinID",
        "skinID",
        "SkinId",
        "skinId",
        "SkinLevelID",
        "skinLevelID",
        "SkinLevelId",
        "skinLevelId",
        "SkinLevels",
        "skinLevels",
        "Chromas",
        "chromas",
    )
    for item in items:
        item_id = str(item.get("ItemID") or item.get("ID") or "")
        content_type = str(item.get("ContentType") or item.get("contentType") or "")
        content_type_id = int(item.get("ContentTypeID") or item.get("TypeID") or CLIENT_CONTENT_TYPE_IDS.get(content_type, 0) or 0)
        asset_name = str(item.get("AssetName") or item.get("AssetPath") or item_id)
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
            "AssetPath": asset_name,
            "DataAsset": asset_name,
            "DataAssetPath": asset_name,
        }
        required_entitlement = item.get("RequiredEntitlement")
        if isinstance(required_entitlement, dict):
            required_entitlement = {
                "ItemID": required_entitlement.get("ItemID") or required_entitlement.get("itemID") or item_id,
                "ItemTypeID": required_entitlement.get("ItemTypeID") or required_entitlement.get("TypeID"),
                "TypeID": required_entitlement.get("TypeID") or required_entitlement.get("ItemTypeID"),
                "Type": required_entitlement.get("Type") or required_entitlement.get("ItemTypeID") or required_entitlement.get("TypeID"),
                "ServiceID": required_entitlement.get("ServiceID") or required_entitlement.get("ItemTypeID") or required_entitlement.get("TypeID"),
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
            "ItemID": item_id,
            "ContentType": content_type,
            "ContentTypeID": content_type_id,
            "TypeID": content_type_id,
            "Content": compact_content_data_payload(item_id, display_name, asset_name),
            "Levels": levels,
            "RequiredEntitlement": required_entitlement,
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
    return {
        **by_type,
        **by_name,
        "ByType": by_type,
    }


def row_asset(row: dict[str, str], key: str, fallback: str) -> str:
    asset_path = DEFAULT_LOADOUT_ASSET_PATHS.get(row.get("name", ""), {}).get(key, fallback)
    return asset_path if asset_path.startswith("BlueprintGeneratedClass'") else blueprint_asset(asset_path)


def content_service_payload(game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    cards = [content_listing(content_asset(DEFAULT_PLAYER_CARD_ID, "Local Card", "PlayerCard", DEFAULT_PLAYER_CARD_ASSET), ITEM_TYPE_PLAYER_CARD)]
    titles = [content_listing(content_asset(DEFAULT_PLAYER_TITLE_ID, "Local Founder", "PlayerTitle", DEFAULT_PLAYER_TITLE_ASSET), ITEM_TYPE_PLAYER_TITLE)]
    maps = [content_listing(content_asset("1f676c76-80e1-4239-95bb-83d0f6d0da78", "Range", "Map", DEFAULT_MAP_ASSET))]
    modes = [content_listing(content_asset("4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38", "Shooting Range", "GameMode", DEFAULT_MODE_ASSET))]
    characters = []
    for display_name, asset_name, agent_id in CHARACTER_CONTENT:
        characters.append(
            content_listing(
                content_asset(
                    agent_id,
                    display_name,
                    "Character",
                    blueprint_asset(f"/Game/Characters/{asset_name}/{asset_name}_PrimaryAsset"),
                ),
                ITEM_TYPE_CHARACTER,
            )
        )
    sprays = [
        content_listing(content_asset(DEFAULT_SPRAY_PREROUND_ID, "Chicken", "Spray", DEFAULT_SPRAY_PREROUND_ASSET), ITEM_TYPE_SPRAY),
        content_listing(content_asset(DEFAULT_SPRAY_MIDROUND_ID, "Salt", "Spray", DEFAULT_SPRAY_MIDROUND_ASSET), ITEM_TYPE_SPRAY),
    ]
    currencies = [
        content_listing(content_asset(LOCAL_CURRENCY_ID, "Ares Points", "Currency", LOCAL_CURRENCY_ASSET)),
        content_listing(content_asset(LOCAL_UPGRADE_TOKEN_ID, "Upgrade Tokens", "Currency", LOCAL_UPGRADE_TOKEN_ASSET)),
        content_listing(content_asset(LOCAL_RECRUITMENT_TOKEN_ID, "Recruitment Tokens", "Currency", LOCAL_RECRUITMENT_TOKEN_ASSET)),
    ]
    contracts = []
    equips = []
    skins = []
    skin_levels = []
    chromas = []
    for row in loadout_content_rows(game_state):
        equip = content_listing(
            content_asset(row["equippable_id"], row["name"], "Equippable", row_asset(row, "equippable", f"/Game/Equippables/{row['name']}/{row['name']}_PrimaryAsset"))
        )
        skin = content_listing(
            content_asset(row["skin_id"], f"Standard {row['name']}", "EquippableSkin", row_asset(row, "skin", f"/Game/Equippables/{row['name']}/Skins/Standard/{row['name']}_Standard_PrimaryAsset")),
            ITEM_TYPE_SKIN,
            [row["skin_level_id"]],
        )
        level = content_listing(
            content_asset(row["skin_level_id"], f"Standard {row['name']} Level", "EquippableSkinLevel", row_asset(row, "level", f"/Game/Equippables/{row['name']}/Skins/Standard/{row['name']}_Standard_Lv1_PrimaryAsset")),
            ITEM_TYPE_SKIN_LEVEL,
        )
        chroma = content_listing(
            content_asset(row["chroma_id"], f"Standard {row['name']} Chroma", "EquippableSkinChroma", row_asset(row, "chroma", f"/Game/Equippables/{row['name']}/Skins/Standard/Chromas/Standard/{row['name']}_Standard_Standard_PrimaryAsset")),
            ITEM_TYPE_SKIN_CHROMA,
        )
        skin.update(
            {
                "EquippableID": row["equippable_id"],
                "equippableID": row["equippable_id"],
                "Equippable": row["equippable_id"],
                "equippable": row["equippable_id"],
                "SkinLevels": [row["skin_level_id"]],
                "skinLevels": [row["skin_level_id"]],
                "Chromas": [row["chroma_id"]],
                "chromas": [row["chroma_id"]],
            }
        )
        level.update(
            {
                "EquippableID": row["equippable_id"],
                "equippableID": row["equippable_id"],
                "SkinID": row["skin_id"],
                "skinID": row["skin_id"],
                "SkinId": row["skin_id"],
                "skinId": row["skin_id"],
                "BaseLevel": True,
                "baseLevel": True,
            }
        )
        chroma.update(
            {
                "EquippableID": row["equippable_id"],
                "equippableID": row["equippable_id"],
                "SkinID": row["skin_id"],
                "skinID": row["skin_id"],
                "SkinId": row["skin_id"],
                "skinId": row["skin_id"],
                "SkinLevelID": row["skin_level_id"],
                "skinLevelID": row["skin_level_id"],
                "SkinLevelId": row["skin_level_id"],
                "skinLevelId": row["skin_level_id"],
            }
        )
        equips.append(equip)
        skins.append(skin)
        skin_levels.append(level)
        chromas.append(chroma)
    full_listing = cards + titles + maps + modes + characters + sprays + currencies + contracts + equips + skins + skin_levels + chromas
    full_listing_by_type: dict[str, list[dict[str, Any]]] = {}
    for item in full_listing:
        type_id = str(item["ContentTypeID"])
        full_listing_by_type.setdefault(type_id, []).append(content_listing_bucket([item])[0])
    full_content_dto = {
        "Characters": content_listing_bucket(characters),
        "Equips": content_listing_bucket(equips),
        "Attachments": [],
        "Skins": content_listing_bucket(skins),
        "SkinLevels": content_listing_bucket(skin_levels),
        "Chromas": content_listing_bucket(chromas),
        "Maps": content_listing_bucket(maps),
        "Themes": [],
        "GameModes": content_listing_bucket(modes),
        "Currencies": content_listing_bucket(currencies),
        "Sprays": content_listing_bucket(sprays),
        "SprayLevels": [],
        "Charms": [],
        "CharmLevels": [],
        "PlayerCards": content_listing_bucket(cards),
        "PlayerTitles": content_listing_bucket(titles),
        "PremiumContractDetails": [],
        "RewardSchedules": [],
        "AlternateProgressionSchedules": [],
        "Contracts": content_listing_bucket(contracts),
        "StorefrontItems": [],
    }
    full_listing_payload = {
        **full_content_listing_payload(full_listing),
        **full_content_dto,
    }
    supported_content_type_names = [
        "Contract",
        "Equippable",
        "EquippableSkin",
        "EquippableSkinLevel",
        "EquippableSkinChroma",
        "Character",
        "Map",
        "Spray",
        "GameMode",
        "Currency",
        "PlayerCard",
        "PlayerTitle",
    ]
    content_types = [
        {
            "ID": CLIENT_CONTENT_TYPE_IDS[name],
            "Id": CLIENT_CONTENT_TYPE_IDS[name],
            "TypeID": CLIENT_CONTENT_TYPE_IDS[name],
            "typeID": CLIENT_CONTENT_TYPE_IDS[name],
            "Name": name,
            "name": name,
        }
        for name in supported_content_type_names
    ]
    player_card_mapping = {DEFAULT_PLAYER_CARD_ID: content_listing_bucket(cards)[0]}
    player_title_mapping = {DEFAULT_PLAYER_TITLE_ID: content_listing_bucket(titles)[0]}
    spray_mapping = {spray["ItemID"]: spray for spray in content_listing_bucket(sprays)}
    equippable_mapping = {equip["ItemID"]: equip for equip in content_listing_bucket(equips)}
    skin_mapping = {skin["ItemID"]: skin for skin in content_listing_bucket(skins)}
    skin_level_mapping = {level["ItemID"]: level for level in content_listing_bucket(skin_levels)}
    chroma_mapping = {chroma["ItemID"]: chroma for chroma in content_listing_bucket(chromas)}
    payload = {
        "Characters": content_listing_bucket(characters),
        "characters": content_listing_bucket(characters),
        "Maps": content_listing_bucket(maps),
        "maps": content_listing_bucket(maps),
        "GameModes": content_listing_bucket(modes),
        "gameModes": content_listing_bucket(modes),
        "Sprays": content_listing_bucket(sprays),
        "sprays": content_listing_bucket(sprays),
        "SprayLevels": [],
        "sprayLevels": [],
        "Equips": content_listing_bucket(equips),
        "equips": content_listing_bucket(equips),
        "Equippables": content_listing_bucket(equips),
        "equippables": content_listing_bucket(equips),
        "Skins": content_listing_bucket(skins),
        "skins": content_listing_bucket(skins),
        "SkinLevels": content_listing_bucket(skin_levels),
        "skinLevels": content_listing_bucket(skin_levels),
        "Chromas": content_listing_bucket(chromas),
        "chromas": content_listing_bucket(chromas),
        "Charms": [],
        "charms": [],
        "CharmLevels": [],
        "charmLevels": [],
        "PlayerCards": content_listing_bucket(cards),
        "playerCards": content_listing_bucket(cards),
        "PlayerTitles": content_listing_bucket(titles),
        "playerTitles": content_listing_bucket(titles),
        "Currencies": content_listing_bucket(currencies),
        "currencies": content_listing_bucket(currencies),
        "Contracts": content_listing_bucket(contracts),
        "contracts": content_listing_bucket(contracts),
        "Themes": [],
        "themes": [],
        "Attachments": [],
        "attachments": [],
        "Bundles": [],
        "bundles": [],
        "StorefrontItems": [],
        "storefrontItems": [],
        "ContentTypes": content_types,
        "contentTypes": content_types,
        "PlayerCardMapping": player_card_mapping,
        "playerCardMapping": player_card_mapping,
        "PlayerTitleMapping": player_title_mapping,
        "playerTitleMapping": player_title_mapping,
        "SprayMapping": spray_mapping,
        "sprayMapping": spray_mapping,
        "EquippableMapping": equippable_mapping,
        "equippableMapping": equippable_mapping,
        "SkinMapping": skin_mapping,
        "skinMapping": skin_mapping,
        "SkinLevelMapping": skin_level_mapping,
        "skinLevelMapping": skin_level_mapping,
        "ChromaMapping": chroma_mapping,
        "chromaMapping": chroma_mapping,
        "FullContentListing": full_listing_payload,
        "fullContentListing": full_listing_payload,
        "FullContentListingDTO": full_listing_payload,
        "fullContentListingDTO": full_listing_payload,
        "FullListing": full_listing_payload,
        "fullListing": full_listing_payload,
        "FullListingByType": full_listing_by_type,
        "fullListingByType": full_listing_by_type,
        "Items": content_listing_bucket(full_listing),
        "items": content_listing_bucket(full_listing),
    }
    return payload


def match_history_payload() -> dict[str, Any]:
    return {
        "Subject": PLAYER_UUID,
        "subject": PLAYER_UUID,
        "BeginIndex": 0,
        "beginIndex": 0,
        "EndIndex": 0,
        "endIndex": 0,
        "Total": 0,
        "total": 0,
        "History": [],
        "history": [],
    }


def competitive_updates_payload() -> dict[str, Any]:
    return {
        "Subject": PLAYER_UUID,
        "subject": PLAYER_UUID,
        "Matches": [],
        "matches": [],
        "Version": 0,
        "version": 0,
    }


def match_details_payload() -> dict[str, Any]:
    return {
        "MatchID": MATCH_ID,
        "matchID": MATCH_ID,
        "Players": [],
        "players": [],
        "Teams": [],
        "teams": [],
        "Rounds": [],
        "rounds": [],
        "Kills": [],
        "kills": [],
    }


def player_loadout_payload(loadout: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
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
        payload["Guns"] = default_loadout_guns()
    if isinstance(payload["Guns"], list):
        payload["Guns"] = [add_gun_aliases(gun) if isinstance(gun, dict) else gun for gun in payload["Guns"]]
    payload.setdefault("guns", payload.get("Guns", []))
    if isinstance(payload["guns"], list):
        payload["guns"] = [add_gun_aliases(gun) if isinstance(gun, dict) else gun for gun in payload["guns"]]
    payload["Guns"] = payload["guns"] = payload["Guns"] or payload["guns"]
    payload.setdefault("Sprays", payload.get("sprays", []))
    payload.setdefault("sprays", payload.get("Sprays", []))
    identity = payload.get("Identity") if isinstance(payload.get("Identity"), dict) else payload.get("identity")
    identity = dict(identity) if isinstance(identity, dict) else player_identity_payload(profile)
    if not identity.get("Subject"):
        identity["Subject"] = profile["subject"]
    identity["subject"] = identity.get("subject") or identity["Subject"]
    if not identity.get("PlayerTitleID"):
        identity["PlayerTitleID"] = DEFAULT_PLAYER_TITLE_ID
    identity["playerTitleID"] = identity.get("playerTitleID") or identity["PlayerTitleID"]
    identity["PlayerCardID"] = identity.get("PlayerCardID") or DEFAULT_PLAYER_CARD_ID
    identity["playerCardID"] = identity.get("playerCardID") or identity["PlayerCardID"]
    payload["Identity"] = identity
    payload["identity"] = identity
    player_card = normalize_item_id_object(payload.get("PlayerCard") or payload.get("playerCard"), DEFAULT_PLAYER_CARD_ID)
    player_title = normalize_item_id_object(payload.get("PlayerTitle") or payload.get("playerTitle"), DEFAULT_PLAYER_TITLE_ID)
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


def contract_model_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    content = content_data_payload(LOCAL_STORY_CONTRACT_ID, "Local Story", LOCAL_CONTRACT_ASSET)
    progression = {
        "ID": LOCAL_STORY_CONTRACT_ID,
        "Id": LOCAL_STORY_CONTRACT_ID,
        "UUID": LOCAL_STORY_CONTRACT_ID,
        "Uuid": LOCAL_STORY_CONTRACT_ID,
        "uuid": LOCAL_STORY_CONTRACT_ID,
        "ContractID": LOCAL_STORY_CONTRACT_ID,
        "contractID": LOCAL_STORY_CONTRACT_ID,
        "ContractId": LOCAL_STORY_CONTRACT_ID,
        "contractId": LOCAL_STORY_CONTRACT_ID,
        "ContractDefinitionID": LOCAL_STORY_CONTRACT_ID,
        "contractDefinitionID": LOCAL_STORY_CONTRACT_ID,
        "ContractDefinitionId": LOCAL_STORY_CONTRACT_ID,
        "contractDefinitionId": LOCAL_STORY_CONTRACT_ID,
        "DataAssetID": LOCAL_STORY_CONTRACT_ID,
        "dataAssetID": LOCAL_STORY_CONTRACT_ID,
        "DataAssetId": LOCAL_STORY_CONTRACT_ID,
        "dataAssetId": LOCAL_STORY_CONTRACT_ID,
        "DataAsset": LOCAL_CONTRACT_ASSET,
        "dataAsset": LOCAL_CONTRACT_ASSET,
        "DataAssetPath": LOCAL_CONTRACT_ASSET,
        "dataAssetPath": LOCAL_CONTRACT_ASSET,
        "AssetName": LOCAL_CONTRACT_ASSET,
        "assetName": LOCAL_CONTRACT_ASSET,
        "AssetPath": LOCAL_CONTRACT_ASSET,
        "assetPath": LOCAL_CONTRACT_ASSET,
        "Guid": LOCAL_STORY_CONTRACT_ID,
        "guid": LOCAL_STORY_CONTRACT_ID,
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "Content": content,
        "content": content,
        "ContentData": content,
        "contentData": content,
        "Name": "Local Story",
        "name": "Local Story",
        "Level": 0,
        "level": 0,
        "ProgressionLevelReached": 0,
        "progressionLevelReached": 0,
        "ProgressionTowardsNextLevel": 0,
        "progressionTowardsNextLevel": 0,
        "TotalProgressionEarned": 0,
        "totalProgressionEarned": 0,
        "TotalProgressionNeeded": 0,
        "totalProgressionNeeded": 0,
        "XPToComplete": 0,
        "xpToComplete": 0,
        "IsActive": True,
        "isActive": True,
        "IsComplete": False,
        "isComplete": False,
        "Rewards": [],
        "rewards": [],
        "Chapters": [],
        "chapters": [],
        "Missions": [],
        "missions": [],
    }
    progression["Contract"] = dict(progression)
    progression["contract"] = progression["Contract"]
    return progression


def remap_contract_payload(value: Any, contract_id: str, name: str) -> Any:
    if isinstance(value, dict):
        return {key: remap_contract_payload(item, contract_id, name) for key, item in value.items()}
    if isinstance(value, list):
        return [remap_contract_payload(item, contract_id, name) for item in value]
    if value == LOCAL_STORY_CONTRACT_ID:
        return contract_id
    if value == "Local Story":
        return name
    return value


def zero_contract_model_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    return remap_contract_payload(contract_model_payload(profile), ZERO_UUID, "Inactive Local Contract")


def contracts_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "Version": 0,
        "version": 0,
        "Contracts": [],
        "contracts": [],
        "ActiveStoryContractID": ZERO_UUID,
        "activeStoryContractID": ZERO_UUID,
        "ActiveStoryContractId": ZERO_UUID,
        "activeStoryContractId": ZERO_UUID,
        "ActiveStoryContract": None,
        "activeStoryContract": None,
        "ActiveStoryContractDefinition": None,
        "activeStoryContractDefinition": None,
        "ProcessedMatches": [],
        "processedMatches": [],
        "ActiveSpecialContractID": ZERO_UUID,
        "activeSpecialContractID": ZERO_UUID,
        "ActiveSpecialContractId": ZERO_UUID,
        "activeSpecialContractId": ZERO_UUID,
        "ActiveSpecialContract": None,
        "activeSpecialContract": None,
        "Missions": [],
        "missions": [],
        "MissionMetadata": {},
        "missionMetadata": {},
    }


def item_progression_definitions_payload(game_state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    definitions = []
    for row in loadout_content_rows(game_state):
        for item_key, item_type, name_suffix in [
            ("skin_level_id", ITEM_TYPE_SKIN_LEVEL, "Level"),
            ("chroma_id", ITEM_TYPE_SKIN_CHROMA, "Chroma"),
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


def contract_definition_payload() -> dict[str, Any]:
    content = content_data_payload(LOCAL_STORY_CONTRACT_ID, "Local Story", LOCAL_CONTRACT_ASSET)
    return {
        "ID": LOCAL_STORY_CONTRACT_ID,
        "Id": LOCAL_STORY_CONTRACT_ID,
        "UUID": LOCAL_STORY_CONTRACT_ID,
        "Uuid": LOCAL_STORY_CONTRACT_ID,
        "uuid": LOCAL_STORY_CONTRACT_ID,
        "Guid": LOCAL_STORY_CONTRACT_ID,
        "guid": LOCAL_STORY_CONTRACT_ID,
        "ContractID": LOCAL_STORY_CONTRACT_ID,
        "contractID": LOCAL_STORY_CONTRACT_ID,
        "ContractId": LOCAL_STORY_CONTRACT_ID,
        "contractId": LOCAL_STORY_CONTRACT_ID,
        "ContractDefinitionID": LOCAL_STORY_CONTRACT_ID,
        "contractDefinitionID": LOCAL_STORY_CONTRACT_ID,
        "ContractDefinitionId": LOCAL_STORY_CONTRACT_ID,
        "contractDefinitionId": LOCAL_STORY_CONTRACT_ID,
        "DataAssetID": LOCAL_STORY_CONTRACT_ID,
        "dataAssetID": LOCAL_STORY_CONTRACT_ID,
        "DataAssetId": LOCAL_STORY_CONTRACT_ID,
        "dataAssetId": LOCAL_STORY_CONTRACT_ID,
        "DataAsset": LOCAL_CONTRACT_ASSET,
        "dataAsset": LOCAL_CONTRACT_ASSET,
        "DataAssetPath": LOCAL_CONTRACT_ASSET,
        "dataAssetPath": LOCAL_CONTRACT_ASSET,
        "AssetName": LOCAL_CONTRACT_ASSET,
        "assetName": LOCAL_CONTRACT_ASSET,
        "AssetPath": LOCAL_CONTRACT_ASSET,
        "assetPath": LOCAL_CONTRACT_ASSET,
        "Name": "Local Story",
        "name": "Local Story",
        "Content": content,
        "content": content,
        "ContentData": content,
        "contentData": content,
        "Chapters": [],
        "chapters": [],
        "Missions": [],
        "missions": [],
        "Rewards": [],
        "rewards": [],
    }


def contract_definitions_payload(game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "Definitions": [],
        "ContractDefinitions": [],
        "definitions": [],
        "contractDefinitions": [],
        "ActiveStoryContractDefinition": None,
        "activeStoryContractDefinition": None,
        "NPEContractID": ZERO_UUID,
        "npeContractID": ZERO_UUID,
        "NPEContractId": ZERO_UUID,
        "npeContractId": ZERO_UUID,
        "ItemProgressionDefinitions": [],
        "itemProgressionDefinitions": [],
    }


def active_story_contract_definition_payload(game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = contract_definitions_payload(game_state)
    return {
        "ActiveStoryContractDefinition": payload["ActiveStoryContractDefinition"],
        "activeStoryContractDefinition": payload["activeStoryContractDefinition"],
        "ContractDefinition": payload["ActiveStoryContractDefinition"],
        "contractDefinition": payload["activeStoryContractDefinition"],
        "Definitions": payload["Definitions"],
        "definitions": payload["definitions"],
        "ContractDefinitions": payload["ContractDefinitions"],
        "contractDefinitions": payload["contractDefinitions"],
        "NPEContractID": payload["NPEContractID"],
        "npeContractID": payload["npeContractID"],
    }


def json_api_event(uri: str, data: Any, event_type: str = "Update") -> dict[str, Any]:
    return {
        "data": data,
        "eventType": event_type,
        "uri": uri,
    }


def rms_resource_messages(service: str, pairs: list[tuple[str, str, Any]]) -> list[dict[str, Any]]:
    messages = []
    for message_id, resource, data in pairs:
        messages.append(json_api_event(resource, data))
        rms_uri = "/riot-messaging-service/v1/message" + resource
        messages.append(json_api_event(rms_uri, data))
        messages.append(
            json_api_event(
                "/riot-messaging-service/v1/message",
                {
                    "id": message_id,
                    "product": "ares",
                    "service": service,
                    "resource": resource,
                    "eventType": "Update",
                    "payload": json.dumps(data, separators=(",", ":")),
                    "data": data,
                },
                "Create",
            )
        )
    return messages


def rms_party_messages(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    profile = profile or default_profile()
    party_id = party_id_for_profile(profile)
    player = party_player_payload(game_state, profile, party_id)
    party = party_payload(game_state, party_id, profile)
    pairs = [
        ("local-party-player-update", f"/ares-parties/parties/v1/players/{profile['subject']}", player),
        ("local-party-party-update", f"/ares-parties/parties/v1/parties/{party_id}", party),
        ("local-party-player-v1-update", f"/v1/players/{profile['subject']}", player),
        ("local-party-party-v1-update", f"/v1/parties/{party_id}", party),
    ]
    messages = []
    for message_id, resource, data in pairs:
        messages.append(json_api_event(resource, data))
        if resource.startswith("/ares-parties/"):
            rms_uri = "/riot-messaging-service/v1/message" + resource
        else:
            rms_uri = "/riot-messaging-service/v1/message/ares-parties/parties" + resource
        messages.append(json_api_event(rms_uri, data))
        messages.append(
            json_api_event(
                "/riot-messaging-service/v1/message",
                {
                    "id": message_id,
                    "product": "ares",
                    "service": "ares-parties",
                    "resource": resource,
                    "eventType": "Update",
                    "payload": json.dumps(data, separators=(",", ":")),
                    "data": data,
                },
                "Create",
            )
        )
    return messages


def rms_match_messages(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    profile = profile or default_profile()
    if not game_state:
        return []
    if game_state.get("phase") == "pregame":
        player = pregame_player_payload(game_state, profile)
        match = pregame_match_payload(game_state, profile)
        return rms_resource_messages(
            "ares-pregame",
            [
                ("local-pregame-player-update", f"/ares-pregame/pregame/v1/players/{profile['subject']}", player),
                ("local-pregame-match-update", f"/ares-pregame/pregame/v1/matches/{MATCH_ID}", match),
            ],
        )
    if game_state.get("phase") == "core":
        player = core_game_player_payload(game_state, profile)
        match = core_game_match_payload(game_state, profile)
        return rms_resource_messages(
            "ares-core-game",
            [
                ("local-core-player-update", f"/ares-core-game/core-game/v1/players/{profile['subject']}", player),
                ("local-core-match-update", f"/ares-core-game/core-game/v1/matches/{MATCH_ID}", match),
            ],
        )
    return []


def chat_presence_events(game_state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return [
        json_api_event("/chat/v4/presences", presences_payload(game_state)),
    ]


def joined_chat_rooms_for_profile(game_state: dict[str, Any] | None, profile: dict[str, str] | None = None) -> set[str]:
    if not game_state:
        return set()
    if profile:
        by_subject = game_state.get("joined_chat_rooms_by_subject")
        if isinstance(by_subject, dict):
            rooms = by_subject.get(profile["subject"], [])
            if isinstance(rooms, list):
                return {str(cid) for cid in rooms if cid}
        return set()
    rooms = game_state.get("joined_chat_rooms")
    if isinstance(rooms, list):
        return {str(cid) for cid in rooms if cid}
    return set()


def profile_has_joined_chat_room(game_state: dict[str, Any] | None, profile: dict[str, str], cid: str | None) -> bool:
    return bool(cid) and str(cid) in joined_chat_rooms_for_profile(game_state, profile)


def chat_room_infos(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    room_profile = profile or default_profile()
    current_party_id = party_id_for_profile(room_profile)
    profiles = party_profiles(game_state, current_party_id, room_profile)
    participant_pids = [profile["chat_pid"] for profile in profiles]
    joined_rooms = joined_chat_rooms_for_profile(game_state, room_profile)
    party_room = party_muc_name(current_party_id)
    rooms = [
        {
            "Cid": party_room,
            "cid": party_room,
            "id": party_room,
            "RoomID": party_room,
            "roomID": party_room,
            "RoomId": party_room,
            "roomId": party_room,
            "type": "groupchat",
            "Type": "groupchat",
            "RoomType": "GroupChat",
            "roomType": "GroupChat",
            "name": "Party",
            "Name": "Party",
            "mucName": party_room,
            "MUCName": party_room,
            "room": party_room,
            "Room": party_room,
            "message_history": True,
            "ConnectionWasInitiated": True,
            "connectionWasInitiated": True,
            "ConnectionWasConfirmed": True,
            "connectionWasConfirmed": True,
            "Subject": room_profile["subject"],
            "subject": room_profile["subject"],
            "TeamId": "",
            "TeamID": "",
            "teamId": "",
            "Side": "",
            "side": "",
            "uiState": {"hidden": False, "changedSinceHidden": False},
            "unreadCount": 0,
            "unread_count": 0,
            "muted": False,
            "Muted": False,
            "participants": participant_pids,
            "Participants": participant_pids,
        },
    ]
    if game_state and game_state.get("phase") in {"pregame", "core"}:
        rooms.extend(
            [
                {
                    "Cid": TEAM_MUC_NAME,
                    "cid": TEAM_MUC_NAME,
                    "id": TEAM_MUC_NAME,
                    "RoomID": TEAM_MUC_NAME,
                    "roomID": TEAM_MUC_NAME,
                    "RoomId": TEAM_MUC_NAME,
                    "roomId": TEAM_MUC_NAME,
                    "type": "groupchat",
                    "Type": "groupchat",
                    "RoomType": "GroupChat",
                    "roomType": "GroupChat",
                    "name": "Team",
                    "Name": "Team",
                    "mucName": TEAM_MUC_NAME,
                    "MUCName": TEAM_MUC_NAME,
                    "room": TEAM_MUC_NAME,
                    "Room": TEAM_MUC_NAME,
                    "message_history": True,
                    "ConnectionWasInitiated": True,
                    "connectionWasInitiated": True,
                    "ConnectionWasConfirmed": True,
                    "connectionWasConfirmed": True,
                    "Subject": room_profile["subject"],
                    "subject": room_profile["subject"],
                    "TeamId": "Blue",
                    "TeamID": "Blue",
                    "teamId": "Blue",
                    "Side": "Blue",
                    "side": "Blue",
                    "uiState": {"hidden": False, "changedSinceHidden": False},
                    "unreadCount": 0,
                    "unread_count": 0,
                    "muted": False,
                    "Muted": False,
                    "participants": participant_pids,
                    "Participants": participant_pids,
                },
                {
                    "Cid": ALL_MUC_NAME,
                    "cid": ALL_MUC_NAME,
                    "id": ALL_MUC_NAME,
                    "RoomID": ALL_MUC_NAME,
                    "roomID": ALL_MUC_NAME,
                    "RoomId": ALL_MUC_NAME,
                    "roomId": ALL_MUC_NAME,
                    "type": "groupchat",
                    "Type": "groupchat",
                    "RoomType": "GroupChat",
                    "roomType": "GroupChat",
                    "name": "All",
                    "Name": "All",
                    "mucName": ALL_MUC_NAME,
                    "MUCName": ALL_MUC_NAME,
                    "room": ALL_MUC_NAME,
                    "Room": ALL_MUC_NAME,
                    "message_history": True,
                    "ConnectionWasInitiated": True,
                    "connectionWasInitiated": True,
                    "ConnectionWasConfirmed": True,
                    "connectionWasConfirmed": True,
                    "Subject": room_profile["subject"],
                    "subject": room_profile["subject"],
                    "TeamId": "",
                    "TeamID": "",
                    "teamId": "",
                    "Side": "",
                    "side": "",
                    "uiState": {"hidden": False, "changedSinceHidden": False},
                    "unreadCount": 0,
                    "unread_count": 0,
                    "muted": False,
                    "Muted": False,
                    "participants": participant_pids,
                    "Participants": participant_pids,
                },
            ]
        )
    filtered_rooms = []
    for room in rooms:
        room_cid = str(room.get("cid") or room.get("Cid") or "")
        if room_cid not in joined_rooms:
            continue
        participants = chat_participants_for_room(game_state, room["cid"], room_profile)
        room["MUCParticipants"] = participants
        room["mucParticipants"] = participants
        filtered_rooms.append(room)
    return filtered_rooms


def join_chat_room(game_state: dict[str, Any], cid: str | None, profile: dict[str, str] | None = None) -> bool:
    if not cid:
        return False
    if profile:
        by_subject = game_state.setdefault("joined_chat_rooms_by_subject", {})
        if isinstance(by_subject, dict):
            rooms = by_subject.setdefault(profile["subject"], [])
            if isinstance(rooms, list) and cid not in rooms:
                rooms.append(cid)
                return True
            return False
    rooms = game_state.setdefault("joined_chat_rooms", [])
    if isinstance(rooms, list) and cid not in rooms:
        rooms.append(cid)
        return True
    return False


def chat_conversation_list(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    return chat_room_infos(game_state, profile)


def chat_conversations_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    conversations = chat_conversation_list(game_state, profile)
    return {
        "Conversations": conversations,
        "conversations": conversations,
        "MUCInfos": conversations,
        "mucInfos": conversations,
        "Scopes": [],
        "scopes": [],
    }


def chat_conversation_for_cid_payload(
    game_state: dict[str, Any] | None = None,
    cid: str | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    rooms = chat_room_infos(game_state, profile)
    if cid:
        rooms = [room for room in rooms if room.get("Cid") == cid or room.get("cid") == cid]
    room = rooms[0] if rooms else {}
    payload = dict(room)
    payload.update(
        {
            "MUCInfo": room,
            "mucInfo": room,
            "Conversation": room,
            "conversation": room,
        }
    )
    return payload


def chat_participants_for_room(
    game_state: dict[str, Any] | None = None,
    cid: str | None = None,
    profile: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    profile = profile or default_profile()
    room = cid or party_muc_name(party_id_for_profile(profile))
    room_party_id = party_id_from_muc(room) or party_id_for_profile(profile)
    participants = []
    for participant_profile in party_profiles(game_state, room_party_id, profile):
        participant = {
            "Cid": room,
            "cid": room,
            "CID": room,
            "RoomID": room,
            "roomID": room,
            "RoomId": room,
            "roomId": room,
            "Pid": participant_profile["chat_pid"],
            "pid": participant_profile["chat_pid"],
            "PID": participant_profile["chat_pid"],
            "Jid": participant_profile["chat_full_pid"],
            "jid": participant_profile["chat_full_pid"],
            "JID": participant_profile["chat_full_pid"],
            "puuid": participant_profile["subject"],
            "Puuid": participant_profile["subject"],
            "Subject": participant_profile["subject"],
            "subject": participant_profile["subject"],
            "Name": participant_profile["game_name"],
            "name": participant_profile["game_name"],
            "Nick": participant_profile["display_name"],
            "nick": participant_profile["display_name"],
            "GameName": participant_profile["game_name"],
            "gameName": participant_profile["game_name"],
            "game_name": participant_profile["game_name"],
            "GameTag": participant_profile["tag_line"],
            "gameTag": participant_profile["tag_line"],
            "game_tag": participant_profile["tag_line"],
            "TagLine": participant_profile["tag_line"],
            "tagLine": participant_profile["tag_line"],
            "DisplayName": participant_profile["display_name"],
            "displayName": participant_profile["display_name"],
            "display_name": participant_profile["display_name"],
            "region": DEFAULT_REGION,
            "resource": CHAT_RESOURCE,
            "Resource": CHAT_RESOURCE,
            "Product": "valorant",
            "product": "valorant",
            "Affiliation": "member",
            "affiliation": "member",
            "Presence": presence_payload(game_state, participant_profile),
            "presence": presence_payload(game_state, participant_profile),
            "muted": False,
            "Muted": False,
            "role": "participant",
            "Role": "participant",
        }
        participants.append(participant)
    return participants


def chat_muc_participants_for_room(game_state: dict[str, Any] | None = None, cid: str | None = None) -> list[dict[str, Any]]:
    return chat_participants_for_room(game_state, cid)


def chat_participants_payload(
    game_state: dict[str, Any] | None = None,
    cid: str | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    rooms = chat_room_infos(game_state, profile)
    if cid:
        rooms = [room for room in rooms if room.get("Cid") == cid or room.get("cid") == cid]
    participants = []
    for room in rooms:
        room_participants = chat_participants_for_room(game_state, room["cid"], profile)
        participants.extend(room_participants)
    first_participant = participants[0] if participants else None
    return {
        "MUCParticipants": participants,
        "mucParticipants": participants,
        "MUCParticipant": first_participant,
        "mucParticipant": first_participant,
        "Participants": participants,
        "participants": participants,
        "Participant": first_participant,
        "participant": first_participant,
    }


def chat_participants_uri(cid: str | None = None) -> str:
    base = "/chat/v5/participants"
    if cid:
        return f"{base}?cid={cid}"
    return base


def friend_requests_payload() -> dict[str, Any]:
    return {
        "InboundFriendRequests": [],
        "inboundFriendRequests": [],
        "OutboundFriendRequests": [],
        "outboundFriendRequests": [],
        "FriendRequests": [],
        "friendRequests": [],
        "Requests": [],
        "requests": [],
    }


def chat_messages_payload(game_state: dict[str, Any] | None = None, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    messages = messages or []
    return {"messages": messages, "Messages": messages, "MUCMessages": messages, "mucMessages": messages}


def chat_message_payload(body: dict[str, Any], profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    room = body.get("Cid") or body.get("cid") or body.get("Room") or body.get("room") or party_muc_name(party_id_for_profile(profile))
    text = body.get("Message") or body.get("message") or body.get("Body") or body.get("body") or ""
    message_type = body.get("Type") or body.get("type") or "GroupChat"
    if str(message_type).lower() == "chat":
        message_type = "GroupChat"
    elif str(message_type).lower() == "groupchat":
        message_type = "GroupChat"
    message_id = f"local-msg-{int(time.time() * 1000)}"
    created = utc_now()
    return {
        "Id": message_id,
        "id": message_id,
        "Cid": room,
        "cid": room,
        "Pid": profile["chat_pid"],
        "pid": profile["chat_pid"],
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "Name": profile["game_name"],
        "name": profile["game_name"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "GameName": profile["game_name"],
        "gameName": profile["game_name"],
        "GameTag": profile["tag_line"],
        "gameTag": profile["tag_line"],
        "resource": CHAT_RESOURCE,
        "Body": text,
        "body": text,
        "Type": message_type,
        "type": message_type,
        "MessageType": message_type,
        "messageType": message_type,
        "Read": True,
        "read": True,
        "Time": created,
        "time": created,
        "CreatedDatetime": created,
        "createdDatetime": created,
    }


def session_events(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    profile = profile or default_profile()
    session = session_payload(game_state, profile)
    return [
        json_api_event(f"/session/v1/sessions/{profile['subject']}", session),
        json_api_event("/riot-messaging-service/v1/session", {"state": "connected", "connected": True}),
    ]


def ensure_cert(cert_path: Path, key_path: Path, ca_cert_path: Path) -> None:
    if cert_path.exists() and key_path.exists() and ca_cert_path.exists():
        return

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    import datetime as dt
    import ipaddress

    now = dt.datetime.now(dt.timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "Project A Local Probe CA"),
        ]
    )
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1"),
        ]
    )
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_subject)
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                    # Riot domains redirected via hosts file
                    x509.DNSName("*.riotgames.com"),
                    x509.DNSName("*.accounts.riotgames.com"),
                    x509.DNSName("stage.auth.accounts.riotgames.com"),
                    x509.DNSName("auth.riotgames.com"),
                    x509.DNSName("*.a.pvp.net"),
                    x509.DNSName("*.na1.a.pvp.net"),
                    x509.DNSName("*.dev1.a.pvp.net"),
                    x509.DNSName("*.pvp.net"),
                    x509.DNSName("pvp.net"),
                    x509.DNSName("*.riotgames.io"),
                    x509.DNSName("riotgames.io"),
                    x509.DNSName("*.service.riotgames.com"),
                ]
            ),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(
        server_cert.public_bytes(serialization.Encoding.PEM)
        + ca_cert.public_bytes(serialization.Encoding.PEM)
    )
    key_path.write_bytes(
        server_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    ca_cert_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))


class DualProtocolHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler_cls: type[BaseHTTPRequestHandler], ssl_context: ssl.SSLContext):
        self.ssl_context = ssl_context
        super().__init__(server_address, handler_cls)

    def get_request(self) -> tuple[socket.socket, tuple[str, int]]:
        sock, addr = self.socket.accept()
        first = sock.recv(1, socket.MSG_PEEK)
        if first == b"\x16":
            sock = self.ssl_context.wrap_socket(sock, server_side=True)
        return sock, addr


class ProbeHandler(BaseHTTPRequestHandler):
    server_version = "RNetProbe/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _read_body(self) -> bytes:
        length = int(self.headers.get("content-length") or "0")
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _profile_from_request(self, path: str = "", body: dict[str, Any] | None = None) -> dict[str, str]:
        auth = self.headers.get("authorization") or ""
        token = ""
        if auth.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8", "replace")
                token = decoded.rsplit(":", 1)[-1]
            except Exception:
                token = ""
        elif auth.lower().startswith("bearer "):
            bearer = auth.split(" ", 1)[1]
            for bare, prefix in (
                ("local-access-token", "local-access-token-"),
                ("local-entitlements-token", "local-entitlements-token-"),
            ):
                if bearer == bare:
                    token = "developer"
                    break
                if bearer.startswith(prefix):
                    token = bearer[len(prefix) :]
                    break
        if not token:
            subject_match = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", path)
            if subject_match:
                account = ACCOUNT_STORE.get_account_by_subject(subject_match.group(0))
                if account:
                    token = account.account_key
        if not token and isinstance(body, dict):
            for field in ("Subject", "subject", "puuid", "Puuid"):
                raw = body.get(field)
                if isinstance(raw, str):
                    account = ACCOUNT_STORE.get_account_by_subject(raw)
                    if account:
                        token = account.account_key
                if token:
                    break
        return profile_by_key(token)

    def _current_profile(self) -> dict[str, str]:
        return getattr(self, "profile", default_profile())

    def _access_token_payload(self) -> dict[str, Any]:
        key = self._current_profile()["key"]
        suffix = "" if key == "developer" else f"-{key}"
        token = f"local-access-token{suffix}"
        return {"token": token, "access_token": token, "expires_in": 3600}

    def _entitlements_token_payload(self) -> dict[str, Any]:
        key = self._current_profile()["key"]
        suffix = "" if key == "developer" else f"-{key}"
        token = f"local-entitlements-token{suffix}"
        return {"entitlements_token": token, "token": token}

    def _write(self, status: int, body: Any, content_type: str = "application/json", localize: bool = True) -> None:
        if localize and isinstance(body, (dict, list)):
            body = localize_payload(body, self._current_profile())
        if isinstance(body, (dict, list)):
            raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
        elif isinstance(body, str):
            raw = body.encode("utf-8")
        else:
            raw = bytes(body)
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(raw)))
        self.send_header("connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        self._record_response(status, raw, content_type)

    def _base_url(self) -> str:
        host = self.headers.get("host") or f"127.0.0.1:{self.server.server_address[1]}"
        return f"https://{host}"

    def _config_payload(self) -> dict[str, Any]:
        base = self._base_url()
        collapsed = {
            "SERVICEURL_AGGSTATS": base,
            "SERVICEURL_CHAT": base,
            "SERVICEURL_CONTENT": base,
            "SERVICEURL_CONTRACT_DEFINITIONS": base,
            "SERVICEURL_CONTRACTS": base,
            "SERVICEURL_COREGAME": base,
            "SERVICEURL_FRIENDS": base,
            "SERVICEURL_LATENCY": base,
            "SERVICEURL_MATCHDETAILS": base,
            "SERVICEURL_MATCHHISTORY": base,
            "SERVICEURL_MATCHMAKING": base,
            "SERVICEURL_MMR": base,
            "SERVICEURL_NAME": base,
            "SERVICEURL_PARTY": base,
            "SERVICEURL_PATCHNOTES": base,
            "SERVICEURL_PERSONALIZATION": base,
            "SERVICEURL_PLAYERFEEDBACK": base,
            "SERVICEURL_PREGAME": base,
            "SERVICEURL_RESTRICTIONS": base,
            "SERVICEURL_SESSION": base,
            "SERVICEURL_SOCIAL": base,
            "SERVICEURL_STORE": base,
            "GAME_ROAMINGSETTINGS_ENABLED": False,
            "chat.enabled": True,
            "chat.affinities.enabled": True,
            "collection.playercards.enabled": True,
            "collection.playertitles.enabled": True,
            "content.maps.disabled": False,
            "customgame.config.interval": 30,
            "friends.enabled": True,
            "gnt.enabled": True,
            "matchmaking.testqueue.enabled": True,
            "partyinvites.enabled": True,
            "queue.competitive.default": "competitive",
            "queue.status.config.interval": 30,
            "queue.status.enabled": True,
            "queue.status.update.interval": 30,
            "rchat-blocking.enabled": True,
            "social.enabled": True,
            "playerFeedbackToolURL": base,
            "playerFeedbackToolAccessURL": base,
            "playerFeedbackToolLocale": PLAYER_FEEDBACK_LOCALE,
            "playerFeedbackToolShard": PLAYER_FEEDBACK_SHARD,
            "playerfeedbacktool.accessurl": base,
            "playerfeedbacktool.url": base,
            "playerfeedbacktool.locale": PLAYER_FEEDBACK_LOCALE,
            "playerfeedbacktool.shard": PLAYER_FEEDBACK_SHARD,
            "playerfeedbacktool.enabled": True,
            "antiAddiction.allowFailures": True,
            "playtime.notifications.enabled": False,
            "playtime.restricted": False,
            # Compatibility switches: some builds probe these optional keys.
            "vanguard.enabled": False,
            "vanguard.required": False,
            "anticheat.enabled": False,
            "anticheat.required": False,
            "ares.vanguard.enabled": False,
            "ares.vanguard.required": False,
            "ares.anticheat.enabled": False,
            "ares.anticheat.required": False,
            "partyinvites.enabled": True,
            "customgame.config.interval": 300,
            "ping.useGamePodsFromParties": False,
            "ping.gamePods": "",
        }
        payload = {
            "LastApplication": "ares",
            "Collapsed": collapsed,
        }
        payload.update(collapsed)
        return payload

    def _process_control_payload(self) -> dict[str, Any]:
        pid = 1
        for key in ("x-riot-clientpid", "x-process-id", "x-riot-pid"):
            raw = self.headers.get(key)
            if raw and raw.isdigit():
                pid = int(raw)
                break
        return {
            "name": "Riot Client",
            "pid": pid,
            "processId": pid,
            "id": pid,
            "state": "Running",
            "status": "Running",
            "isRunning": True,
            "running": True,
            "started": True,
            "exited": False,
            "exitCode": 0,
            "commandLine": "",
        }

    def _plugin_manager_payload(self) -> dict[str, Any]:
        plugins = [
            {"name": "rso-auth", "state": "running", "status": "running", "running": True, "version": "local"},
            {"name": "riot-messaging-service", "state": "running", "status": "running", "running": True, "version": "local"},
            {"name": "process-control", "state": "running", "status": "running", "running": True, "version": "local"},
            {"name": "config-service", "state": "running", "status": "running", "running": True, "version": "local"},
            {"name": "vanguard", "state": "running", "status": "running", "running": True, "version": "local"},
        ]
        return {
            "state": "PluginsInitialized",
            "status": "PluginsInitialized",
            "initializationState": "PluginsInitialized",
            "isInitialized": True,
            "plugins": plugins,
            "pluginStatuses": {p["name"]: p["state"] for p in plugins},
        }

    def _record(self, body: bytes) -> None:
        parsed = urlparse(self.path)
        body_text = body.decode("utf-8", "replace")
        auth = self.headers.get("authorization")
        auth_decoded = None
        if auth and auth.lower().startswith("basic "):
            try:
                auth_decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8", "replace")
            except Exception as exc:  # pragma: no cover - diagnostic path
                auth_decoded = f"<decode failed: {exc}>"
        entry = {
            "ts": time.time(),
            "client": self.client_address[0],
            "client_port": self.client_address[1],
            "profile_id": self._current_profile()["key"],
            "subject": self._current_profile()["subject"],
            "method": self.command,
            "path": parsed.path,
            "query": parsed.query,
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "auth_decoded": auth_decoded,
            "body": body_text[:64000],
            "body_length": len(body_text),
            "body_truncated": len(body_text) > 64000,
        }
        with self.server.log_lock:
            with self.server.request_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")

    def _record_response(self, status: int, body: bytes, content_type: str) -> None:
        parsed = urlparse(self.path)
        body_text = body.decode("utf-8", "replace")
        entry = {
            "ts": time.time(),
            "client": self.client_address[0],
            "client_port": self.client_address[1],
            "profile_id": self._current_profile()["key"],
            "subject": self._current_profile()["subject"],
            "response": True,
            "path": parsed.path,
            "status": status,
            "content_type": content_type,
            "body": body_text[:12000],
            "body_length": len(body_text),
            "body_truncated": len(body_text) > 12000,
        }
        with self.server.log_lock:
            with self.server.request_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")

    def _record_ws(self, direction: str, payload: Any) -> None:
        entry = {
            "ts": time.time(),
            "client": self.client_address[0],
            "client_port": self.client_address[1],
            "profile_id": self._current_profile()["key"],
            "subject": self._current_profile()["subject"],
            "websocket": True,
            "direction": direction,
            "payload": payload,
        }
        with self.server.log_lock:
            with self.server.request_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")

    def _ws_read_exact(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self.rfile.read(n - len(data))
            if not chunk:
                raise ConnectionError("websocket closed while reading")
            data += chunk
        return data

    def _ws_read_frame(self) -> tuple[int, bytes]:
        header = self._ws_read_exact(2)
        opcode = header[0] & 0x0F
        masked = bool(header[1] & 0x80)
        length = header[1] & 0x7F
        if length == 126:
            length = int.from_bytes(self._ws_read_exact(2), "big")
        elif length == 127:
            length = int.from_bytes(self._ws_read_exact(8), "big")
        mask = self._ws_read_exact(4) if masked else b""
        payload = self._ws_read_exact(length) if length else b""
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    def _ws_write_frame(self, opcode: int, payload: bytes) -> None:
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(length)
        elif length <= 0xFFFF:
            header.append(126)
            header += length.to_bytes(2, "big")
        else:
            header.append(127)
            header += length.to_bytes(8, "big")
        self.wfile.write(bytes(header) + payload)
        self.wfile.flush()

    def _ws_send_json(self, message: list[Any]) -> None:
        lock = getattr(self, "ws_write_lock", None)
        if lock is None:
            self._record_ws("out", message)
            self._ws_write_frame(1, json.dumps(message, separators=(",", ":")).encode("utf-8"))
            return
        with lock:
            self._record_ws("out", message)
            self._ws_write_frame(1, json.dumps(message, separators=(",", ":")).encode("utf-8"))

    def _ws_send_wampv1_event(self, topic: str, event: Any) -> None:
        self._ws_send_json([8, topic, event])

    def _broadcast_wampv1_event(self, topic: str, event: Any) -> None:
        with self.server.ws_lock:
            clients = list(self.server.ws_clients)
        for client in clients:
            if topic not in getattr(client, "ws_topics", set()):
                continue
            try:
                client._ws_send_wampv1_event(topic, event)
            except Exception as exc:
                client._record_ws("broadcast-failed", {"topic": topic, "error": str(exc)})

    def _ws_clients_for_profile(self, profile: dict[str, str]) -> list["ProbeHandler"]:
        subject = profile.get("subject")
        with self.server.ws_lock:
            clients = list(self.server.ws_clients)
        return [
            client
            for client in clients
            if (getattr(client, "profile", None) or default_profile()).get("subject") == subject
        ]

    def _send_wampv1_event_to_profile(
        self,
        profile: dict[str, str],
        topic: str,
        event: Any,
        required_topics: set[str] | None = None,
    ) -> None:
        for client in self._ws_clients_for_profile(profile):
            topics = getattr(client, "ws_topics", set())
            if topic not in topics:
                continue
            if required_topics and not required_topics.issubset(topics):
                continue
            try:
                client._ws_send_wampv1_event(topic, event)
            except Exception as exc:
                client._record_ws("profile-broadcast-failed", {"topic": topic, "error": str(exc)})

    def _activate_chat_room(self, cid: str | None) -> None:
        if not cid:
            return
        profile = self._current_profile()
        game_state = self.server.game_state
        join_chat_room(game_state, cid, profile)
        self._send_wampv1_event_to_profile(
            profile,
            "OnJsonApiEvent_chat_v5_conversations",
            json_api_event("/chat/v5/conversations", chat_conversations_payload(game_state, profile), "Update"),
        )
        self._send_wampv1_event_to_profile(
            profile,
            "OnJsonApiEvent_chat_v5_participants",
            json_api_event(chat_participants_uri(), chat_participants_payload(game_state, None, profile), "Update"),
            {"OnJsonApiEvent_chat_v5_conversations"},
        )
        self._send_wampv1_event_to_profile(
            profile,
            "OnJsonApiEvent_chat_v5_participants",
            json_api_event(chat_participants_uri(cid), chat_participants_payload(game_state, cid, profile), "Update"),
            {"OnJsonApiEvent_chat_v5_conversations"},
        )

    def _broadcast_social_roster_update(self) -> None:
        game_state = self.server.game_state
        with self.server.ws_lock:
            clients = list(self.server.ws_clients)
        for client in clients:
            topics = getattr(client, "ws_topics", set())
            client_profile = getattr(client, "profile", None) or default_profile()
            rooms = chat_room_infos(game_state, client_profile)
            try:
                if "OnJsonApiEvent_chat_v5_conversations" in topics:
                    client._ws_send_wampv1_event(
                        "OnJsonApiEvent_chat_v5_conversations",
                        json_api_event("/chat/v5/conversations", chat_conversations_payload(game_state, client_profile), "Update"),
                    )
                if "OnJsonApiEvent_chat_v5_participants" in topics and "OnJsonApiEvent_chat_v5_conversations" in topics:
                    client._ws_send_wampv1_event(
                        "OnJsonApiEvent_chat_v5_participants",
                        json_api_event(chat_participants_uri(), chat_participants_payload(game_state, None, client_profile), "Update"),
                    )
                    for room in rooms:
                        cid = str(room.get("cid") or room.get("Cid") or "")
                        if cid:
                            client._ws_send_wampv1_event(
                                "OnJsonApiEvent_chat_v5_participants",
                                json_api_event(chat_participants_uri(cid), chat_participants_payload(game_state, cid, client_profile), "Update"),
                            )
                if "OnJsonApiEvent_chat_v4_presences" in topics:
                    client._ws_send_wampv1_event(
                        "OnJsonApiEvent_chat_v4_presences",
                        json_api_event("/chat/v4/presences", presences_payload(game_state), "Update"),
                    )
                if "OnJsonApiEvent_chat_v3_friends" in topics:
                    client._ws_send_wampv1_event(
                        "OnJsonApiEvent_chat_v3_friends",
                        json_api_event("/chat/v3/friends", friends_payload(game_state, client_profile), "Update"),
                    )
            except Exception as exc:
                client._record_ws("social-roster-broadcast-failed", {"error": str(exc)})

    def _broadcast_backend_state_update(self) -> None:
        game_state = self.server.game_state
        with self.server.ws_lock:
            clients = list(self.server.ws_clients)
        for client in clients:
            topics = getattr(client, "ws_topics", set())
            profile = getattr(client, "profile", None) or default_profile()
            try:
                if "OnJsonApiEvent_riot-messaging-service_v1_message" in topics:
                    for event in rms_party_messages(game_state, profile):
                        client._ws_send_wampv1_event("OnJsonApiEvent_riot-messaging-service_v1_message", event)
                    for event in rms_match_messages(game_state, profile):
                        client._ws_send_wampv1_event("OnJsonApiEvent_riot-messaging-service_v1_message", event)
                    for event in session_events(game_state, profile):
                        client._ws_send_wampv1_event("OnJsonApiEvent_riot-messaging-service_v1_message", event)
                for topic in topics:
                    if topic.startswith("OnJsonApiEvent_session_v1"):
                        for event in session_events(game_state, profile):
                            client._ws_send_wampv1_event(topic, event)
                    elif topic.startswith("OnJsonApiEvent_parties_v1") or topic.startswith("OnJsonApiEvent_ares-parties"):
                        for event in rms_party_messages(game_state, profile):
                            client._ws_send_wampv1_event(topic, event)
                    elif topic.startswith("OnJsonApiEvent_core-game_v1") or topic.startswith("OnJsonApiEvent_ares-core-game"):
                        for event in rms_match_messages(game_state, profile):
                            if "/core-game/" in event.get("uri", ""):
                                client._ws_send_wampv1_event(topic, event)
                    elif topic.startswith("OnJsonApiEvent_pregame_v1") or topic.startswith("OnJsonApiEvent_ares-pregame"):
                        for event in rms_match_messages(game_state, profile):
                            if "/pregame/" in event.get("uri", ""):
                                client._ws_send_wampv1_event(topic, event)
            except Exception as exc:
                client._record_ws("backend-state-broadcast-failed", {"error": str(exc)})

    def _ws_send_subscription_seed(self, topic: str) -> None:
        game_state = self.server.game_state
        profile = self._current_profile()
        if topic == "OnJsonApiEvent_riot-messaging-service_v1_message":
            for event in rms_party_messages(game_state, profile):
                self._ws_send_wampv1_event(topic, event)
            for event in rms_match_messages(game_state, profile):
                self._ws_send_wampv1_event(topic, event)
            for event in session_events(game_state, profile):
                self._ws_send_wampv1_event(topic, event)
        elif topic == "OnJsonApiEvent_chat_v1_session":
            self._ws_send_wampv1_event(topic, json_api_event("/chat/v1/session", chat_session_payload(profile)))
        elif topic == "OnJsonApiEvent_chat_v3_friends":
            self._ws_send_wampv1_event(topic, json_api_event("/chat/v3/friends", friends_payload(game_state, profile)))
        elif topic == "OnJsonApiEvent_chat_v4_friendrequests":
            self._ws_send_wampv1_event(
                topic,
                json_api_event("/chat/v4/friendrequests", friend_requests_payload()),
            )
        elif topic == "OnJsonApiEvent_chat_v4_presences":
            for event in chat_presence_events(game_state):
                self._ws_send_wampv1_event(topic, event)
        elif topic == "OnJsonApiEvent_chat_v5_conversations":
            self._ws_send_wampv1_event(topic, json_api_event("/chat/v5/conversations", chat_conversations_payload(game_state, profile)))
            if "OnJsonApiEvent_chat_v5_participants" in self.ws_topics:
                self._ws_send_wampv1_event(
                    "OnJsonApiEvent_chat_v5_participants",
                    json_api_event(chat_participants_uri(), chat_participants_payload(game_state, None, profile)),
                )
                for room in chat_room_infos(game_state, profile):
                    cid = str(room.get("cid") or room.get("Cid") or "")
                    if cid:
                        self._ws_send_wampv1_event(
                            "OnJsonApiEvent_chat_v5_participants",
                            json_api_event(chat_participants_uri(cid), chat_participants_payload(game_state, cid, profile)),
                        )
        elif topic == "OnJsonApiEvent_chat_v5_participants":
            if "OnJsonApiEvent_chat_v5_conversations" in self.ws_topics:
                self._ws_send_wampv1_event(topic, json_api_event(chat_participants_uri(), chat_participants_payload(game_state, None, profile)))
                for room in chat_room_infos(game_state, profile):
                    cid = str(room.get("cid") or room.get("Cid") or "")
                    if cid:
                        self._ws_send_wampv1_event(
                            topic,
                            json_api_event(chat_participants_uri(cid), chat_participants_payload(game_state, cid, profile)),
                        )
        elif topic == "OnJsonApiEvent_chat_v5_messages":
            with self.server.chat_lock:
                messages = list(self.server.chat_messages)
            self._ws_send_wampv1_event(topic, json_api_event("/chat/v5/messages", chat_messages_payload(game_state, messages)))
        elif topic == "OnJsonApiEvent_riot-messaging-service_v1_session":
            self._ws_send_wampv1_event(topic, json_api_event("/riot-messaging-service/v1/session", {"state": "connected", "connected": True}))
        elif topic.startswith("OnJsonApiEvent_session_v1"):
            for event in session_events(game_state, profile):
                self._ws_send_wampv1_event(topic, event)
        elif topic.startswith("OnJsonApiEvent_parties_v1") or topic.startswith("OnJsonApiEvent_ares-parties"):
            for event in rms_party_messages(game_state, profile):
                self._ws_send_wampv1_event(topic, event)
        elif topic.startswith("OnJsonApiEvent_core-game_v1") or topic.startswith("OnJsonApiEvent_ares-core-game"):
            for event in rms_match_messages(game_state, profile):
                if "/core-game/" in event.get("uri", ""):
                    self._ws_send_wampv1_event(topic, event)
        elif topic.startswith("OnJsonApiEvent_pregame_v1") or topic.startswith("OnJsonApiEvent_ares-pregame"):
            for event in rms_match_messages(game_state, profile):
                if "/pregame/" in event.get("uri", ""):
                    self._ws_send_wampv1_event(topic, event)

    def _handle_wamp_message(self, message: Any) -> None:
        if not isinstance(message, list) or not message:
            return
        msg_type = message[0]
        if msg_type == 0:  # WAMPv1 WELCOME, client should not send this.
            self._record_ws("wampv1-unexpected-welcome", message)
        elif msg_type == 1 and len(message) >= 3 and isinstance(message[2], dict):  # WAMPv2 HELLO
            self._ws_send_json(
                [
                    2,
                    1,
                    {
                        "roles": {
                            "broker": {"features": {}},
                            "dealer": {"features": {}},
                        }
                    },
                ]
            )
        elif msg_type == 1:  # WAMPv1 PREFIX
            self._record_ws("wampv1-prefix", message)
        elif msg_type == 2 and len(message) >= 3:  # WAMPv1 CALL
            self._ws_send_json([3, message[1], {}])
        elif msg_type == 5 and len(message) >= 2 and isinstance(message[1], str):  # WAMPv1 SUBSCRIBE
            self._record_ws("wampv1-subscribe", message[1])
            self.ws_topics.add(message[1])
            self._ws_send_subscription_seed(message[1])
        elif msg_type == 6 and len(message) >= 2 and isinstance(message[1], str):  # WAMPv1 UNSUBSCRIBE
            self._record_ws("wampv1-unsubscribe", message[1])
            self.ws_topics.discard(message[1])
        elif msg_type == 7:  # WAMPv1 PUBLISH
            self._record_ws("wampv1-publish", message)
        elif msg_type == 32 and len(message) >= 3:  # WAMPv2 SUBSCRIBE
            if len(message) >= 4 and isinstance(message[3], str):
                self.ws_topics.add(message[3])
            self._ws_send_json([33, message[1], self.server.next_ws_id()])
        elif msg_type == 34 and len(message) >= 2:  # UNSUBSCRIBE
            self._ws_send_json([35, message[1]])
        elif msg_type == 48 and len(message) >= 4:  # CALL
            self._ws_send_json([50, message[1], {}, [], {}])
        elif msg_type == 64 and len(message) >= 3:  # REGISTER
            self._ws_send_json([65, message[1], self.server.next_ws_id()])
        elif msg_type == 66 and len(message) >= 2:  # UNREGISTER
            self._ws_send_json([67, message[1]])
        elif msg_type == 6:  # GOODBYE
            self._ws_send_json([6, {}, "wamp.close.goodbye"])
            self._ws_write_frame(8, b"")
        else:
            self._record_ws("unhandled", message)

    def _handle_websocket(self) -> None:
        key = self.headers.get("sec-websocket-key")
        if not key:
            self._write(400, {"error": "missing sec-websocket-key"})
            return
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        self.send_response(101, "Switching Protocols")
        self.send_header("upgrade", "websocket")
        self.send_header("connection", "Upgrade")
        self.send_header("sec-websocket-accept", accept)
        protocol = self.headers.get("sec-websocket-protocol")
        if protocol:
            self.send_header("sec-websocket-protocol", protocol)
        self.end_headers()
        self.ws_topics = set()
        self.ws_write_lock = threading.Lock()
        with self.server.ws_lock:
            self.server.ws_clients.add(self)
        try:
            self._ws_send_json([0, "rnet-probe-session", 1, "rnet-probe"])

            while True:
                try:
                    opcode, payload = self._ws_read_frame()
                except (ConnectionError, OSError, ssl.SSLError):
                    return
                if opcode == 8:  # close
                    self._ws_write_frame(8, payload)
                    return
                if opcode == 9:  # ping
                    self._ws_write_frame(10, payload)
                    continue
                if opcode != 1:
                    self._record_ws("in-binary-or-control", {"opcode": opcode, "length": len(payload)})
                    continue
                text = payload.decode("utf-8", "replace")
                try:
                    message = json.loads(text)
                except json.JSONDecodeError:
                    self._record_ws("in-text", text)
                    continue
                self._record_ws("in", message)
                self._handle_wamp_message(message)
        finally:
            with self.server.ws_lock:
                self.server.ws_clients.discard(self)

    def _json_body(self, body: bytes) -> Any:
        if not body:
            return {}
        try:
            parsed = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, (dict, list)) else {}

    def _bump_party(self) -> None:
        self.server.game_state["party_version"] = int(self.server.game_state.get("party_version", 1)) + 1

    def _bump_match(self) -> None:
        self.server.game_state["match_version"] = int(self.server.game_state.get("match_version", 1)) + 1

    def _handle(self) -> None:
        body = self._read_body()
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)
        json_body = self._json_body(body)
        self.profile = self._profile_from_request(path, json_body)
        with self.server.profile_lock:
            new_profile = self.profile["key"] not in self.server.seen_profiles
            self.server.seen_profiles.add(self.profile["key"])
            self.server.game_state["active_profile_keys"] = sorted(self.server.seen_profiles)
        self._record(body)
        game_state = self.server.game_state
        if self.headers.get("upgrade", "").lower() == "websocket":
            self._handle_websocket()
            return
        if new_profile:
            self._broadcast_social_roster_update()
        route_path = path
        if route_path.startswith("/ares-parties/"):
            route_path = route_path[len("/ares-parties") :]
        elif route_path.startswith("/ares-pregame/"):
            route_path = route_path[len("/ares-pregame") :]
        elif route_path.startswith("/ares-core-game/"):
            route_path = route_path[len("/ares-core-game") :]
        elif route_path.startswith("/ares-contracts/"):
            route_path = route_path[len("/ares-contracts") :]
        elif route_path.startswith("/ares-personalization/"):
            route_path = route_path[len("/ares-personalization") :]

        if route_path.startswith("/client-config/v2/config/") or route_path.startswith("/v1/config/"):
            self._write(200, self._config_payload())
        elif route_path == "/process-control/v1/process":
            self._write(200, self._process_control_payload())
        elif route_path == "/process-control/v1/process/quit":
            self._write(200, {"ok": True})
        elif route_path == "/plugin-manager/v1/status":
            self._write(200, self._plugin_manager_payload())
        elif route_path == "/riotclient/region-locale":
            self._write(200, region_locale_payload())
        elif route_path in {"/rso-auth/v1/authorization/userinfo", "/userinfo"}:
            self._write(200, userinfo_payload(self._current_profile()), localize=False)
        elif route_path == "/rso-auth/v1/authorization/access-token":
            self._write(200, self._access_token_payload())
        elif route_path == "/entitlements/v1/token":
            self._write(200, self._entitlements_token_payload())
        elif route_path == "/riot-messaging-service/v1/session":
            self._write(200, {"state": "connected", "connected": True})
        elif route_path == "/riot-messaging-service/v1/out-of-sync":
            self._write(200, {"ok": True})
        elif route_path.startswith("/riot-messaging-service/v1/message"):
            self._write(200, {"ok": True})
        elif route_path == "/chat/v1/session":
            self._write(200, chat_session_payload(self._current_profile()), localize=False)
        elif route_path == "/chat/v2/me":
            profile = self._current_profile()
            updates = game_state.setdefault("presence_by_profile", {})
            if self.command in {"PUT", "POST", "PATCH"} and json_body:
                if isinstance(json_body, dict):
                    updates[profile["key"]] = {
                        key: json_body[key]
                        for key in ("actor", "basic", "details", "location", "msg", "shared", "state", "summary")
                        if key in json_body
                    }
            presence = presence_payload(game_state, profile, updates.get(profile["key"]))
            self._broadcast_social_roster_update()
            self._write(200, presence, localize=False)
        elif route_path == "/chat/v4/presences":
            self._write(200, presences_payload(game_state), localize=False)
        elif route_path.rstrip("/") == "/chat/v5/conversations/read":
            request_body = json_body if isinstance(json_body, dict) else {}
            cid = (
                request_body.get("Cid")
                or request_body.get("cid")
                or request_body.get("RoomId")
                or request_body.get("roomId")
                or request_body.get("ConversationId")
                or request_body.get("conversationId")
                or request_body.get("ConversationID")
                or request_body.get("conversationID")
                or ""
            )
            message_id = (
                request_body.get("MessageId")
                or request_body.get("messageId")
                or request_body.get("MessageID")
                or request_body.get("messageID")
                or request_body.get("LastReadMessageId")
                or request_body.get("lastReadMessageId")
                or request_body.get("Id")
                or request_body.get("id")
                or ""
            )
            self._write(200, {"ok": True, "Cid": cid, "cid": cid, "MessageId": message_id, "messageId": message_id})
        elif route_path.rstrip("/") == "/chat/v5/conversations":
            if self.command == "POST":
                profile = self._current_profile()
                request_body = json_body if isinstance(json_body, dict) else {}
                cid = request_body.get("Cid") or request_body.get("cid") or request_body.get("Room") or request_body.get("room")
                joined_now = join_chat_room(game_state, str(cid) if cid else None, profile)
                payload = chat_conversation_for_cid_payload(game_state, cid, profile)
                room_cid = str(payload.get("cid") or payload.get("Cid") or cid or "")
                self._write(200, payload, localize=False)
                if room_cid and joined_now:
                    participants = chat_participants_payload(game_state, room_cid, profile)
                    self._send_wampv1_event_to_profile(
                        profile,
                        "OnJsonApiEvent_chat_v5_conversations",
                        json_api_event("/chat/v5/conversations", chat_conversations_payload(game_state, profile), "Update"),
                    )
                    self._send_wampv1_event_to_profile(
                        profile,
                        "OnJsonApiEvent_chat_v5_participants",
                        json_api_event(chat_participants_uri(), chat_participants_payload(game_state, None, profile)),
                        {"OnJsonApiEvent_chat_v5_conversations"},
                    )
                    self._send_wampv1_event_to_profile(
                        profile,
                        "OnJsonApiEvent_chat_v5_participants",
                        json_api_event(chat_participants_uri(room_cid), participants),
                        {"OnJsonApiEvent_chat_v5_conversations"},
                    )
                return
            else:
                self._write(200, chat_conversations_payload(game_state, self._current_profile()), localize=False)
        elif route_path.startswith("/chat/v5/conversations/"):
            self._write(200, chat_conversations_payload(game_state, self._current_profile()), localize=False)
        elif route_path.rstrip("/") == "/chat/v5/participants":
            cid = (query_params.get("cid") or query_params.get("Cid") or [None])[0]
            self._write(200, chat_participants_payload(game_state, cid, self._current_profile()), localize=False)
        elif route_path.rstrip("/") == "/chat/v5/messages":
            if self.command == "POST":
                message = chat_message_payload(json_body, self._current_profile())
                with self.server.chat_lock:
                    self.server.chat_messages.append(message)
                event = json_api_event(
                    "/chat/v5/messages",
                    {"messages": [message], "Messages": [message], "MUCMessages": [message], "mucMessages": [message]},
                    "Update",
                )
                self._broadcast_wampv1_event("OnJsonApiEvent_chat_v5_messages", event)
                self._write(200, message, localize=False)
            else:
                cid = (query_params.get("cid") or query_params.get("Cid") or [None])[0]
                with self.server.chat_lock:
                    messages = list(self.server.chat_messages)
                if cid:
                    messages = [message for message in messages if message.get("Cid") == cid or message.get("cid") == cid]
                self._write(200, {"messages": messages, "Messages": messages, "MUCMessages": messages, "mucMessages": messages}, localize=False)
        elif route_path.startswith("/chat/v5/messages/") and route_path.endswith("/read"):
            self._write(200, {"ok": True})
        elif route_path == "/chat/v3/friends":
            self._write(200, friends_payload(game_state, self._current_profile()), localize=False)
        elif route_path == "/chat/v4/friendrequests":
            self._write(200, friend_requests_payload(), localize=False)
        elif route_path.startswith("/friends/v1/friends"):
            self._write(200, friends_payload(game_state, self._current_profile()), localize=False)
        elif route_path.startswith("/friends/v1/requests"):
            self._write(200, {"requests": [], "Requests": []})
        elif route_path.startswith("/rchat-blocking/v1/blocked") or route_path.startswith("/chat/v3/blocked"):
            self._write(200, {"blockedPlayers": [], "BlockedPlayers": []})
        elif route_path == "/player-account/aliases/v1/eligibility":
            self._write(200, {"errorCode": "", "errorMessage": "", "isSuccess": True, "isTagLineCustomizable": True})
        elif route_path == "/player-account/aliases/v1/active":
            profile = self._current_profile()
            self._write(
                200,
                {
                    "game_name": profile["game_name"],
                    "tag_line": profile["tag_line"],
                    "summoner": profile["game_name"],
                    "GameName": profile["game_name"],
                    "TagLine": profile["tag_line"],
                    "DisplayName": profile["display_name"],
                    "active": True,
                    "created_datetime": 0,
                },
            )
        elif route_path in {"/player-account/aliases/v1/aliases", "/player-account/aliases/v1/validity"}:
            profile = self._current_profile()
            self._write(
                200,
                {
                    "game_name": profile["game_name"],
                    "tag_line": profile["tag_line"],
                    "summoner": profile["game_name"],
                    "GameName": profile["game_name"],
                    "TagLine": profile["tag_line"],
                    "DisplayName": profile["display_name"],
                    "active": True,
                    "created_datetime": 0,
                    "errorCode": "",
                    "errorMessage": "",
                    "isSuccess": True,
                    "isTagLineCustomizable": True,
                },
            )
        elif route_path.startswith("/player-preferences/v1/data-json/"):
            self._write(200, {})
        elif route_path == "/anti-addiction/v1/products/ares/policies/shutdown/anti-addiction-state":
            self._write(200, anti_addiction_state_payload("shutdown"))
        elif route_path == "/anti-addiction/v1/products/ares/policies/playtime/anti-addiction-state":
            self._write(200, anti_addiction_state_payload("playTime"))
        elif route_path == "/anti-addiction/v1/products/ares/policies/warningMessage/anti-addiction-state":
            self._write(200, anti_addiction_state_payload("warningMessage"))
        elif route_path.startswith("/eula/v1/") or route_path.startswith("/legal/v1/"):
            self._write(200, {"content": "", "version": "local", "locale": "en_US"})
        elif route_path == "/voice-chat/v2/sessions":
            if self.command == "GET":
                self._write(200, voice_sessions_payload(game_state, self._current_profile()), localize=False)
            else:
                self._write(200, voice_session_payload(game_state, self._current_profile()), localize=False)
        elif route_path.startswith("/voice-chat/v2/sessions/"):
            self._write(200, voice_session_participants_payload(game_state, self._current_profile()), localize=False)
        elif route_path in {"/voice-chat/v2/devices/capture", "/voice-chat/v2/devices/render"}:
            self._write(200, [])
        elif route_path == "/voice-chat/v2/settings":
            self._write(200, {"inputMode": "push_to_talk", "muted": False, "volume": 1.0})
        elif route_path == "/voice-chat/v1/audio-properties":
            self._write(200, {})
        elif route_path == "/voice-chat/v1/push-to-talk":
            self._write(200, {"ok": True})
        elif re.match(r"^/session/v\d+/sessions/[^/]+/heartbeat$", route_path):
            profile = self._current_profile()
            sessions = game_state.setdefault("session_by_profile", {})
            if isinstance(sessions, dict):
                heartbeat = json_body if isinstance(json_body, dict) else {}
                sessions[profile["key"]] = {
                    "last_heartbeat": utc_now(),
                    "client_loop_state": heartbeat.get("LoopState") or heartbeat.get("loopState") or "",
                    "client_loop_state_metadata": heartbeat.get("LoopStateMetadata") or heartbeat.get("loopStateMetadata") or "",
                }
            self._broadcast_social_roster_update()
            self._write(200, session_payload(game_state, profile), localize=False)
        elif route_path.startswith("/session/v"):
            self._write(200, session_payload(game_state, self._current_profile()), localize=False)
        elif re.match(r"^/parties/v1/players/[^/]+/startsoloexperience(?:v2)?$", route_path):
            profile = self._current_profile()
            party_id = party_id_for_profile(profile)
            configure_solo_experience(game_state, json_body if isinstance(json_body, dict) else {})
            game_state["phase"] = "pregame"
            game_state["party_state"] = "SOLO_EXPERIENCE_STARTING"
            game_state["pregame_state"] = ""
            ensure_character_selections(game_state, "selected", party_profiles(game_state, party_id, profile))
            self._bump_party()
            self._bump_match()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/players/[^/]+/invites(/decline)?$", route_path):
            self._write(200, {"Invites": [], "invites": [], "Requests": [], "requests": []})
        elif route_path.startswith("/parties/v1/players/"):
            profile = self._current_profile()
            self._write(200, party_player_payload(game_state, profile, party_id_for_profile(profile)), localize=False)
        elif route_path.startswith("/parties/v1/parties/") and route_path.endswith("/customgameconfigs"):
            self._write(200, custom_game_configs_payload(game_state))
        elif re.match(r"^/parties/v1/parties/[^/]+/(join|request)$", route_path):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            ACCOUNT_STORE.join_party(profile["key"], party_id)
            self._bump_party()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/parties/[^/]+/leave$", route_path):
            profile = self._current_profile()
            party_id = ACCOUNT_STORE.leave_party(profile["key"])
            self._bump_party()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/parties/[^/]+/invites(/decline)?$", route_path):
            self._write(200, {"Invites": [], "invites": [], "Requests": [], "requests": []})
        elif re.match(r"^/parties/v1/parties/[^/]+/customgamemembership/[^/]+$", route_path):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            game_state["phase"] = "custom"
            game_state["party_state"] = "CUSTOM_GAME_SETUP"
            team = route_path.rsplit("/", 1)[-1]
            request_body = json_body if isinstance(json_body, dict) else {}
            subject = subject_from_team_request(request_body, profile["subject"])
            set_custom_team_for_subject(game_state, str(subject), team)
            self._bump_party()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/parties/[^/]+/muctoken$", route_path):
            party_id = party_id_from_route(route_path) or party_id_for_profile(self._current_profile())
            self._write(200, chat_token_payload(party_muc_name(party_id)))
        elif re.match(r"^/parties/v1/parties/[^/]+/voicetoken$", route_path):
            party_id = party_id_from_route(route_path) or party_id_for_profile(self._current_profile())
            self._write(200, voice_token_payload(party_voice_room_id(party_id)))
        elif re.match(r"^/parties/v1/parties/[^/]+/makecustomgame$", route_path):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            game_state["phase"] = "custom"
            game_state["party_state"] = "CUSTOM_GAME_SETUP"
            game_state["pregame_state"] = ""
            game_state["provisioning_flow"] = DEFAULT_PROVISIONING_FLOW
            game_state["queue"] = DEFAULT_QUEUE
            self._bump_party()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/parties/[^/]+/makedefault", route_path):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            game_state["phase"] = "menus"
            game_state["party_state"] = "DEFAULT"
            game_state["pregame_state"] = ""
            game_state["provisioning_flow"] = DEFAULT_PROVISIONING_FLOW
            game_state["queue"] = DEFAULT_QUEUE
            self._bump_party()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/parties/[^/]+/customgamesettings$", route_path):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            update_state_from_json(game_state, json_body)
            game_state["phase"] = "custom"
            game_state["party_state"] = "CUSTOM_GAME_SETUP"
            game_state["pregame_state"] = ""
            game_state["provisioning_flow"] = DEFAULT_PROVISIONING_FLOW
            self._bump_party()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/parties/[^/]+/startcustomgame$", route_path):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            game_state["phase"] = "pregame"
            game_state["party_state"] = "CUSTOM_GAME_STARTING"
            game_state["provisioning_flow"] = DEFAULT_PROVISIONING_FLOW
            ensure_character_selections(game_state, "selected", party_profiles(game_state, party_id, profile))
            self._bump_party()
            self._bump_match()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/parties/[^/]+/startsoloexperience(?:v2)?$", route_path):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            configure_solo_experience(game_state, json_body if isinstance(json_body, dict) else {})
            game_state["phase"] = "pregame"
            game_state["party_state"] = "SOLO_EXPERIENCE_STARTING"
            game_state["pregame_state"] = ""
            ensure_character_selections(game_state, "selected", party_profiles(game_state, party_id, profile))
            self._bump_party()
            self._bump_match()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/parties/[^/]+/queue$", route_path):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            game_state["queue"] = json_body.get("queueID") or json_body.get("QueueID") or DEFAULT_QUEUE
            game_state["party_state"] = "MATCHMAKING"
            self._bump_party()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/parties/[^/]+/matchmaking/join$", route_path):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            game_state["queue"] = json_body.get("queueID") or json_body.get("QueueID") or game_state.get("queue") or DEFAULT_QUEUE
            game_state["party_state"] = "MATCHMAKING"
            self._bump_party()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/parties/[^/]+/matchmaking/leave$", route_path):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            game_state["party_state"] = "DEFAULT"
            self._bump_party()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif re.match(r"^/parties/v1/parties/[^/]+/(accessibility|lookingForMore|name|cheats|balance)$", route_path):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            self._bump_party()
            self._broadcast_backend_state_update()
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif route_path.startswith("/parties/v1/parties/"):
            profile = self._current_profile()
            party_id = party_id_from_route(route_path) or party_id_for_profile(profile)
            self._write(200, party_payload(game_state, party_id, profile), localize=False)
        elif route_path == "/parties/v1/parties":
            profile = self._current_profile()
            self._write(200, party_payload(game_state, party_id_for_profile(profile), profile), localize=False)
        elif route_path == "/matchmaking/v1/queues/configs":
            self._write(200, queue_configs_payload())
        elif route_path.startswith("/matchmaking/v1/queues/"):
            self._write(200, queue_configs_payload())
        elif re.match(r"^/pregame/v1/players/[^/]+/fixsession$", route_path):
            if game_state.get("phase") not in {"pregame", "core"}:
                game_state["phase"] = "pregame"
            if game_state.get("party_state") == "SOLO_EXPERIENCE_STARTING":
                game_state["pregame_state"] = "provisioned"
            self._bump_match()
            self._broadcast_backend_state_update()
            self._write(200, pregame_player_payload(game_state, self._current_profile()), localize=False)
        elif route_path.startswith("/pregame/v1/players/"):
            if game_state.get("phase") in {"pregame", "core"}:
                self._write(200, pregame_player_payload(game_state, self._current_profile()), localize=False)
            else:
                self._write(200, inactive_match_player_payload(self._current_profile()), localize=False)
        elif route_path == "/pregame/v1/matches/" or route_path == "/pregame/v1/matches":
            if game_state.get("phase") in {"pregame", "core"}:
                self._write(200, pregame_match_payload(game_state, self._current_profile()), localize=False)
            else:
                self._write(200, inactive_match_payload())
        elif route_path == "/pregame/v1/matches//chattoken":
            self._write(200, chat_token_payload(TEAM_MUC_NAME))
        elif route_path == "/pregame/v1/matches//teamvoicetoken":
            self._write(200, voice_token_payload(TEAM_VOICE_ID))
        elif route_path == "/pregame/v1/matches//voicetoken":
            self._write(200, voice_token_payload(TEAM_VOICE_ID))
        elif re.match(r"^/pregame/v1/matches/[^/]+/chattoken$", route_path):
            self._write(200, chat_token_payload(TEAM_MUC_NAME))
        elif re.match(r"^/pregame/v1/matches/[^/]+/teamvoicetoken$", route_path):
            self._write(200, voice_token_payload(TEAM_VOICE_ID))
        elif re.match(r"^/pregame/v1/matches/[^/]+/voicetoken$", route_path):
            self._write(200, voice_token_payload(TEAM_VOICE_ID))
        elif re.match(r"^/pregame/v1/matches/[^/]+/select/[^/]+$", route_path):
            character_id = route_path.rsplit("/", 1)[-1]
            game_state["phase"] = "pregame"
            set_character_for_profile(game_state, self._current_profile(), character_id, "selected")
            self._bump_match()
            self._broadcast_backend_state_update()
            self._write(200, pregame_match_payload(game_state, self._current_profile()), localize=False)
        elif re.match(r"^/pregame/v1/matches/[^/]+/lock/[^/]+$", route_path):
            character_id = route_path.rsplit("/", 1)[-1]
            profile = self._current_profile()
            game_state["phase"] = "pregame"
            set_character_for_profile(game_state, profile, character_id, "locked")
            current_party_profiles = party_profiles(game_state, party_id_for_profile(profile), profile)
            if all(character_state_for_profile(game_state, member_profile) == "locked" for member_profile in current_party_profiles):
                game_state["pregame_state"] = "character_select_finished"
                if should_auto_start_after_lock(game_state):
                    game_state["phase"] = "core"
                    game_state["party_state"] = "SOLO_EXPERIENCE_STARTING"
                    game_state["pregame_state"] = "provisioned"
                    self._bump_party()
            self._bump_match()
            self._broadcast_backend_state_update()
            self._write(200, pregame_match_payload(game_state, profile), localize=False)
        elif re.match(r"^/pregame/v1/matches/[^/]+/(quit|cheatquit)$", route_path):
            game_state["phase"] = "menus"
            game_state["party_state"] = "DEFAULT"
            game_state["provisioning_flow"] = DEFAULT_PROVISIONING_FLOW
            game_state["queue"] = DEFAULT_QUEUE
            self._bump_party()
            self._bump_match()
            self._broadcast_backend_state_update()
            self._write(200, {"ok": True})
        elif re.match(r"^/pregame/v1/matches/[^/]+/(start|cheatstart)$", route_path):
            game_state["phase"] = "core"
            game_state["party_state"] = "MATCHMADE_GAME_STARTING"
            game_state["pregame_state"] = "provisioned"
            profile = self._current_profile()
            ensure_character_selections(game_state, "locked", party_profiles(game_state, party_id_for_profile(profile), profile))
            self._bump_party()
            self._bump_match()
            self._broadcast_backend_state_update()
            self._write(200, core_game_match_payload(game_state, profile), localize=False)
        elif route_path.startswith("/pregame/v1/matches/"):
            if game_state.get("phase") in {"pregame", "core"}:
                self._write(200, pregame_match_payload(game_state, self._current_profile()), localize=False)
            else:
                self._write(200, inactive_match_payload())
        elif re.match(r"^/core-game/v1/players/[^/]+/fixsession$", route_path):
            game_state["phase"] = "core"
            game_state["pregame_state"] = "provisioned"
            self._bump_match()
            self._broadcast_backend_state_update()
            self._write(200, core_game_player_payload(game_state, self._current_profile()), localize=False)
        elif re.match(r"^/core-game/v1/players/[^/]+/disassociate/", route_path):
            self._write(200, {"ok": True})
        elif route_path.startswith("/core-game/v1/players/"):
            if game_state.get("phase") == "core":
                self._write(200, core_game_player_payload(game_state, self._current_profile()), localize=False)
            else:
                self._write(200, inactive_match_player_payload(self._current_profile()), localize=False)
        elif re.match(r"^/core-game/v1/matches/[^/]+/allchatmuctoken$", route_path):
            self._write(200, chat_token_payload(ALL_MUC_NAME))
        elif re.match(r"^/core-game/v1/matches/[^/]+/teamchatmuctoken$", route_path):
            self._write(200, chat_token_payload(TEAM_MUC_NAME))
        elif re.match(r"^/core-game/v1/matches/[^/]+/teamvoicetoken$", route_path):
            self._write(200, voice_token_payload(TEAM_VOICE_ID))
        elif route_path in {"/core-game/v1/provisionfailures", "/core-game/v1/provisionversionfailures"}:
            self._write(200, {"ok": True})
        elif route_path in {"/ares-core-game/core-game/v1/provisionfailures", "/ares-core-game/core-game/v1/provisionversionfailures"}:
            self._write(200, {"ok": True})
        elif re.match(r"^/core-game/v1/matches/[^/]+/rematch/", route_path):
            self._write(200, {"ok": True})
        elif route_path.startswith("/core-game/v1/matches/"):
            if game_state.get("phase") == "core":
                self._write(200, core_game_match_payload(game_state, self._current_profile()), localize=False)
            elif game_state.get("phase") == "pregame" and game_state.get("pregame_state") == "provisioned":
                game_state["phase"] = "core"
                self._bump_match()
                self._broadcast_backend_state_update()
                self._write(200, core_game_match_payload(game_state, self._current_profile()), localize=False)
            else:
                self._write(200, inactive_match_payload())
        elif re.match(r"^/personalization/v2/players/[^/]+/playerloadout$", route_path):
            profile = self._current_profile()
            loadouts = game_state.setdefault("player_loadout_by_profile", {})
            if self.command in {"PUT", "POST", "PATCH"} and json_body:
                loadouts[profile["key"]] = player_loadout_payload(json_body, profile)
            loadout = loadouts.get(profile["key"]) or game_state.get("player_loadout")
            self._write(200, player_loadout_payload(loadout, profile), localize=False)
        elif route_path == "/content-service/v2/content":
            self._write(200, content_service_payload(game_state), localize=False)
        elif re.match(r"^/contracts/v1/contracts/[^/]+$", route_path):
            self._write(200, contracts_payload(self._current_profile()), localize=False)
        elif re.match(r"^/contracts/v1/item-upgrades(/[^/]+)?/?$", route_path):
            progressions = contract_definitions_payload(game_state)["ItemProgressionDefinitions"]
            self._write(200, {"ItemUpgrades": progressions, "Upgrades": progressions, "itemUpgrades": progressions})
        elif re.match(r"^/store/v2/storefront/[^/]+$", route_path):
            self._write(200, store_v2_storefront_payload())
        elif re.match(r"^/store/v1/wallet/[^/]+$", route_path):
            self._write(200, wallet_payload())
        elif route_path in {"/store/v1/offers", "/store/v1/offers/"}:
            self._write(200, store_offers_payload())
        elif re.match(r"^/store/v1/entitlements/[^/]+/[^/]+$", route_path):
            self._write(200, store_entitlements_payload(route_path.rsplit("/", 1)[-1], game_state))
        elif re.match(r"^/cap/v1/wallets(?:/[^/]+)?/?$", route_path):
            self._write(200, wallet_payload())
        elif re.match(r"^/cap/v1/orders(?:/.*)?$", route_path):
            if self.command == "POST":
                self._write(200, purchase_initialized_payload())
            else:
                self._write(200, {"Orders": [], "orders": []})
        elif re.match(r"^/cap/v1/entitlements(?:/.*)?$", route_path):
            parts = [part for part in route_path.split("/") if part]
            item_type_id = parts[-1] if len(parts) >= 4 else ""
            if re.fullmatch(r"[0-9a-fA-F-]{36}", item_type_id):
                self._write(200, store_entitlements_payload(item_type_id, game_state))
            else:
                self._write(200, all_store_entitlements_payload(game_state))
        elif route_path == "/payments/v1/initialize-purchase":
            self._write(200, purchase_initialized_payload())
        elif route_path.startswith("/match-history/v1/history/"):
            self._write(200, match_history_payload())
        elif route_path.startswith("/match-details/v1/matches/") or route_path.startswith("/ares-match-details/match-details/v1/matches/"):
            self._write(200, match_details_payload())
        elif route_path == "/name-service/v1/players":
            self._write(200, display_name_payload(profiles_with_current_first(self._current_profile(), game_state)), localize=False)
        elif route_path.startswith("/name-service/v"):
            profiles = profiles_with_current_first(self._current_profile(), game_state)
            requested_subjects: list[str] = []
            if isinstance(json_body, list):
                requested_subjects = [item for item in json_body if isinstance(item, str)]
            elif isinstance(json_body, dict):
                raw_subjects = json_body.get("Subjects") or json_body.get("subjects") or []
                if isinstance(raw_subjects, list):
                    requested_subjects = [item for item in raw_subjects if isinstance(item, str)]
            if requested_subjects:
                known_profiles = profiles_with_current_first(self._current_profile(), game_state)
                known_by_subject = {profile["subject"]: profile for profile in known_profiles}
                profiles = [
                    known_by_subject.get(subject) or profile_by_subject(subject, index)
                    for index, subject in enumerate(requested_subjects)
                ]
            names = display_name_players_payload(profiles)
            self._write(200, names, localize=False)
        elif route_path == "/contract-definitions/v2/definitions/story":
            self._write(200, active_story_contract_definition_payload(game_state))
        elif route_path.startswith("/contract-definitions/v2/definitions"):
            self._write(200, contract_definitions_payload(game_state))
        elif route_path.startswith("/contract-definitions/v2/item-upgrades"):
            progressions = contract_definitions_payload(game_state)["ItemProgressionDefinitions"]
            self._write(200, {"ItemUpgrades": progressions, "Upgrades": progressions, "itemUpgrades": progressions})
        elif re.match(r"^/mmr/v1/players/[^/]+/competitiveupdates$", route_path) or re.match(r"^/ares-mmr/mmr/v1/players/[^/]+/competitiveupdates$", route_path):
            self._write(200, competitive_updates_payload())
        elif route_path.startswith("/mmr/v1/players/") or route_path.startswith("/ares-mmr/mmr/v1/players/"):
            self._write(200, {"Subject": PLAYER_UUID, "Version": 0, "QueueSkills": {}, "LatestCompetitiveUpdate": {}})
        elif route_path == "/system/v1/builds":
            self._write(200, {"version": "rnet-probe", "builds": []})
        else:
            self._write(200, {"ok": True, "path": path})

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=39001)
    parser.add_argument("--log", type=Path, default=Path("reverse-logs/rnet_requests.jsonl"))
    parser.add_argument("--cert", type=Path, default=Path("reverse-logs/rnet_probe.crt"))
    parser.add_argument("--key", type=Path, default=Path("reverse-logs/rnet_probe.key"))
    parser.add_argument("--ca-cert", type=Path, default=Path("reverse-logs/rnet_probe_ca.crt"))
    parser.add_argument("--game-host", default="127.0.0.1")
    parser.add_argument("--game-port", type=int, default=7777)
    parser.add_argument("--phase", choices=["menus", "custom", "pregame", "core", "practice"], default="menus")
    parser.add_argument("--database-url", default=os.getenv("PROJECTA_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL)
    parser.add_argument("--allow-memory-db", action="store_true", help="Use in-memory account storage for local smoke tests.")
    parser.add_argument("--no-db-migrate", action="store_true", help="Do not apply Server/sql/schema.sql at startup.")
    args = parser.parse_args()

    configure_account_store(args.database_url, allow_memory_db=args.allow_memory_db, migrate=not args.no_db_migrate)
    ensure_cert(args.cert, args.key, args.ca_cert)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text("", encoding="utf-8")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(args.cert, args.key)

    server = DualProtocolHTTPServer((args.host, args.port), ProbeHandler, ctx)
    server.request_log = args.log
    server.log_lock = threading.Lock()
    server.profile_lock = threading.Lock()
    server.ws_lock = threading.Lock()
    server.ws_clients = set()
    server.chat_lock = threading.Lock()
    server.chat_messages = []
    server._ws_id = 1000
    server.game_state = initial_game_state(args.game_host, args.game_port, args.phase)
    server.seen_profiles = set(server.game_state.get("active_profile_keys") or [])

    def next_ws_id() -> int:
        with server.log_lock:
            server._ws_id += 1
            return server._ws_id

    server.next_ws_id = next_ws_id
    print(f"listening on {args.host}:{args.port}; log={args.log}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
