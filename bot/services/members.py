"""Discord member persistence — separate from voice/session lifecycle."""

from disnake import Member as DiscordMember

from database.models import Member
from database.repositories import MemberRepository


class MemberService:
    def __init__(self, member_repository: MemberRepository) -> None:
        self._members = member_repository

    async def sync_from_discord(self, member: DiscordMember) -> Member:
        return await self._members.upsert_member(
            member_id=member.id,
            username=member.name,
            public_name=member.display_name,
            avatar_url=member.display_avatar.url,
        )
