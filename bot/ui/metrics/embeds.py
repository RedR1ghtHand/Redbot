import asyncio
import io
import logging
from pathlib import Path

import disnake as discord
import pandas as pd
import plotly.express as px

import settings
from bot.ui.shared import format_duration_hhmmss
from database.gateways.analytics import AnalyticsGateway
from database.gateways.member import MemberGateway

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


logger = logging.getLogger(__name__)
OVERVIEW_FILENAME = "stats_overview.png"
LEADERBOARD_FILENAME = "stats_leaderboard.png"
ACTIVITY_FILENAME = "stats_activity.png"
WEEKDAY_TRENDS_FILENAME = "stats_weekday_trends.png"


def _metrics_title(scope_label: str, metric_type: str) -> str:
    return f"Stats | {scope_label} | {metric_type}"


def _metrics_description(date_range_text: str, details: str | None = None) -> str:
    base = f"Date range: `{date_range_text}`"
    if details:
        return f"{base}\n{details}"
    return base


def _fig_to_file(fig, filename: str, showlegend: bool = False) -> discord.File | None:
    fig.update_layout(
        template="plotly_dark",
        showlegend=showlegend,
        # Kaleido default fonts often miss Cyrillic/emoji; DejaVu Sans covers most non-Latin labels.
        font=dict(family="DejaVu Sans, Arial, sans-serif"),
    )
    try:
        image_bytes = fig.to_image(format="png", width=1200, height=650, scale=2)
    except Exception:
        logger.exception("Failed to render chart image for %s", filename)
        return None
    return discord.File(io.BytesIO(image_bytes), filename=filename)


def _fig_to_png_bytes(fig, showlegend: bool = False) -> bytes | None:
    fig.update_layout(
        template="plotly_dark",
        showlegend=showlegend,
        font=dict(family="DejaVu Sans, Arial, sans-serif"),
    )
    try:
        return fig.to_image(format="png", width=1200, height=650, scale=2)
    except Exception:
        logger.exception("Failed to render chart image bytes")
        return None


def _build_overview_figure(stats: dict):
    rows = [
        {"metric": "Voice Hours", "value": stats["total_voice_seconds"] / 3600},
        {"metric": "Sessions", "value": stats["sessions_count"]},
        {"metric": "Unique Participants", "value": stats["unique_participants"]},
        {"metric": "Avg Participants/Session", "value": stats["avg_participants_per_session"]},
    ]
    df = pd.DataFrame(rows)
    df["label"] = df["value"].apply(lambda number: f"{number:.2f}")

    fig = px.bar(
        df,
        x="metric",
        y="value",
        color="metric",
        text="label",
        title="Overview Metrics",
        labels={"metric": "Metric", "value": "Value"},
        category_orders={"metric": [row["metric"] for row in rows]},
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        legend_title_text="Metric",
        uniformtext_minsize=10,
        uniformtext_mode="show",
    )
    return fig


def _build_leaderboard_figure(stats: dict):
    creators = stats["top_creators"][:5]
    participants = stats["top_participants"][:5]
    chart_rows = []
    for row in creators:
        chart_rows.append({"name": row["name"], "hours": row["seconds"] / 3600, "group": "Creators"})
    for row in participants:
        chart_rows.append({"name": row["name"], "hours": row["seconds"] / 3600, "group": "Participants"})
    if not chart_rows:
        return None

    df = pd.DataFrame(chart_rows)
    color_map = {
        "Creators": "#1f77b4",
        "Participants": "#ff7f0e",
    }
    fig = px.bar(
        df,
        x="hours",
        y="name",
        color="group",
        barmode="group",
        orientation="h",
        title="Top creators vs top participants (up to 5 each; one row per display name)",
        color_discrete_map=color_map,
        labels={"hours": "Hours", "name": "User", "group": "Leaderboard"},
    )
    fig.update_layout(
        legend_title_text="Color key",
        margin=dict(t=80),
    )
    return fig


def _activity_chart_timezone_label() -> str:
    return settings.REPORTING_TIMEZONE_NAME or "UTC"


def _build_activity_figure(activity_points: list[dict], timezone_label: str | None = None):
    if not activity_points:
        return None
    tz = timezone_label or _activity_chart_timezone_label()
    df = pd.DataFrame(activity_points)
    df = df.sort_values("hour")
    fig = px.line(
        df,
        x="hour",
        y="avg_active_participants",
        markers=True,
        title=f"Average Activity by Hour (0–23, {tz})",
        labels={"hour": "Hour of day", "avg_active_participants": "Avg active participants"},
    )
    fig.update_layout(
        xaxis_title=f"Hour of day (local {tz})",
        yaxis_title="Avg active participants",
    )
    fig.update_xaxes(tickmode="linear", dtick=1, range=[0, 23])
    return fig


