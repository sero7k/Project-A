from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "Server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from accounts import AccountStore, MemoryAccountStore, PostgresAccountStore, create_account_store
import project_a_server as server


def test_storage_backends_share_explicit_contract():
    store = create_account_store(allow_memory_db=True)

    assert isinstance(store, AccountStore)
    assert MemoryAccountStore.__abstractmethods__ == frozenset()
    assert PostgresAccountStore.__abstractmethods__ == frozenset()


def test_account_friend_party_flow():
    store = MemoryAccountStore()
    store.migrate()
    one = store.get_or_create_account("developer")
    two = store.get_or_create_account("developer2")

    assert one.game_name == "DevPlayer"
    assert two.game_name == "DevPlayer2"
    assert store.get_account_by_subject(one.subject).account_key == "developer"
    assert store.find_account_by_alias("DevPlayer2", "LOCAL").account_key == "developer2"

    request = store.create_friend_request("developer", "developer2")
    assert store.friend_requests_for_account("developer2", inbound=True)[0].request_id == request.request_id
    accepted = store.accept_friend_request("developer2", request.request_id)
    assert accepted is not None
    assert [friend.account_key for friend in store.friends_for_account("developer")] == ["developer2"]

    party_id = store.current_party_id("developer")
    invite = store.create_party_invite("developer", "developer2", party_id)
    assert store.invites_for_account("developer2")[0].invite_id == invite.invite_id
    assert store.accept_party_invite("developer2", invite.invite_id) is not None
    assert {member.account_key for member in store.party_members(party_id)} == {"developer", "developer2"}


def test_durable_profile_data_contracts_wallets_entitlements():
    store = MemoryAccountStore()
    store.get_or_create_account("developer")
    store.set_wallet_balance("developer", "85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741", 100)
    assert store.wallet_balances("developer") == {"85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741": 100}

    store.grant_entitlement("developer", "bcef87d6-209b-46c6-8b19-fbe40bd95abc", "8cf33945-4a2a-1da8-02de-a6858a04f07d")
    assert store.entitlements_for_account("developer", "bcef87d6-209b-46c6-8b19-fbe40bd95abc") == ["8cf33945-4a2a-1da8-02de-a6858a04f07d"]

    loadout = {"Subject": "x", "Version": 7, "Guns": []}
    store.save_player_loadout("developer", loadout)
    assert store.get_player_loadout("developer")["Version"] == 7

    state = {"Version": 2, "ActiveSpecialContract": "abc", "Contracts": [], "Missions": [], "ProcessedMatches": []}
    store.save_contract_state("developer", state)
    assert store.contract_state("developer")["ActiveSpecialContract"] == "abc"


def test_seeded_profile_defaults_unlock_owned_data_without_zero_contracts():
    server.configure_account_store(allow_memory_db=True)
    profile = server.profile_by_key("developer")

    wallet = server.wallet_payload(None, profile)["Balances"]
    contracts = server.contracts_payload(profile, None)
    definitions = server.contract_definitions_payload(None)
    content = server.content_service_payload(None)
    identity = server.player_identity_payload(profile)
    expected_contract_ids = {server.LOCAL_STORY_CONTRACT_ID, *(row["id"] for row in server.LOCAL_CHARACTER_CONTRACT_ROWS)}
    expected_currency_ids = {row["id"] for row in server.LOCAL_CURRENCY_ROWS}

    assert wallet[server.LOCAL_CURRENCY_ID] == server.UNLOCKED_WALLET_BALANCE
    assert wallet[server.LOCAL_UPGRADE_TOKEN_ID] == server.UNLOCKED_WALLET_BALANCE
    assert wallet[server.LOCAL_RECRUITMENT_TOKEN_ID] == server.UNLOCKED_WALLET_BALANCE
    assert contracts["ActiveSpecialContract"] == server.LOCAL_STORY_CONTRACT_ID
    assert contracts["Contracts"][0]["ID"] == server.LOCAL_STORY_CONTRACT_ID
    assert definitions["ActiveStoryContractID"] == server.LOCAL_STORY_CONTRACT_ID
    assert definitions["ContractDefinitions"][0]["ID"] == server.LOCAL_STORY_CONTRACT_ID
    assert {entry["ID"] for entry in content["Contracts"]} == expected_contract_ids
    assert {entry["ID"] for entry in content["Currencies"]} == expected_currency_ids
    assert identity["PreferredLevelBorderID"] == server.DEFAULT_LEVEL_BORDER_ID
    assert identity["PreferredLevelBorderID"] != server.ZERO_UUID


