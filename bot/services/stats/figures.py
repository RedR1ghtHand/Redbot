import asyncio
import io
import logging
from collections import Counter

import disnake as discord
import pandas as pd
import plotly.express as px

import settings
from bot.ui.shared import format_duration_hhmmss
from utils import get_message

logger = logging.getLogger(__name__)


def _figure_messages(chart_key: str) -> dict:
    node = get_message(f"embeds.stats.figures.{chart_key}")
    return node if isinstance(node, dict) else {}

OVERVIEW_FILENAME = "stats_overview.png"
LEADERBOARD_FILENAME = "stats_leaderboard.png"
ACTIVITY_FILENAME = "stats_activity.png"
WEEKDAY_TRENDS_FILENAME = "stats_weekday_trends.png"


def fig_to_file(fig, filename: str, showlegend: bool = False) -> discord.File | None:
    fig.update_layout(
        template="plotly_dark",
        showlegend=showlegend,
        font=dict(family="DejaVu Sans, Arial, sans-serif"),
    )
    try:
        image_bytes = fig.to_image(format="png", width=1200, height=650, scale=2)
    except Exception:
        logger.exception("Failed to render chart image for %s", filename)
        return None
    return discord.File(io.BytesIO(image_bytes), filename=filename)


def fig_to_png_bytes(fig, showlegend: bool = False) -> bytes | None:
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


def build_overview_figure(stats: dict):
    messages = _figure_messages("overview")
    metric_labels = messages.get("metrics", {})
    rows = [
        {"metric": metric_labels.get("voice_hours", "Voice Hours"), "value": stats["total_voice_seconds"] / 3600},
        {"metric": metric_labels.get("sessions", "Sessions"), "value": stats["sessions_count"]},
        {"metric": metric_labels.get("unique_participants", "Unique Participants"), "value": stats["unique_participants"]},
        {
            "metric": metric_labels.get("avg_participants_per_session", "Avg Participants/Session"),
            "value": stats["avg_participants_per_session"],
        },
    ]
    df = pd.DataFrame(rows)
    df["label"] = df["value"].apply(lambda number: f"{number:.2f}")

    fig = px.bar(
        df,
        x="metric",
        y="value",
        color="metric",
        text="label",
        title=messages.get("title", "Overview Metrics"),
        labels={
            "metric": messages.get("axis_metric", "Metric"),
            "value": messages.get("axis_value", "Value"),
        },
        category_orders={"metric": [row["metric"] for row in rows]},
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        legend_title_text=messages.get("legend_title", "Metric"),
        uniformtext_minsize=10,
        uniformtext_mode="show",
    )
    return fig


def build_leaderboard_figure(stats: dict):
    combined = stats.get("leaderboard_top_combined") or []
    chart_slice = combined[:5]
    if not chart_slice:
        return None

    messages = _figure_messages("leaderboard")
    groups = messages.get("groups", {})
    creators_label = groups.get("creators", "Creators")
    participants_label = groups.get("participants", "Participants")

    name_counts = Counter(row["name"] for row in chart_slice)
    chart_rows: list[dict] = []
    ordered_labels: list[str] = []
    for row in chart_slice:
        label = row["name"]
        if name_counts[label] > 1:
            label = f"{row['name']} ({row['member_id']})"
        ordered_labels.append(label)
        chart_rows.append(
            {"name": label, "hours": row["participant_seconds"] / 3600.0, "group": participants_label},
        )
        chart_rows.append(
            {"name": label, "hours": row["creator_seconds"] / 3600.0, "group": creators_label},
        )

    df = pd.DataFrame(chart_rows)
    color_map = {
        creators_label: "#1f77b4",
        participants_label: "#ff7f0e",
    }
    fig = px.bar(
        df,
        x="hours",
        y="name",
        color="group",
        barmode="group",
        orientation="h",
        title=messages.get("title", "Top 5 by combined voice time (participant + created channels)"),
        color_discrete_map=color_map,
        labels={
            "hours": messages.get("axis_hours", "Hours"),
            "name": messages.get("axis_user", "User"),
            "group": messages.get("axis_group", "Metric"),
        },
    )
    fig.update_layout(
        legend_title_text=messages.get("legend_title", "Color key"),
        margin=dict(t=80),
        yaxis=dict(
            categoryorder="array",
            categoryarray=list(reversed(ordered_labels)),
        ),
    )
    return fig


