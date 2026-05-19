import asyncio
from pathlib import Path

import disnake as discord

from bot.ui.shared import format_duration_hhmmss
from database.gateways import AnalyticsGateway, MemberGateway

from .charts import (
    ACTIVITY_FILENAME,
    LEADERBOARD_FILENAME,
    OVERVIEW_FILENAME,
    WEEKDAY_TRENDS_FILENAME,
    activity_chart_timezone_label,
    build_activity_figure,
    build_leaderboard_figure,
    build_overview_figure,
    build_weekday_trends_figure,
    fig_to_file,
)
from .messages import stats_embed_scope_title, top_messages


def build_stats_embed(metric_key: str, stats: dict, scope_label: str) -> discord.Embed:
    embed = discord.Embed(title=stats_embed_scope_title(scope_label), color=discord.Color.blurple())

    if metric_key in ("all", "total_voice_time"):
        embed.add_field(
            name="1) Total Voice Time",
            value=f"`{format_duration_hhmmss(stats['total_voice_seconds'])}`",
            inline=False,
        )

    if metric_key in ("all", "sessions"):
        embed.add_field(
            name="2) Sessions",
            value=(
                f"Count: `{stats['sessions_count']}`\n"
                f"Avg Duration: `{format_duration_hhmmss(stats['avg_session_seconds'])}`"
            ),
            inline=False,
        )

    if metric_key in ("all", "unique_participants"):
        embed.add_field(
            name="3) Unique Participants",
            value=f"`{stats['unique_participants']}`",
            inline=False,
        )

    if metric_key in ("all", "avg_participants"):
        embed.add_field(
            name="4) Avg Participants per Session",
            value=f"`{stats['avg_participants_per_session']:.2f}`",
            inline=False,
        )

    if metric_key in ("all", "top_participants"):
        participants = stats["top_participants"]
        participants_value = "\n".join(
            f"{idx}. **{row['name']}** - `{format_duration_hhmmss(row['seconds'])}`"
            for idx, row in enumerate(participants, start=1)
        ) or "No data"
        embed.add_field(name="5) Top Participants", value=participants_value, inline=False)

    return embed


def _metrics_title(scope_label: str, metric_type: str) -> str:
    return f"Stats | {scope_label} | {metric_type}"


def _metrics_description(date_range_text: str, details: str | None = None) -> str:
    base = f"Date range: `{date_range_text}`"
    if details:
        return f"{base}\n{details}"
    return base


async def build_overview_message(
    stats: dict,
    scope_label: str,
    date_range_text: str,
    cached_image_path: str | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    embed = discord.Embed(
        title=_metrics_title(scope_label, "Overview"),
        description=_metrics_description(
            date_range_text,
            details="High-level comparison chart for voice activity metrics.",
        ),
        color=discord.Color.blurple(),
    )

    if cached_image_path and Path(cached_image_path).exists():
        file = discord.File(cached_image_path, filename=OVERVIEW_FILENAME)
    else:
        fig = build_overview_figure(stats)
        file = await asyncio.to_thread(fig_to_file, fig, OVERVIEW_FILENAME, False)
    if file:
        embed.set_image(url=f"attachment://{OVERVIEW_FILENAME}")
    return embed, file


async def build_leaderboard_message(
    stats: dict,
    scope_label: str,
    date_range_text: str,
    cached_image_path: str | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    embed = discord.Embed(
        title=_metrics_title(scope_label, "Leaderboards"),
        description=_metrics_description(
            date_range_text,
            details="Top 5 users by participant + creator hours (ranked on the sum). Orange = time in others’ channels (journal); blue = time in channels you created (session duration).",
        ),
        color=discord.Color.blurple(),
    )
    if cached_image_path and Path(cached_image_path).exists():
        file = discord.File(cached_image_path, filename=LEADERBOARD_FILENAME)
        embed.set_image(url=f"attachment://{LEADERBOARD_FILENAME}")
        return embed, file

    fig = build_leaderboard_figure(stats)
    if fig is not None:
        file = await asyncio.to_thread(fig_to_file, fig, LEADERBOARD_FILENAME, True)
        if file:
            embed.set_image(url=f"attachment://{LEADERBOARD_FILENAME}")
            return embed, file
    embed.add_field(name="No leaderboard data", value="No voice activity in this range.", inline=False)
    return embed, None


async def build_activity_message(
    activity_points: list[dict],
    scope_label: str,
    date_range_text: str,
    cached_image_path: str | None = None,
    timezone_label: str | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    tz = timezone_label or activity_chart_timezone_label()
    embed = discord.Embed(
        title=_metrics_title(scope_label, "Activity"),
        description=_metrics_description(
            date_range_text,
            details=f"Average active participants by hour of day (local clock in {tz}).",
        ),
        color=discord.Color.blurple(),
    )
    if not activity_points:
        embed.add_field(name="Activity", value="No activity data for selected range.", inline=False)
        return embed, None

    if cached_image_path and Path(cached_image_path).exists():
        file = discord.File(cached_image_path, filename=ACTIVITY_FILENAME)
    else:
        fig = build_activity_figure(activity_points, timezone_label=tz)
        if fig is None:
            return embed, None
        file = await asyncio.to_thread(fig_to_file, fig, ACTIVITY_FILENAME, False)
    if file:
        embed.set_image(url=f"attachment://{ACTIVITY_FILENAME}")
    return embed, file


async def build_weekday_trends_message(
    weekday_trends: dict,
    scope_label: str,
    date_range_text: str,
    cached_image_path: str | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    mode = weekday_trends.get("mode", "weekday_average")
    points = weekday_trends.get("points", [])
    summary = weekday_trends.get("summary", {})
    details = (
        "This week (Monday to Sunday)." if mode == "this_week" else "Averages by weekday across selected range."
    )
    embed = discord.Embed(
        title=_metrics_title(scope_label, "Weekday Trends"),
        description=_metrics_description(date_range_text, details=details),
        color=discord.Color.blurple(),
    )

    if not points:
        embed.add_field(name="Weekday trends", value="No data for selected range.", inline=False)
        return embed, None

    if cached_image_path and Path(cached_image_path).exists():
        file = discord.File(cached_image_path, filename=WEEKDAY_TRENDS_FILENAME)
    else:
        fig = build_weekday_trends_figure(points, summary=summary)
        if fig is None:
            return embed, None
        file = await asyncio.to_thread(fig_to_file, fig, WEEKDAY_TRENDS_FILENAME, True)
    if file:
        embed.set_image(url=f"attachment://{WEEKDAY_TRENDS_FILENAME}")
    return embed, file


async def build_top_embed(
    analytics_gateway: AnalyticsGateway,
    member_gateway: MemberGateway,
    limit: int = 10,
) -> tuple[discord.Embed | None, str | None]:
    limit = limit if limit <= 10 else 10
    sessions = await analytics_gateway.longest_sessions_all_time(limit=limit)
    member_ids = [session.creator_id for session in sessions if session.creator_id is not None]
    members_map = await member_gateway.get_members_map(member_ids)

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
        username = (member_info.public_name if member_info else None) or session.created_by or "Unknown"

        if i <= 3:
            line = f"{medals[i - 1]} **{session.channel_name}** *by* {username}\n⏱️ `{duration}`"
        else:
            line = f"{i}. **{session.channel_name}** *by* {username}\n⏱️ `{duration}`"
        lines.append(line)

    if len(lines) > 3:
        top_three = "\n\n".join(lines[:3])
        others = "\n".join(lines[3:])
        embed.description = f"{top_three}\n\n{others}"
    else:
        embed.description = "\n\n".join(lines)

    return embed, None
