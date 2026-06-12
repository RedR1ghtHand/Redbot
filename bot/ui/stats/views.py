import disnake as discord

from bot.services.stats import StatsAggregationService
from utils import get_message

from .embeds import (
    build_activity_message,
    build_leaderboard_message,
    build_overview_message,
    build_stats_embed,
    build_weekday_trends_message,
)
from .messages import RANGE_PRESETS, range_days, range_label, stats_menu_description


class RangeModal(discord.ui.Modal):
    def __init__(self, parent_view: "StatsMainView", target_message: discord.Message):
        self.parent_view = parent_view
        self.target_message = target_message

        select_options = [
            discord.SelectOption(
                label=label,
                value=key,
                default=(key == parent_view.range_key),
            )
            for key, (label, _days) in RANGE_PRESETS.items()
        ]
        self.range_select_custom_id = "stats_range_select_value"
        self.range_select = discord.ui.StringSelect(
            custom_id=self.range_select_custom_id,
            placeholder=get_message("modals.stats_range.placeholder"),
            min_values=1,
            max_values=1,
            options=select_options,
        )

        components = [
            discord.ui.Label(
                text=get_message("modals.stats_range.field_label"),
                component=self.range_select,
            )
        ]

        super().__init__(
            title=get_message("modals.stats_range.title"),
            components=components,
            custom_id="stats_range_modal",
            timeout=300,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        raw = interaction.values.get(self.range_select_custom_id)
        if isinstance(raw, list):
            range_key = raw[0] if raw else None
        elif isinstance(raw, str):
            range_key = raw
        else:
            range_key = None

        if not range_key or range_key not in RANGE_PRESETS:
            await interaction.response.send_message(
                get_message("modals.stats_range.invalid_selection"),
                ephemeral=True,
            )
            return

        self.parent_view.range_key = range_key

        await interaction.response.defer(with_message=False)
        await self.target_message.edit(embed=self.parent_view.menu_embed(), view=self.parent_view)


class StatsMainView(discord.ui.View):
    def __init__(
        self,
        stats_service: StatsAggregationService,
        range_key: str = "week",
        top_limit: int = 5,
    ):
        super().__init__(timeout=300)
        self.stats_service = stats_service
        self.range_key = range_key
        self.top_limit = top_limit

    async def _date_range_text(self, lookback_days: int | None) -> str:
        range_start, range_end = await self.stats_service.get_reporting_range(lookback_days=lookback_days)
        return f"{range_start:%d.%m.%Y} - {range_end:%d.%m.%Y}"

    def menu_embed(self) -> discord.Embed:
        current_range = range_label(self.range_key)
        return discord.Embed(
            title=get_message("embeds.stats.menu.title"),
            description=stats_menu_description(current_range),
            color=discord.Color.blurple(),
        )

    @discord.ui.button(
        label=get_message("buttons.stats_range.label"),
        style=discord.ButtonStyle.secondary,
    )
    async def range_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(RangeModal(parent_view=self, target_message=interaction.message))

    @discord.ui.button(
        label=get_message("buttons.stats_detailed.label"),
        style=discord.ButtonStyle.primary,
    )
    async def detailed_stats(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        member = interaction.author if isinstance(interaction.author, discord.Member) else None
        if member is None or not member.guild_permissions.administrator:
            await interaction.response.send_message(
                get_message("buttons.stats_detailed.msg_error"),
                ephemeral=True,
            )
            return

        await interaction.response.defer(with_message=False)

        lookback_days = range_days(self.range_key)
        scope_label = range_label(self.range_key)
        payload = await self.stats_service.get_detailed_stats(
            range_key=self.range_key,
            lookback_days=lookback_days,
            top_limit=self.top_limit,
        )
        stats = payload["stats"]
        date_range_text = payload["date_range_text"]
        activity_points = payload["activity_points"]
        weekday_trends = payload["weekday_trends"]

        chart_service = self.stats_service.chart_service

        overview_embed, overview_file = await build_overview_message(
            stats=stats,
            scope_label=scope_label,
            date_range_text=date_range_text,
            chart_service=chart_service,
        )

        leaderboard_embed, leaderboard_file = await build_leaderboard_message(
            stats=stats,
            scope_label=scope_label,
            date_range_text=date_range_text,
            chart_service=chart_service,
        )

        activity_embed, activity_file = await build_activity_message(
            activity_points=activity_points,
            scope_label=scope_label,
            date_range_text=date_range_text,
            chart_service=chart_service,
        )
        weekday_trends_embed, weekday_trends_file = await build_weekday_trends_message(
            weekday_trends=weekday_trends,
            scope_label=scope_label,
            date_range_text=date_range_text,
            chart_service=chart_service,
        )

        embeds = [overview_embed, leaderboard_embed, activity_embed, weekday_trends_embed]
        files: list[discord.File] = []
        if overview_file is not None:
            files.append(overview_file)
        if leaderboard_file is not None:
            files.append(leaderboard_file)
        if activity_file is not None:
            files.append(activity_file)
        if weekday_trends_file is not None:
            files.append(weekday_trends_file)

        await interaction.followup.send(embeds=embeds, files=files if files else None)

    @discord.ui.button(
        label=get_message("buttons.stats_all.label"),
        style=discord.ButtonStyle.secondary,
    )
    async def all_stats(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        lookback_days = range_days(self.range_key)
        scope_label = range_label(self.range_key)
        stats = await self.stats_service.get_stats_snapshot(
            lookback_days=lookback_days,
            top_limit=self.top_limit,
        )
        embed = build_stats_embed(metric_key="all", stats=stats, scope_label=scope_label)
        await interaction.response.edit_message(embed=embed, view=self)
