from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models import Member, SessionJournal


class SessionJournalGateway:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["session_journal"]

    async def open_entry(self, session_id: int, member: Member) -> SessionJournal:
        now = datetime.now(timezone.utc)
        await self.collection.update_one(
            {"session_id": session_id, "user_joined.member_id": member.member_id, "user_left_at": None},
            {
                "$setOnInsert": {
                    "session_id": session_id,
                    "user_joined": member.model_dump(),
                    "user_joined_at": now,
                    "user_left_at": None,
                    "created_at": now,
                },
                "$set": {
                    "updated_at": now,
                },
            },
            upsert=True,
        )
        return SessionJournal(
            session_id=session_id,
            user_joined=member,
            user_joined_at=now,
            user_left_at=None,
            created_at=now,
            updated_at=now,
        )

    async def close_entry(self, session_id: int, member_id: int) -> bool:
        now = datetime.now(timezone.utc)
        result = await self.collection.update_one(
            {"session_id": session_id, "user_joined.member_id": member_id, "user_left_at": None},
            {"$set": {"user_left_at": now, "updated_at": now}},
        )
        return result.modified_count > 0
