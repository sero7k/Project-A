#!/usr/bin/env python3
"""Project A compatibility control-plane server.

This process serves the client-facing HTTP/RNet endpoints recovered from the
client dump and persists account, party, social, loadout, wallet, entitlement,
contract, and global game-state data in PostgreSQL.  It can still run with an
in-memory backend for local smoke tests by passing --allow-memory-db.
"""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .common.assets import (
    asset_class_name,
    asset_class_object_path,
    asset_default_object_name,
    asset_object_path,
    asset_reference_name,
    blueprint_asset,
    unwrap_asset_reference,
)
from .common.chat_format import (
    chat_message_body_value,
    chat_message_part_payload,
    chat_message_parts_payload,
    chat_message_room,
    chat_message_text,
    chat_muc_type_value,
    chat_text_room_type_value,
    subject_from_chat_pid,
)
from .data.content_types import (
    ARES_CONTENT_TYPE_INDEX,
    ARES_CONTENT_TYPES,
    CLIENT_CONTENT_TYPE_IDS,
    ITEM_TYPE_CONTENT_TYPE_NAMES,
    content_type_id_for_item_type,
)
from .common.ids import SERVICE_NAMESPACE, account_token, service_uuid, stable_digest, stable_token
from .domain import accounts as account_runtime
from .domain import queues as queue_helpers
from .domain import state_transitions
from .payloads import chat as chat_payloads
from .payloads import client as client_payloads
from .payloads import content as content_payloads
from .payloads import contracts as contract_payloads
from .payloads import loadout as loadout_payloads
from .payloads import match as match_payloads
from .payloads import party as party_payloads
from .payloads import presence as presence_payloads
from .payloads import realtime as realtime_payloads
from .payloads import social as social_payloads
from .payloads import store as store_payloads
from .payloads import voice as voice_payloads
from .domain import backend_state
from .runtime.context import RouteContext
from .routes.normalization import normalize_route_path as _normalize_route_path
from .routes import client as client_routes
from .routes import account as account_routes
from .routes import chat as chat_routes
from .routes import content as content_routes
from .routes import contracts as contracts_routes
from .routes import core_game as core_game_routes
from .routes import matchmaking as matchmaking_routes
from .routes import misc as misc_routes
from .routes import mmr as mmr_routes
from .routes import name_service as name_service_routes
from .routes import personalization as personalization_routes
from .routes import party as party_routes
from .routes import policy as policy_routes
from .routes import pregame as pregame_routes
from .routes import reporting as reporting_routes
from .routes import session as session_routes
from .routes import social as social_routes
from .routes import store as store_routes
from .routes import voice as voice_routes
from .domain.state_helpers import (
    first_string,
    provisioning_flow_enum_value,
    request_settings_from_body,
    subject_from_team_request,
    team_id_for_custom_team,
)
from .common.time_utils import presence_time_now, utc_now

try:
    from ..storage.accounts import (
        DEFAULT_DATABASE_URL,
        AccountRecord,
        AccountStore,
        FriendRequestRecord,
        PartyInviteRecord,
        account_from_hint,
        create_account_store,
        generated_party_id,
        generated_subject,
        normalize_account_key,
    )
except ImportError:
    from projecta.storage.accounts import (
        DEFAULT_DATABASE_URL,
        AccountRecord,
        AccountStore,
        FriendRequestRecord,
        PartyInviteRecord,
        account_from_hint,
        create_account_store,
        generated_party_id,
        generated_subject,
        normalize_account_key,
    )


ACCOUNT_STORE: AccountStore = account_runtime.ACCOUNT_STORE


PLAYER_UUID = generated_subject("developer")
PARTY_ID = generated_party_id(PLAYER_UUID)
GAME_NAME = "DevPlayer"
TAG_LINE = "LOCAL"
CHAT_PID = f"{PLAYER_UUID}@pvp.net"
CHAT_RESOURCE = "project-a-client"
CHAT_FULL_PID = f"{CHAT_PID}/{CHAT_RESOURCE}"
CLIENT_VERSION = "release-0.45-shipping-13-404591"
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
MATCH_ID = service_uuid("default-match")
GAME_POD_ID = f"project-a-pod-{stable_digest('game-pod')[:12]}"
from .data.catalog import *

PARTY_MUC_NAME = f"ares-party-{PARTY_ID}@conference.pvp.net"
TEAM_MUC_NAME = f"ares-team-{MATCH_ID}@conference.pvp.net"
ALL_MUC_NAME = f"ares-all-{MATCH_ID}@conference.pvp.net"
VOICE_ROOM_ID = f"voice-{PARTY_ID}"
TEAM_VOICE_ID = f"voice-{MATCH_ID}"


LOCAL_PROFILES = account_runtime.LOCAL_PROFILES
RUNTIME_PROFILE_HINTS = account_runtime.RUNTIME_PROFILE_HINTS
DEFAULT_PROFILE_KEY = account_runtime.DEFAULT_PROFILE_KEY
PROFILE_ALIASES = account_runtime.PROFILE_ALIASES


def _push_account_runtime_publics() -> None:
    if ACCOUNT_STORE is not account_runtime.ACCOUNT_STORE:
        account_runtime.set_account_store(ACCOUNT_STORE)
    if DEFAULT_PROFILE_KEY != account_runtime.DEFAULT_PROFILE_KEY:
        account_runtime.set_default_profile_key(DEFAULT_PROFILE_KEY)


def _sync_account_runtime_publics() -> None:
    global ACCOUNT_STORE, DEFAULT_PROFILE_KEY
    ACCOUNT_STORE = account_runtime.ACCOUNT_STORE
    DEFAULT_PROFILE_KEY = account_runtime.DEFAULT_PROFILE_KEY


def set_default_profile_key(key: str | None) -> str:
    account_runtime.set_default_profile_key(key)
    _sync_account_runtime_publics()
    return DEFAULT_PROFILE_KEY


def login_key_and_hint(value: str | None) -> tuple[str, dict[str, str] | None]:
    _push_account_runtime_publics()
    result = account_runtime.login_key_and_hint(value)
    _sync_account_runtime_publics()
    return result


def profile_by_login(value: str | None) -> dict[str, str]:
    _push_account_runtime_publics()
    profile = account_runtime.profile_by_login(value, seed_persisted_profile_defaults)
    _sync_account_runtime_publics()
    return profile


def set_default_profile_from_login(value: str | None) -> dict[str, str]:
    _push_account_runtime_publics()
    profile = account_runtime.set_default_profile_from_login(value, seed_persisted_profile_defaults)
    _sync_account_runtime_publics()
    return profile


def canonical_profile_key(key: str | None) -> str:
    return account_runtime.canonical_profile_key(key)


def register_local_profile(account_key: str | None, game_name: str | None = None, tag_line: str | None = None, subject: str | None = None) -> dict[str, str]:
    _push_account_runtime_publics()
    profile = account_runtime.register_local_profile(account_key, game_name, tag_line, subject)
    _sync_account_runtime_publics()
    return profile


def profile_from_display_name(display_name: str) -> dict[str, str] | None:
    _push_account_runtime_publics()
    return account_runtime.profile_from_display_name(display_name)


def configure_account_store(
    database_url: str | None = None,
    *,
    allow_memory_db: bool = False,
    migrate: bool = True,
) -> AccountStore:
    account_runtime.configure_account_store(database_url, allow_memory_db=allow_memory_db, migrate=migrate)
    _sync_account_runtime_publics()
    seeded_keys = globals().get("_SEEDED_PROFILE_KEYS")
    if isinstance(seeded_keys, set):
        seeded_keys.clear()
    return ACCOUNT_STORE


def profile_from_account(account: AccountRecord) -> dict[str, str]:
    return account_runtime.profile_from_account(account)


def alias_payload(profile: dict[str, str]) -> dict[str, Any]:
    return account_runtime.alias_payload(profile)


def local_account_payload(profile: dict[str, str]) -> dict[str, Any]:
    _push_account_runtime_publics()
    return account_runtime.local_account_payload(profile)


