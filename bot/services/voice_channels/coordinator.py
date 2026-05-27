from disnake import Member, VoiceState

from bot.services.members import MemberService
from bot.services.voice_channels.detector import detect_voice_events
from bot.services.voice_channels.handlers import (
    DiscordVoiceChannelService,
    VoiceEventContext,
    VoiceEventServices,
    dispatch_voice_events,
)
from database.repositories import SessionJournalRepository, SessionRepository


class VoiceChannelEventCoordinator:
    def __init__(
        self,
        *,
        member_service: MemberService,
        session_repository: SessionRepository,
        session_journal_repository: SessionJournalRepository,
        temporary_channel_ids: set[int],
        discord_voice: DiscordVoiceChannelService | None = None,
    ) -> None:
        self._member_service = member_service
        self._services = VoiceEventServices(
            session_repository=session_repository,
            session_journal_repository=session_journal_repository,
            discord_voice=discord_voice or DiscordVoiceChannelService(),
        )
        self._temporary_channel_ids = temporary_channel_ids

    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState) -> None:
        member_record = await self._member_service.sync_from_discord(member)
        ctx = VoiceEventContext(
            member=member,
            member_record=member_record,
            before=before,
            after=after,
            temporary_channel_ids=self._temporary_channel_ids,
        )
        events = detect_voice_events(
            before,
            after,
            temporary_channel_ids=self._temporary_channel_ids,
        )
        await dispatch_voice_events(self._services, ctx, events)
