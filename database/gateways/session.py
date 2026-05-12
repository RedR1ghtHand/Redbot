from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from database.models import Session


class SessionGateway:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["sessions"]

    async def start_session(
        self,
        creator_id: int,
        channel_name: str,
        channel_id: int,
    ) -> Session:
        session = Session(
            creator_id=creator_id,
            channel_name=channel_name,
            channel_id=channel_id,
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

    async def get_active_sessions(self) -> list[dict]:
        cursor = self.collection.find({"is_ended": False})
        return [
            {
                "session": Session(**s),
                "creator_id": s.get("creator_id"),
                "created_by": s.get("created_by", ""),
            }
            async for s in cursor
        ]

    async def get_active_session_by_channel(self, channel_id: int) -> Session | None:
        session_data = await self.collection.find_one({"channel_id": channel_id, "is_ended": False})
        return Session(**session_data) if session_data else None

    async def delete_session(self, channel_id: int) -> bool:
        result = await self.collection.delete_one({"channel_id": channel_id, "is_ended": False})
        return result.deleted_count > 0

    async def update_channel_name(self, channel_id: int, new_name: str) -> bool:
        result = await self.collection.update_one(
            {"channel_id": channel_id, "is_ended": False},
            {
                "$set": {
                    "channel_name": new_name,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.modified_count > 0

    async def clean_up_short_sessions(self, treshhold: int = 600) -> int:
        query_filter = {"duration": {"$lte": treshhold}}
        result = await self.collection.delete_many(
            query_filter,
            comment=f"Cleaning up all sessions shorter than {treshhold}seconds",
        )
        return result.deleted_count