def alias_fields_from_body(body: Any, fallback: dict[str, str]) -> tuple[str, str]:
    return account_runtime.alias_fields_from_body(body, fallback)


def alias_availability_payload(game_name: str, tag_line: str, owner_key: str | None = None) -> dict[str, Any]:
    _push_account_runtime_publics()
    return account_runtime.alias_availability_payload(game_name, tag_line, owner_key)


def update_alias_response(profile: dict[str, str], body: Any) -> tuple[int, dict[str, Any], dict[str, str]]:
    _push_account_runtime_publics()
    result = account_runtime.update_alias_response(profile, body, seed_persisted_profile_defaults)
    _sync_account_runtime_publics()
    return result


def profile_by_key(key: str | None) -> dict[str, str]:
    _push_account_runtime_publics()
    profile = account_runtime.profile_by_key(key, seed_persisted_profile_defaults)
    _sync_account_runtime_publics()
    return profile


def profile_by_subject(subject: str, fallback_index: int = 0) -> dict[str, str]:
    _push_account_runtime_publics()
    return account_runtime.profile_by_subject(subject, fallback_index)


def default_profile() -> dict[str, str]:
    _push_account_runtime_publics()
    return account_runtime.default_profile(seed_persisted_profile_defaults)


def profiles_from_game_state(game_state: dict[str, Any] | None = None) -> list[dict[str, str]]:
    _push_account_runtime_publics()
    return account_runtime.profiles_from_game_state(game_state, seed_persisted_profile_defaults)


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


def normalize_route_path(path: str) -> str:
    return _normalize_route_path(path)


def party_id_for_profile(profile: dict[str, str] | None = None) -> str:
    _push_account_runtime_publics()
    return account_runtime.party_id_for_profile(profile)


