"""HTTP route-context construction and dispatch helpers."""

from __future__ import annotations

from typing import Any

from ..routes.normalization import normalize_route_path
from ..routes.registry import dispatch_route
from .context import RouteContext


def build_route_context(
    handler: Any,
    path: str,
    parsed: Any,
    query_params: dict[str, list[str]],
    json_body: Any,
    raw_body: bytes,
) -> RouteContext:
    return RouteContext(
        handler,
        path,
        normalize_route_path(path),
        parsed,
        query_params,
        json_body,
        raw_body,
    )


def dispatch_http_route(ctx: RouteContext) -> bool:
    return dispatch_route(ctx)
