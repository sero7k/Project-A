"""Compatibility wrapper for Project A storage backends."""

from __future__ import annotations

import sys

from projecta.storage import accounts as _accounts


sys.modules[__name__] = _accounts
