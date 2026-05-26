from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "Server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import project_a_server as server
from projecta.control_plane.routes.registry import ROUTE_FAMILIES


def test_app_facade_preserves_route_normalization_aliases():
    cases = {
        "/ares-core-game/v1/matches/abc": "/core-game/v1/matches/abc",
        "/ares-core-game/core-game/v1/matches/abc": "/core-game/v1/matches/abc",
        "/ares-core-game/abc": "/core-game/v1/matches/abc",
        "/ares-parties/parties/v1/players/me": "/parties/v1/players/me",
        "/ares-pregame/pregame/v1/players/me": "/pregame/v1/players/me",
        "/ares-contracts/contracts/v1/contracts/me": "/contracts/v1/contracts/me",
        "/ares-personalization/personalization/v2/players/me/playerloadout": "/personalization/v2/players/me/playerloadout",
        "/v1/parties/party-id": "/parties/v1/parties/party-id",
        "/v1/players/me": "/parties/v1/players/me",
    }

    for raw_path, expected in cases.items():
        assert server.normalize_route_path(raw_path) == expected


def test_route_registry_keeps_behavior_sensitive_dispatch_order():
    assert [family.name for family in ROUTE_FAMILIES] == [
        "client",
        "chat",
        "social",
        "account",
        "policy",
        "voice",
        "session",
        "party",
        "matchmaking",
        "pregame",
        "core_game",
        "personalization",
        "content",
        "contracts",
        "store",
        "reporting",
        "name_service",
        "mmr",
        "misc",
    ]
