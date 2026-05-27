import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def normalize_for_cache_key(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {
            str(key): normalize_for_cache_key(val)
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [normalize_for_cache_key(item) for item in value]
    if isinstance(value, set):
        normalized = [normalize_for_cache_key(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=True))
    return value


def build_payload_digest(payload: Any) -> str:
    normalized = normalize_for_cache_key(payload)
    raw = json.dumps(normalized, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
