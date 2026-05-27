import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import disnake as discord
from disnake import CategoryChannel, Guild, Member, VoiceChannel
from disnake.utils import sleep_until, utcnow

import settings
from bot.services.voice_channels.detector import (
    EnteredTemporarySessionChannel,
    JoinedCreateHubChannel,
    LeftVoiceChannel,
    TemporaryChannelBecameEmpty,
    VoiceEvent,
)
from bot.ui.channels import ChannelControlView, build_private_voice_embed
from database.models import Member as MemberRecord
from database.repositories import SessionJournalRepository, SessionRepository


@dataclass
class VoiceEventContext:
    member: Member
    member_record: MemberRecord
    before: discord.VoiceState
    after: discord.VoiceState
    temporary_channel_ids: set[int]


class DiscordVoiceChannelService:
    async def create_voice_channel(
        self,
        guild: Guild,
        *,
        name: str,
        category: CategoryChannel | None,
        reason: str,
    ) -> VoiceChannel:
        return await guild.create_voice_channel(name=name, category=category, reason=reason)

    async def move_member(self, member: Member, channel: VoiceChannel | None) -> None:
        await member.move_to(channel)

    async def delete_channel(self, channel: VoiceChannel, *, reason: str) -> None:
        await channel.delete(reason=reason)

    async def send_control_message(
        self,
        channel: VoiceChannel,
        *,
        embed: discord.Embed,
        view: Any,
    ) -> None:
        await channel.send(embed=embed, view=view)


@dataclass
class VoiceEventServices:
    session_repository: SessionRepository
    session_journal_repository: SessionJournalRepository
    discord_voice: DiscordVoiceChannelService


VoiceHandler = Callable[[VoiceEventServices, VoiceEventContext, VoiceEvent], Awaitable[None]]


async def handle_joined_create_hub_channel(
    services: VoiceEventServices,
    ctx: VoiceEventContext,
    event: JoinedCreateHubChannel,
) -> None:
    member = ctx.member
    logging.info("%s joined the create channel. Creating new VC...", member)

    guild = member.guild
    after = ctx.after
    assert after.channel is not None

    new_channel = await services.discord_voice.create_voice_channel(
        guild,
        name=random.choice(settings.DEFAULT_CHANNEL_NAMES),
        category=after.channel.category,
        reason="Auto-created private channel",
    )
    ctx.temporary_channel_ids.add(new_channel.id)

    await services.session_repository.start_session(
        creator_id=member.id,
        channel_name=new_channel.name,
        channel_id=new_channel.id,
    )

    await services.discord_voice.move_member(member, new_channel)
    await sleep_until(utcnow() + timedelta(seconds=1))

    try:
        embed = build_private_voice_embed(member)
        await services.discord_voice.send_control_message(
            new_channel,
            embed=embed,
            view=ChannelControlView(
                new_channel,
                member,
                services.session_repository,
                creator_record=ctx.member_record,
            ),
        )
        logging.info("Sent control panel embed to %s", new_channel.name)
    except Exception as e:
        logging.error("Failed to send control panel message to %s: %s", new_channel.id, e)


async def handle_entered_temporary_session_channel(
    services: VoiceEventServices,
    ctx: VoiceEventContext,
    event: EnteredTemporarySessionChannel,
) -> None:
    active_session = await services.session_repository.get_active_session_by_channel(event.channel_id)
    if active_session:
        await services.session_journal_repository.open_entry(
            session_id=event.channel_id,
            member=ctx.member_record,
        )


async def handle_left_voice_channel(
    services: VoiceEventServices,
    ctx: VoiceEventContext,
    event: LeftVoiceChannel,
) -> None:
    if not event.is_create_hub:
        await services.session_repository.update_session(event.channel_id)

    if event.is_tracked_temporary:
        await services.session_journal_repository.close_entry(
            session_id=event.channel_id,
            member_id=ctx.member.id,
        )


async def handle_temporary_channel_became_empty(
    services: VoiceEventServices,
    ctx: VoiceEventContext,
    event: TemporaryChannelBecameEmpty,
) -> None:
    if event.channel_id not in ctx.temporary_channel_ids:
        return

    guild = ctx.member.guild
    channel = guild.get_channel(event.channel_id)
    if not isinstance(channel, VoiceChannel):
        logging.warning(
            "TemporaryChannelBecameEmpty for %s but channel missing or not voice; clearing tracked id",
            event.channel_id,
        )
        ctx.temporary_channel_ids.discard(event.channel_id)
        return

    await services.session_repository.update_and_end_session(event.channel_id)
    logging.info("Session '%s' ended. Entry saved to the database", event.channel_name)
    await services.discord_voice.delete_channel(channel, reason="Temporary VC empty")
    ctx.temporary_channel_ids.discard(event.channel_id)


async def dispatch_voice_events(
    services: VoiceEventServices,
    ctx: VoiceEventContext,
    events: list[VoiceEvent],
) -> None:
    registry: dict[type[VoiceEvent], VoiceHandler] = {
        JoinedCreateHubChannel: handle_joined_create_hub_channel,  # type: ignore[dict-item]
        EnteredTemporarySessionChannel: handle_entered_temporary_session_channel,  # type: ignore[dict-item]
        LeftVoiceChannel: handle_left_voice_channel,  # type: ignore[dict-item]
        TemporaryChannelBecameEmpty: handle_temporary_channel_became_empty,  # type: ignore[dict-item]
    }
    for event in events:
        handler = registry.get(type(event))
        if handler is not None:
            await handler(services, ctx, event)
