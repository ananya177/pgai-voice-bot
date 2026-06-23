"""Thread-safe in-memory call state for the development challenge."""

from __future__ import annotations

import copy
import threading
from typing import Any


class CallStateStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._states: dict[str, dict[str, Any]] = {}

    def create(self, call_id: str, state: dict[str, Any]) -> None:
        with self._lock:
            self._states[call_id] = state

    def alias(self, alias_id: str, call_id: str) -> None:
        with self._lock:
            state = self._states.get(call_id)
            if state is not None:
                self._states[alias_id] = state

    def get(self, call_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._states.get(call_id)

    def snapshot(self, call_id: str) -> dict[str, Any] | None:
        with self._lock:
            state = self._states.get(call_id)
            return copy.deepcopy(state) if state is not None else None

    def update(self, call_id: str, **changes: Any) -> dict[str, Any] | None:
        with self._lock:
            state = self._states.get(call_id)
            if state is None:
                return None
            state.update(changes)
            return state

    def append_turn(self, call_id: str, turn: dict[str, Any]) -> None:
        with self._lock:
            state = self._states[call_id]
            state.setdefault("turns", []).append(turn)

    def append_history(self, call_id: str, message: dict[str, str]) -> None:
        with self._lock:
            state = self._states[call_id]
            state.setdefault("conversation_history", []).append(message)

    def mark_finalized(self, call_id: str) -> bool:
        """Atomically mark outputs finalized. Return False if already finalized."""
        with self._lock:
            state = self._states.get(call_id)
            if state is None or state.get("outputs_finalized"):
                return False
            state["outputs_finalized"] = True
            return True

    def count_unique_calls(self) -> int:
        with self._lock:
            return len({id(state) for state in self._states.values()})


call_store = CallStateStore()
