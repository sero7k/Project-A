"""JSONL event logging shared by gameplay observer modules."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


def append_event(log_path: Path, lock: threading.Lock, event: dict[str, Any]) -> None:
    event.setdefault("ts", time.time())
    with lock:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
