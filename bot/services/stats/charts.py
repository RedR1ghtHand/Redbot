import io
from collections.abc import Awaitable, Callable
from typing import Any

import disnake as discord
from cache import StatsChartCacheStore

from .figures import (
    ACTIVITY_FILENAME,
    LEADERBOARD_FILENAME,
    OVERVIEW_FILENAME,
    WEEKDAY_TRENDS_FILENAME,
    activity_chart_timezone_label,
    render_activity_chart_png,
    render_leaderboard_chart_png,
    render_overview_chart_png,
    render_weekday_trends_chart_png,
)

ChartRenderFn = Callable[[], Awaitable[bytes | None]]


class StatsChartService:
    def __init__(
        self,
        chart_cache: StatsChartCacheStore | None = None,
        ttl_seconds: int = 900,
    ):
        self.chart_cache = chart_cache
        self.ttl_seconds = ttl_seconds

    async def _render_cached(
        self,
        chart_type: str,
        payload: Any,
        filename: str,
        render_fn: ChartRenderFn,
    ) -> discord.File | None:
        if self.chart_cache is not None:
            cached_png = self.chart_cache.get_png(chart_type, payload, ttl_seconds=self.ttl_seconds)
            if cached_png is not None:
                return discord.File(io.BytesIO(cached_png), filename=filename)

        png_bytes = await render_fn()
        if png_bytes is None:
            return None

        if self.chart_cache is not None:
            self.chart_cache.set_png(chart_type, payload, png_bytes)

        return discord.File(io.BytesIO(png_bytes), filename=filename)

    async def render_overview_file(self, stats: dict) -> discord.File | None:
        return await self._render_cached(
            chart_type="overview",
            payload=stats,
            filename=OVERVIEW_FILENAME,
            render_fn=lambda: render_overview_chart_png(stats),
        )

    async def render_leaderboard_file(self, stats: dict) -> discord.File | None:
        return await self._render_cached(
            chart_type="leaderboard",
            payload=stats,
            filename=LEADERBOARD_FILENAME,
            render_fn=lambda: render_leaderboard_chart_png(stats),
        )

    async def render_activity_file(
        self,
        activity_points: list[dict],
        timezone_label: str | None = None,
    ) -> discord.File | None:
        tz = timezone_label or activity_chart_timezone_label()
        payload = {
            "activity_points": activity_points,
            "timezone_label": tz,
        }
        return await self._render_cached(
            chart_type="activity",
            payload=payload,
            filename=ACTIVITY_FILENAME,
            render_fn=lambda: render_activity_chart_png(activity_points, timezone_label=tz),
        )

    async def render_weekday_trends_file(self, weekday_trends: dict) -> discord.File | None:
        payload = {
            "points": weekday_trends.get("points", []),
            "summary": weekday_trends.get("summary", {}),
            "mode": weekday_trends.get("mode"),
        }
        return await self._render_cached(
            chart_type="weekday_trends",
            payload=payload,
            filename=WEEKDAY_TRENDS_FILENAME,
            render_fn=lambda: render_weekday_trends_chart_png(
                payload["points"],
                summary=payload["summary"],
            ),
        )