def party_profiles(
    game_state: dict[str, Any] | None = None,
    party_id: str | None = None,
    profile: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    _push_account_runtime_publics()
    return account_runtime.party_profiles(game_state, party_id, profile, seed_persisted_profile_defaults)


def profiles_with_current_first(current: dict[str, str], game_state: dict[str, Any] | None = None) -> list[dict[str, str]]:
    _push_account_runtime_publics()
    return account_runtime.profiles_with_current_first(current, game_state, seed_persisted_profile_defaults)


def social_roster_profiles(game_state: dict[str, Any] | None = None) -> list[dict[str, str]]:
    _push_account_runtime_publics()
    return account_runtime.social_roster_profiles(game_state, seed_persisted_profile_defaults)


def friend_profiles_for_profile(profile: dict[str, str]) -> list[dict[str, str]]:
    _push_account_runtime_publics()
    return account_runtime.friend_profiles_for_profile(profile)


def presence_roster_profiles(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    _push_account_runtime_publics()
    return account_runtime.presence_roster_profiles(game_state, profile, seed_persisted_profile_defaults)


def online_profile_keys(game_state: dict[str, Any] | None = None) -> set[str]:
    return account_runtime.online_profile_keys(game_state)


def profile_is_online(game_state: dict[str, Any] | None, profile: dict[str, str]) -> bool:
    return profile["key"] in online_profile_keys(game_state)


def mark_backend_ready(game_state: dict[str, Any] | None, profile: dict[str, str], channel: str) -> bool:
    return backend_state.mark_backend_ready(game_state, profile, channel)


def backend_ready(game_state: dict[str, Any] | None, profile: dict[str, str], channel: str) -> bool:
    return backend_state.backend_ready(game_state, profile, channel)


def set_backend_ready_keys(
    game_state: dict[str, Any] | None,
    channel: str,
    profiles: Iterable[dict[str, str]],
) -> None:
    backend_state.set_backend_ready_keys(game_state, channel, profiles, canonical_profile_key)


def clear_backend_ready_channels(game_state: dict[str, Any] | None, *channels: str) -> None:
    backend_state.clear_backend_ready_channels(game_state, *channels)


def prime_backend_state_for_phase(
    game_state: dict[str, Any] | None,
    profiles: Iterable[dict[str, str]],
    phase: str,
) -> None:
    backend_state.prime_backend_state_for_phase(game_state, profiles, phase, canonical_profile_key)


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


def _state_transition_deps() -> state_transitions.StateTransitionDependencies:
    return state_transitions.StateTransitionDependencies(
        default_profile=default_profile,
        party_id_for_profile=party_id_for_profile,
        party_profiles=party_profiles,
        profiles_from_game_state=profiles_from_game_state,
        prime_backend_state_for_phase=prime_backend_state_for_phase,
        utc_now=utc_now,
        presence_time_now=presence_time_now,
        time_now=time.time,
    )


def initial_game_state(game_host: str, game_port: int, phase: str) -> dict[str, Any]:
    return state_transitions.initial_game_state(_state_transition_deps(), game_host, game_port, phase)


loop_state = state_transitions.loop_state
active_party_state = state_transitions.active_party_state
custom_team_for_profile = state_transitions.custom_team_for_profile
set_custom_team_for_subject = state_transitions.set_custom_team_for_subject
active_provisioning_flow = state_transitions.active_provisioning_flow
character_for_profile = state_transitions.character_for_profile
character_state_for_profile = state_transitions.character_state_for_profile
set_character_for_profile = state_transitions.set_character_for_profile
pregame_character_selection_state = state_transitions.pregame_character_selection_state
should_auto_start_after_lock = state_transitions.should_auto_start_after_lock
update_state_from_json = state_transitions.update_state_from_json
configure_solo_experience = state_transitions.configure_solo_experience


def active_match_id(game_state: dict[str, Any] | None = None) -> str:
    return state_transitions.active_match_id(MATCH_ID, game_state)


def transition_to_pregame_from_matchmaking(
    game_state: dict[str, Any],
    profile: dict[str, str],
    party_id: str | None = None,
) -> bool:
    return state_transitions.transition_to_pregame_from_matchmaking(_state_transition_deps(), game_state, profile, party_id)


def start_matchmaking_state(
    game_state: dict[str, Any],
    profile: dict[str, str],
    party_id: str,
    queue_id: str,
    delay_seconds: float = 0.0,
) -> bool:
    return state_transitions.start_matchmaking_state(_state_transition_deps(), game_state, profile, party_id, queue_id, delay_seconds)


def maybe_advance_matchmaking_state(
    game_state: dict[str, Any],
    profile: dict[str, str],
    delay_seconds: float | None = None,
) -> bool:
    return state_transitions.maybe_advance_matchmaking_state(_state_transition_deps(), game_state, profile, delay_seconds)


def ensure_character_selections(
    game_state: dict[str, Any],
    state: str,
    profiles: list[dict[str, str]] | None = None,
) -> None:
    state_transitions.ensure_character_selections(_state_transition_deps(), game_state, state, profiles)


def transition_locked_match_to_core(game_state: dict[str, Any], profiles: list[dict[str, str]]) -> None:
    state_transitions.transition_locked_match_to_core(_state_transition_deps(), game_state, profiles)

def loadout_name_for_equippable(equippable_id: str, fallback_name: str) -> str:
    return loadout_payloads.loadout_name_for_equippable(equippable_id, fallback_name, DEFAULT_LOADOUT_ROWS)


def normalize_loadout_gun(gun: dict[str, Any], fallback_name: str = "Weapon") -> dict[str, str] | None:
    return loadout_payloads.normalize_loadout_gun(gun, fallback_name, DEFAULT_LOADOUT_ROWS)


def loadout_content_rows(game_state: dict[str, Any] | None = None) -> list[dict[str, str]]:
    return loadout_payloads.loadout_content_rows(game_state, DEFAULT_LOADOUT_ROWS, ALLOW_UNVERIFIED_DEFAULT_LOADOUT)


def add_gun_aliases(gun: dict[str, Any]) -> dict[str, Any]:
    return loadout_payloads.add_gun_aliases(gun)


def default_loadout_guns() -> list[dict[str, Any]]:
    return loadout_payloads.default_loadout_guns(DEFAULT_LOADOUT_ROWS, ALLOW_UNVERIFIED_DEFAULT_LOADOUT)


_SEEDED_PROFILE_KEYS: set[str] = set()


def seed_persisted_profile_defaults(profile: dict[str, str]) -> None:
    """Ensure a profile has durable baseline rows for account-owned data.

    These are zero-balance/default ownership rows in the configured persistence
    backend. They make subsequent wallet, entitlement, loadout, and contract
    responses come from stored state rather than transient literals.
    """
    key = profile.get("key", "")
    if not key or key in _SEEDED_PROFILE_KEYS:
        return
    try:
        wallet_reader = getattr(ACCOUNT_STORE, "wallet_balances", None)
        wallet_writer = getattr(ACCOUNT_STORE, "set_wallet_balance", None)
        if callable(wallet_reader) and callable(wallet_writer):
            balances = wallet_reader(key) or {}
            for currency_id in (LOCAL_CURRENCY_ID, LOCAL_UPGRADE_TOKEN_ID, LOCAL_RECRUITMENT_TOKEN_ID):
                if currency_id not in balances:
                    wallet_writer(key, currency_id, UNLOCKED_WALLET_BALANCE)

        entitlement_reader = getattr(ACCOUNT_STORE, "entitlements_for_account", None)
        entitlement_writer = getattr(ACCOUNT_STORE, "grant_entitlement", None)
        if callable(entitlement_reader) and callable(entitlement_writer):
            defaults = [
                (ITEM_TYPE_PLAYER_CARD, DEFAULT_PLAYER_CARD_ID),
                (ITEM_TYPE_PLAYER_TITLE, DEFAULT_PLAYER_TITLE_ID),
                (ITEM_TYPE_SPRAY, DEFAULT_SPRAY_PREROUND_ID),
                (ITEM_TYPE_SPRAY, DEFAULT_SPRAY_MIDROUND_ID),
                (ITEM_TYPE_CONTRACT, LOCAL_STORY_CONTRACT_ID),
            ]
            defaults.extend((ITEM_TYPE_CONTRACT, row["id"]) for row in LOCAL_CHARACTER_CONTRACT_ROWS)
            defaults.extend((ITEM_TYPE_CHARACTER, row["id"]) for row in LOCAL_AGENT_ROWS)
            for _name, _equip_id, skin_id, skin_level_id, chroma_id in DEFAULT_LOADOUT_ROWS:
                defaults.extend([
                    (ITEM_TYPE_SKIN, skin_id),
                    (ITEM_TYPE_SKIN_LEVEL, skin_level_id),
                    (ITEM_TYPE_SKIN_CHROMA, chroma_id),
                ])
            seen_default_entitlements: set[tuple[str, str]] = set()
            for item_type_id, item_id in defaults:
                pair = (str(item_type_id).lower(), str(item_id).lower())
                if pair in seen_default_entitlements:
                    continue
                seen_default_entitlements.add(pair)
                existing = entitlement_reader(key, item_type_id)
                if isinstance(existing, list) and item_id not in existing:
                    entitlement_writer(key, item_type_id, item_id, "bootstrap")

        loadout_reader = getattr(ACCOUNT_STORE, "get_player_loadout", None)
        loadout_writer = getattr(ACCOUNT_STORE, "save_player_loadout", None)
        if callable(loadout_reader) and callable(loadout_writer) and not loadout_reader(key):
            loadout_writer(key, player_loadout_payload(None, profile))

        contract_reader = getattr(ACCOUNT_STORE, "contract_state", None)
        contract_writer = getattr(ACCOUNT_STORE, "save_contract_state", None)
        if callable(contract_reader) and callable(contract_writer):
            existing_contract_state = contract_reader(key) or {}
            active_special = str(
                existing_contract_state.get("ActiveSpecialContract")
                or existing_contract_state.get("activeSpecialContract")
                or ""
            )
            if not existing_contract_state or active_special in {"", ZERO_UUID}:
                contracts = [contract_model_payload(profile, LOCAL_STORY_CONTRACT_ID)]
                contracts.extend(default_character_contract_models(profile))
                version = int(existing_contract_state.get("Version") or existing_contract_state.get("version") or 0)
                contract_writer(key, {
                    "Version": version,
                    "version": version,
                    "ActiveSpecialContract": LOCAL_STORY_CONTRACT_ID,
                    "activeSpecialContract": LOCAL_STORY_CONTRACT_ID,
                    "Contracts": contracts,
                    "contracts": contracts,
                    "Missions": existing_contract_state.get("Missions") or [],
                    "missions": existing_contract_state.get("missions") or [],
                    "ProcessedMatches": existing_contract_state.get("ProcessedMatches") or [],
                    "processedMatches": existing_contract_state.get("processedMatches") or [],
                })
    except Exception:
        return
    _SEEDED_PROFILE_KEYS.add(key)


def item_id_object(item_id: str) -> dict[str, str]:
    return loadout_payloads.item_id_object(item_id)


def normalize_item_id_object(value: Any, default_item_id: str) -> dict[str, str]:
    return loadout_payloads.normalize_item_id_object(value, default_item_id)


def userinfo_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "sub": profile["subject"],
        "acct": {"game_name": profile["game_name"], "tag_line": profile["tag_line"]},
        "country": "USA",
    }


def display_name_players_payload(profiles: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    _push_account_runtime_publics()
    if profiles is None:
        profiles = [default_profile()]
    return account_runtime.display_name_players_payload(profiles)


def display_name_payload(profiles: list[dict[str, str]] | None = None) -> dict[str, Any]:
    _push_account_runtime_publics()
    if profiles is None:
        profiles = [default_profile()]
    return account_runtime.display_name_payload(profiles)


def _configure_presence_payloads() -> None:
    presence_payloads.configure(globals())


def presence_private_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_presence_payloads()
    return presence_payloads.presence_private_payload(game_state, profile)


def presence_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
    update: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _configure_presence_payloads()
    return presence_payloads.presence_payload(game_state, profile, update)


def presences_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    _configure_presence_payloads()
    return presence_payloads.presences_payload(game_state, profile)


def _configure_social_payloads() -> None:
    social_payloads.configure(globals())


def friends_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_social_payloads()
    return social_payloads.friends_payload(game_state, profile)


def friend_payload(friend: dict[str, str], presence: dict[str, Any] | None = None) -> dict[str, Any]:
    _configure_social_payloads()
    return social_payloads.friend_payload(friend, presence)


def session_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_presence_payloads()
    return presence_payloads.session_payload(game_state, profile)


def region_locale_payload() -> dict[str, Any]:
    return {
        "region": DEFAULT_REGION,
        "locale": DEFAULT_LOCALE,
        "webLanguage": DEFAULT_WEB_LANGUAGE,
        "webRegion": DEFAULT_REGION,
    }


def patchline_metadata_payload() -> dict[str, Any]:
    return {
        "PatchLine": "local",
        "patchLine": "local",
        "Product": "ares",
        "product": "ares",
        "ClientVersion": CLIENT_VERSION,
        "clientVersion": CLIENT_VERSION,
        "Version": CLIENT_VERSION,
        "version": CLIENT_VERSION,
        "Metadata": {},
        "metadata": {},
    }


def application_repair_payload(body: Any) -> dict[str, Any]:
    repair_code = body.get("RepairCode") or body.get("repairCode") if isinstance(body, dict) else ""
    return {
        "Success": True,
        "success": True,
        "RepairCode": str(repair_code or ""),
        "repairCode": str(repair_code or ""),
    }


def agg_stats_payload(queue_id: str = "", tier: str = "", profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "QueueID": queue_id,
        "queueID": queue_id,
        "QueueId": queue_id,
        "queueId": queue_id,
        "Tier": tier,
        "tier": tier,
        "Stats": {},
        "stats": {},
        "Matches": [],
        "matches": [],
        "Version": 1,
        "version": 1,
    }


def agg_stats_args_from_route(route_path: str) -> tuple[str, str] | None:
    match = re.match(r"^/v1/stats/([^/]+)/([^/]+)/agg-stats/?$", route_path)
    if match:
        return unquote(match.group(1)), unquote(match.group(2))
    match = re.match(r"^/agg-stats/v1/stats/([^/]+)/([^/]+)/?$", route_path)
    if match:
        return unquote(match.group(1)), unquote(match.group(2))
    return None


def anti_addiction_state_payload(policy: str = "shutdown") -> dict[str, Any]:
    policy_name_by_route = {
        "shutdown": "Shutdown",
        "playTime": "PlayTime",
        "warningMessage": "WarningMessage",
    }
    route_policy_name = policy_name_by_route.get(policy, "None")
    return {
        "type": policy,
        "Type": policy,
        "message": "",
        "Message": "",
        "PolicyType": "None",
        "policyType": "None",
        "Policy": "None",
        "policy": "None",
        "RoutePolicyType": route_policy_name,
        "routePolicyType": route_policy_name,
        "DisplayType": "None",
        "displayType": "None",
        "PolicyTypeEnum": "EPolicyType::None",
        "policyTypeEnum": "EPolicyType::None",
        "DisplayTypeEnum": "EDisplayType::None",
        "displayTypeEnum": "EDisplayType::None",
        "Enabled": False,
        "enabled": False,
        "IsActive": False,
        "isActive": False,
        "CanPlay": True,
        "canPlay": True,
        "ShutdownText": "",
        "shutdownText": "",
        "WarningMessage": "",
        "warningMessage": "",
        "PlayTimeMinutes": 0,
        "playTimeMinutes": 0,
        "RemainingMinutes": 0,
        "remainingMinutes": 0,
        "metadata": {},
        "Metadata": {},
    }


def chat_session_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_presence_payloads()
    return presence_payloads.chat_session_payload(profile)


def riot_messaging_session_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_presence_payloads()
    return presence_payloads.riot_messaging_session_payload(profile)


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
        "PreferredLevelBorderID": DEFAULT_LEVEL_BORDER_ID,
        "preferredLevelBorderID": DEFAULT_LEVEL_BORDER_ID,
        "preferredLevelBorderId": DEFAULT_LEVEL_BORDER_ID,
        "Incognito": False,
        "incognito": False,
        "HideAccountLevel": False,
        "hideAccountLevel": False,
    }


def _party_payload_deps() -> party_payloads.PartyPayloadDependencies:
    return party_payloads.PartyPayloadDependencies(
        account_store=ACCOUNT_STORE,
        client_version=CLIENT_VERSION,
        default_map=DEFAULT_MAP,
        default_mode=DEFAULT_MODE,
        default_queue=DEFAULT_QUEUE,
        game_pod_id=GAME_POD_ID,
        shooting_range_queue=SHOOTING_RANGE_QUEUE,
        shooting_range_provisioning_flow=SHOOTING_RANGE_PROVISIONING_FLOW,
        default_profile=default_profile,
        profile_by_key=profile_by_key,
        party_id_for_profile=party_id_for_profile,
        party_profiles=party_profiles,
        party_muc_name=party_muc_name,
        party_voice_room_id=party_voice_room_id,
        player_identity_payload=player_identity_payload,
        all_map_paths=all_map_paths,
        all_mode_paths=all_mode_paths,
        eligible_queue_ids=eligible_queue_ids,
        active_provisioning_flow=active_provisioning_flow,
        active_party_state=active_party_state,
        custom_team_for_profile=custom_team_for_profile,
    )


def party_member_payload(profile: dict[str, str] | None = None, owner_subject: str | None = None) -> dict[str, Any]:
    return party_payloads.party_member_payload(_party_payload_deps(), profile, owner_subject)


def custom_game_configs_payload(game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    return party_payloads.custom_game_configs_payload(_party_payload_deps(), game_state)


def custom_games_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    return party_payloads.custom_games_payload(_party_payload_deps(), game_state, profile)


def party_player_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
    party_id: str | None = None,
) -> dict[str, Any]:
    return party_payloads.party_player_payload(_party_payload_deps(), game_state, profile, party_id)


def party_payload(
    game_state: dict[str, Any] | None = None,
    party_id: str | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    return party_payloads.party_payload(_party_payload_deps(), game_state, party_id, profile)


def invite_payload(invite: PartyInviteRecord) -> dict[str, Any]:
    return party_payloads.invite_payload(_party_payload_deps(), invite)


def invites_payload(profile: dict[str, str]) -> dict[str, Any]:
    return party_payloads.invites_payload(_party_payload_deps(), profile)


def account_key_from_invite_body(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for field in ("Subjects", "subjects", "Puuids", "puuids", "Invitees", "invitees"):
        raw_values = body.get(field)
        if isinstance(raw_values, list):
            for raw in raw_values:
                if isinstance(raw, str):
                    account = ACCOUNT_STORE.get_account_by_subject(raw)
                    if account:
                        return account.account_key
    for field in ("Subject", "subject", "Puuid", "puuid", "Invitee", "invitee"):
        raw = body.get(field)
        if isinstance(raw, str):
            account = ACCOUNT_STORE.get_account_by_subject(raw)
            if account:
                return account.account_key
    game_name, tag_line = alias_fields_from_body(body, {"game_name": "", "tag_line": ""})
    if game_name and tag_line:
        account = ACCOUNT_STORE.find_account_by_alias(game_name, tag_line)
        if account:
            return account.account_key
    for field in ("account_key", "accountKey", "AccountKey", "key"):
        raw = body.get(field)
        if isinstance(raw, str):
            return canonical_profile_key(raw)
    return None


def account_key_from_invite_route(route_path: str) -> str | None:
    match = re.match(r"^/parties/v1/parties/[^/]+/invites/name/([^/]+)/tag/([^/]+)", route_path)
    if not match:
        return None
    account = ACCOUNT_STORE.find_account_by_alias(unquote(match.group(1)), unquote(match.group(2)))
    return account.account_key if account else None


def invite_id_from_route(route_path: str) -> str | None:
    match = re.match(r"^/parties/v1/parties/[^/]+/invites/([0-9a-fA-F-]{36})", route_path)
    return match.group(1) if match else None


def all_map_paths() -> list[str]:
    return queue_helpers.all_map_paths(LOCAL_MAP_ROWS)


def all_mode_paths() -> list[str]:
    return queue_helpers.all_mode_paths(LOCAL_MODE_ROWS)


def queue_mode_path(queue_id: str) -> str:
    return queue_helpers.queue_mode_path(
        queue_id,
        shooting_range_queue=SHOOTING_RANGE_QUEUE,
        default_mode=DEFAULT_MODE,
        default_matchmaking_queue=DEFAULT_MATCHMAKING_QUEUE,
    )


def queue_map_paths(queue_id: str) -> list[str]:
    return queue_helpers.queue_map_paths(
        queue_id,
        shooting_range_queue=SHOOTING_RANGE_QUEUE,
        default_map=DEFAULT_MAP,
        map_rows=LOCAL_MAP_ROWS,
    )


def queue_config_by_id(queue_id: str) -> dict[str, Any] | None:
    for queue in queue_configs_payload()["Queues"]:
        if str(queue.get("QueueID")) == str(queue_id):
            return queue
    return None


def queue_config_response(queue: dict[str, Any]) -> dict[str, Any]:
    return queue_helpers.queue_config_response(queue)


def _queue_config(
    queue_id: str,
    name: str,
    *,
    team_size: int = 5,
    max_party_size: int = 5,
    ranked: bool = False,
    provisioning_flow: str = MATCHMAKING_PROVISIONING_FLOW,
) -> dict[str, Any]:
    return queue_helpers.queue_config(
        queue_id,
        name,
        map_rows=LOCAL_MAP_ROWS,
        default_map=DEFAULT_MAP,
        default_mode=DEFAULT_MODE,
        default_matchmaking_queue=DEFAULT_MATCHMAKING_QUEUE,
        shooting_range_queue=SHOOTING_RANGE_QUEUE,
        provisioning_flow_enum_value=provisioning_flow_enum_value,
        default_provisioning_flow=DEFAULT_PROVISIONING_FLOW,
        matchmaking_provisioning_flow=MATCHMAKING_PROVISIONING_FLOW,
        team_size=team_size,
        max_party_size=max_party_size,
        ranked=ranked,
        provisioning_flow=provisioning_flow,
    )


def queue_configs_payload() -> dict[str, Any]:
    return queue_helpers.queue_configs_payload(
        map_rows=LOCAL_MAP_ROWS,
        default_map=DEFAULT_MAP,
        default_mode=DEFAULT_MODE,
        default_queue=DEFAULT_QUEUE,
        default_matchmaking_queue=DEFAULT_MATCHMAKING_QUEUE,
        shooting_range_queue=SHOOTING_RANGE_QUEUE,
        default_provisioning_flow=DEFAULT_PROVISIONING_FLOW,
        matchmaking_provisioning_flow=MATCHMAKING_PROVISIONING_FLOW,
        shooting_range_provisioning_flow=SHOOTING_RANGE_PROVISIONING_FLOW,
        provisioning_flow_enum_value=provisioning_flow_enum_value,
    )


def eligible_queue_ids() -> list[str]:
    return [str(queue["QueueID"]) for queue in queue_configs_payload()["Queues"]]


queue_id_from_body = state_transitions.queue_id_from_body


def enter_matchmaking(game_state: dict[str, Any], body: Any, profile: dict[str, str], *, immediate_pregame: bool = True) -> None:
    state_transitions.enter_matchmaking(_state_transition_deps(), game_state, body, profile, immediate_pregame=immediate_pregame)


def _match_payload_deps() -> match_payloads.MatchPayloadDependencies:
    return match_payloads.MatchPayloadDependencies(
        match_id=MATCH_ID,
        game_pod_id=GAME_POD_ID,
        default_map=DEFAULT_MAP,
        default_mode=DEFAULT_MODE,
        default_queue=DEFAULT_QUEUE,
        default_character_id=DEFAULT_CHARACTER_ID,
        team_voice_id=TEAM_VOICE_ID,
        team_muc_name=TEAM_MUC_NAME,
        all_muc_name=ALL_MUC_NAME,
        default_profile=default_profile,
        party_id_for_profile=party_id_for_profile,
        party_profiles=party_profiles,
        player_identity_payload=player_identity_payload,
        active_provisioning_flow=active_provisioning_flow,
        custom_team_for_profile=custom_team_for_profile,
        character_for_profile=character_for_profile,
        character_state_for_profile=character_state_for_profile,
        pregame_character_selection_state=pregame_character_selection_state,
        utc_now=utc_now,
    )


def pregame_player_payload(game_state: dict[str, Any], profile: dict[str, str] | None = None) -> dict[str, Any]:
    return match_payloads.pregame_player_payload(_match_payload_deps(), game_state, profile)


def inactive_match_player_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    return match_payloads.inactive_match_player_payload(_match_payload_deps(), profile)


def inactive_match_payload() -> dict[str, Any]:
    return match_payloads.inactive_match_payload(_match_payload_deps())


def pregame_match_payload(game_state: dict[str, Any], profile: dict[str, str] | None = None) -> dict[str, Any]:
    return match_payloads.pregame_match_payload(_match_payload_deps(), game_state, profile)


def core_game_player_payload(game_state: dict[str, Any], profile: dict[str, str] | None = None) -> dict[str, Any]:
    return match_payloads.core_game_player_payload(_match_payload_deps(), game_state, profile)


def core_game_match_payload(game_state: dict[str, Any], profile: dict[str, str] | None = None) -> dict[str, Any]:
    return match_payloads.core_game_match_payload(_match_payload_deps(), game_state, profile)


def chat_token_payload(room: str = PARTY_MUC_NAME) -> dict[str, Any]:
    token = chat_room_token(room)
    return {
        "Token": token,
        "token": token,
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
        "Service": "project-a-chat",
        "service": "project-a-chat",
    }


def chat_room_token(room: str, profile: dict[str, str] | None = None) -> str:
    subject = profile["subject"] if profile else "room"
    return stable_token("chat-token", room, subject)


def chat_room_token_is_valid(room: str, token: str | None, profile: dict[str, str] | None = None) -> bool:
    if not token:
        return True
    token = str(token)
    # Older harnesses and captured client flows used this before room-scoped tokens existed.
    if token == "local-chat-token":
        return True
    return token in {chat_room_token(room), chat_room_token(room, profile)}


def _configure_voice_payloads() -> None:
    voice_payloads.configure(globals())


def voice_token_payload(room: str = VOICE_ROOM_ID) -> dict[str, Any]:
    _configure_voice_payloads()
    return voice_payloads.voice_token_payload(room)


def voice_session_participants_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
    party_id: str | None = None,
) -> dict[str, Any]:
    _configure_voice_payloads()
    return voice_payloads.voice_session_participants_payload(game_state, profile, party_id)


def voice_session_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_voice_payloads()
    return voice_payloads.voice_session_payload(game_state, profile)


def voice_sessions_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    _configure_voice_payloads()
    return voice_payloads.voice_sessions_payload(game_state, profile)


def account_wallet_balances(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, int]:
    profile = profile or default_profile()
    balances: dict[str, int] = {}
    wallet_by_subject = (game_state or {}).get("wallet_by_subject")
    if isinstance(wallet_by_subject, dict):
        saved = wallet_by_subject.get(profile["subject"])
        if isinstance(saved, dict):
            for item_id, amount in saved.items():
                try:
                    balances[str(item_id)] = int(amount)
                except (TypeError, ValueError):
                    continue
    store_wallet_reader = getattr(ACCOUNT_STORE, "wallet_balances", None)
    if callable(store_wallet_reader):
        try:
            for item_id, amount in store_wallet_reader(profile["key"]).items():
                balances[str(item_id)] = int(amount)
        except Exception:
            # Do not let an optional persistence read break protocol compatibility.
            pass
    return balances


def wallet_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    balances = account_wallet_balances(game_state, profile)
    return {
        "Balances": balances,
        "balances": balances,
    }


def store_offers_payload() -> dict[str, Any]:
    return store_payloads.store_offers_payload()


def account_owned_item_ids(
    item_type_id: str,
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
) -> list[str]:
    profile = profile or default_profile()
    typed_items = {
        ITEM_TYPE_PLAYER_CARD: [],
        ITEM_TYPE_PLAYER_TITLE: [],
        ITEM_TYPE_CHARACTER: [],
        ITEM_TYPE_SPRAY: [],
        ITEM_TYPE_CONTRACT: [],
        ITEM_TYPE_SKIN: [],
        ITEM_TYPE_SKIN_LEVEL: [],
        ITEM_TYPE_SKIN_CHROMA: [],
        ITEM_TYPE_CHARM: [],
        ITEM_TYPE_CHARM_LEVEL: [],
        ITEM_TYPE_SPRAY_LEVEL: [],
    }
    entitlements_by_subject = (game_state or {}).get("entitlements_by_subject")
    if isinstance(entitlements_by_subject, dict):
        saved = entitlements_by_subject.get(profile["subject"])
        if isinstance(saved, dict):
            for saved_type, saved_items in saved.items():
                if not isinstance(saved_items, list):
                    continue
                typed_items[str(saved_type).lower()] = [str(item) for item in saved_items if item]
    store_entitlement_reader = getattr(ACCOUNT_STORE, "entitlements_for_account", None)
    if callable(store_entitlement_reader):
        try:
            stored = store_entitlement_reader(profile["key"], item_type_id)
            if isinstance(stored, list):
                typed_items[item_type_id.lower()] = [str(item) for item in stored if item]
        except Exception:
            pass
    return typed_items.get(item_type_id.lower(), [])


def store_entitlements_payload(
    item_type_id: str,
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    owned_item_ids = account_owned_item_ids(item_type_id, game_state, profile)
    content_type_id = content_type_id_for_item_type(item_type_id)
    entitlements = [
        {
            "ItemID": item_id,
            "itemID": item_id,
            "InstanceID": item_id,
            "instanceID": item_id,
        }
        for item_id in owned_item_ids
    ]
    owned_entitlements = [
        {
            "TypeID": content_type_id,
            "typeID": content_type_id,
            "Type": content_type_id,
            "type": content_type_id,
            "AresContentType": content_type_id,
            "aresContentType": content_type_id,
            "ContentTypeID": content_type_id,
            "contentTypeID": content_type_id,
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
        for item_id in owned_item_ids
    ]
    entitlement_type_info = {
        "AresContentType": content_type_id,
        "aresContentType": content_type_id,
        "ItemTypeUUID": item_type_id,
        "itemTypeUUID": item_type_id,
        "ItemTypeID": item_type_id,
        "itemTypeID": item_type_id,
        "OwnedEntitlements": owned_entitlements,
        "ownedEntitlements": owned_entitlements,
        "OwnedItems": owned_item_ids,
        "ownedItems": owned_item_ids,
        "bInitialized": True,
        "Initialized": True,
        "initialized": True,
    }
    return {
        "ItemTypeID": item_type_id,
        "itemTypeID": item_type_id,
        "EntitlementTypeID": item_type_id,
        "entitlementTypeID": item_type_id,
        "EntitlementTypeId": item_type_id,
        "entitlementTypeId": item_type_id,
        "Entitlements": entitlements,
        "entitlements": entitlements,
        "OwnedEntitlements": owned_entitlements,
        "ownedEntitlements": owned_entitlements,
        "OwnedItems": owned_item_ids,
        "ownedItems": owned_item_ids,
        "EntitlementTypeInfo": entitlement_type_info,
        "entitlementTypeInfo": entitlement_type_info,
    }


def all_store_entitlements_payload(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
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
    by_type = {item_type_id: store_entitlements_payload(item_type_id, game_state, profile) for item_type_id in item_type_ids}
    entitlements = [entry for payload in by_type.values() for entry in payload["Entitlements"]]
    owned_entitlements = [entry for payload in by_type.values() for entry in payload["OwnedEntitlements"]]
    owned_items = [item_id for payload in by_type.values() for item_id in payload["OwnedItems"]]
    type_infos = {item_type_id: payload["EntitlementTypeInfo"] for item_type_id, payload in by_type.items()}
    return {
        "Entitlements": entitlements,
        "entitlements": entitlements,
        "OwnedEntitlements": owned_entitlements,
        "ownedEntitlements": owned_entitlements,
        "OwnedItems": owned_items,
        "ownedItems": owned_items,
        "EntitlementTypeInfos": type_infos,
        "entitlementTypeInfos": type_infos,
        "EntitlementsByItemType": by_type,
        "entitlementsByItemType": by_type,
    }


def store_v2_storefront_payload() -> dict[str, Any]:
    return store_payloads.store_v2_storefront_payload(LOCAL_BUNDLE_ID, LOCAL_CURRENCY_ID)


def purchase_initialized_payload() -> dict[str, Any]:
    return store_payloads.purchase_initialized_payload(LOCAL_ORDER_ID)


def purchase_response_payload(body: Any = None, route_path: str = "") -> dict[str, Any]:
    return store_payloads.purchase_response_payload(service_uuid, body, route_path)


def required_entitlement_payload(item_type_id: str, item_id: str) -> dict[str, Any]:
    return content_payloads.required_entitlement_payload(item_type_id, item_id)


def content_data_payload(item_id: str, name: str, asset: str) -> dict[str, Any]:
    return content_payloads.content_data_payload(item_id, name, asset)


def compact_content_data_payload(item_id: str, name: str, asset: str) -> dict[str, Any]:
    return content_payloads.compact_content_data_payload(item_id, name, asset)


def content_asset(item_id: str, name: str, content_type: str, asset_path: str = "") -> dict[str, Any]:
    return content_payloads.content_asset(item_id, name, content_type, asset_path)


def content_data_struct(item: dict[str, Any]) -> dict[str, Any]:
    return content_payloads.content_data_struct(item)


def content_dto_struct(item: dict[str, Any]) -> dict[str, Any]:
    return content_payloads.content_dto_struct(item)


def season_content_struct(item_id: str, name: str, season_type: str = "act") -> dict[str, Any]:
    return content_payloads.season_content_struct(item_id, name, season_type)


def content_listing(
    item: dict[str, Any],
    item_type_id: str | None = None,
    levels: list[Any] | None = None,
    required_entitlement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return content_payloads.content_listing(item, item_type_id, levels, required_entitlement)


def content_listing_bucket(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return content_payloads.content_listing_bucket(items)


def full_content_listing_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    return content_payloads.full_content_listing_payload(items)


def row_asset(row: dict[str, str], key: str, fallback: str) -> str:
    return content_payloads.row_asset(row, key, fallback, DEFAULT_LOADOUT_ASSET_PATHS)


def content_service_payload(game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    return content_payloads.content_service_payload(
        game_state,
        config={
            "DEFAULT_PLAYER_CARD_ID": DEFAULT_PLAYER_CARD_ID,
            "DEFAULT_PLAYER_CARD_ASSET": DEFAULT_PLAYER_CARD_ASSET,
            "ITEM_TYPE_PLAYER_CARD": ITEM_TYPE_PLAYER_CARD,
            "DEFAULT_PLAYER_TITLE_ID": DEFAULT_PLAYER_TITLE_ID,
            "DEFAULT_PLAYER_TITLE_ASSET": DEFAULT_PLAYER_TITLE_ASSET,
            "ITEM_TYPE_PLAYER_TITLE": ITEM_TYPE_PLAYER_TITLE,
            "LOCAL_MAP_ROWS": LOCAL_MAP_ROWS,
            "LOCAL_MODE_ROWS": LOCAL_MODE_ROWS,
            "LOCAL_CHARACTER_ROLE_ROWS": LOCAL_CHARACTER_ROLE_ROWS,
            "LOCAL_AGENT_ROWS": LOCAL_AGENT_ROWS,
            "LOCAL_CHARACTER_ROLE_BY_SLUG": LOCAL_CHARACTER_ROLE_BY_SLUG,
            "DEFAULT_SPRAY_PREROUND_ID": DEFAULT_SPRAY_PREROUND_ID,
            "DEFAULT_SPRAY_PREROUND_ASSET": DEFAULT_SPRAY_PREROUND_ASSET,
            "DEFAULT_SPRAY_MIDROUND_ID": DEFAULT_SPRAY_MIDROUND_ID,
            "DEFAULT_SPRAY_MIDROUND_ASSET": DEFAULT_SPRAY_MIDROUND_ASSET,
            "ITEM_TYPE_SPRAY": ITEM_TYPE_SPRAY,
            "LOCAL_CURRENCY_ROWS": LOCAL_CURRENCY_ROWS,
            "LOCAL_SEASON_ID": LOCAL_SEASON_ID,
            "LOCAL_SEASON_ASSET": LOCAL_SEASON_ASSET,
            "LOCAL_STORY_CONTRACT_ID": LOCAL_STORY_CONTRACT_ID,
            "LOCAL_CONTRACT_ASSET": LOCAL_CONTRACT_ASSET,
            "ITEM_TYPE_CONTRACT": ITEM_TYPE_CONTRACT,
            "LOCAL_CHARACTER_CONTRACT_ROWS": LOCAL_CHARACTER_CONTRACT_ROWS,
            "ITEM_TYPE_CHARACTER": ITEM_TYPE_CHARACTER,
            "ITEM_TYPE_SKIN": ITEM_TYPE_SKIN,
            "ITEM_TYPE_SKIN_LEVEL": ITEM_TYPE_SKIN_LEVEL,
            "ITEM_TYPE_SKIN_CHROMA": ITEM_TYPE_SKIN_CHROMA,
            "DEFAULT_LOADOUT_ASSET_PATHS": DEFAULT_LOADOUT_ASSET_PATHS,
        },
        loadout_content_rows=loadout_content_rows,
    )


def match_history_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "BeginIndex": 0,
        "beginIndex": 0,
        "EndIndex": 0,
        "endIndex": 0,
        "Total": 0,
        "total": 0,
        "History": [],
        "history": [],
    }


def competitive_updates_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return {
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "Matches": [],
        "matches": [],
        "Version": 0,
        "version": 0,
    }


def match_details_payload() -> dict[str, Any]:
    match_info = {
        "MatchID": MATCH_ID,
        "matchID": MATCH_ID,
        "MapID": DEFAULT_MAP,
        "mapID": DEFAULT_MAP,
        "GameMode": DEFAULT_MODE,
        "gameMode": DEFAULT_MODE,
        "QueueID": DEFAULT_MATCHMAKING_QUEUE,
        "queueID": DEFAULT_MATCHMAKING_QUEUE,
        "GameStartMillis": 0,
        "gameStartMillis": 0,
        "GameLengthMillis": 0,
        "gameLengthMillis": 0,
    }
    return {
        "MatchID": MATCH_ID,
        "matchID": MATCH_ID,
        "MatchInfo": match_info,
        "matchInfo": match_info,
        "Players": [],
        "players": [],
        "Teams": [],
        "teams": [],
        "Rounds": [],
        "rounds": [],
        "Kills": [],
        "kills": [],
    }


def player_report_payload(body: Any, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    report_body = body if isinstance(body, dict) else {}
    offender = (
        report_body.get("Offender_puuid")
        or report_body.get("offender_puuid")
        or report_body.get("OffenderPuuid")
        or report_body.get("offenderPuuid")
        or ""
    )
    token = stable_token("player-report", profile["subject"], offender, utc_now())
    return {
        "Token": token,
        "token": token,
        "Reporter": profile["subject"],
        "reporter": profile["subject"],
        "OffenderPuuid": str(offender or ""),
        "offenderPuuid": str(offender or ""),
        "Success": True,
        "success": True,
    }


def wegame_player_info_payload() -> dict[str, Any]:
    return {
        "IsUnderage": False,
        "isUnderage": False,
    }


def player_loadout_payload(loadout: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    return loadout_payloads.player_loadout_payload(
        loadout,
        profile,
        player_identity_payload,
        DEFAULT_LOADOUT_ROWS,
        ALLOW_UNVERIFIED_DEFAULT_LOADOUT,
        DEFAULT_PLAYER_CARD_ID,
        DEFAULT_PLAYER_TITLE_ID,
    )


def contract_chapter_payload(chapter: dict[str, Any]) -> dict[str, Any]:
    return contract_payloads.contract_chapter_payload(chapter)


def contract_model_payload(
    profile: dict[str, str] | None = None,
    contract_id: str | None = None,
    level_count: int = 10,
) -> dict[str, Any]:
    contract_id = str(contract_id or LOCAL_STORY_CONTRACT_ID)
    return contract_payloads.contract_model_payload(contract_id, level_count)


def remap_contract_payload(value: Any, contract_id: str, name: str) -> Any:
    if isinstance(value, dict):
        return {key: remap_contract_payload(item, contract_id, name) for key, item in value.items()}
    if isinstance(value, list):
        return [remap_contract_payload(item, contract_id, name) for item in value]
    if value == LOCAL_STORY_CONTRACT_ID:
        return contract_id
    if value in {"Inactive Contract", "Local Story Contract"}:
        return name
    return value


def default_character_contract_models(profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    _ = profile
    return contract_payloads.default_character_contract_models(LOCAL_CHARACTER_CONTRACT_ROWS, LOCAL_STORY_CONTRACT_ID)


def subject_contract_state(game_state: dict[str, Any] | None, profile: dict[str, str]) -> dict[str, Any]:
    states = (game_state or {}).get("contracts_by_subject")
    state = states.get(profile["subject"]) or states.get(profile["subject"].lower()) if isinstance(states, dict) else None
    if isinstance(state, dict):
        return state
    store_reader = getattr(ACCOUNT_STORE, "contract_state", None)
    if callable(store_reader):
        try:
            stored = store_reader(profile["key"])
            if isinstance(stored, dict):
                return stored
        except Exception:
            pass
    return {}


def set_active_special_contract(game_state: dict[str, Any], profile: dict[str, str], contract_id: str) -> dict[str, Any]:
    states = game_state.setdefault("contracts_by_subject", {})
    if not isinstance(states, dict):
        states = {}
        game_state["contracts_by_subject"] = states
    previous = subject_contract_state(game_state, profile)
    version = int(previous.get("Version") or previous.get("version") or 0) + 1
    active_contract_id = str(contract_id or LOCAL_STORY_CONTRACT_ID)
    contract = remap_contract_payload(contract_model_payload(profile), active_contract_id, "Active Special Contract")
    state = {
        "Version": version,
        "ActiveSpecialContract": active_contract_id,
        "Contracts": [contract],
        "Missions": [],
        "ProcessedMatches": [],
    }
    states[profile["subject"]] = state
    store_writer = getattr(ACCOUNT_STORE, "save_contract_state", None)
    if callable(store_writer):
        try:
            store_writer(profile["key"], state)
        except Exception:
            pass
    return state


def contracts_payload(profile: dict[str, str] | None = None, game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or default_profile()
    state = subject_contract_state(game_state, profile)
    return contract_payloads.contracts_payload(
        profile,
        state,
        local_story_contract_id=LOCAL_STORY_CONTRACT_ID,
        local_character_contract_rows=LOCAL_CHARACTER_CONTRACT_ROWS,
    )


def item_progression_definitions_payload(game_state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return contract_payloads.item_progression_definitions_payload(
        loadout_content_rows(game_state),
        item_type_skin_level=ITEM_TYPE_SKIN_LEVEL,
        item_type_skin_chroma=ITEM_TYPE_SKIN_CHROMA,
    )


def contract_definition_payload() -> dict[str, Any]:
    return contract_payloads.contract_definition_payload(
        local_story_contract_id=LOCAL_STORY_CONTRACT_ID,
        local_currency_id=LOCAL_CURRENCY_ID,
        item_type_contract=ITEM_TYPE_CONTRACT,
        local_contract_asset=LOCAL_CONTRACT_ASSET,
    )


def character_contract_definition_payload(contract_row: dict[str, Any]) -> dict[str, Any]:
    return contract_payloads.character_contract_definition_payload(
        contract_row,
        local_currency_id=LOCAL_CURRENCY_ID,
        item_type_contract=ITEM_TYPE_CONTRACT,
    )


def contract_definitions_payload(game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    item_progressions = item_progression_definitions_payload(game_state)
    story_definition = contract_definition_payload()
    character_definitions = [character_contract_definition_payload(row) for row in LOCAL_CHARACTER_CONTRACT_ROWS]
    return contract_payloads.contract_definitions_payload(
        item_progressions=item_progressions,
        story_definition=story_definition,
        character_definitions=character_definitions,
        local_story_contract_id=LOCAL_STORY_CONTRACT_ID,
    )


def active_story_contract_definition_payload(game_state: dict[str, Any] | None = None) -> dict[str, Any]:
    story_definition = contract_definition_payload()
    character_definitions = [character_contract_definition_payload(row) for row in LOCAL_CHARACTER_CONTRACT_ROWS]
    return contract_payloads.active_story_contract_definition_payload(
        story_definition=story_definition,
        character_definitions=character_definitions,
        local_story_contract_id=LOCAL_STORY_CONTRACT_ID,
    )


def _configure_realtime_payloads() -> None:
    realtime_payloads.configure(globals())


def json_api_event(uri: str, data: Any, event_type: str = "Update") -> dict[str, Any]:
    _configure_realtime_payloads()
    return realtime_payloads.json_api_event(uri, data, event_type)


def rms_resource_messages(service: str, pairs: list[tuple[str, str, Any]]) -> list[dict[str, Any]]:
    _configure_realtime_payloads()
    return realtime_payloads.rms_resource_messages(service, pairs)


def rms_party_messages(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    _configure_realtime_payloads()
    return realtime_payloads.rms_party_messages(game_state, profile)


def rms_match_messages(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    _configure_realtime_payloads()
    return realtime_payloads.rms_match_messages(game_state, profile)


def riot_messaging_messages_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_realtime_payloads()
    return realtime_payloads.riot_messaging_messages_payload(game_state, profile)


def chat_presence_events(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    _configure_realtime_payloads()
    return realtime_payloads.chat_presence_events(game_state, profile)


def _configure_chat_payloads() -> None:
    chat_payloads.configure(globals())


def joined_chat_rooms_for_profile(game_state: dict[str, Any] | None, profile: dict[str, str] | None = None) -> set[str]:
    _configure_chat_payloads()
    return chat_payloads.joined_chat_rooms_for_profile(game_state, profile)


def profile_has_joined_chat_room(game_state: dict[str, Any] | None, profile: dict[str, str], cid: str | None) -> bool:
    _configure_chat_payloads()
    return chat_payloads.profile_has_joined_chat_room(game_state, profile, cid)


def chat_room_is_available_to_profile(game_state: dict[str, Any] | None, profile: dict[str, str], cid: str | None) -> bool:
    _configure_chat_payloads()
    return chat_payloads.chat_room_is_available_to_profile(game_state, profile, cid)


def chat_messages_for_room(game_state: dict[str, Any] | None, cid: str | None) -> list[dict[str, Any]]:
    _configure_chat_payloads()
    return chat_payloads.chat_messages_for_room(game_state, cid)


def chat_read_ack_payload(body: Any, cid: str = "") -> dict[str, Any]:
    _configure_chat_payloads()
    return chat_payloads.chat_read_ack_payload(body, cid)


def chat_unified_room_type(room: str) -> str:
    _configure_chat_payloads()
    return chat_payloads.chat_unified_room_type(room)


def chat_muc_message_payload(message: dict[str, Any]) -> dict[str, Any]:
    _configure_chat_payloads()
    return chat_payloads.chat_muc_message_payload(message)


def chat_unified_message_payload(message: dict[str, Any]) -> dict[str, Any]:
    _configure_chat_payloads()
    return chat_payloads.chat_unified_message_payload(message)


def chat_room_infos(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    _configure_chat_payloads()
    return chat_payloads.chat_room_infos(game_state, profile)


def join_chat_room(game_state: dict[str, Any], cid: str | None, profile: dict[str, str] | None = None) -> bool:
    _configure_chat_payloads()
    return chat_payloads.join_chat_room(game_state, cid, profile)


def leave_chat_room(game_state: dict[str, Any], cid: str | None, profile: dict[str, str] | None = None) -> bool:
    _configure_chat_payloads()
    return chat_payloads.leave_chat_room(game_state, cid, profile)


def sync_party_chat_room(
    game_state: dict[str, Any],
    profile: dict[str, str],
    previous_party_id: str | None,
    new_party_id: str | None,
) -> bool:
    _configure_chat_payloads()
    return chat_payloads.sync_party_chat_room(game_state, profile, previous_party_id, new_party_id)


def chat_conversation_list(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    _configure_chat_payloads()
    return chat_payloads.chat_conversation_list(game_state, profile)


def chat_conversations_payload(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_chat_payloads()
    return chat_payloads.chat_conversations_payload(game_state, profile)


def chat_conversation_for_cid_payload(
    game_state: dict[str, Any] | None = None,
    cid: str | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    _configure_chat_payloads()
    return chat_payloads.chat_conversation_for_cid_payload(game_state, cid, profile)


def chat_participants_for_room(
    game_state: dict[str, Any] | None = None,
    cid: str | None = None,
    profile: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    _configure_chat_payloads()
    return chat_payloads.chat_participants_for_room(game_state, cid, profile)


def chat_muc_participants_for_room(game_state: dict[str, Any] | None = None, cid: str | None = None) -> list[dict[str, Any]]:
    _configure_chat_payloads()
    return chat_payloads.chat_muc_participants_for_room(game_state, cid)


def chat_participants_payload(
    game_state: dict[str, Any] | None = None,
    cid: str | None = None,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    _configure_chat_payloads()
    return chat_payloads.chat_participants_payload(game_state, cid, profile)


def chat_participants_uri(cid: str | None = None) -> str:
    _configure_chat_payloads()
    return chat_payloads.chat_participants_uri(cid)


def chat_participants_uri_variants(cid: str | None = None) -> list[str]:
    _configure_chat_payloads()
    return chat_payloads.chat_participants_uri_variants(cid)


def profile_from_social_body(body: Any) -> dict[str, str] | None:
    _configure_social_payloads()
    return social_payloads.profile_from_social_body(body)


def friend_request_payload(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_social_payloads()
    return social_payloads.friend_request_payload(record, current_profile)


def friend_request_wire_item(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_social_payloads()
    return social_payloads.friend_request_wire_item(record, current_profile)


def friend_request_model_aliases(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_social_payloads()
    return social_payloads.friend_request_model_aliases(record, current_profile)


def friend_requests_payload(profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_social_payloads()
    return social_payloads.friend_requests_payload(profile)


def friend_request_response_payload(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_social_payloads()
    return social_payloads.friend_request_response_payload(record, current_profile)


def friend_request_add_event_payload(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_social_payloads()
    return social_payloads.friend_request_add_event_payload(record, current_profile)


def friend_request_remove_event_payload(record: FriendRequestRecord, current_profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_social_payloads()
    return social_payloads.friend_request_remove_event_payload(record, current_profile)


def pending_friend_request_for_id(profile: dict[str, str], request_id: str) -> FriendRequestRecord | None:
    _configure_social_payloads()
    return social_payloads.pending_friend_request_for_id(profile, request_id)


def pending_friend_request_for_identifier(profile: dict[str, str], identifier: str) -> FriendRequestRecord | None:
    _configure_social_payloads()
    return social_payloads.pending_friend_request_for_identifier(profile, identifier)


def inbound_friend_request_from_target(profile: dict[str, str], target: dict[str, str]) -> FriendRequestRecord | None:
    _configure_social_payloads()
    return social_payloads.inbound_friend_request_from_target(profile, target)


def create_friend_request_response(
    profile: dict[str, str],
    body: Any,
    game_state: dict[str, Any] | None = None,
    auto_accept: bool = False,
) -> tuple[int, dict[str, Any]]:
    _configure_social_payloads()
    return social_payloads.create_friend_request_response(profile, body, game_state, auto_accept)


def chat_messages_payload(game_state: dict[str, Any] | None = None, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    _configure_chat_payloads()
    return chat_payloads.chat_messages_payload(game_state, messages)


def chat_message_response_payload(message: dict[str, Any]) -> dict[str, Any]:
    _configure_chat_payloads()
    return chat_payloads.chat_message_response_payload(message)


def chat_message_payload(body: Any, profile: dict[str, str] | None = None) -> dict[str, Any]:
    _configure_chat_payloads()
    return chat_payloads.chat_message_payload(body, profile)


def session_events(game_state: dict[str, Any] | None = None, profile: dict[str, str] | None = None) -> list[dict[str, Any]]:
    _configure_realtime_payloads()
    return realtime_payloads.session_events(game_state, profile)


def ensure_cert(cert_path: Path, key_path: Path, ca_cert_path: Path) -> None:
    from .certs import ensure_cert as _ensure_cert

    _ensure_cert(cert_path, key_path, ca_cert_path)


from .runtime.http import DualProtocolHTTPServer, ProbeHandler


def main() -> None:
    from .server import main as _main

    _main()


if __name__ == "__main__":
    main()
