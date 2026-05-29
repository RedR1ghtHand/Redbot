from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Coroutine, TypeVar

from .cache_keys import build_payload_digest, normalize_for_cache_key

T = TypeVar("T")


class StatsCacheStore:
    def __init__(
        self,
        cache_root: str = "stats_output/cache/data",
        cache_version: str = "v1",
    ):
        self.cache_root = Path(cache_root)
        self.cache_version = cache_version

    def build_key(self, namespace: str, params: dict[str, Any]) -> str:
        digest = build_payload_digest(params)
        return f"{namespace}/{digest}"

    def _path(self, key: str) -> Path:
        return self.cache_root / self.cache_version / f"{key}.json"

    def get(self, key: str, ttl_seconds: int | None = None) -> dict | None:
        path = self._path(key)
        if not path.exists():
            return None

        try:
            import json

            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

        stored_at = payload.get("stored_at")
        if ttl_seconds is not None and stored_at:
            try:
                stored_dt = datetime.fromisoformat(stored_at)
                age_seconds = (datetime.now(timezone.utc) - stored_dt).total_seconds()
                if age_seconds > ttl_seconds:
                    return None
            except Exception:
                return None

        data = payload.get("data")
        return data if isinstance(data, dict) else None

    def set(self, key: str, data: dict) -> None:
        import json

        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def cached_stats_payload(
    namespace: str, ttl_seconds: int
) -> Callable[[Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]]:
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> T:
            cache_store = getattr(self, "cache_store", None)
            if cache_store is None:
                return await func(self, *args, **kwargs)

            key = cache_store.build_key(
                namespace=namespace,
                params={
                    "function": func.__name__,
                    "args": args,
                    "kwargs": kwargs,
                },
            )
            cached_data = cache_store.get(key=key, ttl_seconds=ttl_seconds)
            if cached_data is not None:
                return cached_data

            result = await func(self, *args, **kwargs)
            if isinstance(result, dict):
                cache_store.set(key=key, data=result)
            return result

        return wrapper

    return decorator


__all__ = ["StatsCacheStore", "cached_stats_payload", "build_payload_digest", "normalize_for_cache_key"]