def test_matchmaking_primes_pregame_backend_state():
    server.configure_account_store(allow_memory_db=True)
    profile = server.profile_by_key("developer")
    game_state = server.initial_game_state("127.0.0.1", 7777, "menus")

    server.enter_matchmaking(game_state, {"QueueID": "v"}, profile, immediate_pregame=True)

    assert game_state["phase"] == "pregame"
    assert game_state["party_state"] == "MATCHMADE_GAME_STARTING"
    assert game_state["pregame_ready_keys"] == ["developer"]
    assert game_state["core_ready_keys"] == []


def test_custom_game_start_primes_pregame_backend_state():
    server.configure_account_store(allow_memory_db=True)
    profile = server.profile_by_key("developer")
    game_state = server.initial_game_state("127.0.0.1", 7777, "custom")
    party_id = server.party_id_for_profile(profile)

    game_state["phase"] = "pregame"
    game_state["party_state"] = "CUSTOM_GAME_STARTING"
    game_state["pregame_state"] = "character_select_active"
    members = server.party_profiles(game_state, party_id, profile)
    server.ensure_character_selections(game_state, "selected", members)
    server.prime_backend_state_for_phase(game_state, members, "pregame")

    assert game_state["pregame_ready_keys"] == ["developer"]
    events = server.rms_match_messages(game_state, profile)
    assert any(event["uri"].endswith(f"/pregame/v1/players/{profile['subject']}") for event in events)
    assert any(event["uri"].endswith(f"/pregame/v1/matches/{server.MATCH_ID}") for event in events)


def test_content_service_exposes_and_grants_all_local_agents():
    server.configure_account_store(allow_memory_db=True)
    profile = server.profile_by_key("developer")
    game_state = server.initial_game_state("127.0.0.1", 7777, "menus")

    content = server.content_service_payload(game_state)
    expected_ids = {row["id"] for row in server.LOCAL_AGENT_ROWS}
    top_level_ids = {entry["ID"] for entry in content["Characters"]}
    bucket_ids = {entry["ItemID"] for entry in content["characters"]}
    entitlement_payload = server.store_entitlements_payload(server.ITEM_TYPE_CHARACTER, game_state, profile)
    entitlement_ids = {entry["ItemID"] for entry in entitlement_payload["Entitlements"]}
    owned_entitlements = entitlement_payload["OwnedEntitlements"]

    assert top_level_ids == expected_ids
    assert bucket_ids == expected_ids
    assert entitlement_ids == expected_ids
    assert set(entitlement_payload["OwnedItems"]) == expected_ids
    assert {entry["ServiceID"] for entry in owned_entitlements} == expected_ids
    assert all(entry["AresContentType"] == server.CLIENT_CONTENT_TYPE_IDS["Character"] for entry in owned_entitlements)
    assert all(entry["IsEnabled"] for entry in content["Characters"])
    assert all(entry["AssetName"].endswith("_PrimaryAsset") for entry in content["Characters"])
    assert all(entry["AssetClassName"].endswith("_PrimaryAsset_C") for entry in content["Characters"])
    assert all(entry["AssetPath"].endswith("_PrimaryAsset_C") for entry in content["Characters"])
    assert all(entry["UIDataPath"].endswith("_UIData_C") for entry in content["characters"])
    assert all(entry["CharacterAssetPath"].endswith("_PC_C") for entry in content["characters"])


def test_friend_request_add_event_payload_keeps_subscription():
    server.configure_account_store(allow_memory_db=True)
    sender = server.profile_by_key("developer")
    receiver = server.profile_by_key("developer2")
    request = server.ACCOUNT_STORE.create_friend_request(sender["key"], receiver["key"])

    payload = server.friend_request_add_event_payload(request, receiver)

    assert payload["Pid"] == sender["chat_pid"]
    assert payload["Subscription"] == server.FRIEND_REQUEST_SUBSCRIPTION_INBOUND


