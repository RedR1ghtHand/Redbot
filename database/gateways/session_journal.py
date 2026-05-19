from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models import Member, SessionJournal


class SessionJournalGateway:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["session_journal"]
        self._sessions = db["sessions"]

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

    async def delete_open_journals_for_ended_sessions(self) -> int:
        deleted = 0
        async for entry in self.collection.find({"user_left_at": None}):
            session_id = entry.get("session_id")
            if session_id is None:
                continue
            ended = await self._sessions.find_one(
                {"channel_id": session_id, "is_ended": True},
                projection={"_id": 1},
            )
            if ended is None:
                continue
            result = await self.collection.delete_one({"_id": entry["_id"]})
            if result.deleted_count:
                deleted += 1
        return deleted