def _build_weekday_trends_figure(weekday_points: list[dict], summary: dict | None = None):
    if not weekday_points:
        return None
    df = pd.DataFrame(weekday_points)
    value_columns = [
        "avg_voice_time_hours",
        "avg_users_participated",
        "avg_time_per_user_hours",
    ]
    melted = df.melt(id_vars=["weekday"], value_vars=value_columns, var_name="metric", value_name="value")
    metric_labels = {
        "avg_voice_time_hours": "Avg voice time (participant-hours)",
        "avg_users_participated": "Avg users participated",
        "avg_time_per_user_hours": "Avg time per user (hours)",
    }
    melted["metric"] = melted["metric"].map(metric_labels)
    fig = px.line(
        melted,
        x="weekday",
        y="value",
        color="metric",
        markers=True,
        title="Weekday Voice Trends (Mon-Sun)",
        labels={"weekday": "Weekday", "value": "Value", "metric": "Metric"},
    )
    if summary:
        summary_text = (
            "Averages:<br>"
            f"- time in voices: {format_duration_hhmmss(summary.get('avg_voice_time_seconds', 0))}<br>"
            f"- users: {summary.get('avg_users_participated', 0.0):.2f}<br>"
            f"- time per user: {format_duration_hhmmss(summary.get('avg_time_per_user_seconds', 0))}"
        )
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=1.21,
            y=0.77,
            text=summary_text,
            showarrow=False,
            align="left",
            font={"size": 11},
            bordercolor="#888",
            borderwidth=1,
            borderpad=6,
            bgcolor="rgba(30,30,30,0.6)",
        )
        fig.update_layout(margin=dict(r=280))
    return fig


async def render_overview_chart_png(stats: dict) -> bytes | None:
    fig = _build_overview_figure(stats)
    return await asyncio.to_thread(_fig_to_png_bytes, fig, False)


async def render_leaderboard_chart_png(stats: dict) -> bytes | None:
    fig = _build_leaderboard_figure(stats)
    if fig is None:
        return None
    return await asyncio.to_thread(_fig_to_png_bytes, fig, True)


async def render_activity_chart_png(
    activity_points: list[dict],
    timezone_label: str | None = None,
) -> bytes | None:
    fig = _build_activity_figure(activity_points, timezone_label=timezone_label)
    if fig is None:
        return None
    return await asyncio.to_thread(_fig_to_png_bytes, fig, False)


async def render_weekday_trends_chart_png(weekday_points: list[dict], summary: dict | None = None) -> bytes | None:
    fig = _build_weekday_trends_figure(weekday_points, summary=summary)
    if fig is None:
        return None
    return await asyncio.to_thread(_fig_to_png_bytes, fig, True)


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
        fig = _build_overview_figure(stats)
        file = await asyncio.to_thread(_fig_to_file, fig, OVERVIEW_FILENAME, False)
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
            details="Up to top 5 creators and top 5 participants by hours (participant time from join/leave journal; creator time from session duration).",
        ),
        color=discord.Color.blurple(),
    )
    if cached_image_path and Path(cached_image_path).exists():
        file = discord.File(cached_image_path, filename=LEADERBOARD_FILENAME)
        embed.set_image(url=f"attachment://{LEADERBOARD_FILENAME}")
        return embed, file

    fig = _build_leaderboard_figure(stats)
    if fig is not None:
        file = await asyncio.to_thread(_fig_to_file, fig, LEADERBOARD_FILENAME, True)
        if file:
            embed.set_image(url=f"attachment://{LEADERBOARD_FILENAME}")
            return embed, file
    embed.add_field(name="No leaderboard data", value="No creator or participant activity in this range.", inline=False)
    return embed, None


async def build_activity_message(
    activity_points: list[dict],
    scope_label: str,
    date_range_text: str,
    cached_image_path: str | None = None,
    timezone_label: str | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    tz = timezone_label or _activity_chart_timezone_label()
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
        fig = _build_activity_figure(activity_points, timezone_label=tz)
        if fig is None:
            return embed, None
        file = await asyncio.to_thread(_fig_to_file, fig, ACTIVITY_FILENAME, False)
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
        fig = _build_weekday_trends_figure(points, summary=summary)
        if fig is None:
            return embed, None
        file = await asyncio.to_thread(_fig_to_file, fig, WEEKDAY_TRENDS_FILENAME, True)
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
