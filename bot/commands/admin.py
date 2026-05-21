import logging
from typing import Any

import disnake as discord
from disnake.ext import commands

from database.gateways import SessionGateway, SessionJournalGateway

logger = logging.getLogger(__name__)

CleanupResult = tuple[int, str]


def _result_line(title: str, count: int, done_template: str, empty: str) -> CleanupResult:
    if count:
        return count, f"**{title}**: {done_template.format(count=count)}"
    return 0, f"**{title}**: {empty}"


async def _cleanup_short_sessions(
    session_gateway: SessionGateway,
    threshold: int,
) -> CleanupResult:
    deleted = await session_gateway.clean_up_short_sessions(treshhold=threshold)
    return _result_line(
        f"Short sessions (≤{threshold}s)",
        deleted,
        "removed **{count}** from the database",
        "nothing to remove",
    )


async def _cleanup_empty_temporary_channels(
    guild: discord.Guild | None,
    session_gateway: SessionGateway,
    temporary_channels: set[int],
) -> CleanupResult:
    if guild is None:
        return 0, "**Empty temporary channels**: skipped (use this command in a server)."

    empty = [ch for ch in guild.voice_channels if ch.id in temporary_channels and not ch.members]
    for ch in empty:
        await session_gateway.update_and_end_session(ch.id)
        logger.info("Session '%s' ended via cleanup. Entry saved to the database", ch.name)
        await ch.delete(reason="Cleanup: temporary VC empty")
        temporary_channels.discard(ch.id)

    return _result_line(
        "Empty temporary channels",
        len(empty),
        "closed **{count}** and saved their sessions",
        "none to close",
    )


async def _cleanup_broken_db_sessions(
    session_gateway: SessionGateway,
    client: Any,
    temporary_channels: set[int],
) -> CleanupResult:
    active = await session_gateway.get_active_sessions()
    broken = [item["session"] for item in active if client.get_channel(item["session"].channel_id) is None]

    for session in broken:
        await session_gateway.delete_session(session.channel_id)
        temporary_channels.discard(session.channel_id)
        logger.info(
            "Broken session '%s' (channel_id=%s) removed from DB.",
            session.channel_name,
            session.channel_id,
        )

    return _result_line(
        "Broken DB sessions (channel gone)",
        len(broken),
        "removed **{count}**",
        "none found",
    )


async def _cleanup_stale_journals(session_journal_gateway: SessionJournalGateway) -> CleanupResult:
    removed = await session_journal_gateway.delete_open_journals_for_ended_sessions()
    return _result_line(
        "Stale open journals (session already ended)",
        removed,
        "removed **{count}**",
        "none found",
    )


def _format_cleanup_message(results: list[CleanupResult]) -> str:
    total = sum(count for count, _ in results)
    header = (
        "**Cleanup finished.**"
        if total
        else "**Cleanup finished.** No changes were needed."
    )
    body = "\n".join(line for _, line in results)
    return f"{header}\n\n{body}"


def register_admin_commands(
    bot: commands.InteractionBot,
    session_gateway: SessionGateway,
    client: commands.InteractionBot,
    temporary_channels: set[int],
    session_journal_gateway: SessionJournalGateway,
) -> None:
    @bot.slash_command(
        name="cleanup",
        description="Run all database and voice clean-ups (admin only)",
    )
    @commands.has_permissions(administrator=True)
    async def cleanup(
        interaction: discord.ApplicationCommandInteraction,
        short_session_threshold: int = commands.Param(
            default=600,
            ge=1,
            description="Delete ended sessions with duration at or below this many seconds",
        ),
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        results = [
            await _cleanup_short_sessions(session_gateway, short_session_threshold),
            await _cleanup_empty_temporary_channels(
                interaction.guild, session_gateway, temporary_channels
            ),
            await _cleanup_broken_db_sessions(session_gateway, client, temporary_channels),
            await _cleanup_stale_journals(session_journal_gateway),
        ]

        await interaction.edit_original_response(content=_format_cleanup_message(results))
