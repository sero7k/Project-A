"""Static local catalog rows and default content constants."""

from __future__ import annotations

import os

from ..common.assets import blueprint_asset
from ..common.ids import service_uuid, stable_token

try:
    from ...storage.accounts import generated_subject
except ImportError:
    from projecta.storage.accounts import generated_subject

DEFAULT_MAP = "/Game/Maps/Ascent/Ascent"
DEFAULT_MODE = "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C"
SHOOTING_RANGE_MAP = "/Game/Maps/Poveglia/Range"
SHOOTING_RANGE_MODE = "/Game/GameModes/ShootingRange/ShootingRangeGameMode.ShootingRangeGameMode_C"
DEFAULT_QUEUE = "custom"
DEFAULT_MATCHMAKING_QUEUE = "v"
SHOOTING_RANGE_QUEUE = "ShootingRange"
MATCHMAKING_PROVISIONING_FLOW = "Matchmaking"
DEFAULT_PROVISIONING_FLOW = "CustomGame"
SHOOTING_RANGE_PROVISIONING_FLOW = "ShootingRange"
LOCAL_AGENT_SPECS = [
    ("Breach", "Breach", "5f8d3a7f-467b-97f3-062c-13acf203c006"),
    ("Gumshoe", "Gumshoe", "117ed9e3-49f3-6512-3ccf-0cada7e3823b"),
    ("Hunter", "Hunter", "320b2a48-4d9b-a075-30f1-1f93a9b638fa"),
    ("Pandemic", "Pandemic", "707eab51-4836-f488-046a-cda6bf494859"),
    ("Phoenix", "Phoenix", "eb93336a-449b-9c1b-0a54-a891f7921d69"),
    ("Sarge", "Sarge", "9f0d8ba9-4140-b941-57d3-a7ad57c6b417"),
    ("Thorne", "Thorne", "569fdd95-4d10-43ab-ca70-79becc718b46"),
    ("Wraith", "Wraith", "8e253930-4c05-31dd-1b6c-968525494517"),
    ("Wushu", "Wushu", "add6443a-41bd-e414-f6ad-e58d267f4e95"),
]
LOCAL_AGENT_ROWS = [
    {
        "id": agent_id,
        "name": name,
        "slug": slug,
        "asset": blueprint_asset(f"/Game/Characters/{slug}/{slug}_PrimaryAsset"),
        "character_asset": blueprint_asset(f"/Game/Characters/{slug}/{slug}_PC"),
        "ui_data": blueprint_asset(f"/Game/Characters/{slug}/{slug}_UIData"),
        "select_fxc": blueprint_asset(f"/Game/Characters/{slug}/FXC_CharacterSelect_{slug}"),
    }
    for name, slug, agent_id in LOCAL_AGENT_SPECS
]
LOCAL_CHARACTER_ROLE_SPECS = [
    ("Assault", "Assault"),
    ("Breaker", "Breaker"),
    ("Sentinel", "Sentinel"),
    ("Strategist", "Strategist"),
]
LOCAL_CHARACTER_ROLE_ROWS = [
    {
        "id": service_uuid(f"character-role-{slug.lower()}"),
        "name": name,
        "slug": slug,
        "asset": blueprint_asset(f"/Game/Characters/_Core/Roles/{slug}_PrimaryDataAsset"),
        "ui_data": blueprint_asset(f"/Game/Characters/_Core/Roles/{slug}_UIData"),
    }
    for name, slug in LOCAL_CHARACTER_ROLE_SPECS
]
LOCAL_CHARACTER_ROLE_BY_SLUG = {
    "Breach": "Breaker",
    "Gumshoe": "Sentinel",
    "Hunter": "Breaker",
    "Pandemic": "Strategist",
    "Phoenix": "Assault",
    "Sarge": "Strategist",
    "Thorne": "Sentinel",
    "Wraith": "Strategist",
    "Wushu": "Assault",
}
LOCAL_CHARACTER_CONTRACT_ROWS = [
    {
        "id": service_uuid(f"character-contract-{slug.lower()}"),
        "name": name,
        "slug": slug,
        "asset": blueprint_asset(f"/Game/Contracts/Characters/{slug}/Contract_{slug}_DataAsset"),
        "ui_data": blueprint_asset(f"/Game/Contracts/Characters/{slug}/Contract_{slug}_UIData"),
        "chapters": [
            {
                "id": service_uuid(f"character-contract-{slug.lower()}-chapter-1"),
                "name": f"{slug}Chapter1",
                "asset": blueprint_asset(f"/Game/Contracts/Characters/{slug}/{slug}Chapter1_DataAsset"),
                "ui_data": blueprint_asset(f"/Game/Contracts/Characters/{slug}/{slug}Chapter1_UIData"),
            },
            {
                "id": service_uuid(f"character-contract-{slug.lower()}-chapter-2"),
                "name": f"{slug}Chapter2",
                "asset": blueprint_asset(f"/Game/Contracts/Characters/{slug}/{slug}Chapter2_DataAsset"),
                "ui_data": blueprint_asset(f"/Game/Contracts/Characters/{slug}/{slug}Chapter2_UIData"),
            },
        ],
    }
    for name, slug, _agent_id in LOCAL_AGENT_SPECS
]
LOCAL_CHARACTER_CONTRACT_BY_SLUG = {row["slug"]: row for row in LOCAL_CHARACTER_CONTRACT_ROWS}
DEFAULT_CHARACTER_ID = next(row["id"] for row in LOCAL_AGENT_ROWS if row["slug"] == "Phoenix")
DEFAULT_PLAYER_CARD_ID = "8cf33945-4a2a-1da8-02de-a6858a04f07d"
DEFAULT_PLAYER_TITLE_ID = "e59aa87c-4cbf-517a-5983-6e81511be9b7"
DEFAULT_LEVEL_BORDER_ID = service_uuid("level-border-default")
DEFAULT_PLAYER_CARD_ASSET = blueprint_asset("/Game/Personalization/PlayerCards/Default/EtherExplosion/PlayerCard_EtherExplosion_PrimaryAsset")
DEFAULT_PLAYER_TITLE_ASSET = blueprint_asset("/Game/Personalization/Titles/PlayerTitle_Default_PrimaryAsset")
DEFAULT_SPRAY_PREROUND_ID = "35138b9a-5d96-4fbd-8e2d-a2440225f93a"
DEFAULT_SPRAY_MIDROUND_ID = "8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a"
DEFAULT_SPRAY_PREROUND_ASSET = blueprint_asset("/Game/Personalization/Sprays/Chicken/Spray_Chicken_PrimaryAsset")
DEFAULT_SPRAY_MIDROUND_ASSET = blueprint_asset("/Game/Personalization/Sprays/Salt/Spray_Salt_PrimaryAsset")
DEFAULT_MAP_ASSET = blueprint_asset("/Game/Maps/Poveglia/Poveglia_PrimaryAsset")
DEFAULT_MODE_ASSET = blueprint_asset("/Game/GameModes/ShootingRange/ShootingRangeGameMode_PrimaryAsset")
LOCAL_MAP_ROWS = [
    {
        "id": generated_subject("map-ascent"),
        "name": "Ascent",
        "path": "/Game/Maps/Ascent/Ascent",
        "asset": blueprint_asset("/Game/Maps/Ascent/Ascent_PrimaryAsset"),
        "ui_data": "/Game/Maps/Ascent/Ascent_UIData",
    },
    {
        "id": generated_subject("map-duality"),
        "name": "Bind",
        "path": "/Game/Maps/Duality/Duality",
        "asset": blueprint_asset("/Game/Maps/Duality/Duality_PrimaryAsset"),
        "ui_data": "/Game/Maps/Duality/Duality_UIData",
    },
    {
        "id": generated_subject("map-triad"),
        "name": "Haven",
        "path": "/Game/Maps/Triad/Triad",
        "asset": blueprint_asset("/Game/Maps/Triad/Triad_PrimaryAsset"),
        "ui_data": "/Game/Maps/Triad/Triad_UIData",
    },
    {
        "id": generated_subject("map-bonsai"),
        "name": "Split",
        "path": "/Game/Maps/Bonsai/Bonsai",
        "asset": blueprint_asset("/Game/Maps/Bonsai/Bonsai_PrimaryAsset"),
        "ui_data": "/Game/Maps/Bonsai/Bonsai_UIData",
    },
    {
        "id": generated_subject("map-poveglia"),
        "name": "Poveglia",
        "path": "/Game/Maps/Poveglia/Poveglia",
        "asset": DEFAULT_MAP_ASSET,
        "ui_data": "/Game/Maps/Poveglia/Poveglia_UIData",
    },
    {
        "id": "1f676c76-80e1-4239-95bb-83d0f6d0da78",
        "name": "Range",
        "path": "/Game/Maps/Poveglia/Range",
        "asset": DEFAULT_MAP_ASSET,
        "ui_data": "/Game/Maps/Poveglia/Poveglia_UIData",
    },
    {
        "id": generated_subject("map-range-npe"),
        "name": "Range NPE",
        "path": "/Game/Maps/Poveglia/Range_NewPlayerExperience_Master",
        "asset": DEFAULT_MAP_ASSET,
        "ui_data": "/Game/Maps/Poveglia/Range_NewPlayerExperience_Master_UIData",
    },
]
LOCAL_MODE_ROWS = [
    {
        "id": "4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38",
        "name": "Shooting Range",
        "path": SHOOTING_RANGE_MODE,
        "asset": DEFAULT_MODE_ASSET,
        "ui_data": "/Game/GameModes/ShootingRange/ShootingRangeGameMode_UIData",
    },
    {
        "id": generated_subject("mode-bomb"),
        "name": "Bomb",
        "path": "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C",
        "asset": blueprint_asset("/Game/GameModes/Bomb/BombGameMode_PrimaryAsset"),
        "ui_data": "/Game/GameModes/Bomb/BombGameMode_UIData",
    },
    {
        "id": generated_subject("mode-quickplay-bomb"),
        "name": "Quick Play Bomb",
        "path": "/Game/GameModes/Bomb/QuickPlay_BombGameMode.QuickPlay_BombGameMode_C",
        "asset": blueprint_asset("/Game/GameModes/Bomb/QuickPlay_BombGameMode_PrimaryAsset"),
        "ui_data": "/Game/GameModes/Bomb/QuickPlay_BombGameMode_UIData",
    },
    {
        "id": generated_subject("mode-npe"),
        "name": "New Player Experience",
        "path": "/Game/GameModes/NewPlayerExperience/NPEGameMode.NPEGameMode_C",
        "asset": blueprint_asset("/Game/GameModes/NewPlayerExperience/NPEGameMode_PrimaryAsset"),
        "ui_data": "/Game/GameModes/NewPlayerExperience/NPEGameMode_UIData",
    },
]
LOCAL_CURRENCY_ID = "85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741"
LOCAL_CURRENCY_ASSET = blueprint_asset("/Game/Currencies/Currency_AresPoints_DataAsset")
LOCAL_UPGRADE_TOKEN_ID = "6f0f9a79-3df2-5e16-bbdc-8c38e9c751b1"
LOCAL_UPGRADE_TOKEN_ASSET = blueprint_asset("/Game/Currencies/Currency_UpgradeToken_DataAsset")
LOCAL_RECRUITMENT_TOKEN_ID = "62fc60a0-97c9-5588-85cf-3b2f1e0a0464"
LOCAL_RECRUITMENT_TOKEN_ASSET = blueprint_asset("/Game/Currencies/Currency_RecruitmentToken_DataAsset")
LOCAL_CURRENCY_ROWS = [
    {"id": LOCAL_CURRENCY_ID, "name": "Ares Points", "asset": LOCAL_CURRENCY_ASSET},
    {"id": LOCAL_UPGRADE_TOKEN_ID, "name": "Upgrade Token", "asset": LOCAL_UPGRADE_TOKEN_ASSET},
    {"id": LOCAL_RECRUITMENT_TOKEN_ID, "name": "Recruitment Token", "asset": LOCAL_RECRUITMENT_TOKEN_ASSET},
]
LOCAL_BUNDLE_ID = "77258665-71d1-4623-bc72-44db9bd5b3b3"
LOCAL_ORDER_ID = stable_token("order", "bootstrap")
LOCAL_STORY_CONTRACT_ID = os.environ.get("PROJECT_A_LOCAL_STORY_CONTRACT_ID", "90a1aaa8-f6dc-42f7-ae65-181c9fd0d80b")
LOCAL_CONTRACT_ASSET = blueprint_asset("/Game/Contracts/NPE/Contract_NPE_DataAsset")
UNLOCKED_WALLET_BALANCE = int(os.environ.get("PROJECT_A_UNLOCKED_WALLET_BALANCE", "10000000"))
LOCAL_SEASON_ID = "7f2641a8-42cd-5e5e-a5c8-f8f2d5dc3e75"
LOCAL_SEASON_ASSET = blueprint_asset("/Game/Seasons/Season_Local_DataAsset")
DEFAULT_LOCALE = "en_US"
DEFAULT_WEB_LANGUAGE = "en-us"
DEFAULT_REGION = "na"
PLAYER_FEEDBACK_LOCALE = "en_GB"
PLAYER_FEEDBACK_SHARD = "NA1"
FRIEND_REQUEST_SUBSCRIPTION_INBOUND = os.environ.get("PROJECT_A_FRIEND_SUBSCRIPTION_INBOUND", "pending_in")
FRIEND_REQUEST_SUBSCRIPTION_OUTBOUND = os.environ.get("PROJECT_A_FRIEND_SUBSCRIPTION_OUTBOUND", "pending_out")

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
ALLOW_UNVERIFIED_DEFAULT_LOADOUT = os.environ.get("PROJECT_A_ALLOW_UNVERIFIED_DEFAULT_LOADOUT", "1") not in {"0", "false", "False"}
RECOGNIZED_ROUTE_PREFIXES = (
    "/v1/parties/",
    "/v1/players/",
    "/parties/v1/",
    "/contracts/v1/",
    "/contract-definitions/v2/",
    "/pregame/v1/",
    "/ares-core-game",
    "/core-game/v1/",
    "/chat/",
    "/voice-chat/",
    "/player-account/aliases/v1/",
    "/store/",
    "/cap/v1/",
    "/entitlements/",
)


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


__all__ = [name for name in globals() if name.isupper()]
