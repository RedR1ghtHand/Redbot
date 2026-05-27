from dataclasses import dataclass

from disnake import VoiceState

import settings


@dataclass(frozen=True)
class JoinedCreateHubChannel:
    create_channel_id: int


@dataclass(frozen=True)
class EnteredTemporarySessionChannel:
    channel_id: int


@dataclass(frozen=True)
class LeftVoiceChannel:
    channel_id: int
    channel_name: str
    is_create_hub: bool
    is_tracked_temporary: bool


@dataclass(frozen=True)
class TemporaryChannelBecameEmpty:
    channel_id: int
    channel_name: str


VoiceEvent = (
    JoinedCreateHubChannel
    | EnteredTemporarySessionChannel
    | LeftVoiceChannel
    | TemporaryChannelBecameEmpty
)


def detect_voice_events(
    before: VoiceState,
    after: VoiceState,
    *,
    temporary_channel_ids: set[int],
) -> list[VoiceEvent]:
    create_ids = frozenset(settings.CREATE_CHANNEL_IDS)
    tracked = frozenset(temporary_channel_ids)

    events: list[VoiceEvent] = []

    if after.channel is not None and after.channel.id in create_ids:
        events.append(JoinedCreateHubChannel(create_channel_id=after.channel.id))

    if (
        after.channel is not None
        and before.channel != after.channel
        and after.channel.id in tracked
    ):
        events.append(EnteredTemporarySessionChannel(channel_id=after.channel.id))

    if before.channel is not None and before.channel != after.channel:
        cid = before.channel.id
        events.append(
            LeftVoiceChannel(
                channel_id=cid,
                channel_name=before.channel.name,
                is_create_hub=cid in create_ids,
                is_tracked_temporary=cid in tracked,
            )
        )
        if cid in tracked and len(before.channel.members) == 0:
            events.append(
                TemporaryChannelBecameEmpty(
                    channel_id=cid,
                    channel_name=before.channel.name,
                )
            )

    return events
