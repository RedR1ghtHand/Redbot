import json
from datetime import datetime, timezone
from pathlib import Path

from database.gateways.analytics import AnalyticsGateway

from bot.ui.metrics.embeds import (
    ACTIVITY_FILENAME,
    LEADERBOARD_FILENAME,
    OVERVIEW_FILENAME,
    WEEKDAY_TRENDS_FILENAME,
    render_activity_chart_png,
    render_leaderboard_chart_png,
    render_overview_chart_png,
    render_weekday_trends_chart_png,
)


class MetricsCacheManager:
    def __init__(self, analytics_gateway: AnalyticsGateway, cache_root: str = "analysis_output/cache/metrics"):
        self.analytics_gateway = analytics_gateway
        self.cache_root = Path(cache_root)
        self.cache_version = "v3"

    def _range_dir(self, range_key: str) -> Path:
        day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.cache_root / self.cache_version / day_key / range_key

    async def get_or_build_detailed_metrics(
        self,
        range_key: str,
        lookback_days: int | None,
        top_limit: int,
    ) -> dict:
        range_dir = self._range_dir(range_key)
        data_path = range_dir / "data.json"
        overview_path = range_dir / OVERVIEW_FILENAME
        leaderboard_path = range_dir / LEADERBOARD_FILENAME
        activity_path = range_dir / ACTIVITY_FILENAME
        weekday_trends_path = range_dir / WEEKDAY_TRENDS_FILENAME

        if data_path.exists():
            with data_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            images = payload.get("images", {})
            if overview_path.exists():
                images["overview"] = str(overview_path)
            if leaderboard_path.exists():
                images["leaderboard"] = str(leaderboard_path)
            if activity_path.exists():
                images["activity"] = str(activity_path)
            if weekday_trends_path.exists():
                images["weekday_trends"] = str(weekday_trends_path)
            payload["images"] = images
            return payload

        range_start, range_end = await self.analytics_gateway.get_detailed_metrics_range(lookback_days=lookback_days)

        stats = await self.analytics_gateway.get_stats_snapshot(
            top_limit=top_limit,
            range_start=range_start,
            range_end=range_end,
        )
        activity_points = await self.analytics_gateway.get_activity_by_hour(
            lookback_days=lookback_days,
            range_start=range_start,
            range_end=range_end,
        )
        weekday_trends = await self.analytics_gateway.get_weekday_voice_trends(
            lookback_days=lookback_days,
            range_start=range_start,
            range_end=range_end,
        )
        date_range_text = f"{range_start:%d.%m.%Y} - {range_end:%d.%m.%Y}"

        range_dir.mkdir(parents=True, exist_ok=True)

        overview_bytes = await render_overview_chart_png(stats)
        if overview_bytes is not None:
            overview_path.write_bytes(overview_bytes)

        leaderboard_bytes = await render_leaderboard_chart_png(stats)
        if leaderboard_bytes is not None:
            leaderboard_path.write_bytes(leaderboard_bytes)

        activity_bytes = await render_activity_chart_png(activity_points)
        if activity_bytes is not None:
            activity_path.write_bytes(activity_bytes)
        weekday_trends_bytes = await render_weekday_trends_chart_png(
            weekday_trends.get("points", []),
            summary=weekday_trends.get("summary"),
        )
        if weekday_trends_bytes is not None:
            weekday_trends_path.write_bytes(weekday_trends_bytes)

        payload = {
            "date_range_text": date_range_text,
            "stats": stats,
            "activity_points": activity_points,
            "weekday_trends": weekday_trends,
            "images": {
                "overview": str(overview_path) if overview_path.exists() else None,
                "leaderboard": str(leaderboard_path) if leaderboard_path.exists() else None,
                "activity": str(activity_path) if activity_path.exists() else None,
                "weekday_trends": str(weekday_trends_path) if weekday_trends_path.exists() else None,
            },
        }

        with data_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True)
        return payload
