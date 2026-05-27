import logging

import disnake as discord
from disnake.ext import commands

import settings
from bot.services.members import MemberService
from bot.services.stats import (
    StatsAggregationService,
    StatsCacheStore,
    StatsChartCacheStore,
)
from bot.services.voice_channels import VoiceChannelEventCoordinator
from bot.ui.channels import ChannelControlView
from database.connection import db
from database.repositories import (
    MemberRepository,
    SessionJournalRepository,
    SessionRepository,
    StatsReadRepository,
)

from .commands import register_admin_commands, register_stats_commands

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.presences = True  
intents.message_content = True

ALLOWED_GUILDS = settings.ALLOWED_GUILDS

bot = commands.InteractionBot(intents=intents, test_guilds=list(ALLOWED_GUILDS))
session_repository = SessionRepository(db)
member_repository = MemberRepository(db)
session_journal_repository = SessionJournalRepository(db)
stats_read_repository = StatsReadRepository(db)
stats_cache_store = StatsCacheStore()
stats_chart_cache_store = StatsChartCacheStore()
stats_service = StatsAggregationService(
    stats_read_repository,
    cache_store=stats_cache_store,
    chart_cache=stats_chart_cache_store,
)

temporary_channels: set[int] = set()
member_service = MemberService(member_repository)
voice_channel_coordinator = VoiceChannelEventCoordinator(
    member_service=member_service,
    session_repository=session_repository,
    session_journal_repository=session_journal_repository,
    temporary_channel_ids=temporary_channels,
)
register_stats_commands(bot, stats_service, member_repository)
register_admin_commands(bot, session_repository, bot, temporary_channels, session_journal_repository)


@bot.event
async def on_guild_join(guild):
    if guild.id not in ALLOWED_GUILDS:
        logging.info(f"Bot joined unauthorized guild: {guild.name} (ID: {guild.id})")
        logging.info(f"Leaving guild: {guild.name}")
        await guild.leave()
        return
    
    logging.info(f"Bot joined authorized guild: {guild.name} (ID: {guild.id})")


@bot.event
async def on_ready():
    global temporary_channels
    logging.info(f"Bot is ready! Logged in as {bot.user}")
    logging.info(f"Registered slash commands: {len(bot.slash_commands)}")

    removed_journals = await session_journal_repository.delete_open_journals_for_ended_sessions()
    if removed_journals:
        logging.info(
            "Removed %s open journal row(s) whose session was already ended (stale after missed leave events).",
            removed_journals,
        )

    active_sessions = await session_repository.get_active_sessions()
    temporary_channels.clear()
    temporary_channels.update(item["session"].channel_id for item in active_sessions)
    for item in active_sessions:
        session = item["session"]
        creator_id = item.get("creator_id")
        created_by = item.get("created_by")
        channel = bot.get_channel(session.channel_id)
        if channel is not None:
            owner = None
            if channel.guild:
                if creator_id is not None:
                    owner = channel.guild.get_member(creator_id)
                if owner is None and created_by:
                    owner = channel.guild.get_member_named(created_by)
            creator_record = None
            if creator_id is not None:
                creator_record = await member_repository.get_member(creator_id)
            bot.add_view(
                ChannelControlView(
                    channel,
                    owner=owner,
                    session_gateway=session_repository,
                    creator_record=creator_record,
                )
            )
    if active_sessions:
        logging.info(f"Restored {len(active_sessions)} active session(s) into temporary_channels and re-added ChannelControlViews")

    for guild in bot.guilds:
        if guild.id not in ALLOWED_GUILDS:
            logging.info(f"Found unauthorized guild: {guild.name} (ID: {guild.id})")
            logging.info(f"Leaving guild: {guild.name}")
            await guild.leave()
        else:
            logging.info(f"Authorized guild: {guild.name} (ID: {guild.id})")


@bot.event
async def on_voice_state_update(member, before, after):
    await voice_channel_coordinator.on_voice_state_update(member, before, after)


def run_bot():
    bot.run(settings.BOT_TOKEN)
