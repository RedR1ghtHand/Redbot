import logging
import random
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

import settings
from database import SessionManager
from database.connection import db
from database.models import Session

from .books_dict import books_dict
from .ui.views import ChannelControlView

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.presences = True  
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
session_manager = SessionManager(db)

temporary_channels = set()
channel_owners = {}

ALLOWED_GUILDS = settings.ALLOWED_GUILDS
MESSAGES = settings.MESSAGES


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
    logging.info(f"Currently registered commands: {len(tree.get_commands())}")
    try:
        synced = await tree.sync()
        logging.info(f"Synced {len(synced)} slash command(s) with Discord globally. Command tree: {tree.get_commands()}")
    except Exception as e:
        logging.error(f"Failed to sync slash commands globally: {e}")
    
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
            msg = MESSAGES["embeds"]["private_voice"]
            color = getattr(discord.Color, msg["color"])()

            embed = discord.Embed(
                title=msg["title"],
                description=msg["description"].format(mention=member.mention),
                color=color
            )

            for field in msg["fields"]:
                embed.add_field(name=field["name"], value=field["value"], inline=True)

            embed.set_footer(
                text=msg["footer"].format(display_name=member.display_name), 
                icon_url=member.display_avatar.url
                )
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


@tree.command(name="top", description="Show top sessions sorted by duration")
async def top_sessions(interaction: discord.Interaction, limit: int = 10):
    limit = limit if limit <= 10 else 10
    sessions = await session_manager.longest_sessions_all_time(limit=limit)

    top_config = MESSAGES.get("top", {})

    title_template = top_config.get("title", "Top {limit} Longest Voice Sessions")
    color_name = top_config.get("color", "red")
    no_sessions_text = top_config.get("no_sessions", "No sessions found yet.")
    medals_override = top_config.get("medals")

    if not sessions:
        await interaction.response.send_message(no_sessions_text)
        return

    color = getattr(discord.Color, color_name, discord.Color.red)()
    embed = discord.Embed(
        title=title_template.format(limit=limit),
        color=color
    )

    lines = []
    medals = medals_override or ["🥇", "🥈", "🥉"]

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

    await interaction.response.send_message(embed=embed)


@tree.command(name="clean-up-short-sessions", description="Clean up short sessions")
@app_commands.checks.has_permissions(administrator=True)
async def clean_up_short_sessions(interaction: discord.Interaction, treshhold: int):
    deleted_count = await session_manager.clean_up_short_sessions(treshhold=treshhold)

    if not deleted_count:
        await interaction.response.send_message(f"No sessions shorter than **{treshhold}**seconds found")
    else:
        await interaction.response.send_message(f"Cleaned up **{deleted_count}** sessions shorter than **{treshhold}**seconds")


def run_bot():
    bot.run(settings.BOT_TOKEN)
