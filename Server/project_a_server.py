#!/usr/bin/env python3
"""Compatibility entrypoint for the Project A local server."""

from __future__ import annotations

import sys

try:
    from . import app as _app
except ImportError:  # Supports running as: python Server/project_a_server.py
    import app as _app  # type: ignore[no-redef]


if __name__ == "__main__":
    _app.main()
else:
    sys.modules[__name__] = _app
