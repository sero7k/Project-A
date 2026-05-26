"""Ordered route-family registry for HTTP control-plane dispatch."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import (
    account,
    chat,
    client,
    content,
    contracts,
    core_game,
    matchmaking,
    misc,
    mmr,
    name_service,
    party,
    personalization,
    policy,
    pregame,
    reporting,
    session,
    social,
    store,
    voice,
)

if TYPE_CHECKING:
    from ..runtime.context import RouteContext


RouteHandler = Callable[["RouteContext"], bool]


@dataclass(frozen=True, slots=True)
class RouteFamily:
    name: str
    handle: RouteHandler


ROUTE_FAMILIES: tuple[RouteFamily, ...] = (
    RouteFamily("client", client.handle),
    RouteFamily("chat", chat.handle),
    RouteFamily("social", social.handle),
    RouteFamily("account", account.handle),
    RouteFamily("policy", policy.handle),
    RouteFamily("voice", voice.handle),
    RouteFamily("session", session.handle),
    RouteFamily("party", party.handle),
    RouteFamily("matchmaking", matchmaking.handle),
    RouteFamily("pregame", pregame.handle),
    RouteFamily("core_game", core_game.handle),
    RouteFamily("personalization", personalization.handle),
    RouteFamily("content", content.handle),
    RouteFamily("contracts", contracts.handle),
    RouteFamily("store", store.handle),
    RouteFamily("reporting", reporting.handle),
    RouteFamily("name_service", name_service.handle),
    RouteFamily("mmr", mmr.handle),
    RouteFamily("misc", misc.handle),
)


def iter_route_handlers() -> Iterator[RouteHandler]:
    for family in ROUTE_FAMILIES:
        yield family.handle


def dispatch_route(ctx: "RouteContext") -> bool:
    for route_handler in iter_route_handlers():
        if route_handler(ctx):
            return True
    return False