def test_pregame_match_payload_uses_client_wire_states():
    server.configure_account_store(allow_memory_db=True)
    profile = server.profile_by_key("developer")
    game_state = server.initial_game_state("127.0.0.1", 7777, "menus")

    server.enter_matchmaking(game_state, {"QueueID": "v"}, profile, immediate_pregame=True)
    payload = server.pregame_match_payload(game_state, profile)

    assert payload["ProvisioningFlowID"] == server.MATCHMAKING_PROVISIONING_FLOW
    assert payload["ProvisioningFlowEnum"] == 4
    assert payload["PhaseTimeRemainingNS"] > 0
    assert payload["EnemyTeam"]["Players"] == []
    assert payload["Players"][0]["CharacterSelectionState"] == "Free"


def test_custom_pregame_lock_uses_wire_state_and_finishes_select():
    server.configure_account_store(allow_memory_db=True)
    profile = server.profile_by_key("developer")
    game_state = server.initial_game_state("127.0.0.1", 7777, "custom")
    character_id = "eb93336a-449b-9c1b-0a54-a891f7921d69"

    server.set_character_for_profile(game_state, profile, character_id, "selected")
    selected = server.pregame_match_payload(game_state, profile)

    assert selected["Players"][0]["CharacterSelectionState"] == "selected"
    assert selected["PregameState"] == "character_select_active"
    assert selected["PhaseTimeRemainingNS"] > 0

    server.set_character_for_profile(game_state, profile, character_id, "locked")
    locked = server.pregame_match_payload(game_state, profile)

    assert locked["Players"][0]["CharacterSelectionState"] == "locked"
    assert locked["PregameState"] == "character_select_finished"
    assert locked["PhaseTimeRemainingNS"] == 0


def test_custom_range_lock_transitions_to_core():
    server.configure_account_store(allow_memory_db=True)
    profile = server.profile_by_key("developer")
    game_state = server.initial_game_state("127.0.0.1", 7777, "custom")
    character_id = "add6443a-41bd-e414-f6ad-e58d267f4e95"
    members = server.party_profiles(game_state, server.party_id_for_profile(profile), profile)

    server.set_character_for_profile(game_state, profile, character_id, "locked")
    server.transition_locked_match_to_core(game_state, members)

    assert game_state["phase"] == "core"
    assert game_state["pregame_state"] == "provisioned"
    assert game_state["party_state"] == "SOLO_EXPERIENCE_STARTING"
    assert game_state["queue"] == server.SHOOTING_RANGE_QUEUE
    assert game_state["provisioning_flow"] == server.SHOOTING_RANGE_PROVISIONING_FLOW
    assert game_state["core_ready_keys"] == ["developer"]


def test_update_state_from_json_persists_custom_settings():
    game_state = server.initial_game_state("127.0.0.1", 7777, "custom")

    server.update_state_from_json(
        game_state,
        {
            "Settings": {
                "Map": "/Game/Maps/Triad/Triad",
                "Mode": "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C",
                "Name": "Night Custom",
                "Description": "Bots and rules",
                "UseBots": True,
                "AllowGameModifiers": True,
                "GameRules": {"ScoreLimit": 13},
            }
        },
    )

    assert game_state["map"] == "/Game/Maps/Triad/Triad"
    assert game_state["mode"] == "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C"
    assert game_state["custom_game_name"] == "Night Custom"
    assert game_state["custom_game_description"] == "Bots and rules"
    assert game_state["use_bots"] is True
    assert game_state["allow_game_modifiers"] is True
    assert game_state["game_rules"] == {"ScoreLimit": 13}


