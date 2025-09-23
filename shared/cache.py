import json
from dataclasses import dataclass

from django.core.cache import cache


@dataclass
class Structure:
    id: int
    name: str


class CacheService:
    @staticmethod
    def _build_key(namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    def set(self, namespace: str, key: str, value: dict, ttl: int | None = None):
        payload = json.dumps(value if isinstance(value, dict) else value.__dict__)
        cache.set(self._build_key(namespace, key), payload, timeout=ttl)

    def get(self, namespace: str, key: str):
        result: str | None = cache.get(self._build_key(namespace, key))
        if result is None:
            return None
        else:
            return json.loads(result)

    def delete(self, namespace: str, key: str):
        cache.delete(self._build_key(namespace, key))
