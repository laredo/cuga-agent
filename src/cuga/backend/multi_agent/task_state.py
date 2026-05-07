"""Per-task namespaced shared state, scoped to a single task_id."""

import copy
from typing import Any, Callable, Dict, Optional


class TaskState:
    def __init__(self, task_id: str, on_complete: Optional[Callable[[Dict], None]] = None):
        self.task_id = task_id
        self._on_complete = on_complete
        self._state: Dict[str, Dict[str, Any]] = {}
        self.is_active = True

    def set(self, namespace: str, key: str, value: Any) -> None:
        if not self.is_active:
            raise RuntimeError(f"Cannot write to a completed TaskState (task_id={self.task_id})")
        self._state.setdefault(namespace, {})[key] = value

    def get(self, namespace: str) -> Dict[str, Any]:
        return copy.deepcopy(self._state.get(namespace, {}))

    def get_all(self) -> Dict[str, Any]:
        snapshot = {k: copy.deepcopy(v) for k, v in self._state.items()}
        snapshot["task_id"] = self.task_id
        return snapshot

    def complete(self) -> None:
        if not self.is_active:
            return
        self.is_active = False
        if self._on_complete is not None:
            self._on_complete(self.get_all())
