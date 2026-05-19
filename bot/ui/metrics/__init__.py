from .charts import (
    ACTIVITY_FILENAME,
    LEADERBOARD_FILENAME,
    OVERVIEW_FILENAME,
    WEEKDAY_TRENDS_FILENAME,
    render_activity_chart_png,
    render_leaderboard_chart_png,
    render_overview_chart_png,
    render_weekday_trends_chart_png,
)
from .embeds import (
    build_activity_message,
    build_leaderboard_message,
    build_overview_message,
    build_stats_embed,
    build_top_embed,
    build_weekday_trends_message,
)

__all__ = [
    "ACTIVITY_FILENAME",
    "LEADERBOARD_FILENAME",
    "OVERVIEW_FILENAME",
    "WEEKDAY_TRENDS_FILENAME",
    "render_activity_chart_png",
    "render_leaderboard_chart_png",
    "render_overview_chart_png",
    "render_weekday_trends_chart_png",
    "build_activity_message",
    "build_leaderboard_message",
    "build_overview_message",
    "build_stats_embed",
    "build_top_embed",
    "build_weekday_trends_message",
    "StatsMainView",
]


def __getattr__(name: str):
    if name == "StatsMainView":
        from .views import StatsMainView

        return StatsMainView
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
