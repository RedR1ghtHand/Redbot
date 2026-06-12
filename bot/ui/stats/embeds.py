from dataclasses import dataclass
from typing import Callable

import disnake as discord

from bot.services.stats import StatsAggregationService, StatsChartService
from bot.services.stats.figures import (
    ACTIVITY_FILENAME,
    LEADERBOARD_FILENAME,
    OVERVIEW_FILENAME,
    WEEKDAY_TRENDS_FILENAME,
    activity_chart_timezone_label,
    build_leaderboard_figure,
)
from bot.ui.shared import format_duration_hhmmss
from database.repositories import MemberRepository
from utils import get_message

from .messages import stats_chart_title, stats_date_range_description, stats_embed_scope_title, top_messages

ALL_METRICS_KEY = "all"


def _format_total_voice_time(stats: dict) -> str:
    return f"`{format_duration_hhmmss(stats.get('total_voice_seconds', 0))}`"


def _format_sessions(stats: dict) -> str:
    count = stats.get("sessions_count", 0)
    avg_seconds = stats.get("avg_session_seconds", 0)
    return get_message(
        "embeds.stats.sessions_value",
        count=count,
        avg_duration=format_duration_hhmmss(avg_seconds),
    )


def _format_unique_participants(stats: dict) -> str:
    return f"`{stats.get('unique_participants', 0)}`"


def _format_avg_participants(stats: dict) -> str:
    return f"`{stats.get('avg_participants_per_session', 0):.2f}`"


def _format_top_participants(stats: dict) -> str:
    participants = stats.get("top_participants") or []
    lines = [
        get_message(
            "embeds.stats.top_participant_line",
            rank=idx,
            name=row["name"],
            duration=format_duration_hhmmss(row["seconds"]),
        )
        for idx, row in enumerate(participants, start=1)
    ]
    return "\n".join(lines) or get_message("no_data")


@dataclass(frozen=True)
class StatsMetricSpec:
    key: str
    name_message_key: str
    formatter: Callable[[dict], str]


STATS_METRIC_SPECS: list[StatsMetricSpec] = [
    StatsMetricSpec("total_voice_time", "embeds.stats.fields.total_voice_time", _format_total_voice_time),
    StatsMetricSpec("sessions", "embeds.stats.fields.sessions", _format_sessions),
    StatsMetricSpec("unique_participants", "embeds.stats.fields.unique_participants", _format_unique_participants),
    StatsMetricSpec("avg_participants", "embeds.stats.fields.avg_participants", _format_avg_participants),
    StatsMetricSpec("top_participants", "embeds.stats.fields.top_participants", _format_top_participants),
]


def build_stats_embed(metric_key: str, stats: dict, scope_label: str) -> discord.Embed:
    embed = discord.Embed(title=stats_embed_scope_title(scope_label), color=discord.Color.blurple())

    selected_specs = [
        spec for spec in STATS_METRIC_SPECS if metric_key == ALL_METRICS_KEY or spec.key == metric_key
    ]
    for position, spec in enumerate(selected_specs, start=1):
        embed.add_field(
            name=f"{position}) {get_message(spec.name_message_key)}",
            value=spec.formatter(stats),
            inline=False,
        )

    return embed


def _chart_messages(chart_key: str) -> dict:
    node = get_message(f"embeds.stats.charts.{chart_key}")
    return node if isinstance(node, dict) else {}


