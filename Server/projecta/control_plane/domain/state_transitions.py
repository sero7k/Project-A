"""Game, party, and match state transition helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from ..data.catalog import (
    DEFAULT_CHARACTER_ID,
    DEFAULT_MAP,
    DEFAULT_MATCHMAKING_QUEUE,
    DEFAULT_MODE,
    DEFAULT_PROVISIONING_FLOW,
    LOCAL_MAP_ROWS,
    LOCAL_MODE_ROWS,
    DEFAULT_QUEUE,
    MATCHMAKING_PROVISIONING_FLOW,
    SHOOTING_RANGE_MAP,
    SHOOTING_RANGE_MODE,
    SHOOTING_RANGE_PROVISIONING_FLOW,
    SHOOTING_RANGE_QUEUE,
)
from .state_helpers import first_string, normalize_custom_team, request_settings_from_body


@dataclass(frozen=True)
class StateTransitionDependencies:
    default_profile: Callable[[], dict[str, str]]
    party_id_for_profile: Callable[[dict[str, str] | None], str]
    party_profiles: Callable[[dict[str, Any] | None, str | None, dict[str, str] | None], list[dict[str, str]]]
    profiles_from_game_state: Callable[[dict[str, Any] | None], list[dict[str, str]]]
    prime_backend_state_for_phase: Callable[[dict[str, Any] | None, Iterable[dict[str, str]], str], None]
    utc_now: Callable[[], str]
    presence_time_now: Callable[[], str]
    time_now: Callable[[], float] = time.time


def initial_game_state(deps: StateTransitionDependencies, game_host: str, game_port: int, phase: str) -> dict[str, Any]:
    default = deps.default_profile()
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
        "party_ready_keys": [],
        "pregame_ready_keys": [],
        "core_ready_keys": [],
        "session_by_profile": {},
        "joined_chat_rooms": [],
        "joined_chat_rooms_by_subject": {},
        "chat_messages": [],
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
                "character_selection_state": "locked",
                "character_id_by_subject": {default["subject"]: DEFAULT_CHARACTER_ID},
                "character_selection_state_by_subject": {default["subject"]: "locked"},
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
        if explicit_state in {"CUSTOM_GAME_STARTING", "SOLO_EXPERIENCE_STARTING", "MATCHMADE_GAME_STARTING", "MATCHMAKING"}:
            return explicit_state
        return "CUSTOM_GAME_STARTING"
    if game_state.get("phase") == "core":
        explicit_state = str(game_state.get("party_state") or "")
        if explicit_state in {"SOLO_EXPERIENCE_STARTING", "MATCHMADE_GAME_STARTING"}:
            return explicit_state
        return "MATCHMADE_GAME_STARTING"
    return str(game_state.get("party_state") or "DEFAULT")


def active_match_id(match_id: str, game_state: dict[str, Any] | None = None) -> str:
    if game_state and game_state.get("phase") in {"pregame", "core"}:
        return match_id
    return ""


def transition_to_pregame_from_matchmaking(
    deps: StateTransitionDependencies,
    game_state: dict[str, Any],
    profile: dict[str, str],
    party_id: str | None = None,
) -> bool:
    if game_state.get("party_state") != "MATCHMAKING":
        return False
    party_id = party_id or deps.party_id_for_profile(profile)
    game_state["phase"] = "pregame"
    game_state["party_state"] = "MATCHMADE_GAME_STARTING"
    game_state["pregame_state"] = "character_select_active"
    game_state["provisioning_flow"] = game_state.get("provisioning_flow") or DEFAULT_PROVISIONING_FLOW
    game_state["matchmaking_transitioned_at"] = deps.utc_now()
    current_party_profiles = deps.party_profiles(game_state, party_id, profile)
    ensure_character_selections(deps, game_state, "", current_party_profiles)
    deps.prime_backend_state_for_phase(game_state, current_party_profiles, "pregame")
    return True


def start_matchmaking_state(
    deps: StateTransitionDependencies,
    game_state: dict[str, Any],
    profile: dict[str, str],
    party_id: str,
    queue_id: str,
    delay_seconds: float = 0.0,
) -> bool:
    queue_id = str(queue_id or DEFAULT_QUEUE)
    game_state["phase"] = "menus"
    game_state["party_state"] = "MATCHMAKING"
    game_state["pregame_state"] = ""
    game_state["queue"] = queue_id
    game_state["provisioning_flow"] = DEFAULT_PROVISIONING_FLOW
    game_state["matchmaking_party_id"] = party_id
    game_state["matchmaking_queue_id"] = queue_id
    game_state["matchmaking_started_unix"] = deps.time_now()
    game_state["matchmaking_started_at"] = deps.utc_now()
    game_state["matchmaking_delay_seconds"] = max(0.0, float(delay_seconds or 0.0))
    deps.prime_backend_state_for_phase(game_state, deps.party_profiles(game_state, party_id, profile), "menus")
    if delay_seconds <= 0:
        return transition_to_pregame_from_matchmaking(deps, game_state, profile, party_id)
    return False


def maybe_advance_matchmaking_state(
    deps: StateTransitionDependencies,
    game_state: dict[str, Any],
    profile: dict[str, str],
    delay_seconds: float | None = None,
) -> bool:
    if game_state.get("party_state") != "MATCHMAKING":
        return False
    delay = game_state.get("matchmaking_delay_seconds")
    if delay is None:
        delay = delay_seconds if delay_seconds is not None else 0.0
    try:
        delay = float(delay)
    except (TypeError, ValueError):
        delay = 0.0
    try:
        started = float(game_state.get("matchmaking_started_unix") or 0.0)
    except (TypeError, ValueError):
        started = 0.0
    if delay <= 0 or not started or (deps.time_now() - started) >= delay:
        return transition_to_pregame_from_matchmaking(
            deps,
            game_state,
            profile,
            str(game_state.get("matchmaking_party_id") or deps.party_id_for_profile(profile)),
        )
    return False


def custom_team_for_profile(game_state: dict[str, Any] | None, profile: dict[str, str]) -> str:
    team_by_subject = (game_state or {}).get("custom_team_by_subject")
    if isinstance(team_by_subject, dict):
        value = team_by_subject.get(profile["subject"]) or team_by_subject.get(profile["key"])
        if isinstance(value, str) and value:
            return normalize_custom_team(value)
    return "TeamOne"


def set_custom_team_for_subject(game_state: dict[str, Any], subject: str, team: str) -> None:
    team_by_subject = game_state.setdefault("custom_team_by_subject", {})
    if isinstance(team_by_subject, dict) and subject:
        team_by_subject[subject] = normalize_custom_team(team)


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


def pregame_character_selection_state(
    game_state: dict[str, Any],
    match_profile: dict[str, str],
    viewer_profile: dict[str, str],
) -> str:
    state = str(character_state_for_profile(game_state, match_profile) or "").strip().lower()
    if state == "locked":
        return "locked"
    if state == "selected":
        return "selected"
    return "Free"


def ensure_character_selections(
    deps: StateTransitionDependencies,
    game_state: dict[str, Any],
    state: str,
    profiles: list[dict[str, str]] | None = None,
) -> None:
    for profile in profiles or deps.profiles_from_game_state(game_state):
        default_character = DEFAULT_CHARACTER_ID if state in {"selected", "locked"} else ""
        character_id = character_for_profile(game_state, profile, default_character)
        set_character_for_profile(game_state, profile, character_id, state)


def should_auto_start_after_lock(game_state: dict[str, Any]) -> bool:
    flow = active_provisioning_flow(game_state)
    queue = str(game_state.get("queue") or "")
    solo_type = str(game_state.get("solo_experience_type") or "")
    mode_id = str(game_state.get("mode") or DEFAULT_MODE)
    map_id = str(game_state.get("map") or DEFAULT_MAP)
    return (
        flow == SHOOTING_RANGE_PROVISIONING_FLOW
        or queue == SHOOTING_RANGE_QUEUE
        or solo_type == SHOOTING_RANGE_PROVISIONING_FLOW
        or (
            queue == DEFAULT_QUEUE
            and flow == DEFAULT_PROVISIONING_FLOW
            and mode_id == DEFAULT_MODE
            and map_id == DEFAULT_MAP
        )
    )


def transition_locked_match_to_core(
    deps: StateTransitionDependencies,
    game_state: dict[str, Any],
    profiles: list[dict[str, str]],
) -> None:
    if should_auto_start_after_lock(game_state):
        game_state["queue"] = SHOOTING_RANGE_QUEUE
        game_state["provisioning_flow"] = SHOOTING_RANGE_PROVISIONING_FLOW
        game_state["solo_experience_type"] = SHOOTING_RANGE_PROVISIONING_FLOW
        game_state["party_state"] = "SOLO_EXPERIENCE_STARTING"
    else:
        game_state["party_state"] = "MATCHMADE_GAME_STARTING"
    game_state["phase"] = "core"
    game_state["pregame_state"] = "provisioned"
    deps.prime_backend_state_for_phase(game_state, profiles, "core")


def _normalize_catalog_value(value: str, rows: list[dict[str, str]], aliases: dict[str, str]) -> str:
    raw = str(value or "").strip().strip('"').strip("'")
    if not raw:
        return raw
    lookup = raw.replace("\\", "/").lower()
    if lookup in aliases:
        return aliases[lookup]
    for row in rows:
        path = str(row.get("path") or "")
        values = {
            path,
            str(row.get("id") or ""),
            str(row.get("name") or ""),
            str(row.get("asset") or ""),
            str(row.get("ui_data") or ""),
        }
        for item in values:
            if item and item.lower() == lookup:
                return path
        if path and lookup.startswith(path.lower() + "."):
            return path
    return raw


def normalize_map_value(value: str) -> str:
    return _normalize_catalog_value(
        value,
        LOCAL_MAP_ROWS,
        {
            "bind": "/Game/Maps/Duality/Duality",
            "duality": "/Game/Maps/Duality/Duality",
            "haven": "/Game/Maps/Triad/Triad",
            "triad": "/Game/Maps/Triad/Triad",
            "range": SHOOTING_RANGE_MAP,
            "shootingrange": SHOOTING_RANGE_MAP,
            "shooting range": SHOOTING_RANGE_MAP,
            "poveglia": "/Game/Maps/Poveglia/Poveglia",
        },
    )


def normalize_mode_value(value: str) -> str:
    return _normalize_catalog_value(
        value,
        LOCAL_MODE_ROWS,
        {
            "bomb": "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C",
            "standard": "/Game/GameModes/Bomb/BombGameMode.BombGameMode_C",
            "quickplay": "/Game/GameModes/Bomb/QuickPlay_BombGameMode.QuickPlay_BombGameMode_C",
            "quick play": "/Game/GameModes/Bomb/QuickPlay_BombGameMode.QuickPlay_BombGameMode_C",
            "shootingrange": SHOOTING_RANGE_MODE,
            "shooting range": SHOOTING_RANGE_MODE,
            "range": SHOOTING_RANGE_MODE,
        },
    )


def update_state_from_json(game_state: dict[str, Any], body: dict[str, Any]) -> None:
    if not isinstance(body, dict):
        return
    settings = request_settings_from_body(body)
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
        ("GameMode", "mode"),
        ("gameMode", "mode"),
        ("GameModeID", "mode"),
        ("gameModeID", "mode"),
        ("GameModeId", "mode"),
        ("gameModeId", "mode"),
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
            if state_key == "map":
                value = normalize_map_value(value)
            elif state_key == "mode":
                value = normalize_mode_value(value)
            game_state[state_key] = value
    for source_key, state_key in [
        ("Name", "custom_game_name"),
        ("name", "custom_game_name"),
        ("Description", "custom_game_description"),
        ("description", "custom_game_description"),
    ]:
        value = settings.get(source_key) if isinstance(settings, dict) else None
        if isinstance(value, str):
            game_state[state_key] = value
    for source_key, state_key in [
        ("UseBots", "use_bots"),
        ("useBots", "use_bots"),
        ("AllowGameModifiers", "allow_game_modifiers"),
        ("allowGameModifiers", "allow_game_modifiers"),
    ]:
        value = settings.get(source_key) if isinstance(settings, dict) else None
        if isinstance(value, bool):
            game_state[state_key] = value
    rules = settings.get("GameRules") if isinstance(settings, dict) else None
    if isinstance(rules, dict):
        game_state["game_rules"] = dict(rules)


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
        game_state["map"] = SHOOTING_RANGE_MAP
        game_state["mode"] = SHOOTING_RANGE_MODE
        game_state["queue"] = SHOOTING_RANGE_QUEUE
        game_state["provisioning_flow"] = SHOOTING_RANGE_PROVISIONING_FLOW
    elif normalized in {"newplayerexperience", "npe"}:
        game_type = "NewPlayerExperience"
        game_state["map"] = SHOOTING_RANGE_MAP
        game_state["mode"] = SHOOTING_RANGE_MODE
        game_state["queue"] = SHOOTING_RANGE_QUEUE
        game_state["provisioning_flow"] = game_type
    else:
        game_state["provisioning_flow"] = game_type
    game_state["solo_experience_type"] = game_type


def queue_id_from_body(body: Any, fallback: str = DEFAULT_MATCHMAKING_QUEUE) -> str:
    if not isinstance(body, dict):
        return fallback
    for key in ("QueueID", "queueID", "QueueId", "queueId", "Queue", "queue", "id", "ID"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
    settings = body.get("Settings")
    if isinstance(settings, dict):
        return queue_id_from_body(settings, fallback)
    return fallback


def enter_matchmaking(
    deps: StateTransitionDependencies,
    game_state: dict[str, Any],
    body: Any,
    profile: dict[str, str],
    *,
    immediate_pregame: bool = True,
) -> None:
    queue_id = queue_id_from_body(body, str(game_state.get("queue") or DEFAULT_MATCHMAKING_QUEUE))
    game_state["queue"] = queue_id
    update_state_from_json(game_state, body if isinstance(body, dict) else {})
    game_state.setdefault("map", DEFAULT_MAP)
    game_state.setdefault("mode", DEFAULT_MODE)
    game_state["provisioning_flow"] = MATCHMAKING_PROVISIONING_FLOW
    game_state["matchmaking_started_unix"] = deps.time_now()
    game_state["matchmaking_started_at"] = deps.utc_now()
    game_state["matchmaking_presence_started_at"] = deps.presence_time_now()
    current_party_profiles = deps.party_profiles(game_state, deps.party_id_for_profile(profile), profile)
    if immediate_pregame:
        game_state["phase"] = "pregame"
        game_state["party_state"] = "MATCHMADE_GAME_STARTING"
        game_state["pregame_state"] = "character_select_active"
        for member_profile in current_party_profiles:
            if not character_state_for_profile(game_state, member_profile):
                set_character_for_profile(game_state, member_profile, "", "")
        deps.prime_backend_state_for_phase(game_state, current_party_profiles, "pregame")
    else:
        game_state["phase"] = "menus"
        game_state["party_state"] = "MATCHMAKING"
        game_state["pregame_state"] = ""
        deps.prime_backend_state_for_phase(game_state, current_party_profiles, "menus")
