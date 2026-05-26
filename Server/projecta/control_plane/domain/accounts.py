"""Runtime account/profile helpers for the control-plane app."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Callable

try:
    from ...storage.accounts import (
        AccountRecord,
        AccountStore,
        account_from_hint,
        create_account_store,
        generated_subject,
        normalize_account_key,
    )
except ImportError:
    from projecta.storage.accounts import (
        AccountRecord,
        AccountStore,
        account_from_hint,
        create_account_store,
        generated_subject,
        normalize_account_key,
    )


CHAT_RESOURCE = "project-a-client"
ACCOUNT_STORE: AccountStore = create_account_store(allow_memory_db=True)
LOCAL_PROFILES = {
    "developer": {
        "key": "developer",
    },
    "developer2": {
        "key": "developer2",
    },
}
RUNTIME_PROFILE_HINTS: dict[str, dict[str, str]] = {}
DEFAULT_PROFILE_KEY = "developer"
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

SeedDefaults = Callable[[dict[str, str]], None]


def set_account_store(store: AccountStore) -> AccountStore:
    global ACCOUNT_STORE
    ACCOUNT_STORE = store
    return ACCOUNT_STORE


def configure_account_store(
    database_url: str | None = None,
    *,
    allow_memory_db: bool = False,
    migrate: bool = True,
) -> AccountStore:
    store = create_account_store(database_url, allow_memory_db=allow_memory_db)
    if migrate:
        store.migrate()
    return set_account_store(store)


def set_default_profile_key(key: str | None) -> str:
    global DEFAULT_PROFILE_KEY
    DEFAULT_PROFILE_KEY = canonical_profile_key(key)
    return DEFAULT_PROFILE_KEY


def login_key_and_hint(value: str | None) -> tuple[str, dict[str, str] | None]:
    """Return a canonical local account key plus optional alias hint."""
    raw = str(value or "").strip().strip('"')
    if not raw:
        return canonical_profile_key(None), None
    if raw.lower().startswith("bearer "):
        raw = raw.split(" ", 1)[1].strip()
    for prefix in ("local-access-token-", "local-entitlements-token-", "access-token-", "entitlements-token-"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    if "#" in raw:
        game_name, tag_line = raw.rsplit("#", 1)
        game_name = game_name.strip() or "Player"
        tag_line = tag_line.strip() or "LOCAL"
        key = normalize_account_key(f"{game_name}-{tag_line}")
        hint = {"key": key, "game_name": game_name, "tag_line": tag_line}
        RUNTIME_PROFILE_HINTS[key] = hint
        return key, hint
    key = canonical_profile_key(raw)
    return key, RUNTIME_PROFILE_HINTS.get(key)


def profile_by_login(value: str | None, seed_defaults: SeedDefaults | None = None) -> dict[str, str]:
    key, hint = login_key_and_hint(value)
    if hint is None:
        hint = LOCAL_PROFILES.get(key) or RUNTIME_PROFILE_HINTS.get(key)
    if hint and hint.get("game_name") and hint.get("tag_line"):
        existing = ACCOUNT_STORE.find_account_by_alias(str(hint["game_name"]), str(hint["tag_line"]))
        if existing:
            profile = profile_from_account(existing)
            if seed_defaults:
                seed_defaults(profile)
            return profile
    account = ACCOUNT_STORE.get_or_create_account(key, hint)
    profile = profile_from_account(account)
    if seed_defaults:
        seed_defaults(profile)
    return profile


def set_default_profile_from_login(value: str | None, seed_defaults: SeedDefaults | None = None) -> dict[str, str]:
    key, hint = login_key_and_hint(value)
    set_default_profile_key(key)
    if hint:
        RUNTIME_PROFILE_HINTS[key] = hint
    return profile_by_login(value or key, seed_defaults)


def canonical_profile_key(key: str | None) -> str:
    raw = normalize_account_key(key)
    raw = PROFILE_ALIASES.get(raw, raw)
    return normalize_account_key(raw)


def register_local_profile(
    account_key: str | None,
    game_name: str | None = None,
    tag_line: str | None = None,
    subject: str | None = None,
) -> dict[str, str]:
    """Register and persist a local profile hint used by startup scripts and tests."""
    key = canonical_profile_key(account_key)
    hint: dict[str, str] = {"key": key}
    if game_name:
        hint["game_name"] = str(game_name).strip()
    if tag_line:
        hint["tag_line"] = str(tag_line).strip()
    if subject:
        hint["subject"] = str(subject).strip()
    LOCAL_PROFILES[key] = hint
    PROFILE_ALIASES[key] = key
    account = ACCOUNT_STORE.get_or_create_account(key, hint)
    if game_name or tag_line:
        account = ACCOUNT_STORE.update_alias(account.account_key, hint.get("game_name", account.game_name), hint.get("tag_line", account.tag_line))
    return profile_from_account(account)


def profile_from_display_name(display_name: str) -> dict[str, str] | None:
    raw = str(display_name or "").strip()
    if "#" not in raw:
        return None
    game_name, tag_line = raw.rsplit("#", 1)
    account = ACCOUNT_STORE.find_account_by_alias(game_name.strip(), tag_line.strip())
    return profile_from_account(account) if account else None


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


def alias_payload(profile: dict[str, str]) -> dict[str, Any]:
    return {
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "game_name": profile["game_name"],
        "tag_line": profile["tag_line"],
        "summoner": profile["game_name"],
        "GameName": profile["game_name"],
        "TagLine": profile["tag_line"],
        "GameTag": profile["tag_line"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "active": True,
        "created_datetime": 0,
        "errorCode": "",
        "errorMessage": "",
        "isSuccess": True,
        "isTagLineCustomizable": True,
    }


def local_account_payload(profile: dict[str, str]) -> dict[str, Any]:
    return {
        "account_key": profile["key"],
        "accountKey": profile["key"],
        "Subject": profile["subject"],
        "subject": profile["subject"],
        "Puuid": profile["subject"],
        "puuid": profile["subject"],
        "GameName": profile["game_name"],
        "gameName": profile["game_name"],
        "game_name": profile["game_name"],
        "TagLine": profile["tag_line"],
        "tagLine": profile["tag_line"],
        "tag_line": profile["tag_line"],
        "DisplayName": profile["display_name"],
        "displayName": profile["display_name"],
        "riotId": profile["display_name"],
        "chatPid": profile["chat_pid"],
        "partyId": party_id_for_profile(profile),
        "active": True,
    }


def alias_fields_from_body(body: Any, fallback: dict[str, str]) -> tuple[str, str]:
    if not isinstance(body, dict):
        return fallback["game_name"], fallback["tag_line"]
    game_name = (
        body.get("game_name")
        or body.get("gameName")
        or body.get("GameName")
        or body.get("summoner")
        or body.get("name")
        or fallback["game_name"]
    )
    tag_line = (
        body.get("tag_line")
        or body.get("tagLine")
        or body.get("TagLine")
        or body.get("game_tag")
        or body.get("GameTag")
        or body.get("gameTag")
        or body.get("tag")
        or fallback["tag_line"]
    )
    return str(game_name), str(tag_line)


def alias_availability_payload(game_name: str, tag_line: str, owner_key: str | None = None) -> dict[str, Any]:
    game_name = str(game_name or "").strip()
    tag_line = str(tag_line or "").strip()
    valid = bool(game_name and tag_line and len(game_name) <= 16 and len(tag_line) <= 8)
    owner = ACCOUNT_STORE.find_account_by_alias(game_name, tag_line) if valid else None
    available = valid and (owner is None or owner.account_key == owner_key)
    code = "" if available else ("INVALID_ALIAS" if not valid else "ALIAS_NOT_AVAILABLE")
    message = "" if available else ("Invalid display name or tag line." if not valid else "That name and tag are already in use.")
    return {
        "errorCode": code,
        "errorMessage": message,
        "isSuccess": available,
        "IsSuccess": available,
        "isAvailable": available,
        "available": available,
        "isTagLineCustomizable": True,
        "GameName": game_name,
        "TagLine": tag_line,
        "game_name": game_name,
        "tag_line": tag_line,
    }


def update_alias_response(
    profile: dict[str, str],
    body: Any,
    seed_defaults: SeedDefaults | None = None,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    game_name, tag_line = alias_fields_from_body(body, profile)
    availability = alias_availability_payload(game_name, tag_line, profile["key"])
    if not availability["isSuccess"]:
        return 409, availability, profile
    try:
        updated = profile_from_account(ACCOUNT_STORE.update_alias(profile["key"], game_name, tag_line))
    except ValueError as exc:
        payload = dict(availability)
        payload.update({"errorCode": "ALIAS_NOT_AVAILABLE", "errorMessage": str(exc), "isSuccess": False, "IsSuccess": False})
        return 409, payload, profile
    if seed_defaults:
        seed_defaults(updated)
    return 200, alias_payload(updated), updated


def profile_by_key(key: str | None, seed_defaults: SeedDefaults | None = None) -> dict[str, str]:
    canonical = canonical_profile_key(key)
    hint = LOCAL_PROFILES.get(canonical) or RUNTIME_PROFILE_HINTS.get(canonical)
    account = ACCOUNT_STORE.get_or_create_account(canonical, hint)
    profile = profile_from_account(account)
    if seed_defaults:
        seed_defaults(profile)
    return profile


def profile_by_subject(subject: str, fallback_index: int = 0) -> dict[str, str]:
    subject = str(subject or "").strip()
    account = ACCOUNT_STORE.get_account_by_subject(subject)
    if account:
        return profile_from_account(account)
    for key, hint in LOCAL_PROFILES.items():
        hint_subject = str(hint.get("subject") or generated_subject(key))
        if hint_subject.lower() == subject.lower():
            return profile_by_key(key)
    try:
        suffix = str(uuid.UUID(subject)).split("-")[0][:4].upper()
    except ValueError:
        suffix = hashlib.sha1(subject.encode("utf-8", errors="ignore")).hexdigest()[:4].upper()
    if not suffix:
        suffix = str(fallback_index + 1)
    account = account_from_hint(f"subject-{suffix.lower()}", {"subject": subject})
    return profile_from_account(account)


def default_profile(seed_defaults: SeedDefaults | None = None) -> dict[str, str]:
    return profile_by_key(DEFAULT_PROFILE_KEY, seed_defaults)


def profiles_from_game_state(
    game_state: dict[str, Any] | None = None,
    seed_defaults: SeedDefaults | None = None,
) -> list[dict[str, str]]:
    keys = []
    if game_state:
        raw_keys = game_state.get("active_profile_keys")
        if isinstance(raw_keys, list):
            keys = [str(key) for key in raw_keys]
    if not keys:
        keys = [DEFAULT_PROFILE_KEY]
    canonical_keys = []
    for key in keys:
        canonical = canonical_profile_key(key)
        if canonical not in canonical_keys:
            canonical_keys.append(canonical)
    profiles = [profile_by_key(key, seed_defaults) for key in canonical_keys]
    return profiles or [default_profile(seed_defaults)]


def party_id_for_profile(profile: dict[str, str] | None = None) -> str:
    profile = profile or default_profile()
    return ACCOUNT_STORE.current_party_id(profile["key"])


def party_profiles(
    game_state: dict[str, Any] | None = None,
    party_id: str | None = None,
    profile: dict[str, str] | None = None,
    seed_defaults: SeedDefaults | None = None,
) -> list[dict[str, str]]:
    profile = profile or default_profile(seed_defaults)
    party_id = party_id or party_id_for_profile(profile)
    members = [profile_from_account(account) for account in ACCOUNT_STORE.party_members(party_id)]
    if not any(member["subject"].lower() == profile["subject"].lower() for member in members):
        if party_id_for_profile(profile) == party_id:
            members.insert(0, profile)
    if not members and party_id_for_profile(profile) == party_id:
        return [profile]
    return members


def profiles_with_current_first(
    current: dict[str, str],
    game_state: dict[str, Any] | None = None,
    seed_defaults: SeedDefaults | None = None,
) -> list[dict[str, str]]:
    profiles = [current]
    profiles.extend(profile for profile in profiles_from_game_state(game_state, seed_defaults) if profile["subject"] != current["subject"])
    return profiles


def social_roster_profiles(
    game_state: dict[str, Any] | None = None,
    seed_defaults: SeedDefaults | None = None,
) -> list[dict[str, str]]:
    profiles = profiles_from_game_state(game_state, seed_defaults)
    for account in ACCOUNT_STORE.known_accounts():
        profile = profile_from_account(account)
        if all(existing["subject"] != profile["subject"] for existing in profiles):
            profiles.append(profile)
    return profiles


def friend_profiles_for_profile(profile: dict[str, str]) -> list[dict[str, str]]:
    return [profile_from_account(account) for account in ACCOUNT_STORE.friends_for_account(profile["key"])]


def presence_roster_profiles(
    game_state: dict[str, Any] | None = None,
    profile: dict[str, str] | None = None,
    seed_defaults: SeedDefaults | None = None,
) -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    if profile:
        profiles.append(profile)
        profiles.extend(friend_profiles_for_profile(profile))
    for key in sorted(online_profile_keys(game_state)):
        active_profile = profile_by_key(key, seed_defaults)
        if all(existing["subject"] != active_profile["subject"] for existing in profiles):
            profiles.append(active_profile)
    return profiles


def online_profile_keys(game_state: dict[str, Any] | None = None) -> set[str]:
    raw_keys = (game_state or {}).get("active_profile_keys")
    if not isinstance(raw_keys, list):
        return set()
    return {canonical_profile_key(str(key)) for key in raw_keys}


def display_name_players_payload(profiles: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    profiles = [default_profile()] if profiles is None else profiles
    return [
        {
            "Subject": profile["subject"],
            "FullName": profile["display_name"],
            "fullName": profile["display_name"],
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
    if not players:
        return {
            "Subject": "",
            "FullName": "",
            "GameName": "",
            "TagLine": "",
            "GameTag": "",
            "DisplayName": "",
            "fullName": "",
            "gameName": "",
            "tagLine": "",
            "displayName": "",
            "Player": None,
            "Name": "",
            "Names": [],
            "names": [],
            "Players": [],
            "players": [],
        }
    first = players[0]
    return {
        "Subject": first["Subject"],
        "FullName": first["FullName"],
        "GameName": first["GameName"],
        "TagLine": first["TagLine"],
        "GameTag": first["GameTag"],
        "DisplayName": first["DisplayName"],
        "fullName": first["FullName"],
        "gameName": first["gameName"],
        "tagLine": first["tagLine"],
        "displayName": first["displayName"],
        "Player": first,
        "Name": first["FullName"],
        "Names": players,
        "names": players,
        "Players": players,
        "players": players,
    }