async def build_overview_message(
    stats: dict,
    scope_label: str,
    date_range_text: str,
    chart_service: StatsChartService | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    chart = _chart_messages("overview")
    embed = discord.Embed(
        title=stats_chart_title(scope_label, chart.get("type", "Overview")),
        description=stats_date_range_description(date_range_text, details=chart.get("details")),
        color=discord.Color.blurple(),
    )

    file = None
    if chart_service is not None:
        file = await chart_service.render_overview_file(stats)
    if file:
        embed.set_image(url=f"attachment://{OVERVIEW_FILENAME}")
    return embed, file


async def build_leaderboard_message(
    stats: dict,
    scope_label: str,
    date_range_text: str,
    chart_service: StatsChartService | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    chart = _chart_messages("leaderboards")
    embed = discord.Embed(
        title=stats_chart_title(scope_label, chart.get("type", "Leaderboards")),
        description=stats_date_range_description(date_range_text, details=chart.get("details")),
        color=discord.Color.blurple(),
    )

    file = None
    if chart_service is not None:
        file = await chart_service.render_leaderboard_file(stats)

    if file is not None:
        embed.set_image(url=f"attachment://{LEADERBOARD_FILENAME}")
        return embed, file

    if build_leaderboard_figure(stats) is None:
        embed.add_field(
            name=chart.get("empty_field_name", "No leaderboard data"),
            value=chart.get("empty_field_value", "No voice activity in this range."),
            inline=False,
        )
    return embed, None


async def build_activity_message(
    activity_points: list[dict],
    scope_label: str,
    date_range_text: str,
    chart_service: StatsChartService | None = None,
    timezone_label: str | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    chart = _chart_messages("activity")
    tz = timezone_label or activity_chart_timezone_label()
    details = chart.get("details", "").format(timezone=tz) if chart.get("details") else None
    embed = discord.Embed(
        title=stats_chart_title(scope_label, chart.get("type", "Activity")),
        description=stats_date_range_description(date_range_text, details=details),
        color=discord.Color.blurple(),
    )
    if not activity_points:
        embed.add_field(
            name=chart.get("empty_field_name", "Activity"),
            value=chart.get("empty_field_value", "No activity data for selected range."),
            inline=False,
        )
        return embed, None

    file = None
    if chart_service is not None:
        file = await chart_service.render_activity_file(activity_points, timezone_label=tz)
    if file:
        embed.set_image(url=f"attachment://{ACTIVITY_FILENAME}")
    return embed, file


async def build_weekday_trends_message(
    weekday_trends: dict,
    scope_label: str,
    date_range_text: str,
    chart_service: StatsChartService | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    chart = _chart_messages("weekday_trends")
    points = weekday_trends.get("points", [])
    embed = discord.Embed(
        title=stats_chart_title(scope_label, chart.get("type", "Weekday Trends")),
        description=stats_date_range_description(date_range_text, details=chart.get("details")),
        color=discord.Color.blurple(),
    )

    if not points:
        embed.add_field(
            name=chart.get("empty_field_name", "Weekday trends"),
            value=chart.get("empty_field_value", "No data for selected range."),
            inline=False,
        )
        return embed, None

    file = None
    if chart_service is not None:
        file = await chart_service.render_weekday_trends_file(weekday_trends)
    if file:
        embed.set_image(url=f"attachment://{WEEKDAY_TRENDS_FILENAME}")
    return embed, file


async def build_top_embed(
    stats_service: StatsAggregationService,
    member_repository: MemberRepository,
    limit: int = 10,
) -> tuple[discord.Embed | None, str | None]:
    limit = limit if limit <= 10 else 10
    sessions = await stats_service.longest_sessions_all_time(limit=limit)
    member_ids = [session.creator_id for session in sessions if session.creator_id is not None]
    members_map = await member_repository.get_members_map(member_ids)

    top_msg = top_messages(limit)
    title_template = top_msg["title_template"]
    color_name = top_msg["color_name"]
    no_sessions_text = top_msg["no_sessions"]
    medals = top_msg["medals"]

    if not sessions:
        return None, no_sessions_text

    color = getattr(discord.Color, color_name, discord.Color.red)()
    embed = discord.Embed(
        title=title_template.format(limit=limit),
        color=color,
    )

    lines = []
    for i, session in enumerate(sessions, start=1):
        duration = session.duration_pretty()
        member_info = members_map.get(session.creator_id) if session.creator_id is not None else None
        username = (member_info.public_name if member_info else None) or session.created_by or get_message(
            "embeds.top.unknown_user"
        )

        if i <= 3:
            line = get_message(
                "embeds.top.line_medal",
                medal=medals[i - 1],
                channel_name=session.channel_name,
                username=username,
                duration=duration,
            )
        else:
            line = get_message(
                "embeds.top.line_numbered",
                rank=i,
                channel_name=session.channel_name,
                username=username,
                duration=duration,
            )
        lines.append(line)

    if len(lines) > 3:
        top_three = "\n\n".join(lines[:3])
        others = "\n".join(lines[3:])
        embed.description = f"{top_three}\n\n{others}"
    else:
        embed.description = "\n\n".join(lines)

    return embed, None