def test_custom_game_configs_and_content_expose_multiple_maps_and_modes():
    server.configure_account_store(allow_memory_db=True)
    profile = server.profile_by_key("developer")
    game_state = server.initial_game_state("127.0.0.1", 7777, "custom")
    game_state["custom_game_name"] = "Local Lab"
    game_state["custom_game_description"] = "Expanded config"
    game_state["use_bots"] = True
    game_state["allow_game_modifiers"] = True
    game_state["game_rules"] = {"ScoreLimit": 7}

    configs = server.custom_game_configs_payload(game_state)
    content = server.content_service_payload(game_state)
    party = server.party_payload(game_state, server.party_id_for_profile(profile), profile)

    assert len(configs["EnabledMaps"]) >= 4
    assert len(configs["EnabledModes"]) >= 4
    assert configs["CustomGameConfigs"][0]["MapOptions"] == configs["EnabledMaps"]
    assert configs["CustomGameConfigs"][0]["ModeOptions"] == configs["EnabledModes"]
    assert configs["PingProxyAddress"].endswith(":7777")
    assert len(content["Maps"]) >= 4
    assert len(content["GameModes"]) >= 4
    assert {entry["Name"] for entry in content["Maps"]} >= {"Bind", "Haven"}
    assert all(entry["UIDataPath"].endswith("_UIData") or entry["UIDataPath"].endswith("_UIData_C") for entry in content["Maps"])
    assert all(entry["UIDataPath"].endswith("_UIData") or entry["UIDataPath"].endswith("_UIData_C") for entry in content["GameModes"])
    assert party["CustomGameData"]["Settings"]["UseBots"] is True
    assert party["CustomGameData"]["Settings"]["AllowGameModifiers"] is True
    assert party["CustomGameData"]["Settings"]["Name"] == "Local Lab"
    assert party["CustomGameData"]["MapOptions"] == configs["EnabledMaps"]


def test_custom_game_settings_accept_nested_game_mode_shape():
    game_state = server.initial_game_state("127.0.0.1", 7777, "custom")

    server.update_state_from_json(
        game_state,
        {
            "CustomGameData": {
                "Settings": {
                    "Map": "/Game/Maps/Duality/Duality",
                    "GameMode": "/Game/GameModes/Bomb/QuickPlay_BombGameMode.QuickPlay_BombGameMode_C",
                    "Name": "Nested Custom",
                }
            }
        },
    )

    assert game_state["map"] == "/Game/Maps/Duality/Duality"
    assert game_state["mode"] == "/Game/GameModes/Bomb/QuickPlay_BombGameMode.QuickPlay_BombGameMode_C"
    assert game_state["custom_game_name"] == "Nested Custom"


def test_custom_game_settings_accept_human_map_and_mode_aliases():
    game_state = server.initial_game_state("127.0.0.1", 7777, "custom")

    server.update_state_from_json(
        game_state,
        {
            "CustomGameData": {
                "Settings": {
                    "Map": "Haven",
                    "GameMode": "Bomb",
                }
            }
        },
    )

    assert game_state["map"] == "/Game/Maps/Triad/Triad"
    assert game_state["mode"] == "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C"


def test_enabled_custom_game_maps_match_content_ids():
    game_state = server.initial_game_state("127.0.0.1", 7777, "custom")
    configs = server.custom_game_configs_payload(game_state)
    content = server.content_service_payload(game_state)

    content_map_ids = {entry["ID"] for entry in content["Maps"]}
    content_mode_ids = {entry["ID"] for entry in content["GameModes"]}

    assert set(configs["EnabledMaps"]).issubset(content_map_ids)
    assert set(configs["EnabledModes"]).issubset(content_mode_ids)


def test_versioned_matchmaking_queue_path_returns_single_queue_shape():
    queue = server.queue_config_by_id("unrated")
    payload = server.queue_config_response(queue)

    assert payload["QueueID"] == "unrated"
    assert payload["Queues"] == [queue]
    assert payload["Enabled"] is True


def test_party_chat_room_is_available_before_explicit_join():
    server.configure_account_store(allow_memory_db=True)
    profile = server.profile_by_key("developer")
    game_state = server.initial_game_state("127.0.0.1", 7777, "menus")
    party_room = server.party_muc_name(server.party_id_for_profile(profile))

    conversations = server.chat_conversations_payload(game_state, profile)
    participants = server.chat_participants_payload(game_state, party_room, profile)

    assert conversations["Conversations"][0]["Cid"] == party_room
    assert participants["Cid"] == party_room
    assert participants["Participants"]
