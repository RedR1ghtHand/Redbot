import logging

import disnake as discord
from disnake.ext import commands

from database.gateways import SessionGateway, SessionJournalGateway


def register_fix_commands(
    bot: commands.InteractionBot,
    session_gateway: SessionGateway,
    client: commands.InteractionBot,
    temporary_channels: set[int],
    session_journal_gateway: SessionJournalGateway,
) -> None:
    @bot.slash_command(name="clean-up-short-sessions", description="Clean up short sessions")
    @commands.has_permissions(administrator=True)
    async def clean_up_short_sessions(
        interaction: discord.ApplicationCommandInteraction,
        treshhold: int = commands.Param(ge=1),
    ) -> None:
        deleted_count = await session_gateway.clean_up_short_sessions(treshhold=treshhold)

        if not deleted_count:
            await interaction.response.send_message(f"No sessions shorter than **{treshhold}**seconds found")
        else:
            await interaction.response.send_message(
                f"Cleaned up **{deleted_count}** sessions shorter than **{treshhold}**seconds"
            )

    @bot.slash_command(
        name="clean-up-active-sessions",
        description="Close empty temporary voice channels and save their sessions",
    )
    @commands.has_permissions(administrator=True)
    async def clean_up_active_sessions(interaction: discord.ApplicationCommandInteraction) -> None:
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        empty_temporary = [
            ch for ch in guild.voice_channels if ch.id in temporary_channels and len(ch.members) == 0
        ]
        closed = 0
        for ch in empty_temporary:
            await session_gateway.update_and_end_session(ch.id)
            logging.info(f"Session '{ch.name}' ended via clean-up. Entry saved to the database")
            await ch.delete(reason="Clean-up: temporary VC empty")
            temporary_channels.discard(ch.id)
            closed += 1

        if closed == 0:
            await interaction.response.send_message("No empty temporary voice channels to close.")
        else:
            await interaction.response.send_message(
                f"Closed **{closed}** empty temporary channel(s) and saved their sessions."
            )

    @bot.slash_command(
        name="clean-up-db-sessions",
        description="Remove from DB sessions that have is_ended=False but their voice channel no longer exists",
    )
    @commands.has_permissions(administrator=True)
    async def clean_up_db_sessions(interaction: discord.ApplicationCommandInteraction) -> None:
        active = await session_gateway.get_active_sessions()
        broken = [item["session"] for item in active if client.get_channel(item["session"].channel_id) is None]
        cleaned = 0

        for session in broken:
            await session_gateway.delete_session(session.channel_id)
            temporary_channels.discard(session.channel_id)
            logging.info(
                f"Broken session '{session.channel_name}' (channel_id={session.channel_id}) removed from DB."
            )
            cleaned += 1

        if cleaned == 0:
            await interaction.response.send_message("No broken sessions found.")
        else:
            await interaction.response.send_message(
                f"Removed **{cleaned}** broken session(s) from the database (channel no longer exists)."
            )

    @bot.slash_command(
        name="clean-up-db-journals",
        description=(
            "Delete open journal rows (user_left_at unset) whose voice session is already ended in the DB"
        ),
    )
    @commands.has_permissions(administrator=True)
    async def clean_up_db_journals(interaction: discord.ApplicationCommandInteraction) -> None:
        removed = await session_journal_gateway.delete_open_journals_for_ended_sessions()
        if removed == 0:
            await interaction.response.send_message("No stale open journal rows found.")
        else:
            await interaction.response.send_message(
                f"Removed **{removed}** open journal row(s) tied to already-ended sessions."
            )
