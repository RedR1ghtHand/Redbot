from .embeds import (
    build_activity_message,
    build_leaderboard_message,
    build_overview_message,
    build_stats_embed,
    build_top_embed,
    build_weekday_trends_message,
)

__all__ = [
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
