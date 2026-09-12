import json
import time
from pathlib import Path


class SeenStorage:
    def __init__(self, filepath: str):
        self.path = Path(filepath)
        self.seen: set[str] = set()
        self.stale: dict[str, float] = {}  # key -> expires_ts (временная пометка stale)
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.seen = set(data.get("seen", []))
                    self.stale = {str(k): float(v) for k, v in data.get("stale", {}).items()}
                else:
                    self.seen = set(data)
            except Exception:
                self.seen = set()
                self.stale = {}

    def save(self):
        self.path.write_text(
            json.dumps({"seen": sorted(self.seen), "stale": self.stale}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_seen(self, item_id: str) -> bool:
        if item_id in self.seen:
            return True
        if item_id in self.stale:
            if time.time() >= self.stale[item_id]:
                del self.stale[item_id]
                self.save()
                return False
            return True
        return False

    def mark_seen(self, item_id: str):
        self.seen.add(item_id)
        self.stale.pop(item_id, None)

    def mark_stale(self, item_id: str, ttl_hours: float = 1.0):
        """Временно игнорировать, но перепроверить через TTL (резюме может обновиться позже)."""
        self.stale[item_id] = time.time() + ttl_hours * 3600

    def has(self, item_id: str) -> bool:
        return item_id in self.seen