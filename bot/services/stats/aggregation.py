from datetime import datetime

from database.models import Session
from database.repositories import StatsReadRepository

from .cache import StatsCacheStore, StatsChartCacheStore, cached_stats_payload
from .calculators import ActivityCalculator, SnapshotCalculator, WeekdayTrendsCalculator
from .charts import StatsChartService


class StatsAggregationService:
    def __init__(
        self,
        stats_read_repository: StatsReadRepository,
        cache_store: StatsCacheStore | None = None,
        chart_cache: StatsChartCacheStore | None = None,
        chart_ttl_seconds: int = 900,
    ):
        self.stats_read_repository = stats_read_repository
        self.cache_store = cache_store
        self.chart_service = StatsChartService(chart_cache=chart_cache, ttl_seconds=chart_ttl_seconds)

        self._snapshot = SnapshotCalculator(stats_read_repository)
        self._activity = ActivityCalculator(stats_read_repository)
        self._weekday_trends = WeekdayTrendsCalculator(stats_read_repository)

    async def longest_sessions_all_time(self, limit: int = 10) -> list[Session]:
        return await self.stats_read_repository.longest_sessions_all_time(limit=limit)

    async def get_reporting_range(self, lookback_days: int | None = None) -> tuple[datetime, datetime]:
        return await self.stats_read_repository.get_reporting_range(lookback_days=lookback_days)

    async def get_detailed_stats_range(self, lookback_days: int | None = None) -> tuple[datetime, datetime]:
        return await self.stats_read_repository.get_detailed_stats_range(lookback_days=lookback_days)

    @cached_stats_payload(namespace="detailed_stats", ttl_seconds=900)
    async def get_detailed_stats(
        self,
        range_key: str,
        lookback_days: int | None,
        top_limit: int,
    ) -> dict:
        range_start, range_end = await self.get_detailed_stats_range(lookback_days=lookback_days)
        stats = await self.get_stats_snapshot(
            top_limit=top_limit,
            range_start=range_start,
            range_end=range_end,
        )
        activity_points = await self.get_activity_by_hour(
            lookback_days=lookback_days,
            range_start=range_start,
            range_end=range_end,
        )
        weekday_trends = await self.get_weekday_voice_trends(
            lookback_days=lookback_days,
            range_start=range_start,
            range_end=range_end,
        )

        return {
            "range_key": range_key,
            "date_range_text": f"{range_start:%d.%m.%Y} - {range_end:%d.%m.%Y}",
            "stats": stats,
            "activity_points": activity_points,
            "weekday_trends": weekday_trends,
        }

    async def get_stats_snapshot(
        self,
        lookback_days: int | None = None,
        top_limit: int = 10,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
    ) -> dict:
        if range_start is None or range_end is None:
            range_start, range_end = await self.get_reporting_range(lookback_days=lookback_days)

        return await self._snapshot.compute(
            range_start=range_start,
            range_end=range_end,
            top_limit=top_limit,
        )

    async def get_activity_by_hour(
        self,
        lookback_days: int | None = None,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
    ) -> list[dict]:
        if range_start is None or range_end is None:
            range_start, range_end = await self.get_reporting_range(lookback_days=lookback_days)

        return await self._activity.compute(range_start=range_start, range_end=range_end)

    async def get_weekday_voice_trends(
        self,
        lookback_days: int | None = None,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
    ) -> dict:
        if range_start is None or range_end is None:
            range_start, range_end = await self.get_reporting_range(lookback_days=lookback_days)

        return await self._weekday_trends.compute(
            range_start=range_start,
            range_end=range_end,
        )
