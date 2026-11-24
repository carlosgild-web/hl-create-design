"""Stop flags for the agent runs in progress (`POST /api/runs/{id}/cancel`).

In memory, per process: a run that is not running here cannot be stopped, and that is fine,
because it ends on its own (bounded by `AGENT_MAX_ITERATIONS` and `AGENT_TURN_TIMEOUT_S`).
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_flags: dict[int, threading.Event] = {}


def register(run_id: int) -> threading.Event:
    with _lock:
        return _flags.setdefault(run_id, threading.Event())


def cancel(run_id: int) -> bool:
    """Ask the run to stop. False if it is not running in this process."""
    with _lock:
        flag = _flags.get(run_id)
    if flag is None:
        return False
    flag.set()
    return True


def release(run_id: int) -> None:
    with _lock:
        _flags.pop(run_id, None)