def activity_chart_timezone_label() -> str:
    return settings.REPORTING_TIMEZONE_NAME or "UTC"


def build_activity_figure(activity_points: list[dict], timezone_label: str | None = None):
    if not activity_points:
        return None
    tz = timezone_label or activity_chart_timezone_label()
    messages = _figure_messages("activity")
    df = pd.DataFrame(activity_points)
    df = df.sort_values("hour")
    fig = px.line(
        df,
        x="hour",
        y="avg_active_participants",
        markers=True,
        title=messages.get("title", "Average Activity by Hour (0–23, {timezone})").format(timezone=tz),
        labels={
            "hour": messages.get("axis_hour", "Hour of day"),
            "avg_active_participants": messages.get("axis_avg_active", "Avg active participants"),
        },
    )
    fig.update_layout(
        xaxis_title=messages.get("axis_hour_local", "Hour of day (local {timezone})").format(timezone=tz),
        yaxis_title=messages.get("axis_avg_active", "Avg active participants"),
    )
    fig.update_xaxes(tickmode="linear", dtick=1, range=[0, 23])
    return fig


WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def build_weekday_trends_figure(weekday_points: list[dict], summary: dict | None = None):
    if not weekday_points:
        return None
    df = pd.DataFrame(weekday_points)
    value_columns = [
        "avg_active_participants",
        "avg_time_per_user_hours",
    ]
    melted = df.melt(id_vars=["weekday"], value_vars=value_columns, var_name="metric", value_name="value")
    messages = _figure_messages("weekday_trends")
    metric_labels = messages.get(
        "metric_labels",
        {
            "avg_active_participants": "Avg active participants",
            "avg_time_per_user_hours": "Avg time per user (hours)",
        },
    )
    melted["metric"] = melted["metric"].map(metric_labels)
    fig = px.line(
        melted,
        x="weekday",
        y="value",
        color="metric",
        markers=True,
        title=messages.get("title", "Weekday Voice Trends (Mon-Sun)"),
        labels={
            "weekday": messages.get("axis_weekday", "Weekday"),
            "value": messages.get("axis_value", "Value"),
            "metric": messages.get("axis_metric", "Metric"),
        },
        category_orders={"weekday": WEEKDAY_ORDER},
    )
    if summary:
        summary_text = (
            f"{messages.get('summary_header', 'Averages:')}<br>"
            f"{messages.get('summary_active_users', '- active users/day: {value:.2f}').format(value=summary.get('avg_active_participants', 0.0))}<br>"
            f"{messages.get('summary_time_per_user', '- time per user: {duration}').format(duration=format_duration_hhmmss(summary.get('avg_time_per_user_seconds', 0)))}"
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
    fig = build_overview_figure(stats)
    return await asyncio.to_thread(fig_to_png_bytes, fig, False)


async def render_leaderboard_chart_png(stats: dict) -> bytes | None:
    fig = build_leaderboard_figure(stats)
    if fig is None:
        return None
    return await asyncio.to_thread(fig_to_png_bytes, fig, True)


async def render_activity_chart_png(
    activity_points: list[dict],
    timezone_label: str | None = None,
) -> bytes | None:
    fig = build_activity_figure(activity_points, timezone_label=timezone_label)
    if fig is None:
        return None
    return await asyncio.to_thread(fig_to_png_bytes, fig, False)


async def render_weekday_trends_chart_png(weekday_points: list[dict], summary: dict | None = None) -> bytes | None:
    fig = build_weekday_trends_figure(weekday_points, summary=summary)
    if fig is None:
        return None
    return await asyncio.to_thread(fig_to_png_bytes, fig, True)
