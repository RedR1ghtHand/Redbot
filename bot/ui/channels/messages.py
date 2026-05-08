import disnake as discord

from utils import get_message


def button_label(path: str) -> str:
    return get_message(path)


def modal_text(path: str, **kwargs):
    return get_message(path, **kwargs)


def build_private_voice_embed(member: discord.Member) -> discord.Embed:
    color = getattr(discord.Color, get_message("embeds.private_voice.color"))()
    embed = discord.Embed(
        title=get_message("embeds.private_voice.title"),
        description=get_message("embeds.private_voice.description", mention=member.mention),
        color=color,
    )

    for field in get_message("embeds.private_voice.fields"):
        embed.add_field(name=field["name"], value=field["value"], inline=True)

    embed.set_footer(
        text=get_message("embeds.private_voice.footer", display_name=member.display_name),
        icon_url=member.display_avatar.url,
    )
    embed.timestamp = discord.utils.utcnow()
    return embed
