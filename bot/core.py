import logging

logging.basicConfig(level=logging.DEBUG)

import random
from datetime import timedelta

import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING

from database import SessionManager
from database.connection import db
from database.models import Session
from utils.get_project_settings import get_settings

from .books_dict import books_dict
from .ui.channel_control_view import ChannelControlView

settings = get_settings()

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.presences = True  
intents.message_content = True

bot = commands.Bot(command_prefix="r!", intents=intents)

session_manager = SessionManager(db)

temporary_channels = set()
channel_owners = {}

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == int(settings.CREATE_CHANNEL_ID):
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

            await new_channel.send(embed=embed, view=ChannelControlView(new_channel, member))
            logging.info(f"Sent control panel embed to {new_channel.name}")
        except Exception as e:
            logging.error(f"Failed to send control panel message to {new_channel.id}: {e}")

    if before.channel and before.channel != after.channel:
        if before.channel.id not in (int(settings.CREATE_CHANNEL_ID),):
            await session_manager.update_session(before.channel.id)

            if before.channel.id in temporary_channels and len(before.channel.members) == 0:
                await session_manager.update_and_end_session(before.channel.id)
                await before.channel.delete(reason="Temporary VC empty")
                temporary_channels.remove(before.channel.id)
                channel_owners.pop(before.channel.id, None)

@bot.command()
async def show_books(ctx):
    for name, data in books_dict.items():
        embed = discord.Embed(
            title=f"📖  **{name}**",
            color=discord.Color(int(data["color"].lstrip("#"), 16))
        )
        embed.set_thumbnail(url=data["icon"])
        await ctx.send(embed=embed)

@bot.command(name="top")
async def top_sessions(ctx):
    cursor = (
        session_manager.collection
        .find({"duration": {"$ne": None}})
        .sort("duration", DESCENDING)
        .limit(10)
    )
    sessions = [Session(**s) async for s in cursor]

    if not sessions:
        await ctx.send("No sessions found yet.")
        return

    embed = discord.Embed(
        title="Top 10 Longest Voice Sessions",
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


bot.run(settings.BOT_TOKEN)
