import json
from pathlib import Path


class SeenStorage:
    def __init__(self, filepath: str):
        self.path = Path(filepath)
        self.seen: set[str] = set()
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.seen = set(data)
            except Exception:
                self.seen = set()

    def save(self):
        self.path.write_text(
            json.dumps(sorted(self.seen), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_seen(self, item_id: str) -> bool:
        return item_id in self.seen

    def mark_seen(self, item_id: str):
        self.seen.add(item_id)

    def has(self, item_id: str) -> bool:
        return item_id in self.seen
