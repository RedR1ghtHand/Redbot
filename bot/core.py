import logging
import random
from datetime import timedelta

import disnake as discord
from disnake.ext import commands

import settings
from database import (
    AnalyticsGateway,
    MemberGateway,
    SessionGateway,
    SessionJournalGateway,
)
from database.connection import db

from bot.services import MetricsCacheManager
from bot.ui.channels import ChannelControlView, build_private_voice_embed

from .commands.fixes import register_fix_commands
from .commands.metrics import register_metrics_commands

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.presences = True  
intents.message_content = True

ALLOWED_GUILDS = settings.ALLOWED_GUILDS

bot = commands.InteractionBot(intents=intents, test_guilds=list(ALLOWED_GUILDS))
session_gateway = SessionGateway(db)
member_gateway = MemberGateway(db)
session_journal_gateway = SessionJournalGateway(db)
analytics_gateway = AnalyticsGateway(db)
metrics_cache_manager = MetricsCacheManager(analytics_gateway)

temporary_channels: set[int] = set()
register_metrics_commands(bot, analytics_gateway, member_gateway, metrics_cache_manager)
register_fix_commands(bot, session_gateway, bot, temporary_channels, session_journal_gateway)


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

    removed_journals = await session_journal_gateway.delete_open_journals_for_ended_sessions()
    if removed_journals:
        logging.info(
            "Removed %s open journal row(s) whose session was already ended (stale after missed leave events).",
            removed_journals,
        )

    active_sessions = await session_gateway.get_active_sessions()
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
                creator_record = await member_gateway.get_member(creator_id)
            bot.add_view(
                ChannelControlView(
                    channel,
                    owner=owner,
                    session_gateway=session_gateway,
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
    member_record = await member_gateway.upsert_member(
        member_id=member.id,
        username=member.name,
        public_name=member.display_name,
        avatar_url=member.display_avatar.url,
    )

    if after.channel and after.channel.id in settings.CREATE_CHANNEL_IDS:
        logging.info(f"{member} joined the create channel. Creating new VC...")
        guild = member.guild
        category = after.channel.category

        new_channel = await guild.create_voice_channel(
            name=random.choice(settings.DEFAULT_CHANNEL_NAMES),
            category=category,
            reason="Auto-created private channel"
        )
        temporary_channels.add(new_channel.id)

        await session_gateway.start_session(
            creator_id=member.id,
            channel_name=new_channel.name,
            channel_id=new_channel.id,
        )

        await member.move_to(new_channel)

        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=1))

        try:
            embed = build_private_voice_embed(member)

            await new_channel.send(
                embed=embed,
                view=ChannelControlView(
                    new_channel,
                    member,
                    session_gateway,
                    creator_record=member_record,
                ),
            )
            logging.info(f"Sent control panel embed to {new_channel.name}")
        except Exception as e:
            logging.error(f"Failed to send control panel message to {new_channel.id}: {e}")

    if after.channel and before.channel != after.channel and after.channel.id in temporary_channels:
        active_session = await session_gateway.get_active_session_by_channel(after.channel.id)
        if active_session:
            await session_journal_gateway.open_entry(
                session_id=after.channel.id,
                member=member_record,
            )

    if before.channel and before.channel != after.channel:
        if before.channel.id not in settings.CREATE_CHANNEL_IDS:
            await session_gateway.update_session(before.channel.id)

            if before.channel.id in temporary_channels:
                await session_journal_gateway.close_entry(
                    session_id=before.channel.id,
                    member_id=member.id,
                )

            if before.channel.id in temporary_channels and len(before.channel.members) == 0:
                await session_gateway.update_and_end_session(before.channel.id)
                logging.info(F"Session '{before.channel.name}' ended. Entry saved to the database")
                await before.channel.delete(reason="Temporary VC empty")
                temporary_channels.remove(before.channel.id)



def run_bot():
    bot.run(settings.BOT_TOKEN)
