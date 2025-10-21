from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models import Session


class SessionManager:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["sessions"]

    async def start_session(
        self,
        created_by: str,
        channel_name: str,
        channel_id: int,
        creator_metadata: dict | None = None,
    ) -> Session:
        session = Session(
            created_by=created_by,
            channel_name=channel_name,
            channel_id=channel_id,
            creator_metadata=creator_metadata or {},
        )

        await self.collection.insert_one(session.model_dump(by_alias=True))
        return session

    async def update_session(self, channel_id: int) -> bool:
        result = await self.collection.update_one(
            {"channel_id": channel_id, "is_ended": False},
            {"$set": {"updated_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0

    async def update_and_end_session(self, channel_id: int) -> bool:
        now = datetime.now(timezone.utc)
        session_data = await self.collection.find_one({"channel_id": channel_id, "is_ended": False})
        if not session_data:
            return False

        created_at = session_data["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        duration = int((now - created_at).total_seconds())

        result = await self.collection.update_one(
            {"channel_id": channel_id, "is_ended": False},
            {"$set": {"is_ended": True, "updated_at": now, "duration": duration}},
        )
        return result.modified_count > 0
        

    async def longest_sessions_all_time(self, limit: int = 10) -> list[Session]:
        cursor = self.collection.find({"duration": {"$exists": True}}).sort("duration", -1).limit(limit)
        return [Session(**s) async for s in cursor]


    async def longest_sessions_this_week(self, limit: int = 10) -> list[Session]:
        from datetime import timedelta
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        cursor = self.collection.find({
            "duration": {"$exists": True},
            "created_at": {"$gte": week_ago}
        }).sort("duration", -1).limit(limit)
        return [Session(**s) async for s in cursor]