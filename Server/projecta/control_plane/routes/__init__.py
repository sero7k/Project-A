"""Ordered route-family handlers for the HTTP control plane."""

from .normalization import normalize_route_path
from .registry import ROUTE_FAMILIES, RouteFamily, dispatch_route, iter_route_handlers

__all__ = [
    "ROUTE_FAMILIES",
    "RouteFamily",
    "dispatch_route",
    "iter_route_handlers",
    "normalize_route_path",
]
