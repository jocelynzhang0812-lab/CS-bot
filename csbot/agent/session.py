from typing import Dict, Optional
import time


class SessionStore:
    def __init__(self):
        self._data: Dict[str, Dict] = {}

    def get(self, session_id: str, default: Optional[Dict] = None) -> Optional[Dict]:
        return self._data.get(session_id, default)

    def get_or_create(self, session_id: str) -> Dict:
        s = self._data.get(session_id)
        if not s:
            s = {"history": [], "state": {}, "_last_update": time.time()}
            self._data[session_id] = s
        return s

    def set(self, session_id: str, state: Dict):
        self._data[session_id] = state

    def update(self, session_id: str, patch: Dict):
        if session_id not in self._data:
            self._data[session_id] = {"history": [], "state": {}}
        self._data[session_id].update(patch)

    def clear(self, session_id: str):
        self._data.pop(session_id, None)

    def is_expired(self, session_id: str, timeout_min: int = 30) -> bool:
        s = self._data.get(session_id)
        if not s:
            return True
        last = s.get("_last_update", 0)
        return (time.time() - last) > timeout_min * 60

    def touch(self, session_id: str):
        if session_id in self._data:
            self._data[session_id]["_last_update"] = time.time()