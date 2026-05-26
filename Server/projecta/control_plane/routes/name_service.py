"""Name service routes."""

from __future__ import annotations


def _requested_subjects(json_body) -> list[str]:
    if isinstance(json_body, list):
        return [item for item in json_body if isinstance(item, str)]
    if isinstance(json_body, dict):
        raw_subjects = json_body.get("Subjects") or json_body.get("subjects") or []
        if isinstance(raw_subjects, list):
            return [item for item in raw_subjects if isinstance(item, str)]
    return []


def _profiles_for_subjects(cp, current_profile, game_state, subjects: list[str]):
    profiles = cp.profiles_with_current_first(current_profile, game_state)
    if not subjects:
        return profiles
    known_profiles = cp.profiles_with_current_first(current_profile, game_state)
    for known in cp.social_roster_profiles(game_state):
        if all(existing["subject"] != known["subject"] for existing in known_profiles):
            known_profiles.append(known)
    known_by_subject = {profile["subject"]: profile for profile in known_profiles}
    return [known_by_subject[subject] for subject in subjects if subject in known_by_subject]


def handle(ctx) -> bool:
    from .. import app as cp

    route_path = ctx.route_path
    if route_path == "/name-service/v1/players" or route_path.startswith("/name-service/v"):
        profiles = _profiles_for_subjects(cp, ctx.current_profile(), ctx.game_state, _requested_subjects(ctx.json_body))
        ctx.write(200, cp.display_name_payload(profiles), localize=False)
    else:
        return False
    return True
