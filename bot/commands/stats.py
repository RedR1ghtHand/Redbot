import disnake as discord
from disnake.ext import commands

from bot.services.stats import StatsAggregationService
from bot.ui.stats import StatsMainView, build_top_embed
from database.repositories import MemberRepository
from utils import get_message


def register_stats_commands(
    bot: commands.InteractionBot,
    stats_service: StatsAggregationService,
    member_repository: MemberRepository,
) -> None:
    @bot.slash_command(name="stats", description=get_message("commands.stats.description"))
    async def stats_command(interaction: discord.ApplicationCommandInteraction) -> None:
        menu_view = StatsMainView(
            stats_service=stats_service,
        )
        await interaction.response.send_message(embed=menu_view.menu_embed(), view=menu_view)

    @bot.slash_command(name="top", description=get_message("commands.top.description"))
    async def top_sessions(
        interaction: discord.ApplicationCommandInteraction,
        limit: int = commands.Param(default=10, ge=1, le=10),
    ) -> None:
        embed, no_data_text = await build_top_embed(
            stats_service=stats_service,
            member_repository=member_repository,
            limit=limit,
        )
        if embed is None:
            await interaction.response.send_message(
                no_data_text or get_message("commands.top.fallback_no_data")
            )
            return
        await interaction.response.send_message(embed=embed)
