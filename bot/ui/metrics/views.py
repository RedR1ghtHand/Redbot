import disnake as discord

from bot.services import MetricsCacheManager
from database.gateways import AnalyticsGateway

from .embeds import (
    build_activity_message,
    build_leaderboard_message,
    build_overview_message,
    build_stats_embed,
    build_weekday_trends_message,
)
from .messages import RANGE_PRESETS, range_days, range_label


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
            placeholder="Select reporting range",
            min_values=1,
            max_values=1,
            options=select_options,
        )

        components = [
            discord.ui.Label(
                text="Range",
                component=self.range_select,
            )
        ]

        super().__init__(
            title="Select Range",
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
                "Please select a reporting range from the menu.",
                ephemeral=True,
            )
            return

        self.parent_view.range_key = range_key

        await interaction.response.defer(with_message=False)
        await self.target_message.edit(embed=self.parent_view.menu_embed(), view=self.parent_view)


class StatsMainView(discord.ui.View):
    def __init__(
        self,
        analytics_gateway: AnalyticsGateway,
        cache_manager: MetricsCacheManager,
        range_key: str = "week",
        top_limit: int = 5,
    ):
        super().__init__(timeout=300)
        self.analytics_gateway = analytics_gateway
        self.cache_manager = cache_manager
        self.range_key = range_key
        self.top_limit = top_limit

    async def _date_range_text(self, lookback_days: int | None) -> str:
        range_start, range_end = await self.analytics_gateway.get_reporting_range(lookback_days=lookback_days)
        return f"{range_start:%d.%m.%Y} - {range_end:%d.%m.%Y}"

    def menu_embed(self) -> discord.Embed:
        current_range = range_label(self.range_key)
        return discord.Embed(
            title="Stats Menu",
            description=(
                f"Current range: **{current_range}**\n\n"
                "Use buttons below:\n"
                "- **Range**: change reporting period\n"
                "- **Detailed metrics**: send overview + leaderboard + activity chart embeds\n"
                "- **All Stats**: show full stats snapshot"
            ),
            color=discord.Color.blurple(),
        )

    @discord.ui.button(label="Range", style=discord.ButtonStyle.secondary)
    async def range_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(RangeModal(parent_view=self, target_message=interaction.message))

    @discord.ui.button(label="Detailed metrics", style=discord.ButtonStyle.primary)
    async def detailed_metrics(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        member = interaction.author if isinstance(interaction.author, discord.Member) else None
        if member is None or not member.guild_permissions.administrator:
            await interaction.response.send_message(
                "Only administrators can use Detailed metrics.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(with_message=False)

        lookback_days = range_days(self.range_key)
        scope_label = range_label(self.range_key)
        cached_payload = await self.cache_manager.get_or_build_detailed_metrics(
            range_key=self.range_key,
            lookback_days=lookback_days,
            top_limit=self.top_limit,
        )
        stats = cached_payload["stats"]
        date_range_text = cached_payload["date_range_text"]
        activity_points = cached_payload["activity_points"]
        weekday_trends = cached_payload["weekday_trends"]
        image_paths = cached_payload["images"]

        overview_embed, overview_file = await build_overview_message(
            stats=stats,
            scope_label=scope_label,
            date_range_text=date_range_text,
            cached_image_path=image_paths.get("overview"),
        )

        leaderboard_embed, leaderboard_file = await build_leaderboard_message(
            stats=stats,
            scope_label=scope_label,
            date_range_text=date_range_text,
            cached_image_path=image_paths.get("leaderboard"),
        )

        activity_embed, activity_file = await build_activity_message(
            activity_points=activity_points,
            scope_label=scope_label,
            date_range_text=date_range_text,
            cached_image_path=image_paths.get("activity"),
        )
        weekday_trends_embed, weekday_trends_file = await build_weekday_trends_message(
            weekday_trends=weekday_trends,
            scope_label=scope_label,
            date_range_text=date_range_text,
            cached_image_path=image_paths.get("weekday_trends"),
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

    @discord.ui.button(label="All Stats", style=discord.ButtonStyle.secondary)
    async def all_stats(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        lookback_days = range_days(self.range_key)
        scope_label = range_label(self.range_key)
        stats = await self.analytics_gateway.get_stats_snapshot(
            lookback_days=lookback_days,
            top_limit=self.top_limit,
        )
        embed = build_stats_embed(metric_key="all", stats=stats, scope_label=scope_label)
        await interaction.response.edit_message(embed=embed, view=self)
