"""Timestamp helpers for control-plane payloads."""

from __future__ import annotations

import time


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())


def presence_time_now() -> str:
    return time.strftime("%Y.%m.%d-%H.%M.%S", time.gmtime())
