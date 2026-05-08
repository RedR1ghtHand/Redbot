import disnake as discord
from disnake.ext import commands

from database.analytics_manager import AnalyticsManager
from database.member_manager import MemberManager
from bot.ui.metrics.embeds import build_top_embed
from bot.ui.metrics.cache import MetricsCacheManager
from bot.ui.metrics.views import StatsMainView


def register_metrics_commands(
    bot: commands.InteractionBot,
    analytics_manager: AnalyticsManager,
    member_manager: MemberManager,
    metrics_cache_manager: MetricsCacheManager,
) -> None:
    @bot.slash_command(name="stats", description="Open interactive stats menu")
    async def stats_command(interaction: discord.ApplicationCommandInteraction) -> None:
        menu_view = StatsMainView(
            analytics_manager=analytics_manager,
            cache_manager=metrics_cache_manager,
        )
        await interaction.response.send_message(embed=menu_view.menu_embed(), view=menu_view)

    @bot.slash_command(name="top", description="Show top sessions sorted by duration")
    async def top_sessions(
        interaction: discord.ApplicationCommandInteraction,
        limit: int = commands.Param(default=10, ge=1, le=10),
    ) -> None:
        embed, no_data_text = await build_top_embed(
            analytics_manager=analytics_manager,
            member_manager=member_manager,
            limit=limit,
        )
        if embed is None:
            await interaction.response.send_message(no_data_text or "No data")
            return
        await interaction.response.send_message(embed=embed)
