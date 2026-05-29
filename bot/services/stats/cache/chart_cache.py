from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cache_keys import build_payload_digest


class StatsChartCacheStore:
    def __init__(
        self,
        cache_root: str = "analysis_output/cache/stats/charts",
        cache_version: str = "v2",
    ):
        self.cache_root = Path(cache_root)
        self.cache_version = cache_version

    def build_key(self, chart_type: str, payload: Any) -> str:
        digest = build_payload_digest(payload)
        return f"{chart_type}/{digest}"

    def _path(self, key: str) -> Path:
        return self.cache_root / self.cache_version / f"{key}.png"

    def get_png(self, chart_type: str, payload: Any, ttl_seconds: int | None = None) -> bytes | None:
        key = self.build_key(chart_type, payload)
        path = self._path(key)
        if not path.exists():
            return None

        meta_path = path.with_suffix(".meta")
        if ttl_seconds is not None and meta_path.exists():
            try:
                stored_at = datetime.fromisoformat(meta_path.read_text(encoding="utf-8").strip())
                age_seconds = (datetime.now(timezone.utc) - stored_at).total_seconds()
                if age_seconds > ttl_seconds:
                    return None
            except Exception:
                return None

        try:
            return path.read_bytes()
        except Exception:
            return None

    def set_png(self, chart_type: str, payload: Any, png_bytes: bytes) -> Path:
        key = self.build_key(chart_type, payload)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png_bytes)
        meta_path = path.with_suffix(".meta")
        meta_path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
        return path
