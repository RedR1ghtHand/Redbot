import logging
import random
from datetime import timedelta

import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

from database import SessionManager
from database.connection import db
from database.models import Session
from utils import get_settings

from .books_dict import books_dict
from .ui.views import ChannelControlView

settings = get_settings()

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.presences = True  
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)
session_manager = SessionManager(db)

temporary_channels = set()
channel_owners = {}

ALLOWED_GUILDS = settings.ALLOWED_GUILDS


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
    logging.info(f"Bot is ready! Logged in as {bot.user}")
    
    for guild in bot.guilds:
        if guild.id not in ALLOWED_GUILDS:
            logging.info(f"Found unauthorized guild: {guild.name} (ID: {guild.id})")
            logging.info(f"Leaving guild: {guild.name}")
            await guild.leave()
        else:
            logging.info(f"Authorized guild: {guild.name} (ID: {guild.id})")


@bot.event
async def on_voice_state_update(member, before, after):
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
        channel_owners[new_channel.id] = member.id

        await session_manager.start_session(
            created_by=str(member.name),
            channel_name=new_channel.name,
            channel_id=new_channel.id,
            creator_metadata={
                "public_name": member.display_name,
                "username": member.name,
                "avatar_url": member.display_avatar.url,
            }
        )

        await member.move_to(new_channel)

        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=1))

        try:
            embed = discord.Embed(
                title="Your Private Voice Channel",
                description=f"Welcome {member.mention}!\n\nUse the buttons below to manage your channel.",
                color=discord.Color.red()
            )
            embed.add_field(name="📝", value="Change your channel name.", inline=True)
            embed.add_field(name="👥 *", value="Set or adjust the member limit.", inline=True)
            embed.add_field(name="👥 +", value="Increase member limit by 1.", inline=True)
            embed.add_field(name="👥 -", value="Decrease member limit by 1.", inline=True)
            embed.set_footer(text=f"Owner: {member.display_name}", icon_url=member.display_avatar.url)
            embed.timestamp = discord.utils.utcnow()

            await new_channel.send(embed=embed,view=ChannelControlView(new_channel, member, session_manager))
            logging.info(f"Sent control panel embed to {new_channel.name}")
        except Exception as e:
            logging.error(f"Failed to send control panel message to {new_channel.id}: {e}")

    if before.channel and before.channel != after.channel:
        if before.channel.id not in settings.CREATE_CHANNEL_IDS:
            await session_manager.update_session(before.channel.id)

            if before.channel.id in temporary_channels and len(before.channel.members) == 0:
                await session_manager.update_and_end_session(before.channel.id)
                logging.info(F"Session '{before.channel.name}' ended. Entry saved to the database")
                await before.channel.delete(reason="Temporary VC empty")
                temporary_channels.remove(before.channel.id)
                channel_owners.pop(before.channel.id, None)


@bot.command()
@commands.has_permissions(administrator=True)
async def show_books(ctx):
    for name, data in books_dict.items():
        embed = discord.Embed(
            title=f"📖  **{name}**",
            color=discord.Color(int(data["color"].lstrip("#"), 16))
        )
        embed.set_thumbnail(url=data["icon"])
        await ctx.send(embed=embed)


@bot.command(name="top")
async def top_sessions(ctx, limit: int):
    limit = limit if limit <= 10 else 10
    sessions = await session_manager.longest_sessions_all_time(limit=limit)

    if not sessions:
        await ctx.send("No sessions found yet.")
        return

    embed = discord.Embed(
        title=f"Top {limit} Longest Voice Sessions",
        color=discord.Color.red()
    )

    lines = []
    medals = ["🥇", "🥈", "🥉"]

    for i, session in enumerate(sessions, start=1):
        duration = session.duration_pretty()
        meta = session.creator_metadata or {}
        username = meta.get("public_name") or session.created_by

        if i <= 3:
            line = f"{medals[i - 1]} **{session.channel_name}** *by* {username}\n⏱️ `{duration}`"
        else:
            line = f"{i}. **{session.channel_name}** *by* {username}\n⏱️ `{duration}`"

        lines.append(line)

    if len(lines) > 3:
        top_three = "\n\n".join(lines[:3])
        others = "\n".join(lines[3:])
        description = f"{top_three}\n\n{others}"
    else:
        description = "\n\n".join(lines)

    embed.description = description

    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
async def clean_up_short_sessions(ctx, treshhold: int):
    deleted_count = await session_manager.clean_up_short_sessions(treshhold=treshhold)

    if not deleted_count:
        await ctx.send(f"No sessions shorter than **{treshhold}**seconds found")
    else:
        await ctx.send(f"Cleaned up **{deleted_count}** sessions shorter than **{treshhold}**seconds")


def run_bot():
    bot.run(settings.BOT_TOKEN)
